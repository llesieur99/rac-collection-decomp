"""Make a copy of a rebuilt ELF whose section names are unique.

A retail PlayStation 3 executable is a SELF container: the string table of
its sections is encrypted, so the names of the sections decode to noise, and
several of them decode to the *same* noise.  A disassembler that creates one
memory block per section refuses the file because of the duplicate names.

This tool writes a copy whose section names are unique and meaningless
(``.sec0``, ``.sec1``, ...).  Nothing else is touched: the program headers,
the section headers, the addresses and the bytes stay exactly as they were,
so the copy is still the program, and it is only a convenience for the
analysis tools.

    python tools/elf_unique_sections.py <in.elf> <out.elf>
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from typing import Sequence

SHT_STRTAB = 3


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="the rebuilt ELF")
    parser.add_argument("target", help="the copy to write")
    args = parser.parse_args(argv)

    with open(args.source, "rb") as handle:
        data = bytearray(handle.read())

    if data[:4] != b"\x7fELF" or data[4] != 2:
        print("error: the file is not a 64-bit ELF", file=sys.stderr)
        return 1

    e_shoff = struct.unpack_from(">Q", data, 0x28)[0]
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from(">3H", data, 0x3A)

    # the string table of the section names
    offset = e_shoff + e_shstrndx * e_shentsize
    strtab_offset = struct.unpack_from(">Q", data, offset + 24)[0]
    strtab_size = struct.unpack_from(">Q", data, offset + 32)[0]

    # the new names, and where they sit in the string table
    names = [f".sec{i}".encode("ascii") for i in range(e_shnum)]
    blob = bytearray()
    offsets = []
    for name in names:
        offsets.append(len(blob))
        blob += name + b"\x00"
    if len(blob) > strtab_size:
        print(f"error: the names need {len(blob)} bytes, the string table has "
              f"{strtab_size}", file=sys.stderr)
        return 1

    data[strtab_offset:strtab_offset + len(blob)] = blob
    for i, name_offset in enumerate(offsets):
        struct.pack_into(">I", data, e_shoff + i * e_shentsize, name_offset)

    with open(args.target, "wb") as handle:
        handle.write(data)
    print(f"wrote {args.target}: {e_shnum} sections, unique names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
