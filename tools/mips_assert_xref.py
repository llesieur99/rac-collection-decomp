"""Find the assert sites of a PS2 executable, and the triplet they carry.

The naming evidence of a function is what the code at its address says about
it.  On the PlayStation 2 the strongest of it is the *triplet*: the name of
the source file, the line inside it, and the text of the condition.  A
function that asserts says which file it comes from and where.

How the code reaches the triplet
---------------------------------

Measured on the retail build of Ratchet & Clank (SCUS-971.99), the core
executable and the nineteen overlays of the levels:

* An address is built in two instructions, ``lui $rD, %hi(str)`` then
  ``addiu $rD, $rD, %lo(str)`` (or ``ori``).  The compiler reuses the
  registers freely, so the two halves are often more than a dozen
  instructions apart: the tool follows the *value* of the registers, not a
  window of instructions.

* The name of the source file is a **string of the literal section**
  (``.lit`` of the core, ``0x0015EF00`` and after), and the retail build
  holds three of them: ``hud.cpp``, ``loaders.cpp`` and ``map.cpp``.

* The line is an **immediate**, and it is loaded in the **delay slot** of
  the call::

      0x00202B04:  lui   $v0, 0x0016
      0x00202B0C:  addiu $s6, $v0, -1104   ; $s6 = "loaders.cpp"
      ...
      0x00202B34:  move  $a2, $s6          ; the third argument: the file
      0x00202B38:  jal   0x001FF288        ; the call
      0x00202B3C:  addiu $a3, $zero, 570   ; the fourth argument: the line

  The delay slot runs *before* the call, so the line is already in the
  register when the callee sees it.  A reader that does not honour the
  delay slot misses every one of these sites.

* The arguments follow the o32 convention: ``$a0`` to ``$a3``.  The
  engine's own wrapper takes them as ``(size, flag, file, line)`` — the
  file is the third argument and the line the fourth — while the SDK's
  ``assert`` takes them as ``(condition, file, line)``.  The tool does not
  assume one convention: it looks for the argument that holds the name of
  a source file, and for the argument beside it that holds a line.

* A value is forgotten when the code does not say what it is: every
  instruction that writes a register without a known value invalidates it.
  The argument registers are invalidated after every call, because the
  o32 convention says the callee may change them.

The tool reads the code, watches the registers, and reports every call
that carries a triplet, with the function that holds it.

    python tools/mips_assert_xref.py <overlay.elf> \\
        --program LVL00 --level 00 --out work/ps2-asserts.tsv

Only metadata is written: the address of a function, the address of the
call, the name of the file and the line.  No game byte is copied.
"""

from __future__ import annotations

import argparse
import bisect
import os
import re
import struct
import sys
from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mips_elf import ElfError, MipsElf  # noqa: E402
from mips_funcs import (OP_ADDI, OP_ADDIU, OP_ANDI, OP_JAL, OP_LB,  # noqa: E402
                        OP_LBU, OP_LDC1, OP_LD, OP_LH, OP_LHU, OP_LQ, OP_LW,
                        OP_LWC1, OP_ORI, OP_SB, OP_SD, OP_SH, OP_SQ, OP_SW,
                        OP_SWC1, OP_XORI, OP_LUI, OP_SPECIAL, build_catalogue,
                        function_body, text_code)
from mips_strings_xref import StringTable  # noqa: E402

MASK32 = 0xFFFFFFFF

# The opcodes the tool reads.
OP_REGIMM = 0x01
OP_J = 0x02
OP_BEQ = 0x04
OP_BNE = 0x05
OP_BLEZ = 0x06
OP_BGTZ = 0x07
OP_SLTI = 0x0A
OP_SLTIU = 0x0B
OP_SPECIAL2 = 0x1C
OP_BEQL = 0x14
OP_BNEL = 0x15
OP_BLEZL = 0x16
OP_BGTZL = 0x17
OP_LWU = 0x27

# The functions of the SPECIAL opcode.
SPECIAL_SLL = 0x00
SPECIAL_JR = 0x08
SPECIAL_JALR = 0x09
SPECIAL_MFHI = 0x10
SPECIAL_MTHI = 0x11
SPECIAL_MFLO = 0x12
SPECIAL_MTLO = 0x13
SPECIAL_ADD = 0x20
SPECIAL_ADDU = 0x21
SPECIAL_SUB = 0x22
SPECIAL_SUBU = 0x23
SPECIAL_AND = 0x24
SPECIAL_OR = 0x25
SPECIAL_XOR = 0x26
SPECIAL_NOR = 0x27
SPECIAL_SLT = 0x2A
SPECIAL_SLTU = 0x2B
# The R5900 adds the doubleword instructions to the SPECIAL opcode:
# ``dadd``, ``daddu``, ``dsub`` and ``dsubu``.  The compiler uses
# ``daddu $rD, $rS, $zero`` as its move, so the reader has to know it.
SPECIAL_DADD = 0x2C
SPECIAL_DADDU = 0x2D
SPECIAL_DSUB = 0x2E
SPECIAL_DSUBU = 0x2F

