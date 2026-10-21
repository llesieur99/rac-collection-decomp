"""Find the strings a PS2 function touches, by reading the MIPS code.

The naming evidence of a function is what the code at its address says about
it: the strings it touches, the functions it calls, the functions that call
it.  The calls are easy — the code names them.  The strings need the
addresses of the data, and the code builds those addresses in two
instructions:

    lui   $at, %hi(str)     the high half of an address
    addiu $v0, $at, %lo(str)  the low half

The tool reads the strings of the data, watches the code build an address,
and reports the function that holds it.

    python tools/mips_strings_xref.py <overlay.elf> \\
        --program LVL00 --out work/ps2/LVL00-strings.tsv

The MIPS differs from the PS3 in three ways that the tool has to take into
account:

* the address is built by ``lui``/``addiu`` (or ``lui``/``ori``), not by
  ``lis``/``addi``;
* the load and the store take the low half of the address as their offset
  (``lw $v0, %lo(str)($v0)``), so the address is complete even when the
  code never adds the two halves;
* the strings of a game live in the ``.data`` of the *overlay* that carries
  the code, and the same function sits at a different address in every
  overlay, so the tables are per program and never merged.

Only metadata is written: the address of a function, the address of a
string, and the string itself.  No game bytes.
"""

from __future__ import annotations

import argparse
import bisect
import os
import struct
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mips_elf import ElfError, MipsElf  # noqa: E402
from mips_funcs import (OP_ADDI, OP_ADDIU, OP_ANDI, OP_JAL, OP_LB,  # noqa: E402
                        OP_LBU, OP_LDC1, OP_LD, OP_LH, OP_LHU, OP_LQ, OP_LW,
                        OP_LWC1, OP_ORI, OP_SB, OP_SD, OP_SH, OP_SQ, OP_SW,
                        OP_SWC1, OP_XORI, OP_LUI, OP_SPECIAL,
                        build_catalogue, function_body, text_code)
from mips_funcs import _word_at  # noqa: E402

# The opcodes that write their destination register.  The value of a
# register is only known until the instruction that writes it.
WRITES_RT = frozenset({
    OP_ADDI, OP_ADDIU, OP_ANDI, OP_ORI, OP_XORI, OP_LUI,
    OP_LB, OP_LBU, OP_LH, OP_LHU, OP_LW, OP_LQ, OP_LD, OP_LWC1, OP_LDC1,
})

# The opcodes that read or write memory through a base register and an
# immediate: the immediate is the low half of the address when the base
# holds the high half.
MEMORY = frozenset({
    OP_LB, OP_LBU, OP_LH, OP_LHU, OP_LW, OP_LQ, OP_LD, OP_LWC1, OP_LDC1,
    OP_SB, OP_SH, OP_SW, OP_SQ, OP_SD, OP_SWC1,
})

# The shortest run of printable characters that is read as a string.
MINIMUM = 4

PRINTABLE = bytes(range(0x20, 0x7F)) + b"\t\r\n"


class StringTable:
    """The strings of the data, and the addresses they sit at."""

    def __init__(self, data: list[tuple[int, bytes]]):
        self.runs: list[tuple[int, int, str]] = []
        for base, blob in data:
            at = 0
            while at < len(blob):
                if blob[at] in PRINTABLE:
                    end = at
                    while end < len(blob) and blob[end] in PRINTABLE:
                        end += 1
                    if end - at >= MINIMUM and end < len(blob) and blob[end] == 0:
                        text = blob[at:end].decode("ascii", "replace")
                        if text.strip():
                            start = base + at
                            # A string of Pascal carries its length in the
                            # first byte: the game keeps its messages that way.
                            if len(text) - 1 == ord(text[0]):
                                start += 1
                                text = text[1:]
                            self.runs.append((start, base + end, text))
                        at = end
                    else:
                        at = end
                else:
                    at += 1
        self.runs.sort()
        self.starts = [start for start, _end, _text in self.runs]

    def at(self, address: int) -> str | None:
        """The string that holds an address, if any."""
        index = bisect.bisect_right(self.starts, address) - 1
        if index < 0:
            return None
        start, end, text = self.runs[index]
        if start <= address < end:
            return text
        return None

    def __len__(self) -> int:
        return len(self.runs)


def data_of(elf: MipsElf) -> list[tuple[int, bytes]]:
    """The sections that hold the data, with the address they sit at."""
    out = []
    for section in elf.data_sections():
        out.append((section.addr, elf.section_data(section)))
    return out


def read_pointer(data: list[tuple[int, bytes]], address: int, width: int) -> int | None:
    """The pointer written at an address, if there is one."""
    for base, blob in data:
        offset = address - base
        if 0 <= offset and offset + width <= len(blob):
            return int.from_bytes(blob[offset:offset + width], "little")
    return None


