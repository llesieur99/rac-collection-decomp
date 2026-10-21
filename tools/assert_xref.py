"""Find the assert messages of a PPU executable, and the functions that use them.

The naming evidence of a function is what the code at its address says about
it.  The assert messages are the best of it: they carry the name of the
source file and the line inside it, so a function that asserts says which
file it comes from and where.

How the code reaches a message
------------------------------

The PPU is a 64-bit PowerPC, big endian.  Measured on the retail builds of
this game:

* An address is built in two instructions: ``addis rD, r0, HI`` puts the
  high half of the address in a register, and ``addi``/``addic``/``ori``
  adds the low half.  The high half is the address shifted right by
  sixteen, and the low half is added **with its sign**, so the address
  whose low half has its top bit set is built with the high half one
  greater.  ``r0`` reads as zero: the compiler uses it as the base of the
  idiom, and a function called from six places builds the same address at
  every call, while the link register added to it would fall outside every
  section of the program.
* The assert reaches the code in one of two shapes, both measured:

  - **one message** — the whole text of the assert is a single literal,
    already carrying the file and the line::

        lis  r3, 0x0014
        li   r4, 0
        addi r3, r3, 0x7018      ; r3 = "j:/Ratchet/rcc/.../Draw_PS.cpp:175 texture != 0"
        bl   assertHandler

  - **the file, the line and the condition** — three arguments, in that
    order, to a function that prints them::

        lis  r3, 0x0124
        lis  r4, 0x0124
        li   r5, 359
        addi r3, r3, -0x6B54     ; r3 = the text of the condition
        addi r4, r4, -0x6B0C     ; r4 = "j:/Ratchet/.../IMSeqMem.cpp"
        bl   assertHandler       ; r5 = the line

The tool reads the code, watches the registers, and reports every call
that carries a message of that shape, with the function that holds it.

    python tools/assert_xref.py work/decrypted/RC2.elf \\
        --catalogue config/functions.tsv --program RC2 --out work/asserts.tsv

The mode ``--strings-out`` writes the other half of the question: the
assert strings of the data, and whether the code builds their address.
A string that the code never builds is the leftover of a library the
retail build links but does not call: it can name no function.

Only metadata is written: the address of a function, the address of the
call, and the text of the message.  No game byte is copied.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import os
import re
import struct
import sys
from dataclasses import dataclass
from typing import Iterable, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402
from strings_xref import StringTable, segments  # noqa: E402

MASK32 = 0xFFFFFFFF

# The opcodes the tool reads.
ADDIS = 15       # addis rD, rA, HI   the high half of an address
ADDI = 14        # addi  rD, rA, LO   the low half of an address
ADDIC = 12       # addic rD, rA, LO
ADDICD = 13      # addic. rD, rA, LO
ORI = 24         # ori   rA, rS, LO   the low half, unsigned
ORIS = 25        # oris  rA, rS, HI
XORI = 26        # xori  rA, rS, LO
ANDI = 28        # andi. rA, rS, LO
ANDIS = 29       # andis. rA, rS, HI
BRANCH = 18      # b / bl
BCOND = 16       # bc
BINDIR = 19      # bc / bclr / bctr

# The opcodes that read memory through a base register and an immediate.
LOADS = frozenset({32, 33, 34, 35, 40, 41, 44, 45, 48, 49, 52, 53, 58})
STORES = frozenset({36, 37, 38, 39, 42, 43, 46, 47, 50, 51, 54, 55, 62})

# The extended opcodes of the 31 family the tool knows.
XO_CMP = frozenset({0, 26})        # cmpw, cmplw
XO_MTCRF = 144
XO_MTLR = 467
XO_OR = 444                       # mr rD, rS  (or rD, rS, rS)
XO_ADDC = 10                      # addc rD, rA, rB
XO_ADDE = 138                     # adde rD, rA, rB
XO_SUBF = 8                       # subf rD, rA, rB
XO_SUBFE = 136
XO_MULLW = 235

# The returns and the indirect jumps.
BLR = 0x4E800020
BLR32 = 0x48000009
BCTR = 0x4E800420
BCTRL = 0x4E800421

# The registers that carry the arguments of a call.
ARGUMENT_REGISTERS = (3, 4, 5, 6, 7, 8, 9, 10)

# The source files a message can name.
SOURCE_SUFFIXES = ("c", "cpp", "cxx", "cc", "h", "hh", "hpp", "hxx",
                   "inl", "inc")
# A file name on its own: "LightSetup.cpp", "j:/Ratchet/game/hud.cpp".
SOURCE_RE = re.compile(
    r"(?:[A-Za-z]:)?(?:[^\s]*[/\\])?[\w.+-]*\.(?:%s)\Z"
    % "|".join(SOURCE_SUFFIXES))
# A message that carries its line: "texture.cpp:91 p != NULL".
MESSAGE_RE = re.compile(
    r"(?:[\w.+-]*[/\\])?[\w.+-]*\.(?:%s):(\d+)"
    % "|".join(SOURCE_SUFFIXES + ("s", "asm")))


def sign16(value: int) -> int:
    """The signed value of a sixteen bit field."""
    return value - 0x10000 if value & 0x8000 else value


def branch_target(word: int, address: int) -> int:
    """The target of a branch with a twenty six bit displacement."""
    displacement = word & 0x03FFFFFC
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return (address + displacement) & MASK32


def conditional_target(word: int, address: int) -> int:
    """The target of a conditional branch.

    The displacement of the ``bc`` of the PPU is a byte offset in the low
    fourteen bits, like the displacement of the ``b``: measured on the
    retail build, fifty thousand nine hundred and forty eight of the
    conditional branches land on an address the program branches to, when
    the field is read that way, against three thousand eight hundred and
    sixty three when it is read as a word offset.
    """
    return (address + sign16(word & 0xFFFC)) & MASK32


class Tracker:
    """The values of the registers, as the code builds them.

    Only the shapes that carry an address are followed.  Every other
    instruction invalidates the register it writes, so a value is never
    claimed when the code does not say what it is.

    ``r0`` is kept at zero.  The compiler builds the high half of an
    address with ``addis rD, r0, HI``, and the value of ``r0`` takes no
    part in the result, so the register reads as the zero base of the
    idiom and the instructions that write it are ignored.
    """

    def __init__(self) -> None:
        self.registers: list[int | None] = [None] * 32
        self.registers[0] = 0

    def value(self, register: int) -> int | None:
        return self.registers[register]

    def _write(self, register: int, value: int | None) -> None:
        if register:
            self.registers[register] = value

    def step(self, word: int) -> None:
        """Apply one instruction to the state."""
        opcode = word >> 26
        rD = (word >> 21) & 0x1F
        rA = (word >> 16) & 0x1F
        rB = (word >> 11) & 0x1F
        uimm = word & 0xFFFF
        simm = sign16(uimm)
        held = self.registers[rA]

        if opcode == ADDIS:
            base = 0 if rA == 0 else held
            self._write(rD, ((base + (uimm << 16)) & MASK32)
                        if base is not None else None)
            return
        if opcode in (ADDI, ADDIC, ADDICD):
            self._write(rD, ((held + simm) & MASK32)
                        if held is not None else None)
            return
        if opcode == ORI:
            source = self.registers[rD]
            self._write(rA, ((source | uimm) & MASK32)
                        if source is not None else None)
            return
        if opcode == ORIS:
            source = self.registers[rD]
            self._write(rA, ((source | (uimm << 16)) & MASK32)
                        if source is not None else None)
            return
        if opcode == XORI:
            source = self.registers[rD]
            self._write(rA, ((source ^ uimm) & MASK32)
                        if source is not None else None)
            return
        if opcode == ANDI:
            source = self.registers[rD]
            self._write(rA, ((source & uimm) & MASK32)
                        if source is not None else None)
            return
        if opcode == ANDIS:
            source = self.registers[rD]
            self._write(rA, ((source & (uimm << 16)) & MASK32)
                        if source is not None else None)
            return
        if opcode in (BRANCH, BCOND, BINDIR, 10, 11, 17):
            return                          # branches and comparisons
        if opcode == 31:
            extended = (word >> 1) & 0x3FF
            if extended in XO_CMP or extended in (XO_MTCRF, XO_MTLR):
                return
            if extended == XO_OR and rB == rD:
                self._write(rD, self.registers[rA])
                return
            if extended in (XO_ADDC, XO_ADDE):
                left = self.registers[rA]
                right = self.registers[rB]
                self._write(rD, ((left + right) & MASK32)
                            if left is not None and right is not None
                            else None)
                return
            if extended in (XO_SUBF, XO_SUBFE):
                left = self.registers[rA]
                right = self.registers[rB]
                self._write(rD, ((right - left) & MASK32)
                            if left is not None and right is not None
                            else None)
                return
            if extended == XO_MULLW:
                left = self.registers[rA]
                right = self.registers[rB]
                self._write(rD, ((left * right) & MASK32)
                            if left is not None and right is not None
                            else None)
                return
            if rD:
                self.registers[rD] = None
            return
        if opcode in LOADS:
            if rD:
                self.registers[rD] = None
            return
        if opcode in STORES:
            return                              # a store writes no register
        if rD:
            self.registers[rD] = None


@dataclass(frozen=True)
class Call:
    """A call the code makes, with the arguments it passes."""
    address: int
    target: int
    arguments: dict[int, int]


def calls(elf: PpuElf) -> Iterable[Call]:
    """The calls the program makes, with the arguments they pass.

    The registers are **not** reset at the entry of a function: the
    compiler passes a base pointer in a callee saved register, and the
    value of that register at a call is a real one.  What tells a real
    assert from a log call that happens to carry a file name is the
    line: an assert always passes one.
    """
    from ppu_funcs import text_code
    base, blob = text_code(elf)
    tracker = Tracker()
    for offset in range(0, len(blob) - 3, 4):
        word = struct.unpack_from(">I", blob, offset)[0]
        address = base + offset
        if word >> 26 == BRANCH and word & 1:
            tracker.step(word)
            arguments = {register: tracker.value(register)
                         for register in ARGUMENT_REGISTERS}
            yield Call(address, branch_target(word, address), arguments)
            continue
        tracker.step(word)


@dataclass(frozen=True)
class Assert:
    """An assert message, and the call that carries it."""
    site: int
    target: int
    message: str
    file: str
    line: str
    expression: str


def classify(call: Call, strings: StringTable,
             loaded: Sequence[tuple[int, int]]) -> Assert | None:
    """The assert message a call carries, if it carries one.

    Two shapes are read, both measured on the retail builds:

    * one argument holds the whole message, the file and the line
      included;
    * one argument names the source file, another holds the line, and
      another holds the text of the condition.
    """
    texts: dict[int, str] = {}
    for register in ARGUMENT_REGISTERS:
        value = call.arguments.get(register)
        if value is None:
            continue
        text = strings.at(value)
        if text is not None:
            texts[register] = text

    # one message, the file and the line included
    for register in sorted(texts):
        text = texts[register]
        match = MESSAGE_RE.search(text)
        if match:
            return Assert(call.address, call.target, text,
                          match.group(0), match.group(1), "")

    # the file, the line and the text of the condition
    for register in sorted(texts):
        text = texts[register]
        if not SOURCE_RE.fullmatch(text):
            continue
        line = _line_of(call, register, loaded)
        if not line:
            # a call that names a file but no line is not an assert: the
            # name is left in a register by the code before
            continue
        expression = ""
        for other in sorted(texts):
            if other >= register:
                break
            # a format is not the text of the condition
            if "%" not in texts[other]:
                expression = texts[other]
                break
        message = f"{text}:{line}"
        if expression:
            message += f" {expression}"
        return Assert(call.address, call.target, message, text, line,
                      expression)
    return None


def _line_of(call: Call, register: int,
             loaded: Sequence[tuple[int, int]]) -> str:
    """The line the call passes beside the name of the file."""
    candidates = []
    for other in ARGUMENT_REGISTERS:
        if other == register:
            continue
        value = call.arguments.get(other)
        if value is None or value <= 0 or value > 999999:
            continue
        if any(low <= value < high for low, high in loaded):
            continue                      # a pointer, not a line
        candidates.append((other, value))
    if not candidates:
        return ""
    # the line usually follows the file
    for other, value in candidates:
        if other == register + 1:
            return str(value)
    return str(candidates[0][1])


def read_catalogue(path: str, program: str | None) -> list[tuple[int, int]]:
    """The (address, size) of the functions of the catalogue.

    Only the confirmed functions are read: the extent of a candidate is
    provisional, and an assert belongs to the function that owns the code.
    """
    functions: list[tuple[int, int]] = []
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if program and row["program"] != program:
                continue
            if row.get("state", "bounded") != "bounded":
                continue
            functions.append((int(row["address"], 0), int(row["size"])))
    functions.sort()
    return functions


def function_body(elf: PpuElf, start: int,
                  entries: set[int]) -> set[int]:
    """The addresses the function owns.

    The walk follows the branches and stops at the return that no path
    falls through from.  A conditional branch of the sixteen (``bc``)
    opens two paths, and both are followed: the blocks of a switch sit
    outside the run of instructions that starts at the entry, and they
    belong to the function that reaches them.
    """
    from ppu_funcs import text_code
    base, blob = text_code(elf)
    size = len(blob)

    def word_at(address: int) -> int | None:
        offset = address - base
        if offset < 0 or offset + 4 > size:
            return None
        return struct.unpack_from(">I", blob, offset)[0]

    visited: set[int] = set()
    pending = [start]
    while pending:
        address = pending.pop()
        while True:
            if address in visited:
                break
            if address != start and address in entries:
                break                      # the flow reached the next function
            word = word_at(address)
            if word is None:
                break
            visited.add(address)
            if word in (BLR, BLR32):
                break
            if word in (BCTR, BCTRL):
                break
            if word >> 26 == BRANCH:
                if word & 1:
                    address += 4            # a call: the flow goes on
                    continue
                if word & 0x2:
                    break                  # an absolute branch leaves the code
                target = branch_target(word, address)
                if target <= start or target >= base + size:
                    break
                if target not in visited:
                    pending.append(target)
                break
            if word >> 26 == BCOND:
                target = conditional_target(word, address)
                if start < target < base + size and target not in visited:
                    pending.append(target)
                address += 4
                continue
            if word >> 26 == BINDIR:
                # an indirect call: the flow goes on after it
                if (word >> 1) & 0x3FF in (528, 529):
                    address += 4
                    continue
                break                      # the condition is not known
            address += 4
    return visited


class Owners:
    """The function that holds an address.

    The extent of a function is not only the run of instructions that
    starts at it: a switch, or a block the compiler moved, sits outside.
    The walk of the control flow finds them, and the block belongs to the
    function that reaches it.

    The catalogue of the repository does not name every function of the
    retail builds, so the addresses the prologue and the calls give are
    added to the list of the entries.
    """

    def __init__(self, elf: PpuElf, functions: list[tuple[int, int]]):
        self.elf = elf
        self.functions = functions
        self.starts = sorted({start for start, _size in functions}
                              | _detected_entries(elf))
        self.entries = set(self.starts)
        self.cache: dict[int, set[int]] = {}

    def body(self, start: int) -> set[int]:
        """The addresses the function owns."""
        if start not in self.cache:
            self.cache[start] = function_body(self.elf, start, self.entries)
        return self.cache[start]

    def of(self, address: int) -> int | None:
        """The function that holds an address, or None."""
        if not self.starts:
            return None
        index = bisect.bisect_right(self.starts, address) - 1
        while index >= 0:
            start = self.starts[index]
            if address in self.body(start):
                return start
            index -= 1
        return None


def _detected_entries(elf: PpuElf) -> set[int]:
    """The addresses the prologue and the calls of the program give."""
    from ppu_funcs import build_catalogue
    return {address for address, _kind, _evidence in build_catalogue(elf)}


def escape(text: str) -> str:
    """A string, with the characters that would break the table escaped."""
    return (text.replace("\\", "\\\\").replace("\t", "\\t")
            .replace("\r", "\\r").replace("\n", "\\n"))


def built_addresses(elf: PpuElf) -> set[int]:
    """The addresses the code builds."""
    from ppu_funcs import text_code
    base, blob = text_code(elf)
    tracker = Tracker()
    addresses: set[int] = set()
    for offset in range(0, len(blob) - 3, 4):
        word = struct.unpack_from(">I", blob, offset)[0]
        tracker.step(word)
        for register in ARGUMENT_REGISTERS:
            value = tracker.value(register)
            if value is not None:
                addresses.add(value)
    return addresses


def assert_strings(elf: PpuElf, data: list[tuple[int, bytes]]) -> list[tuple[int, str]]:
    """The strings of the data that carry a source file, or a line."""
    table = StringTable(data)
    out = []
    for start, _end, text in table.runs:
        if MESSAGE_RE.search(text) or SOURCE_RE.fullmatch(text):
            out.append((start, text))
    out.sort()
    return out


def write_strings(elf: PpuElf, data: list[tuple[int, bytes]], path: str) -> int:
    """Write the assert strings of the data, and whether the code uses them.

    A string that the code never builds is a string that no function can
    be named after: it is the leftover of a library the retail build
    links but does not call.
    """
    built = built_addresses(elf)
    pointers: dict[int, list[int]] = {}
    for low, blob in data:
        for offset in range(0, len(blob) - 3, 4):
            value = int.from_bytes(blob[offset:offset + 4], "big")
            pointers.setdefault(value, []).append(low + offset)
    rows = []
    for address, text in assert_strings(elf, data):
        rows.append((f"0x{address:08X}", escape(text),
                     "yes" if address in built else "no",
                     " ".join(f"0x{where:08X}"
                              for where in pointers.get(address, ()))))
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("address\ttext\treferenced\tpointer_at\n")
        for row in rows:
            out.write("\t".join(row) + "\n")
    return len(rows)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("elf", help="path to the decrypted PPU ELF")
    parser.add_argument("--catalogue", default=None,
                        help="config/functions.tsv, to name the functions")
    parser.add_argument("--program", default=None,
                        help="the program of the catalogue to use")
    parser.add_argument("--out", required=True, help="the file to write")
    parser.add_argument("--append", action="store_true",
                        help="add to the file instead of replacing it")
    parser.add_argument("--strings-out", default=None,
                        help="also write the assert strings of the data, and "
                             "whether the code uses them")
    args = parser.parse_args(argv)

    try:
        with open(args.elf, "rb") as handle:
            elf = PpuElf(handle.read(), args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _code, data = segments(elf)
    strings = StringTable(data)
    loaded = [(low, low + len(blob)) for low, blob in data]

    if args.strings_out:
        count = write_strings(elf, data, args.strings_out)
        print(f"wrote {args.strings_out}: {count} assert strings")

    functions: list[tuple[int, int]] = []
    if args.catalogue:
        functions = read_catalogue(args.catalogue, args.program)
    owners = Owners(elf, functions)
    known = {start for start, _size in functions}

    rows = []
    for call in calls(elf):
        found = classify(call, strings, loaded)
        if found is None:
            continue
        function = owners.of(found.site)
        rows.append((args.program or "",
                     f"0x{function:08X}" if function is not None else "",
                     escape(found.message),
                     f"0x{found.site:08X}",
                     escape(found.file),
                     found.line,
                     escape(found.expression),
                     f"0x{found.target:08X}",
                     "yes" if function in known else "no"))

    rows.sort(key=lambda row: (row[0], row[1], row[3]))

    mode = "a" if args.append else "w"
    with open(args.out, mode, encoding="utf-8", newline="") as out:
        # The csv module, and not a join: a message of the game may hold a
        # double quote, and a table that a quote breaks is a table that lies.
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        if not args.append:
            writer.writerow(["program", "address", "message", "site", "file",
                             "line", "expression", "handler", "in_catalogue"])
        writer.writerows(rows)
    print(f"wrote {args.out}: {len(rows)} asserts "
          f"({sum(1 for row in rows if row[1])} in a function)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
