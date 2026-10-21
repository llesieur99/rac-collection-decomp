"""Find the strings a function touches, by reading the code.

The naming evidence of a function is what the code at its address says about
it: the strings it touches, the functions it calls, the functions that call
it.  The calls are easy — the code names them.  The strings need the
addresses of the data, and the code builds those addresses in two
instructions:

    addis r6, r0, 0x12    the high half of an address
    addi  r6, r6, 0x345   the low half

The tool reads the strings of the data, watches the code build an address,
and reports the function that holds it.

    python tools/strings_xref.py work/decrypted/RC2.elf \\
        --catalogue config/functions.tsv --out work/strings-xref.tsv

Only metadata is written: the address of a function, the address of a string,
and the string itself.  No game bytes.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import os
import struct
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402
from ppu_funcs import function_body  # noqa: E402

# The opcodes the tool reads.
ADDIS = 15      # addis rD, rA, hi      the high half of an address
ADDI = 14       # addi  rD, rA, lo      the low half of an address
ADDIC = 12      # addic rD, rA, lo     the low half, with the carry
ADDICD = 13     # addic. rD, rA, lo    the same, and the condition
ORI = 24        # ori   rA, rA, lo      the low half, unsigned
ORIS = 25       # oris  rA, rA, hi

# The opcodes that read or write memory through a base register and an
# immediate: the immediate is the low half of the address when the base
# holds the high half.
MEMORY = frozenset({
    32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45,
    46, 47, 48, 49, 50, 51, 52, 53, 58, 62,
})

# The shortest run of printable characters that is read as a string.
MINIMUM = 4

# The opcodes that write their destination register.  The value of a
# register is only known until the instruction that writes it.
WRITES_RD = frozenset({7, 8, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29, 31, 58})

PRINTABLE = bytes(range(0x20, 0x7F)) + b"\t\r\n"


def segments(elf: PpuElf) -> tuple[tuple[int, bytes], list[tuple[int, bytes]]]:
    """The code segment of the program, and the sections the strings live in.

    The strings are not in a segment of their own: the SDK puts the read
    only data in the segment of the code, and the writable data in the other
    one.  What tells them from the code is the section table: a section that
    is allocated but **not** executable holds data, never instructions.

    The section names are encrypted in the container, but their flags are
    not, and the flags are enough.
    """
    code = None
    for ph in elf.program_headers():
        if not ph.is_load or not ph.filesz:
            continue
        if ph.flags & 0x4:
            blob = elf.data[ph.offset:ph.offset + ph.filesz]
            if code is None or ph.filesz > len(code[1]):
                code = (ph.vaddr, blob)
    if code is None:
        raise ElfError("no executable segment found")

    data = []
    for section in elf.sections():
        if section.type != 1 or not section.size:
            continue
        if not section.flags & 0x2 or section.flags & 0x4:
            continue  # not allocated, or executable: that is code
        blob = elf.data[section.offset:section.offset + section.size]
        data.append((section.addr, blob))
    return code, data


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
                    at += 1
        self.runs.sort()
        self.starts = [start for start, _end, _text in self.runs]

    def at(self, address: int) -> str | None:
        """The string that starts at an address, if any.

        The text is the one that **starts at the address**, not the one of the
        whole printable run: the game keeps its messages in records whose
        first byte is a tag, and the code points at the text that follows
        the tag.  Returning the whole run put a stray character at the head
        of 16 % of the references.
        """
        index = bisect.bisect_right(self.starts, address) - 1
        if index < 0:
            return None
        start, end, text = self.runs[index]
        if not start <= address < end:
            return None
        return text[address - start:]

    def __len__(self) -> int:
        return len(self.runs)


def read_pointer(data: list[tuple[int, bytes]], address: int, width: int) -> int | None:
    """The pointer written at an address, if there is one."""
    for base, blob in data:
        offset = address - base
        if 0 <= offset and offset + width <= len(blob):
            return int.from_bytes(blob[offset:offset + width], "big")
    return None


def addresses(code: tuple[int, bytes],
              strings: StringTable,
              data: list[tuple[int, bytes]]) -> dict[int, list[tuple[int, str]]]:
    """The addresses of strings that the code builds, with the instruction.

    Only the pairs that make a full address are read: a high half that is
    followed, within the window, by the low half of the same register.

    The engine's messages are not always pointed at directly: the game keeps
    them in a table of pointers, and the code points at the table.  An
    address that lands on a pointer of the table is followed once more.
    """
    base, blob = code
    found: dict[int, list[tuple[int, str]]] = {}
    # The value of the registers that hold the high half of an address.
    # A register keeps its value until an instruction writes it, and the
    # compiler reuses the registers freely: the two halves of an address
    # are often more than a dozen instructions apart.
    high: dict[int, tuple[int, int]] = {}  # register -> (position, value)

    def resolve(address: int) -> list[tuple[int, str]]:
        """The string at an address, directly or through a pointer."""
        text = strings.at(address)
        if text is not None:
            return [(address, text)]
        for width in (8, 4):
            pointer = read_pointer(data, address, width)
            if pointer is None:
                continue
            text = strings.at(pointer)
            if text is not None:
                return [(pointer, text)]
        return []

    for offset in range(0, len(blob) - 3, 4):
        word = struct.unpack_from(">I", blob, offset)[0]
        opcode = word >> 26
        rD = (word >> 21) & 0x1F
        rA = (word >> 16) & 0x1F
        position = offset // 4

        # the value of the base register, before the instruction overwrites it
        held = high.get(rA)
        if opcode in WRITES_RD:
            high.pop(rD, None)

        if opcode == ADDIS and rA == 0:
            # the high half of an address: lis rD, hi
            high[rD] = (position, (word & 0xFFFF) << 16)
            continue
        if opcode == ORIS:
            # oris rA, rA, hi : the high half of a 64 bit address
            if held is not None:
                high[rD] = (position, held[1] | ((word & 0xFFFF) << 16))
            continue
        if held is None:
            continue
        value = held[1]
        if opcode in (ADDI, ADDIC, ADDICD):
            low = word & 0xFFFF
            if low & 0x8000:
                low -= 0x10000
            entries = resolve(value + low)
            if entries:
                found.setdefault(base + offset, []).extend(entries)
            continue
        if opcode == ORI:
            entries = resolve(value | (word & 0xFFFF))
            if entries:
                found.setdefault(base + offset, []).extend(entries)
            continue
        if opcode in MEMORY:
            # the high half of the address is in the base register, and the
            # immediate is the low half: lbz r3, -0x11C(r3)
            low = word & 0xFFFF
            if low & 0x8000:
                low -= 0x10000
            entries = resolve(value + low)
            if entries:
                found.setdefault(base + offset, []).extend(entries)
    return found


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("elf", help="path to the rebuilt PPU ELF")
    parser.add_argument("--catalogue", default=None,
                        help="config/functions.tsv, to name the functions")
    parser.add_argument("--program", default=None,
                        help="the program of the catalogue to use")
    parser.add_argument("--out", required=True, help="the file to write")
    args = parser.parse_args(argv)

    try:
        with open(args.elf, "rb") as handle:
            elf = PpuElf(handle.read(), args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    code, data = segments(elf)
    strings = StringTable(data)
    found = addresses(code, strings, data)
    print(f"{len(strings)} strings in the data, {len(found)} address references in the code")

    # the functions, to say which function owns the reference
    functions: list[tuple[int, int]] = []
    if args.catalogue:
        with open(args.catalogue, encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                if args.program and row["program"] != args.program:
                    continue
                # Only the confirmed functions own an address: the extent of a
                # candidate is provisional, and a string is attributed to the
                # function that owns the code, not to a guess.
                if row.get("state", "bounded") != "bounded":
                    continue
                functions.append((int(row["address"], 0), int(row["size"])))
        functions.sort()

    owners: dict[int, int] = {}
    if functions:
        # The owner of an instruction is the function whose control flow
        # reaches it: a function whose blocks are scattered — a jump table,
        # a cold block the compiler moved — owns those blocks too, and its
        # extent does not say so.
        entries = {start for start, _size in functions}
        wanted = set(found)
        for start, _size in functions:
            _end, _why, body = function_body(elf, start, entries=entries, full=True)
            for address in body:
                if address in wanted:
                    owners[address] = start
        print(f"{len(owners)} of the references are inside a function")

    rows = []
    for address, entries in sorted(found.items()):
        function = owners.get(address)
        for string_address, text in entries:
            rows.append((args.program or "",
                         f"0x{function:08X}" if function is not None else "",
                         f"0x{string_address:08X}", escape(text)))
    # The csv module, and not a join: a message of the game may hold a
    # double quote, and a table that a quote breaks is a table that lies.
    with open(args.out, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        writer.writerow(["program", "function", "string_address", "string"])
        writer.writerows(rows)
    print(f"wrote {args.out}: {len(rows)} references")
    return 0


def escape(text: str) -> str:
    """A string, with the characters that would break the table escaped."""
    return (text.replace("\\", "\\\\").replace("\t", "\\t")
            .replace("\r", "\\r").replace("\n", "\\n"))


if __name__ == "__main__":
    raise SystemExit(main())
