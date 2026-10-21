"""Compare the SDK's libgcc code with the copy the retail executable links.

The retail executable links libgcc statically, so the runtime's own code is
in the text segment.  This script takes every function of our build of the
SDK's libgcc, and looks for its bytes in the retail text: a function that is
found is byte-identical to the one the game runs.

It is the cheapest possible qualification of the toolchain: no source has to
be written, and every function that is found is a body the compiler
reproduces exactly.

    python tools/compare_libgcc.py --elf work/eboot.elf
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402

PREFIX = "/usr/local/cell/host-linux/ppu"
OBJDUMP = f"{PREFIX}/bin/ppu-lv2-objdump"

VARIANTS = (
    ("default", "/usr/local/cell/host-linux/ppu/lib/gcc/ppu-lv2/4.1.1/libgcc.a"),
    ("fno-exceptions",
     "/usr/local/cell/host-linux/ppu/lib/gcc/ppu-lv2/4.1.1/fno-exceptions/libgcc.a"),
    ("fno-exceptions/fno-rtti",
     "/usr/local/cell/host-linux/ppu/lib/gcc/ppu-lv2/4.1.1/fno-exceptions/fno-rtti/libgcc.a"),
)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def libgcc_functions(path: str, image: str, toolchain: str) -> dict[str, bytes]:
    """Return ``{name: bytes}`` for the functions of our libgcc build."""
    result = run(["docker", "run", "--rm", "-v", f"{toolchain}:/usr/local/cell",
                  image, "bash", "-c", f"{OBJDUMP} -d {path}"])
    functions: dict[str, bytearray] = {}
    name = None
    for line in result.stdout.splitlines():
        header = re.match(r"^[0-9a-f]+ <([^>]+)>:$", line)
        if header:
            name = header.group(1)
            functions[name] = bytearray()
            continue
        if name is None:
            continue
        parts = line.split("\t")
        if len(parts) >= 3 and re.match(r"^\s*[0-9a-f]+:$", parts[0]):
            for value in parts[1].split():
                if re.fullmatch(r"[0-9a-f]{2}", value):
                    functions[name].append(int(value, 16))
                else:
                    break
    return {k: bytes(v) for k, v in functions.items() if len(v) >= 32}


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--elf", required=True, help="the rebuilt retail PPU ELF")
    parser.add_argument("--image", default="ps3gcc-toolchain",
                        help="the container that holds the compiler")
    parser.add_argument("--toolchain", default=r"D:\RAC-COLLECTION\toolchain",
                        help="the directory the toolchain was built in")
    parser.add_argument("--limit", type=int, default=15,
                        help="how many functions to list per variant")
    args = parser.parse_args(argv)

    try:
        with open(args.elf, "rb") as handle:
            elf = PpuElf(handle.read(), args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    text = None
    for ph in elf.program_headers():
        if ph.is_load and (ph.flags & 0x4) and ph.filesz:
            text = elf.read_vaddr(ph.vaddr, ph.filesz)
            base = ph.vaddr
            break
    if text is None:
        print("error: no code segment", file=sys.stderr)
        return 1

    for label, path in VARIANTS:
        functions = libgcc_functions(path, args.image, args.toolchain)
        found = []
        for name, data in sorted(functions.items()):
            index = text.find(data)
            if index >= 0:
                found.append((name, len(data), base + index))
        print(f"=== {label}: {len(found)} of {len(functions)} functions are "
              f"byte-identical in the retail executable")
        for name, size, address in found[:args.limit]:
            print(f"     {name:32s} {size:5d} bytes  at retail 0x{address:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
