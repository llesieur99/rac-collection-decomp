"""Recover the function boundaries of a PPU executable.

The retail build of a PlayStation 3 game is stripped: there is no symbol
table and no section name.  The boundaries have to come from the code
itself, and a boundary that only one method sees is a candidate, not a
function.

This tool offers the two cheap, independent methods:

* **prologue scan** — the PS3 SDK's PPU functions open with a fixed
  pattern: the stack pointer is moved down with ``stdu r1, -N(r1)`` and the
  link register is saved with ``mflr r0`` / ``stw r0, 0x10(r1)``;
* **call scan** — every ``bl`` (branch and link) names an address that the
  program calls, and a called address is a function.

Both sets are published separately, so that they can be compared.  Only the
tool needs the Python standard library: the few opcodes that matter are
decoded directly.

A third pass walks the control flow from a candidate to find where the
function ends: a function ends at the return that no path falls through
from.

    python tools/ppu_funcs.py prologue <eboot.elf> [--out FILE]
    python tools/ppu_funcs.py calls    <eboot.elf> [--out FILE]
    python tools/ppu_funcs.py catalogue <eboot.elf> [--out FILE]
    python tools/ppu_funcs.py bounds   <eboot.elf> [--out FILE]
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import PpuElf, ElfError  # noqa: E402

# PPU instruction patterns, measured on the target's code.
#
# The PPU uses the 64-bit PowerPC encoding.  A function opens with
# ``stdu r1, -N(r1)`` (opcode 62, rD = rS = 1, rA = 1, signed 16-bit
# offset), and the SDK saves the link register right after with
# ``mflr rX`` (the mfspr/mflr family, extended opcode 0x2A6).
STDU_R1 = 0xF8210000
# ``mflr rX`` is the mfspr family with the extended opcode 0x2A6; the
# destination register sits in bits 21-25.
MFLR_MASK = 0xFF1FFCFF
MFLR_VALUE = 0x7C0800A6

# The call instruction: the unconditional branch with the link bit set
# (opcode 18, LK at bit 0; AA at bit 1).
BRANCH_MASK = 0xFC000001
BRANCH_LINK = 0x48000001

# The conditional branches (opcode 16) and the indirect ones (opcode 19).
CONDITIONAL_MASK = 0xFC000003
CONDITIONAL = 0x80000000
INDIRECT_MASK = 0xFC000003
INDIRECT = 0x4C000000

# ``blr`` — branch to the link register: the return of a function.  The PPU
# is a 64-bit PowerPC, so the return is the 64-bit form; the 32-bit form is
# kept for completeness.
BLR = 0x4E800020
BLR32 = 0x48000009
# ``bctr`` — branch to the count register: an indirect jump.
BCTR = 0x4E800420
# ``bctrl`` — the same, with the link: an indirect call.
BCTRL = 0x4E800421
# ``bclr`` — branch to the link register, as a conditional branch.
BCLR = 0x4C800020

# The branch condition field, bits 6-10.
BO_MASK = 0x01FFFC00


def branch_target(word: int, address: int) -> int:
    """The target of a branch, for the 26-bit displacement form."""
    displacement = word & 0x03FFFFFC
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return (address + displacement) & 0xFFFFFFFF


@dataclass(frozen=True)
class Candidate:
    address: int
    kind: str


def _text_range(elf: PpuElf) -> tuple[int, int]:
    """Return the (address, size) of the segment that holds the code."""
    best = None
    for ph in elf.program_headers():
        if not ph.is_load or (ph.flags & 0x4) == 0:
            continue
        if best is None or ph.filesz > best.filesz:
            best = ph
    if best is None:
        raise ElfError("no executable segment found")
    return best.vaddr, best.filesz


def text_code(elf: PpuElf) -> tuple[int, bytes]:
    """The code of the program, read once and kept on the executable.

    The boundaries are found by walking the code over and over: reading the
    segment again at every step costs more than the walk itself, so the
    bytes are read once and reused.
    """
    cached = getattr(elf, "_ppu_code", None)
    if cached is not None:
        return cached
    vaddr, size = _text_range(elf)
    data = elf.read_vaddr(vaddr, size)
    try:
        elf._ppu_code = (vaddr, data)
    except AttributeError:  # pragma: no cover
        pass
    return vaddr, data


def _words(elf: PpuElf) -> Iterator[tuple[int, int]]:
    """Yield the instruction words of the code segment, with their addresses."""
    base, data = text_code(elf)
    for offset in range(0, len(data) - 3, 4):
        yield base + offset, struct.unpack_from(">I", data, offset)[0]


def prologue_candidates(elf: PpuElf) -> list[Candidate]:
    """The addresses where the SDK's function prologue appears.

    Two shapes were measured on the target's code:

    * ``stdu r1, -N(r1)`` followed by ``mflr rX``;
    * ``mflr rX`` followed by ``stdu r1, -N(r1)`` (the compiler's other
      order, seen when the frame is set up before the link register is
      saved).
    """
    out = []
    base, data = text_code(elf)
    count = len(data) // 4

    def word(index: int) -> int:
        return struct.unpack_from(">I", data, index * 4)[0]

    for index in range(count):
        current = word(index)
        if current & 0xFFFF0000 != STDU_R1:
            continue
        offset = current & 0xFFFF
        if not 0x8000 <= offset:
            # The offset is signed: a prologue moves the stack *down*.
            continue
        following = word(index + 1) if index + 1 < count else 0
        preceding = word(index - 1) if index > 0 else 0
        if following & MFLR_MASK == MFLR_VALUE or preceding & MFLR_MASK == MFLR_VALUE:
            out.append(Candidate(base + index * 4, "prologue"))
    return out


def call_targets(elf: PpuElf) -> list[Candidate]:
    """The addresses the program calls."""
    seen = set()
    out = []
    for address, word in _words(elf):
        if word & BRANCH_MASK != BRANCH_LINK:
            continue
        displacement = word & 0x03FFFFFC
        if displacement & 0x02000000:
            displacement -= 0x04000000
        target = (address + displacement) & 0xFFFFFFFFFFFFFFFF
        if target in seen:
            continue
        seen.add(target)
        out.append(Candidate(target, "call"))
    return out


def build_catalogue(elf: PpuElf) -> list[tuple[int, str, str]]:
    """The union of both methods, with the evidence for each address."""
    prologues = {c.address for c in prologue_candidates(elf)}
    calls = {c.address for c in call_targets(elf)}
    rows = []
    for address in sorted(prologues | calls):
        evidence = []
        if address in prologues:
            evidence.append("prologue")
        if address in calls:
            evidence.append("call")
        rows.append((address, "+".join(evidence), "both" if len(evidence) == 2 else evidence[0]))
    return rows


def cmd_prologue(elf: PpuElf, args: argparse.Namespace) -> int:
    rows = [(c.address, "", "prologue") for c in prologue_candidates(elf)]
    return _write(rows, args)


def cmd_calls(elf: PpuElf, args: argparse.Namespace) -> int:
    rows = [(c.address, "", "call") for c in call_targets(elf)]
    return _write(rows, args)


def cmd_catalogue(elf: PpuElf, args: argparse.Namespace) -> int:
    rows = [(address, kind, evidence) for address, kind, evidence in build_catalogue(elf)]
    if getattr(args, "confirmed", False):
        rows = [row for row in rows if row[2] == "both"]
    return _write(rows, args)


def function_body(elf: PpuElf, start: int, limit: int = 200000,
                  entries: set[int] | None = None) -> tuple[int, str, list[int]]:
    """Walk the control flow from a candidate and find where the function ends.

    The function ends at the return that no path falls through from.  The walk
    follows the branches, stops at an indirect jump, and does not leave the
    function: a branch that goes outside is a tail call, and the function ends
    where the branch is.

    When the set of the known function entries is given, the walk also stops
    as soon as it lands on one of them: the flow has left the function, and
    the next function starts there.  Without that bound the walk wanders into
    the code that follows — a branch that skips over a function lands in the
    middle of the next one — and reports an extent that covers half the
    program.

    Returns the address just after the last instruction of the function, the
    evidence (``return`` when a ``blr`` was reached, ``branch`` when the
    function leaves by a branch, ``entry`` when the flow reached the next
    function, ``indirect`` at an indirect jump, ``limit`` when the walk gave
    up), and the addresses of the instructions of the body, sorted.
    """
    base, data = text_code(elf)
    size = len(data)

    def word_at(address: int) -> int | None:
        offset = address - base
        if offset < 0 or offset + 4 > len(data):
            return None
        return struct.unpack_from(">I", data, offset)[0]

    visited: set[int] = set()
    body: list[int] = []
    pending = [start]
    last = start
    evidence = "limit"
    steps = 0

    while pending:
        address = pending.pop()
        while True:
            if address in visited:
                break
            if entries is not None and address != start and address in entries:
                # The flow reached the next function: this one ends before it.
                evidence = "entry"
                break
            word = word_at(address)
            if word is None:
                break
            visited.add(address)
            body.append(address)
            steps += 1
            if steps > limit:
                evidence = "limit"
                break
            last = max(last, address)

            if word in (BLR, BLR32):
                evidence = "return"
                break
            if word in (BCTR, BCTRL):
                evidence = "indirect"
                break
            if word & BRANCH_MASK == BRANCH_LINK:
                # a call: the flow continues after it
                address += 4
                continue
            if word & BRANCH_MASK == 0x48000000:
                # an unconditional branch
                if word & 0x2:
                    evidence = "branch"
                    break
                target = branch_target(word, address)
                if target <= start or target >= base + size:
                    evidence = "branch"
                    break
                if target in visited:
                    break
                pending.append(target)
                break
            if word & CONDITIONAL_MASK == CONDITIONAL:
                # a conditional branch: both paths
                target = branch_target(word, address)
                if start < target < base + size and target not in visited:
                    pending.append(target)
                address += 4
                continue
            if word & INDIRECT_MASK == INDIRECT:
                evidence = "indirect"
                break
            address += 4

    body.sort()
    # The extent of a function is the block of code that starts at it: the
    # walk may reach further (a jump table, a block of data read as code),
    # but the function itself is the contiguous run of instructions that
    # starts at its entry and that the walk covered.
    end = start
    while end in visited:
        end += 4
    run = list(range(start, end, 4))
    return end, evidence, run


def function_extent(elf: PpuElf, start: int, limit: int = 200000,
                    entries: set[int] | None = None) -> tuple[int | None, str]:
    """The address just after the last instruction of the function, and why."""
    end, why, _body = function_body(elf, start, limit, entries)
    return end, why


def cmd_bounds(elf: PpuElf, args: argparse.Namespace) -> int:
    rows = []
    catalogue = build_catalogue(elf)
    entries = {address for address, _kind, _evidence in catalogue}
    for address, kind, evidence in catalogue:
        if getattr(args, "confirmed", False) and evidence != "both":
            continue
        end, why = function_extent(elf, address, entries=entries)
        rows.append((address, end, kind, f"{evidence};{why}"))
    text = "address\tend\tkind\tevidence\n" + "".join(
        f"0x{address:08X}\t0x{end:08X}\t{kind}\t{evidence}\n"
        for address, end, kind, evidence in rows)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"wrote {args.out}: {len(rows)} entries")
    else:
        sys.stdout.write(text)
    return 0


def _write(rows: list[tuple[int, str, str]], args: argparse.Namespace) -> int:
    text = "address\tkind\tevidence\n" + "".join(
        f"0x{address:08X}\t{kind}\t{evidence}\n" for address, kind, evidence in rows)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"wrote {args.out}: {len(rows)} entries")
    else:
        sys.stdout.write(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("elf", help="path to the rebuilt PPU ELF")
        p.add_argument("--out", help="write a TSV file instead of stdout")
        return p

    add("prologue", "the addresses with the SDK function prologue").set_defaults(func=cmd_prologue)
    add("calls", "the addresses the program calls").set_defaults(func=cmd_calls)
    p_catalogue = add("catalogue", "both methods, with their evidence")
    p_catalogue.add_argument("--confirmed", action="store_true",
                             help="keep only the addresses both methods agree on")
    p_catalogue.set_defaults(func=cmd_catalogue)

    p_bounds = add("bounds", "the extent of every candidate")
    p_bounds.add_argument("--confirmed", action="store_true",
                           help="keep only the addresses both methods agree on")
    p_bounds.set_defaults(func=cmd_bounds)

    args = parser.parse_args(argv)
    try:
        with open(args.elf, "rb") as handle:
            elf = PpuElf(handle.read(), args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return args.func(elf, args)


if __name__ == "__main__":
    raise SystemExit(main())