# The functions of the SPECIAL2 opcode.
SPECIAL2_MADD = 0x00
SPECIAL2_MADDU = 0x01
SPECIAL2_MUL = 0x02

# The registers of the arguments of a call, in the order the o32
# convention uses.  The first four are the ``$a`` registers; the SDK's
# assert takes two more, and the compiler passes them in ``$t0`` and
# ``$t1`` rather than on the stack.
ARGUMENT_REGISTERS = (4, 5, 6, 7, 8, 9)

# The registers the o32 convention lets a callee change: the two
# ``$v``, the four ``$a``, the eight ``$t``, the two ``$t8``/``$t9`` and
# the link register.  The ``$s`` registers are saved by the callee, and
# the engine keeps the name of the source file in one of them.
VOLATILE_REGISTERS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                       24, 25, 31)

# The loads that write their destination register.
LOADS = frozenset({OP_LB, OP_LBU, OP_LH, OP_LHU, OP_LW, OP_LQ, OP_LD,
                   OP_LWC1, OP_LDC1, OP_LWU})

# The suffix a source file of the game carries.
SOURCE_SUFFIXES = ("c", "cpp", "cxx", "cc", "h", "hh", "hpp", "hxx",
                   "inl", "inc")
# A file name, alone or under a path: "map.cpp", "ui/hud/loaders.cpp".
SOURCE_RE = re.compile(
    r"\A(?:[A-Za-z]:)?(?:[^\s]*[/\\])?[\w.+-]*\.(?:%s)\Z"
    % "|".join(SOURCE_SUFFIXES))

# The highest line number a source file of the game can carry.
MAXIMUM_LINE = 100000


def escape(text: str) -> str:
    """A string, with the characters that would break the table escaped."""
    return (text.replace("\\", "\\\\").replace("\t", "\\t")
            .replace("\r", "\\r").replace("\n", "\\n"))


class Tracker:
    """The values of the registers, as the code builds them.

    Only the shapes that carry an address are followed.  Every other
    instruction invalidates the register it writes, so a value is never
    claimed when the code does not say what it is.
    """

    def __init__(self) -> None:
        self.registers: list[int | None] = [None] * 32
        self.registers[0] = 0

    def value(self, register: int) -> int | None:
        return self.registers[register]

    def _write(self, register: int, value: int | None) -> None:
        if register:
            self.registers[register] = value

    def forget(self, registers: Iterable[int]) -> None:
        for register in registers:
            self.registers[register] = None

    def step(self, word: int, address: int,
             data: list[tuple[int, bytes]] | None = None,
             strings: StringTable | None = None) -> None:
        """Apply one instruction to the state."""
        opcode = word >> 26
        rs = (word >> 21) & 0x1F
        rt = (word >> 16) & 0x1F
        rd = (word >> 11) & 0x1F
        uimm = word & 0xFFFF
        simm = uimm - 0x10000 if uimm & 0x8000 else uimm

        if opcode == OP_LUI:
            self._write(rt, (uimm << 16) & MASK32)
            return
        if opcode in (OP_ADDI, OP_ADDIU):
            base = self.registers[rs]
            self._write(rt, (base + simm) & MASK32 if base is not None else None)
            return
        if opcode == OP_ORI:
            base = self.registers[rs]
            self._write(rt, (base | uimm) & MASK32 if base is not None else None)
            return
        if opcode in (OP_ANDI, OP_XORI):
            self._write(rt, None)
            return
        if opcode == OP_SLTI or opcode == OP_SLTIU:
            self._write(rt, None)
            return
        if opcode == OP_SPECIAL:
            self._step_special(word, address, rs, rt, rd)
            return
        if opcode == OP_SPECIAL2:
            self._step_special2(word, rs, rt, rd)
            return
        if opcode in LOADS:
            self._step_load(word, rs, rt, simm, data, strings)
            return
        if opcode in (OP_J, OP_JAL):
            self.registers[31] = None
            return
        # everything else writes no general purpose register
        return

    def _step_special(self, word: int, address: int, rs: int, rt: int,
                      rd: int) -> None:
        function = word & 0x3F
        if function in (SPECIAL_JR,):
            return
        if function == SPECIAL_JALR:
            self.registers[31] = None
            return
        if function in (0x0C, 0x0D, SPECIAL_MTHI, SPECIAL_MTLO, 0x18, 0x19,
                        0x1A, 0x1B):
            return                              # traps and the integer unit
        if function in (SPECIAL_MFHI, SPECIAL_MFLO, SPECIAL_SLL, 0x02, 0x03,
                        0x04, 0x06):
            self._write(rd, None)
            return
        left = self.registers[rs]
        right = self.registers[rt]
        if function in (SPECIAL_ADD, SPECIAL_ADDU, SPECIAL_DADD,
                        SPECIAL_DADDU):
            self._write(rd, (left + right) & MASK32
                        if left is not None and right is not None else None)
            return
        if function in (SPECIAL_SUB, SPECIAL_SUBU, SPECIAL_DSUB,
                        SPECIAL_DSUBU):
            self._write(rd, (left - right) & MASK32
                        if left is not None and right is not None else None)
            return
        if function == SPECIAL_AND:
            self._write(rd, (left & right) & MASK32
                        if left is not None and right is not None else None)
            return
        if function == SPECIAL_OR:
            self._write(rd, (left | right) & MASK32
                        if left is not None and right is not None else None)
            return
        if function == SPECIAL_XOR:
            self._write(rd, (left ^ right) & MASK32
                        if left is not None and right is not None else None)
            return
        if function == SPECIAL_NOR:
            self._write(rd, ~(left | right) & MASK32
                        if left is not None and right is not None else None)
            return
        if function in (SPECIAL_SLT, SPECIAL_SLTU):
            self._write(rd, None)
            return
        self._write(rd, None)

    def _step_special2(self, word: int, rs: int, rt: int, rd: int) -> None:
        function = word & 0x3F
        if function == SPECIAL2_MUL:
            left = self.registers[rs]
            right = self.registers[rt]
            self._write(rd, (left * right) & MASK32
                        if left is not None and right is not None else None)
            return
        if function in (SPECIAL2_MADD, SPECIAL2_MADDU):
            return
        self._write(rd, None)

    def _step_load(self, word: int, rs: int, rt: int, simm: int,
                   data: list[tuple[int, bytes]] | None,
                   strings: StringTable | None) -> None:
        """A load writes its destination register.

        A load that reads a pointer of the data is followed once: the game
        keeps some of its messages in a table of pointers.
        """
        base = self.registers[rs]
        if base is None or data is None or strings is None:
            self._write(rt, None)
            return
        address = (base + simm) & MASK32
        pointer = read_word(data, address)
        if pointer is not None and strings.at(pointer) is not None:
            self._write(rt, pointer)
            return
        self._write(rt, None)


