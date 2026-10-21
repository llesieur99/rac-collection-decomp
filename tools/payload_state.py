"""Report whether the payload of a retail PPU executable is in the clear.

A SELF container of a retail PlayStation 3 program keeps two layers of
encryption, and they are easy to confuse:

* the **disc key** protects the files on the disc.  A copy taken with a
  disc key holds the program in the clear;
* the **NPDRM** protects the executable itself.  The header of the
  container, the ELF header, the program headers, the section table and the
  module names stay in the clear, but the **segment payloads -- the code and
  the data -- remain encrypted**.

The second layer is what makes a matching decompilation wait: without the
console's key material, the program can be measured but not read.

The tool measures the entropy of the segments and of the section table, and
says what it found.

    python tools/payload_state.py <file.self> [<file.self> ...]

It needs nothing but the Python standard library.
"""

from __future__ import annotations

import argparse
import collections
import math
import os
import struct
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from self_header import Self, SelfError  # noqa: E402

# Above this entropy, a block of bytes is indistinguishable from random.
ENCRYPTED = 7.90
PLAUSIBLE = 7.00


def entropy(data: bytes) -> float:
    """The Shannon entropy of a block, in bits per byte."""
    if not data:
        return 0.0
    counts = collections.Counter(data)
    n = len(data)
    return -sum((v / n) * math.log2(v / n) for v in counts.values())


def segments_of(elf: bytes) -> list[tuple[int, int, int, int]]:
    """Return ``(type, offset, vaddr, size)`` for the program headers."""
    phoff = struct.unpack_from(">Q", elf, 32)[0]
    phentsize = struct.unpack_from(">H", elf, 54)[0]
    phnum = struct.unpack_from(">H", elf, 56)[0]
    out = []
    for i in range(phnum):
        o = phoff + i * phentsize
        ptype = struct.unpack_from(">I", elf, o)[0]
        off, vaddr, paddr, filesz, memsz = struct.unpack_from(">5Q", elf, o + 8)
        out.append((ptype, off, vaddr, filesz))
    return out


def state_of(path: str) -> int:
    """Print the payload state of one executable; return 0 or 1."""
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw[:4] == b"\x7fELF":
        elf = raw
        container = None
    else:
        container = Self(raw, path)
        elf = container.rebuild_elf()

    print(f"file        : {path}")
    if container is not None:
        print(f"key revision: 0x{container.key_revision:04X}")
        print(f"header size : 0x{container.header_size:X}")
    print(f"elf size    : {len(elf)}")

    shoff = struct.unpack_from(">Q", elf, 40)[0]
    shnum = struct.unpack_from(">H", elf, 60)[0]
    table = elf[shoff:shoff + shnum * 64]
    print(f"section table entropy : {entropy(table):.2f} bits/byte  "
          f"({'in the clear' if entropy(table) < PLAUSIBLE else 'not readable'})")

    encrypted = 0
    readable = 0
    code = 0
    for index, (ptype, off, vaddr, size) in enumerate(segments_of(elf)):
        if not size:
            continue
        sample = elf[off:off + min(size, 65536)]
        value = entropy(sample)
        verdict = "encrypted" if value >= ENCRYPTED else (
            "in the clear" if value < PLAUSIBLE else "unclear")
        # The code and the data are the segments that carry a virtual
        # address; the SCE records of the end of the text stay in the clear
        # whatever the state of the program is.
        is_code = ptype == 1 and vaddr != 0
        if is_code:
            code += 1
            if value >= ENCRYPTED:
                encrypted += 1
            elif value < PLAUSIBLE:
                readable += 1
        print(f"  segment {index}: type=0x{ptype:X} off=0x{off:X} size=0x{size:X} "
              f"vaddr=0x{vaddr:X}  {value:.2f} bits/byte  {verdict}")

    if code and encrypted == code:
        print("payload state: ENCRYPTED (the NPDRM layer is still there)")
        return 1
    if code and readable == code:
        print("payload state: IN THE CLEAR")
        return 0
    print("payload state: UNDETERMINED")
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("executables", nargs="+",
                        help="paths to the SELF containers or to the PPU ELFs")
    args = parser.parse_args(argv)
    status = 0
    for path in args.executables:
        try:
            status |= state_of(path)
        except (OSError, SelfError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            status = 2
        print()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
