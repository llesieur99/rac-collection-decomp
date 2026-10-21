"""Compile, link and compare a candidate body with the retail bytes.

The compiler of the retail program is a Linux binary, so it runs in the
container that built it.  The candidate is linked at the retail address with
a minimal script — the callees are placed at their retail addresses, so the
calls resolve the way they do in the game — and the linked code is compared
with the retail bytes.

The tool tries a list of flag sets and reports the first difference of each,
so that the next attempt knows where to look.

    python tools/try_body.py <source.c> <address> --elf work/eboot.elf \\
        --symbol sub_147B0=0x147B0 --symbol sub_14820=0x14820

The toolchain is the one built from the sources of the Cell OS Lv-2
toolchain; see docs/TOOLCHAIN.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# The flag sets to try, in the order they are tried.
#
# -mno-nop-after-bl is the SCE option that shortens the call sequence: the
# SCE backend emits the branch and a second word that restores the TOC, and
# the option drops that second word.  The retail program has both shapes, so
# the game was built with the option on some files and off on others.
FLAG_SETS = [
    ["-O1", "-mno-save-restore-tocbase"],
    ["-O1", "-mno-save-restore-tocbase", "-mno-nop-after-bl"],
    ["-O1", "-mno-nop-after-bl"],
    ["-O2", "-mno-save-restore-tocbase"],
    ["-O2", "-mno-save-restore-tocbase", "-mno-nop-after-bl"],
    ["-O0", "-mno-save-restore-tocbase"],
    ["-O1"],
    ["-O2"],
    ["-Os", "-mno-save-restore-tocbase"],
    ["-O3", "-mno-save-restore-tocbase"],
    ["-O2", "-mno-save-restore-tocbase", "-fno-strict-aliasing"],
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def compile_and_link(source: str, flags: list[str], address: int,
                      symbols: dict[str, int], out_dir: str,
                      image: str, toolchain: str) -> tuple[str | None, str]:
    """Compile and link in the container; return the linked file's path."""
    obj = os.path.join(out_dir, "candidate.o")
    linked = os.path.join(out_dir, "candidate.elf")
    script = os.path.join(out_dir, "link.lds")
    lines = ["SECTIONS", "{", f"  . = {hex(address)};", "  .text : { *(.text) }", "}"]
    for name, value in symbols.items():
        # GCC 4.1 calls an undefined function through a ".sub_" alias.
        lines.insert(2, f"  {name} = {hex(value)};")
        lines.insert(2, f"  .{name} = {hex(value)};")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    prefix = "/usr/local/cell/host-linux/ppu"
    gcc = f"{prefix}/bin/ppu-lv2-gcc"
    ld = f"{prefix}/bin/ppu-lv2-ld"
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{os.path.dirname(source)}:/src:ro",
        "-v", f"{out_dir}:/out",
        "-v", f"{toolchain}:/usr/local/cell",
        image,
        "bash", "-c",
        f"{gcc} -c -nostdinc -fno-builtin {' '.join(flags)} "
        f"-o /out/candidate.o /src/{os.path.basename(source)} && "
        f"{ld} -T /out/link.lds -o /out/candidate.elf /out/candidate.o",
    ]
    result = run(cmd)
    if not os.path.exists(linked):
        return None, (result.stdout + result.stderr).strip()[-300:]
    return linked, ""


def compare(elf: str, obj: str, address: int) -> tuple[int, str]:
    result = run([sys.executable, os.path.join(HERE, "compare_body.py"),
                  "--elf", elf, "--object", obj, "--address", hex(address)])
    return result.returncode, (result.stdout + result.stderr).strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="the candidate's C file")
    parser.add_argument("address", help="the retail address, in hexadecimal")
    parser.add_argument("--elf", required=True, help="the rebuilt retail PPU ELF")
    parser.add_argument("--symbol", action="append", default=[],
                        help="a callee, as NAME=0xADDRESS (repeatable)")
    parser.add_argument("--image", default="ps3gcc-toolchain",
                        help="the container that holds the compiler")
    parser.add_argument("--toolchain", default=r"D:\RAC-COLLECTION\toolchain",
                        help="the directory the toolchain was built in")
    args = parser.parse_args(argv)

    address = int(args.address, 0)
    symbols = {}
    for item in args.symbol:
        name, _, value = item.partition("=")
        symbols[name] = int(value, 0)

    out_dir = tempfile.mkdtemp(prefix="body-")
    try:
        for flags in FLAG_SETS:
            linked, error = compile_and_link(args.source, flags, address, symbols,
                                             out_dir, args.image, args.toolchain)
            label = " ".join(flags)
            if linked is None:
                print(f"{label:46s} failed: {error}")
                continue
            code, text = compare(args.elf, linked, address)
            first = text.splitlines()[0] if text else ""
            print(f"{label:46s} {first}")
            if code == 0:
                print("  MATCH: the candidate reproduces the retail bytes")
                return 0
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