def read_word(data: list[tuple[int, bytes]], address: int) -> int | None:
    """The 32 bit word written at an address, if there is one."""
    for base, blob in data:
        offset = address - base
        if 0 <= offset and offset + 4 <= len(blob):
            return int.from_bytes(blob[offset:offset + 4], "little")
    return None


@dataclass(frozen=True)
class Call:
    """A call the code makes, with the arguments it passes."""
    address: int
    target: int
    arguments: dict[int, int]


def calls(elf: MipsElf, data: list[tuple[int, bytes]],
          strings: StringTable, clobber: bool = True) -> Iterator[Call]:
    """The calls the program makes, with the arguments they pass.

    The MIPS has a **delay slot**: the instruction that follows a branch
    always runs, and it runs *before* the branch is taken.  The reader
    therefore applies the instruction of the slot before it reads the
    arguments of the call.
    """
    tracker = Tracker()
    for base, blob in zip(*text_code(elf)):
        offset = 0
        limit = len(blob) - 3
        while offset <= limit:
            address = base + offset
            word = struct.unpack_from("<I", blob, offset)[0]
            opcode = word >> 26
            if opcode == OP_JAL:
                target = (address + 4) & 0xF0000000 | (word & 0x03FFFFFF) << 2
                # the delay slot runs before the call
                if offset + 4 <= limit:
                    tracker.step(struct.unpack_from("<I", blob, offset + 4)[0],
                                 address + 4, data, strings)
                arguments = {register: tracker.value(register)
                             for register in ARGUMENT_REGISTERS}
                yield Call(address, target, arguments)
                if clobber:
                    tracker.forget(VOLATILE_REGISTERS)
                offset += 8
                continue
            tracker.step(word, address, data, strings)
            offset += 4


@dataclass(frozen=True)
class Assert:
    """An assert site, and the triplet it carries."""
    site: int
    target: int
    file: str
    file_address: int
    line: int
    condition: str
    file_register: int
    line_register: int


def classify(call: Call, strings: StringTable,
             ranges: Sequence[tuple[int, int]]) -> Assert | None:
    """The triplet a call carries, if it carries one.

    The file is the argument that holds the name of a source file, and the
    line is the argument beside it that holds a number small enough to be
    a line.  A pointer is never a line: the address of the data of the
    program is never small.
    """
    texts: dict[int, str] = {}
    addresses: dict[int, int] = {}
    for register in ARGUMENT_REGISTERS:
        value = call.arguments.get(register)
        if value is None:
            continue
        text = strings.at(value)
        if text is not None:
            texts[register] = text
            addresses[register] = value

    files = [register for register, text in sorted(texts.items())
             if SOURCE_RE.fullmatch(text)]
    if not files:
        return None

    for file_register in files:
        line_register = _line_of(call, file_register, ranges)
        if line_register is None:
            continue
        condition = _condition_of(texts, file_register)
        return Assert(call.address, call.target, texts[file_register],
                      addresses[file_register],
                      call.arguments[line_register], condition,
                      file_register, line_register)
    return None


