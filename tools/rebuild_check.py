"""Check that a rebuilt PPU ELF is internally consistent.

A rebuild can have the right size and still be misaligned.  The check is
structural and does not read the code:

* the ELF header must agree with the program headers and the section headers;
* the section header table must end exactly at the size of the ELF;
* every allocated section, except the ones that are not in the file, must lie
  inside a segment;
* the module names in the string table must be readable.

    python tools/rebuild_check.py <file.self> [<file.self> ...]
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from self_header import Self, SelfError  # noqa: E402
from compiler_stamp import module_names  # noqa: E402
from payload_state import ENCRYPTED, entropy, segments_of  # noqa: E402

SHF_ALLOC = 0x2
SHT_NOBITS = 0x8


def check(path: str) -> list[str]:
    problems: list[str] = []
    with open(path, "rb") as handle:
        raw = handle.read()
    container = Self(raw, path)
    elf = container.rebuild_elf()

    # is the payload in the clear?  the section names are only readable
    # when it is.
    readable_names = True
    for ptype, off, vaddr, size in segments_of(elf):
        if ptype == 1 and vaddr and size:
            if entropy(elf[off:off + min(size, 65536)]) >= ENCRYPTED:
                readable_names = False
            break

    if len(elf) != container.elf_size:
        problems.append(f"the rebuild is {len(elf)} bytes, the header declares "
                        f"{container.elf_size}")

    entry, phoff, shoff = struct.unpack_from(">3Q", elf, 0x18)
    phentsize, phnum, shentsize, shnum, shstrndx = struct.unpack_from(">5H", elf, 0x36)

    if phoff + phnum * phentsize > len(elf):
        problems.append("the program header table is outside the image")
    if shoff + shnum * shentsize > len(elf):
        problems.append("the section header table is outside the image")
    elif shnum and shoff + shnum * shentsize != len(elf):
        problems.append(f"the section header table ends at "
                        f"0x{shoff + shnum * shentsize:X}, the image ends at "
                        f"0x{len(elf):X}")

    # the segments, as the file lays them out
    spans: list[tuple[int, int]] = []
    for i in range(phnum):
        o = phoff + i * phentsize
        ptype = struct.unpack_from(">I", elf, o)[0]
        off = struct.unpack_from(">Q", elf, o + 8)[0]
        filesz = struct.unpack_from(">Q", elf, o + 8 + 24)[0]
        if ptype == 1 and filesz:
            spans.append((off, off + filesz))
    if not spans:
        problems.append("the image has no loaded segment")

    # the section table, and the sections that must live in a segment
    if shnum == 0:
        return problems
    if shstrndx < shnum:
        o = shoff + shstrndx * shentsize
        strtab_off = struct.unpack_from(">Q", elf, o + 24)[0]
        strtab_size = struct.unpack_from(">Q", elf, o + 32)[0]
        if strtab_off + strtab_size > len(elf):
            problems.append("the string table is outside the image")
    else:
        problems.append("the string table index is out of range")
        strtab_off = 0

    outside = 0
    for i in range(shnum):
        o = shoff + i * shentsize
        sh_type = struct.unpack_from(">I", elf, o + 4)[0]
        sh_flags = struct.unpack_from(">Q", elf, o + 8)[0]
        sh_offset = struct.unpack_from(">Q", elf, o + 24)[0]
        sh_size = struct.unpack_from(">Q", elf, o + 32)[0]
        if not (sh_flags & SHF_ALLOC) or sh_type == SHT_NOBITS or not sh_size:
            continue
        if not any(start <= sh_offset and sh_offset + sh_size <= end
                   for start, end in spans):
            outside += 1
            if outside <= 3:
                problems.append(f"section {i} lies outside every segment "
                                f"(0x{sh_offset:X}, {sh_size} bytes)")
    if outside > 3:
        problems.append(f"{outside} sections in total lie outside every segment")

    # the module names must be readable
    printable = 0
    for i in range(shnum):
        o = shoff + i * shentsize
        sh_name = struct.unpack_from(">I", elf, o)[0]
        start = strtab_off + sh_name
        if start >= len(elf):
            continue
        end = elf.find(b"\x00", start)
        name = elf[start:end]
        if name and all(32 <= b < 127 for b in name):
            printable += 1
    # The string table of the sections is part of the encrypted metadata
    # headers, so its names are only readable once the payload is in the
    # clear.  The SCE module names live in the tail of the image, just
    # before the section header table, and they are always readable.
    modules = module_names(elf)
    if not modules:
        problems.append("the SCE module names are not readable")
    if readable_names and printable < 2:
        problems.append("the section names are not readable, although the "
                        "payload is in the clear")

    return problems


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("executables", nargs="+",
                        help="paths to the SELF containers")
    args = parser.parse_args(argv)
    failed = 0
    for path in args.executables:
        try:
            problems = check(path)
        except (OSError, SelfError) as exc:
            print(f"{os.path.basename(path):24s} error: {exc}")
            failed += 1
            continue
        if problems:
            failed += 1
            print(f"{os.path.basename(path):24s} FAILED")
            for problem in problems:
                print(f"    {problem}")
        else:
            print(f"{os.path.basename(path):24s} consistent")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
