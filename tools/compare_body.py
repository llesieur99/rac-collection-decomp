"""Compare a compiled function with the retail bytes it should reproduce.

This is the body gate's measurement: the candidate is compiled to an object
file, linked at the retail address, and every byte is compared with the
retail bytes at the measured address.  The first difference is reported, with
its address, so that the next attempt knows where to look.

The tool needs the retail executable and the candidate's linked file; it
publishes neither.

    python tools/compare_body.py --elf work/eboot.elf --object candidate.elf \\
        --address 0x10200
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402


def read_object_sections(path: str) -> dict[str, bytes]:
    """Return the sections of a big-endian ELF file, by name."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:4] != b"\x7fELF":
        raise ElfError("the file is not an ELF")
    if data[5] != 2:
        raise ElfError("the file is not big-endian")
    is64 = data[4] == 2
    if is64:
        e_shoff = struct.unpack_from(">Q", data, 0x28)[0]
        e_shentsize, e_shnum, e_shstrndx = struct.unpack_from(">3H", data, 0x3A)
    else:
        e_shoff = struct.unpack_from(">I", data, 0x20)[0]
        e_shentsize, e_shnum, e_shstrndx = struct.unpack_from(">3H", data, 0x2E)
    raw = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        name_off, sh_type = struct.unpack_from(">II", data, off)
        if is64:
            flags, addr, sh_offset, size = struct.unpack_from(">4Q", data, off + 8)
        else:
            flags, addr, sh_offset, size = struct.unpack_from(">4I", data, off + 8)
        raw.append((name_off, sh_type, addr, sh_offset, size))
    strtab_off = raw[e_shstrndx][3]
    sections = {}
    for name_off, sh_type, addr, sh_offset, size in raw:
        end = data.index(b"\x00", strtab_off + name_off)
        name = data[strtab_off + name_off:end].decode("ascii", "replace")
        if sh_type == 8 or not size:
            continue
        sections[name] = data[sh_offset:sh_offset + size]
    return sections


def compare(retail: bytes, candidate: bytes) -> int:
    """Return the index of the first difference, or -1 when they are equal."""
    limit = min(len(retail), len(candidate))
    for i in range(limit):
        if retail[i] != candidate[i]:
            return i
    if len(retail) != len(candidate):
        return limit
    return -1


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--elf", required=True, help="the rebuilt retail PPU ELF")
    parser.add_argument("--object", required=True,
                        help="the candidate's object or linked file")
    parser.add_argument("--address", required=True, help="the retail address, in hexadecimal")
    parser.add_argument("--section", default=".text", help="the section to compare")
    parser.add_argument("--skip", type=int, default=0,
                        help="skip N bytes at the start of the section")
    args = parser.parse_args(argv)

    address = int(args.address, 16)
    try:
        with open(args.elf, "rb") as handle:
            elf = PpuElf(handle.read(), args.elf)
        sections = read_object_sections(args.object)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.section not in sections:
        print(f"error: the file has no section '{args.section}'", file=sys.stderr)
        return 1
    candidate = sections[args.section][args.skip:]
    if not candidate:
        print("error: the section is empty", file=sys.stderr)
        return 1

    try:
        retail = elf.read_vaddr(address, len(candidate))
    except ElfError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    index = compare(retail, candidate)
    if index < 0:
        print(f"match: {len(candidate)} bytes at 0x{address:X}")
        return 0

    print(f"difference at 0x{address + index:X} (+{index} bytes in)")
    print(f"  retail   : {retail[index:index + 16].hex(' ')}")
    print(f"  candidate: {candidate[index:index + 16].hex(' ')}")
    print(f"  matched  : {index} of {len(candidate)} bytes")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