def _line_of(call: Call, file_register: int,
             ranges: Sequence[tuple[int, int]]) -> int | None:
    """The register that holds the line beside the name of the file.

    The line follows the file in the order of the arguments: the engine's
    own wrapper takes them as ``(size, flag, file, line)`` — the file is
    the third argument and the line the fourth — and the SDK's assert
    takes them as ``(condition, file, line)``, or as five arguments when
    the condition is there too, the line then being the sixth.
    """
    index = ARGUMENT_REGISTERS.index(file_register)
    candidates = []
    for offset in (1, -1):
        place = index + offset
        if 0 <= place < len(ARGUMENT_REGISTERS):
            candidates.append(ARGUMENT_REGISTERS[place])
    for register in candidates:
        value = call.arguments.get(register)
        if value is None or value <= 0 or value > MAXIMUM_LINE:
            continue
        if any(low <= value < high for low, high in ranges):
            continue                       # a pointer, not a line
        return register
    return None


def _condition_of(texts: dict[int, str], file_register: int) -> str:
    """The text of the condition, when the call carries one."""
    for register in sorted(texts):
        if register == file_register:
            continue
        text = texts[register]
        if "%" in text:
            continue                       # a format is not a condition
        return text
    return ""


class Owners:
    """The function that holds an address."""

    def __init__(self, elf: MipsElf):
        self.elf = elf
        self.starts: list[int] = []
        self.cache: dict[int, set[int]] = {}

    def build(self) -> None:
        catalogue = build_catalogue(self.elf)
        entries = {address for address, _kind, _evidence in catalogue}
        for address, _kind, _evidence in catalogue:
            end, _why, body = function_body(self.elf, address, entries=entries,
                                            full=True)
            if end <= address:
                continue
            self.starts.append(address)
            for at in body:
                self.cache[at] = address
        self.starts.sort()

    def of(self, address: int) -> int | None:
        """The function that holds an address, or None."""
        return self.cache.get(address)


def data_of(elf: MipsElf) -> list[tuple[int, bytes]]:
    """The sections that hold the data, with the address they sit at."""
    return [(section.addr, elf.section_data(section))
            for section in elf.data_sections()]


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("elf", help="path to the MIPS ELF")
    parser.add_argument("--program", default="",
                        help="the name of the program, written in the table")
    parser.add_argument("--level", default="-",
                        help="the level the program belongs to, or -")
    parser.add_argument("--out", required=True, help="the file to write")
    parser.add_argument("--append", action="store_true",
                        help="add to the file instead of replacing it")
    parser.add_argument("--keep-arguments", action="store_true",
                        help="do not forget the argument registers after a "
                             "call (the o32 convention says the callee may "
                             "change them)")
    args = parser.parse_args(argv)

    try:
        with open(args.elf, "rb") as handle:
            elf = MipsElf(handle.read(), args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    data = data_of(elf)
    strings = StringTable(data)
    ranges = [(low, low + len(blob)) for low, blob in data]
    for section in elf.code_sections():
        ranges.append((section.addr, section.addr + section.size))

    owners = Owners(elf)
    owners.build()
    print(f"{len(owners.starts)} functions in the catalogue")

    rows = []
    for call in calls(elf, data, strings, clobber=not args.keep_arguments):
        found = classify(call, strings, ranges)
        if found is None:
            continue
        function = owners.of(found.site)
        rows.append((args.program,
                     args.level,
                     f"0x{function:08X}" if function is not None else "",
                     f"0x{found.site:08X}",
                     escape(found.file),
                     str(found.line),
                     escape(found.condition),
                     f"0x{found.target:08X}",
                     f"0x{found.file_address:08X}",
                     f"${found.file_register}",
                     f"${found.line_register}"))
    rows.sort(key=lambda row: (row[0], row[1], row[2], row[3]))

    mode = "a" if args.append else "w"
    with open(args.out, mode, encoding="utf-8", newline="\n") as out:
        if not args.append:
            out.write("program\tlevel\tfunction\tsite\tfile\tline\tcondition\t"
                      "handler\tfile_address\tfile_register\tline_register\n")
        for row in rows:
            out.write("\t".join(row) + "\n")
    print(f"wrote {args.out}: {len(rows)} assert sites "
          f"({sum(1 for row in rows if row[2])} in a function)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
