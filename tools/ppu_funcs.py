"""Recover the function boundaries of a PPU executable.

The retail build of a PlayStation 3 game is stripped: there is no symbol
table and no section name.  The boundaries have to come from the code
itself, and a boundary that only one method sees is a candidate, not a
function.

This tool offers the cheap, independent methods:

* **prologue scan** — the PS3 SDK's PPU functions open with a fixed
  pattern: the stack pointer is moved down with ``stdu r1, -N(r1)`` and the
  link register is saved with ``mflr r0`` / ``stw r0, 0x10(r1)``;
* **call scan** — every ``bl`` (branch and link) names an address that the
  program calls, and a called address is a function;
* **entry scan** — an address the flow cannot fall into is the start of a
  new block, and a function starts with a new block.

Both sets are published separately, so that they can be compared.  Only the
tool needs the Python standard library: the few opcodes that matter are
decoded directly.

A third pass walks the control flow from a candidate to find where the
function ends: a function ends at the return that no path falls through
from.

    python tools/ppu_funcs.py prologue <eboot.elf> [--out FILE]
    python tools/ppu_funcs.py calls    <eboot.elf> [--out FILE]
    python tools/ppu_funcs.py entries  <eboot.elf> [--out FILE]
    python tools/ppu_funcs.py catalogue <eboot.elf> [--out FILE] [--wide]
    python tools/ppu_funcs.py bounds   <eboot.elf> [--out FILE] [--wide]

The **narrow** prologue is the frame at the first instruction of the
function.  The measurement showed that the compiler does not always put it
there, so the **wide** prologue accepts the frame a few instructions later,
and accepts the frame without the save of the link register.  The wide
catalogue weighs four signals — the prologue, the call, the entry and the
return: an address that two of them agree on is a function, an address that
only one of them sees is a candidate.
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
# destination register sits in bits 21-25.  The mask keeps every bit but
# the destination and the link bit: ``mtlr`` (the extended opcode 0x1D3)
# must not pass for a ``mflr``.
MFLR_MASK = 0xFC1FFFFE
MFLR_VALUE = 0x7C0802A6

# The call instruction: the unconditional branch with the link bit set
# (opcode 18, LK at bit 0; AA at bit 1).
BRANCH_MASK = 0xFC000001
BRANCH_LINK = 0x48000001

# The conditional branches (opcode 16) and the indirect ones (opcode 19).
#
# The conditional branch of the PowerPC has the opcode 16, whose top
# bits are 0x40000000.  The test that read 0x80000000 never matched a
# conditional branch: it matched the loads with an offset, whose opcode
# is 32, and the walk then followed the "target" of a load, which is
# nothing.  The conditional branch is now read by its opcode.
CONDITIONAL_OPCODE = 16
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


def conditional_target(word: int, address: int) -> int:
    """The target of a conditional branch.

    The displacement of the conditional branch is a signed value in the
    bits 2-15, counted in bytes — the reading of ``tools/ppu_disasm.py``,
    and the one the measurement confirmed: the target of the branch
    0x41DE0014 at 0x147C4 is 0x147D8, a block of the function that
    holds the branch.
    """
    displacement = word & 0xFFFC
    if displacement & 0x8000:
        displacement -= 0x10000
    return (address + displacement) & 0xFFFFFFFF


def walk_bound(confirmed: set[int], calls: set[int],
               entries: set[int]) -> set[int]:
    """The addresses the walk of the control flow must stop on.

    The bound holds the **entries of the functions**: the confirmed
    functions, and the targets of a call that the control flow cannot
    fall into.  A target of a call is not always a function — a word of
    a table of the text segment, decoded as a call, names an address
    that no function starts at — and stopping on it cuts the extent of
    the function that reaches it in two.

    The criterion is the one of the *entry* signal: the instruction that
    precedes the address does not fall through, so the address opens a
    new block, and a function opens with a new block.
    """
    return confirmed | (calls & entries)


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

    This is the *narrow* prologue: the frame is the first instruction of
    the function.  :func:`prologue_forms` is the wide one, and it is what
    the extended catalogue uses.
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


# -- the signals of a function entry ---------------------------------------
#
# The narrow prologue above is the shape the SDK uses when the frame is the
# first instruction of the function.  The measurement showed that it is not
# always: the compiler sometimes emits one or two instructions before the
# frame, and sometimes no link-register save at all.  The three signals
# below are the ones the extended catalogue weighs.
#
# * **the prologue** — the shape of the code: the frame of the SDK, with or
#   without the save of the link register, at or shortly after the address;
# * **the call** — the references of the code: a ``bl`` lands on the address;
# * **the entry** — the control flow: the instruction before the address
#   does not fall through, so the address opens a new block.

# The frame of the SDK: ``stdu r1, -N(r1)``.  On the PPU the instruction
# keeps the old stack pointer and moves it down; the displacement is a
# 16-bit signed value whose low two bits are ignored.
def is_frame(word: int) -> bool:
    """``stdu r1, -N(r1)``: the stack pointer moves down."""
    return (word & 0xFFFF0000) == STDU_R1 and (word & 0x8000) != 0


def is_link_save(word: int) -> bool:
    """``mflr rX``: the link register is saved."""
    return (word & MFLR_MASK) == MFLR_VALUE


def falls_through(word: int) -> bool:
    """The flow continues on the instruction that follows.

    A return, an unconditional branch and an indirect jump do not; every
    other instruction does.  The conditional branch of the PPU that
    targets itself is a spin — the code never goes on — and does not
    fall through either.
    """
    opcode = word >> 26
    if opcode == 18:
        # b / bl: only the call falls through.
        return (word & 3) == 1
    if opcode == 16:
        # The conditional branch of the PPU: a branch to itself spins.
        return (word & 0xFFFC) != 0
    if opcode == 19:
        xo = (word >> 1) & 0x3FF
        bo = (word >> 21) & 0x1F
        if xo == 16:
            # bclr: the conditional forms fall through, the plain return does not.
            return bo != 20
        if xo == 528:
            # bcctr: bctrl falls through, bctr does not.
            return (word & 1) != 0
    return True


# How far the frame of the SDK may be from the entry of the function.  The
# measurement put the frame at +0, +1 and +2 for the functions the narrow
# prologue misses; the values beyond are the frame of the *next* function.
# The block is found by the two instructions that make it, not by a window:
# the address of the block is the address of the first of the two.

# The forms the prologue takes, from the strongest to the weakest.
PROLOGUE_FRAME_LR = "frame+lr"
PROLOGUE_FRAME = "frame"


def prologue_forms(elf: PpuElf) -> dict[int, str]:
    """The prologue block that starts at every address of the program.

    The prologue of the SDK is a block of two instructions: the frame
    (``stdu r1, -N(r1)``) and the save of the link register
    (``mflr r0``).  The block has two orders — the frame first, the link
    register first — and the frame may stand alone when the function
    calls nothing and never has to save the link register.

    The form is recorded at the address where the block **starts**: the
    frame when the frame comes first, the link register when it comes
    first.  The address of the frame alone is not a prologue of its own
    when the link register was saved just before it: the block started
    one instruction earlier.

    This is what the narrow prologue cannot see.  It records the address
    of the frame, and the compiler does not always put the frame at the
    first instruction of the function.
    """
    base, data = text_code(elf)
    count = len(data) // 4
    words = struct.unpack_from(">%dI" % count, data, 0)
    out: dict[int, str] = {}
    for index in range(count):
        word = words[index]
        following = words[index + 1] if index + 1 < count else 0
        preceding = words[index - 1] if index > 0 else 0
        if is_frame(word):
            if is_link_save(following):
                out[base + index * 4] = PROLOGUE_FRAME_LR
            elif not is_link_save(preceding):
                # The frame alone: the function has locals but calls nothing.
                out[base + index * 4] = PROLOGUE_FRAME
        elif is_link_save(word) and is_frame(following):
            # The link register first: the block starts here.
            out[base + index * 4] = PROLOGUE_FRAME_LR
    return out


def entry_candidates(elf: PpuElf) -> list[Candidate]:
    """The addresses that open a new block: the flow cannot fall into them.

    The instruction that precedes the address does not fall through: it is
    a return, an unconditional branch or an indirect jump.  The address is
    then the start of a new block, and a function starts with a new block.
    """
    base, data = text_code(elf)
    count = len(data) // 4
    words = struct.unpack_from(">%dI" % count, data, 0)
    out = []
    for index in range(1, count):
        if not falls_through(words[index - 1]):
            out.append(Candidate(base + index * 4, "entry"))
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


def signals(elf: PpuElf) -> dict[str, set[int]]:
    """The three signals of the **start** of a function, as sets of addresses.

    * ``prologue`` — the frame of the SDK, with or without the save of the
      link register, at the address;
    * ``call`` — the addresses a ``bl`` lands on;
    * ``entry`` — the addresses the flow cannot fall into.

    The fourth signal — the return the walk ends on — needs the walk, and
    :func:`entry_evidence` weighs it.  The forms of the prologue are in
    :func:`prologue_forms`.
    """
    forms = prologue_forms(elf)
    return {
        "prologue": set(forms),
        "call": {c.address for c in call_targets(elf)},
        "entry": {c.address for c in entry_candidates(elf)},
    }


def entry_evidence(elf: PpuElf) -> tuple[dict[int, list[str]], set[int]]:
    """The signals of every candidate address, and the confirmed ones.

    The signals of the start of a function are the prologue, the call and
    the entry.  Two of them agree on a function.  The prologue alone is
    not enough — a frame in the middle of a function would pass it — so
    the prologue is confirmed by a fourth signal: the walk from the
    address must end on a return.

    The addresses that only the *entry* signal sees are the starts of
    the blocks that are not functions; they are not in the catalogue.
    """
    forms = prologue_forms(elf)
    calls = {c.address for c in call_targets(elf)}
    entries = {c.address for c in entry_candidates(elf)}
    universe = set(forms) | calls
    evidence: dict[int, list[str]] = {}
    for address in sorted(universe):
        seen = []
        if address in forms:
            seen.append(forms[address])
        if address in calls:
            seen.append("call")
        if address in entries:
            seen.append("entry")
        evidence[address] = seen
    confirmed = {address for address, seen in evidence.items() if len(seen) >= 2}

    # The prologue alone: the walk has to end on a return for the address
    # to be a function and not a frame in the middle of one.
    bound = walk_bound(confirmed, calls, entries)
    for address in sorted(universe - confirmed):
        if len(evidence[address]) != 1:
            continue
        if evidence[address][0] not in (PROLOGUE_FRAME_LR, PROLOGUE_FRAME):
            continue
        _end, why, _body = function_body(elf, address, entries=bound)
        if why == "return":
            evidence[address].append("return")
            confirmed.add(address)
    return evidence, confirmed


def build_catalogue(elf: PpuElf, wide: bool = False) -> list[tuple[int, str, str]]:
    """The union of both methods, with the evidence for each address.

    With ``wide``, the signals of a function entry are weighed instead
    of the two of the narrow method:

    * **prologue** — the frame of the SDK, with or without the save of
      the link register, at the address;
    * **call** — a ``bl`` lands on the address;
    * **entry** — the flow cannot fall into the address;
    * **return** — the walk from the address ends on a return.

    An address that two of the signals agree on is a function; an
    address that only one of them sees is a candidate, and the evidence
    says which one.  The addresses that only the *entry* signal sees are
    the starts of the blocks that are not functions; they are not in the
    catalogue.
    """
    if not wide:
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

    evidence, _confirmed = entry_evidence(elf)
    rows = []
    for address in sorted(evidence):
        seen = evidence[address]
        rows.append((address, "+".join(seen),
                     "both" if len(seen) >= 2 else seen[0]))
    return rows


def cmd_prologue(elf: PpuElf, args: argparse.Namespace) -> int:
    rows = [(c.address, "", "prologue") for c in prologue_candidates(elf)]
    return _write(rows, args)


def cmd_calls(elf: PpuElf, args: argparse.Namespace) -> int:
    rows = [(c.address, "", "call") for c in call_targets(elf)]
    return _write(rows, args)


def cmd_catalogue(elf: PpuElf, args: argparse.Namespace) -> int:
    rows = [(address, kind, evidence)
            for address, kind, evidence in
            build_catalogue(elf, wide=getattr(args, "wide", False))]
    if getattr(args, "confirmed", False):
        rows = [row for row in rows if row[2] == "both"]
    return _write(rows, args)


def function_body(elf: PpuElf, start: int, limit: int = 200000,
                  entries: set[int] | None = None,
                  full: bool = False) -> tuple[int, str, list[int]]:
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

    With ``full``, the body is every instruction the walk reached, and not
    only the contiguous block that starts at the entry: a function whose
    blocks are scattered — a jump table, a cold block the compiler moved —
    owns the instructions of those blocks too.
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
                if word == BCTR:
                    # bctr is a jump: the flow does not come back.
                    evidence = "indirect"
                    break
                # bctrl is a *call* through a pointer: the flow comes back,
                # and the walk continues on the next instruction.  Stopping
                # there cut 954 functions short.
                address += 4
                continue
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
            if word >> 26 == CONDITIONAL_OPCODE:
                # a conditional branch: both paths
                target = conditional_target(word, address)
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
    if full:
        return end, evidence, body
    return end, evidence, run


def function_extent(elf: PpuElf, start: int, limit: int = 200000,
                    entries: set[int] | None = None) -> tuple[int | None, str]:
    """The address just after the last instruction of the function, and why."""
    end, why, _body = function_body(elf, start, limit, entries)
    return end, why


def cmd_entries(elf: PpuElf, args: argparse.Namespace) -> int:
    rows = [(c.address, "", "entry") for c in entry_candidates(elf)]
    return _write(rows, args)


def cmd_bounds(elf: PpuElf, args: argparse.Namespace) -> int:
    rows = []
    catalogue = build_catalogue(elf, wide=getattr(args, "wide", False))
    if getattr(args, "wide", False):
        # the bound of the walk: the entries of the functions
        confirmed = {address for address, kind, _evidence in catalogue
                     if kind == "both"}
        entries = walk_bound(confirmed,
                             {c.address for c in call_targets(elf)},
                             {c.address for c in entry_candidates(elf)})
    else:
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
    add("entries", "the addresses the flow cannot fall into").set_defaults(func=cmd_entries)
    p_catalogue = add("catalogue", "both methods, with their evidence")
    p_catalogue.add_argument("--confirmed", action="store_true",
                             help="keep only the addresses both methods agree on")
    p_catalogue.add_argument("--wide", action="store_true",
                             help="weigh the three signals of an entry")
    p_catalogue.set_defaults(func=cmd_catalogue)

    p_bounds = add("bounds", "the extent of every candidate")
    p_bounds.add_argument("--confirmed", action="store_true",
                           help="keep only the addresses both methods agree on")
    p_bounds.add_argument("--wide", action="store_true",
                           help="weigh the three signals of an entry")
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
