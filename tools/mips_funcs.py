"""Recover the function boundaries of a PS2 executable (the MIPS code).

The retail PlayStation 2 executables are stripped: there is no symbol table
to say where a function starts or ends.  The boundaries have to come from the
code itself, and a boundary that only one method sees is a candidate, not a
function.

The tool offers the two cheap, independent methods, the same ones the PS3
side uses:

* **prologue scan** — the game's functions open by moving the stack down:
  ``addiu $sp, $sp, -N``.  The frame of the function is the size of the
  stack it takes.
* **call scan** — every ``jal`` names the address of a function, and a
  called address is a function.

Both sets are published separately, so that they can be compared.  Only the
Python standard library is needed: the few instructions that matter are
decoded directly.

A third pass walks the control flow from a candidate to find where the
function ends.  The MIPS has a **delay slot**: the instruction that follows a
branch always runs, which the walk has to honour, or it reports an extent
that covers half of the program.

    python tools/mips_funcs.py prologue <overlay.elf> [--out FILE]
    python tools/mips_funcs.py calls    <overlay.elf> [--out FILE]
    python tools/mips_funcs.py catalogue <overlay.elf> [--out FILE]
    python tools/mips_funcs.py bounds   <overlay.elf> [--out FILE]
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from dataclasses import dataclass
from typing import Iterator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mips_elf import ElfError, MipsElf  # noqa: E402

# The opcodes of the MIPS instruction set, as they are encoded in the
# R5900 (a MIPS III core with the Sony extensions).  Only the ones that
# matter here are named.
OP_SPECIAL = 0x00
OP_REGIMM = 0x01
OP_J = 0x02
OP_JAL = 0x03
OP_BEQ = 0x04
OP_BNE = 0x05
OP_BLEZ = 0x06
OP_BGTZ = 0x07
OP_ADDI = 0x08
OP_ADDIU = 0x09
OP_SLTI = 0x0A
OP_SLTIU = 0x0B
OP_ANDI = 0x0C
OP_ORI = 0x0D
OP_XORI = 0x0E
OP_LUI = 0x0F
OP_BEQL = 0x14
OP_BNEL = 0x15
OP_BLEZL = 0x16
OP_BGTZL = 0x17
OP_LQ = 0x1E
OP_SQ = 0x1F
OP_LB = 0x20
OP_LH = 0x21
OP_LW = 0x23
OP_LBU = 0x24
OP_LHU = 0x25
OP_LWU = 0x27
OP_SB = 0x28
OP_SH = 0x29
OP_SW = 0x2B
OP_LWC1 = 0x31
OP_LDC1 = 0x35
OP_LQC2 = 0x36
OP_LD = 0x37
OP_SWC1 = 0x39
OP_SDC1 = 0x3D
OP_SQC2 = 0x3E
OP_SD = 0x3F

# The functions of the SPECIAL opcode.
SPECIAL_SLL = 0x00
SPECIAL_JR = 0x08
SPECIAL_JALR = 0x09
SPECIAL_SYSCALL = 0x0C
SPECIAL_BREAK = 0x0D
SPECIAL_SYNC = 0x0F
SPECIAL_MFHI = 0x10
SPECIAL_MTHI = 0x11
SPECIAL_MFLO = 0x12
SPECIAL_MTLO = 0x13
SPECIAL_MULT = 0x18
SPECIAL_MULTU = 0x19
SPECIAL_DIV = 0x1A
SPECIAL_DIVU = 0x1B
SPECIAL_MFC1 = 0x11
SPECIAL_MTC1 = 0x13
SPECIAL_MFC2 = 0x11
SPECIAL_MTC2 = 0x13

# The SPECIAL functions that do not write a general purpose register.
SPECIAL_NO_RD = frozenset({
    SPECIAL_SLL, 0x04, 0x06, 0x07, SPECIAL_JR, SPECIAL_SYSCALL,
    SPECIAL_BREAK, SPECIAL_SYNC, SPECIAL_MFHI, SPECIAL_MTHI, SPECIAL_MFLO,
    SPECIAL_MTLO, SPECIAL_MULT, SPECIAL_MULTU, SPECIAL_DIV, SPECIAL_DIVU,
})

# The registers of the MIPS: $zero, $at, $v0-$v1, $a0-$a3, $t0-$t9, $s0-$s7,
# $k0-$k1, $gp, $sp, $fp, $ra.
REG_ZERO = 0
REG_SP = 29
REG_FP = 30
REG_RA = 31

# The conditional branches, with the register that holds the condition.
BRANCHES = frozenset({OP_BEQ, OP_BNE, OP_BLEZ, OP_BGTZ,
                      OP_BEQL, OP_BNEL, OP_BLEZL, OP_BGTZL, OP_REGIMM})


@dataclass(frozen=True)
class Candidate:
    address: int
    kind: str


def text_code(elf: MipsElf) -> tuple[int, bytes]:
    """The code of the program, read once and kept on the executable.

    The core executable and the overlays hold several code sections; they
    are gathered into one buffer, and the address of every byte is kept so
    that a reference can be read back.
    """
    cached = getattr(elf, "_mips_code", None)
    if cached is not None:
        return cached
    chunks = []
    for section in elf.code_sections():
        chunks.append((section.addr, elf.section_data(section)))
    chunks.sort()
    if not chunks:
        raise ElfError("no executable section found")
    # The code is a set of ranges; the buffer keeps them in one piece and a
    # parallel table says where each range starts.
    starts = [start for start, _blob in chunks]
    blobs = [blob for _start, blob in chunks]
    packed = getattr(elf, "_mips_code", None)
    if packed is None:
        try:
            elf._mips_code = (starts, blobs)
        except AttributeError:  # pragma: no cover
            pass
    return starts, blobs


def _word_at(starts: list[int], blobs: list[bytes], address: int) -> int | None:
    """The instruction word at an address, if the address holds code."""
    import bisect
    index = bisect.bisect_right(starts, address) - 1
    if index < 0:
        return None
    offset = address - starts[index]
    blob = blobs[index]
    if offset < 0 or offset + 4 > len(blob):
        return None
    return struct.unpack_from("<I", blob, offset)[0]


def _words(starts: list[int], blobs: list[bytes]) -> Iterator[tuple[int, int]]:
    for start, blob in zip(starts, blobs):
        for offset in range(0, len(blob) - 3, 4):
            yield start + offset, struct.unpack_from("<I", blob, offset)[0]


def prologue_candidates(elf: MipsElf) -> list[Candidate]:
    """The addresses where the game's function prologue appears.

    The prologue moves the stack down: ``addiu $sp, $sp, -N``.  The
    immediate is signed, and a function that does not take a frame does not
    open with one, so only the negative offsets are kept.
    """
    out = []
    for address, word in _words(*text_code(elf)):
        if word >> 26 != OP_ADDIU:
            continue
        rs = (word >> 21) & 0x1F
        rt = (word >> 16) & 0x1F
        if not (rs == REG_SP and rt == REG_SP) and not (rs == REG_FP and rt == REG_FP):
            continue
        immediate = word & 0xFFFF
        if immediate & 0x8000:
            immediate -= 0x10000
        if immediate >= 0:
            continue
        out.append(Candidate(address, "prologue"))
    return out


def call_targets(elf: MipsElf) -> list[Candidate]:
    """The addresses the program calls.

    ``jal`` names the address of the function; ``jalr`` calls through a
    register, and the register is not known without running the program, so
    the indirect calls give nothing here.
    """
    seen = set()
    out = []
    for address, word in _words(*text_code(elf)):
        if word >> 26 != OP_JAL:
            continue
        target = (address + 4) & 0xF0000000 | (word & 0x03FFFFFF) << 2
        if target in seen:
            continue
        seen.add(target)
        out.append(Candidate(target, "call"))
    return out


def build_catalogue(elf: MipsElf) -> list[tuple[int, str, str]]:
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
        rows.append((address, "+".join(evidence),
                     "both" if len(evidence) == 2 else evidence[0]))
    return rows


def _branch_target(word: int, address: int) -> int:
    """The target of a branch, for the 16-bit displacement form."""
    offset = word & 0xFFFF
    if offset & 0x8000:
        offset -= 0x10000
    return address + 4 + offset * 4


def _jump_target(word: int, address: int) -> int:
    """The target of a jump, for the 26-bit index form."""
    return (address + 4) & 0xF0000000 | (word & 0x03FFFFFF) << 2


def function_body(elf: MipsElf, start: int, limit: int = 400000,
                  entries: set[int] | None = None,
                  full: bool = False) -> tuple[int, str, list[int]]:
    """Walk the control flow from a candidate and find where the function ends.

    The MIPS has a delay slot: the instruction that follows a branch always
    runs.  The walk therefore executes the delay slot, and then follows both
    the target of the branch and the instruction after it.

    The function ends at the return that no path falls through from.  The
    walk follows the branches, stops at an indirect jump, and does not leave
    the function: a jump that goes outside is a tail call, and the function
    ends where the jump is.

    When the set of the known function entries is given, the walk also stops
    as soon as it lands on one of them: the flow has left the function, and
    the next function starts there.

    Returns the address just after the last instruction of the function, the
    evidence (``return`` when a ``jr $ra`` was reached, ``jump`` when the
    function leaves by a jump, ``entry`` when the flow reached the next
    function, ``limit`` when the walk gave up), and the addresses of the
    instructions of the body, sorted.

    With ``full``, the body is every instruction the walk reached, and not
    only the contiguous block that starts at the entry: a function whose
    blocks are scattered owns the instructions of those blocks too.
    """
    starts, blobs = text_code(elf)
    visited: set[int] = set()
    body: list[int] = []
    pending = [start]
    last = start
    evidence = "limit"
    steps = 0

    def word_at(address: int) -> int | None:
        return _word_at(starts, blobs, address)

    while pending:
        address = pending.pop()
        while True:
            if address in visited:
                break
            if entries is not None and address != start and address in entries:
                # the flow reached the next function: this one ends before it
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

            opcode = word >> 26
            if opcode == OP_JAL:
                # a call: the delay slot runs, and the flow continues after it
                address += 8
                continue
            if opcode == OP_SPECIAL:
                function = word & 0x3F
                if function == SPECIAL_JR:
                    # the return, or an indirect jump: the function ends here
                    delay = address + 4
                    if delay not in visited and _word_at(starts, blobs, delay) is not None:
                        # the delay slot of the jump runs before the return
                        visited.add(delay)
                        body.append(delay)
                    evidence = "return"
                    break
                if function == SPECIAL_JALR:
                    address += 8
                    continue
                address += 4
                continue
            if opcode == OP_J:
                # a jump: a tail call, the function ends here
                target = _jump_target(word, address)
                if start <= target:
                    pending.append(target)
                evidence = "jump"
                break
            if opcode in BRANCHES:
                target = _branch_target(word, address)
                # the delay slot runs, then the two paths
                delay = address + 4
                if delay not in visited:
                    visited.add(delay)
                    body.append(delay)
                if opcode in (OP_BEQ, OP_BNE, OP_BEQL, OP_BNEL, OP_REGIMM):
                    pending.append(target)
                address += 8
                continue
            address += 4

    body.sort()
    # the extent of a function is the block of code that starts at it
    end = start
    while end in visited:
        end += 4
    run = list(range(start, end, 4))
    if full:
        return end, evidence, body
    return end, evidence, run


def function_extent(elf: MipsElf, start: int, limit: int = 400000,
                    entries: set[int] | None = None) -> tuple[int | None, str]:
    """The address just after the last instruction of the function, and why."""
    end, why, _body = function_body(elf, start, limit, entries)
    return end, why


def cmd_prologue(elf: MipsElf, args: argparse.Namespace) -> int:
    rows = [(c.address, "", "prologue") for c in prologue_candidates(elf)]
    return _write(rows, args)


def cmd_calls(elf: MipsElf, args: argparse.Namespace) -> int:
    rows = [(c.address, "", "call") for c in call_targets(elf)]
    return _write(rows, args)


def cmd_catalogue(elf: MipsElf, args: argparse.Namespace) -> int:
    rows = [(address, kind, evidence) for address, kind, evidence in build_catalogue(elf)]
    if getattr(args, "confirmed", False):
        rows = [row for row in rows if row[2] == "both"]
    return _write(rows, args)


def cmd_bounds(elf: MipsElf, args: argparse.Namespace) -> int:
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
        p.add_argument("elf", help="path to the MIPS ELF")
        p.add_argument("--out", help="write a TSV file instead of stdout")
        return p

    add("prologue", "the addresses with the game's function prologue").set_defaults(func=cmd_prologue)
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
            elf = MipsElf(handle.read(), args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return args.func(elf, args)


if __name__ == "__main__":
    raise SystemExit(main())