def addresses(code: list[tuple[int, bytes]],
              strings: StringTable,
              data: list[tuple[int, bytes]]) -> dict[int, list[tuple[int, str]]]:
    """The addresses of strings that the code builds, with the instruction.

    Only the pairs that make a full address are read: a high half that is
    followed, within the window, by the low half of the same register.

    The engine's messages are not always pointed at directly: the game keeps
    them in a table of pointers, and the code points at the table.  An
    address that lands on a pointer of the table is followed once more.
    """
    found: dict[int, list[tuple[int, str]]] = {}
    # The value of the registers that hold an address.  A register keeps its
    # value until an instruction writes it, and the compiler reuses the
    # registers freely: the two halves of an address are often more than a
    # dozen instructions apart.
    known: dict[int, int] = {}

    def resolve(address: int) -> list[tuple[int, str]]:
        """The string at an address, directly or through a pointer."""
        text = strings.at(address)
        if text is not None:
            return [(address, text)]
        for width in (4, 8):
            pointer = read_pointer(data, address, width)
            if pointer is None:
                continue
            text = strings.at(pointer)
            if text is not None:
                return [(pointer, text)]
        return []

    for base, blob in code:
        for offset in range(0, len(blob) - 3, 4):
            word = struct.unpack_from("<I", blob, offset)[0]
            opcode = word >> 26
            rs = (word >> 21) & 0x1F
            rt = (word >> 16) & 0x1F
            address = base + offset

            # the value of the base register, before the instruction
            # overwrites it
            held = known.get(rs)
            if opcode in WRITES_RT or opcode == OP_SPECIAL:
                known.pop(rt, None)
            if opcode == OP_SPECIAL:
                # a SPECIAL function that writes its destination register
                function = word & 0x3F
                if function not in (0x00, 0x04, 0x06, 0x07, 0x08, 0x0C, 0x0D,
                                    0x0F, 0x10, 0x11, 0x12, 0x13, 0x18, 0x19,
                                    0x1A, 0x1B):
                    known.pop((word >> 11) & 0x1F, None)

            if opcode == OP_LUI:
                # the high half of an address
                known[rt] = (word & 0xFFFF) << 16
                continue
            if held is None:
                continue
            if opcode in (OP_ADDI, OP_ADDIU):
                low = word & 0xFFFF
                if low & 0x8000:
                    low -= 0x10000
                value = held + low
                known[rt] = value
                entries = resolve(value)
                if entries:
                    found.setdefault(address, []).extend(entries)
                continue
            if opcode == OP_ORI:
                value = held | (word & 0xFFFF)
                known[rt] = value
                entries = resolve(value)
                if entries:
                    found.setdefault(address, []).extend(entries)
                continue
            if opcode in MEMORY:
                # the base holds the high half of the address, and the
                # immediate is the low half: lw $v0, %lo(str)($v0)
                low = word & 0xFFFF
                if low & 0x8000:
                    low -= 0x10000
                entries = resolve(held + low)
                if entries:
                    found.setdefault(address, []).extend(entries)
    return found


def call_targets_of(elf: MipsElf, body: list[int]) -> list[int]:
    """The addresses the instructions of a body call."""
    starts, blobs = text_code(elf)
    out: list[int] = []
    seen: set[int] = set()
    for address in body:
        word = _word_at(starts, blobs, address)
        if word is None or word >> 26 != OP_JAL:
            continue
        target = (address + 4) & 0xF0000000 | (word & 0x03FFFFFF) << 2
        if target in seen:
            continue
        seen.add(target)
        out.append(target)
    return out


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
    parser.add_argument("--out", required=True, help="the file to write")
    args = parser.parse_args(argv)

    try:
        with open(args.elf, "rb") as handle:
            elf = MipsElf(handle.read(), args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    data = data_of(elf)
    strings = StringTable(data)
    code = [(sec.addr, elf.section_data(sec)) for sec in elf.code_sections()]
    found = addresses(code, strings, data)
    print(f"{len(strings)} strings in the data, {len(found)} address references in the code")

    # the functions, to say which function owns the reference
    catalogue = build_catalogue(elf)
    entries = {address for address, _kind, _evidence in catalogue}
    functions = []
    for address, _kind, _evidence in catalogue:
        end, _why, body = function_body(elf, address, entries=entries, full=True)
        if end > address:
            functions.append((address, end, body))
    print(f"{len(functions)} functions in the catalogue")

    owners: dict[int, int] = {}
    for start, _end, body in functions:
        for address in body:
            if address in found:
                owners[address] = start
    print(f"{len(owners)} of the references are inside a function")

    rows = []
    for address, entries_found in sorted(found.items()):
        function = owners.get(address)
        for string_address, text in entries_found:
            rows.append((args.program,
                         f"0x{function:08X}" if function is not None else "",
                         f"0x{string_address:08X}", escape(text)))
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("program\tfunction\tstring_address\tstring\n")
        for row in rows:
            out.write("\t".join(row) + "\n")
    print(f"wrote {args.out}: {len(rows)} references")
    return 0


def escape(text: str) -> str:
    """A string, with the characters that would break the table escaped."""
    return (text.replace("\\", "\\\\").replace("\t", "\\t")
            .replace("\r", "\\r").replace("\n", "\\n"))


if __name__ == "__main__":
    raise SystemExit(main())
