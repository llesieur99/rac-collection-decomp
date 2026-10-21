"""Write the table of a PS3 program: its functions and the calls they make.

The table is the twin of the one the PS2 side writes
(``tools/mips_program.py``): it says, for every function of the program,
how big it is and which functions it calls.  The two tables are read
together by ``tools/ps2_ps3_match.py``.

    python tools/ppu_program.py work/decrypted/RC1.elf \\
        --catalogue config/functions.tsv --program RC1 \\
        --out work/ps3/RC1.funcs.tsv

The table is metadata: addresses, sizes and the addresses of the calls.  No
game byte is written.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402
from ppu_funcs import BRANCH_LINK, BRANCH_MASK, branch_target  # noqa: E402
from ppu_funcs import function_body, text_code  # noqa: E402


def read_catalogue(path: str, program: str) -> dict[int, int]:
    """The functions of a program, with their extent, from the catalogue."""
    out: dict[int, int] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["program"] != program:
                continue
            out[int(row["address"], 0)] = int(row["size"])
    return out


def call_targets(elf: PpuElf, body: list[int]) -> list[int]:
    """The addresses the instructions of a body call."""
    base, data = text_code(elf)
    out: list[int] = []
    seen: set[int] = set()
    for address in body:
        offset = address - base
        if offset < 0 or offset + 4 > len(data):
            continue
        word = int.from_bytes(data[offset:offset + 4], "big")
        if word & BRANCH_MASK != BRANCH_LINK:
            continue
        target = branch_target(word, address)
        if target in seen:
            continue
        seen.add(target)
        out.append(target)
    return out


def program_table(elf: PpuElf, catalogue: dict[int, int]) -> list[tuple[int, int, list[int]]]:
    """The functions of the program, with the addresses they call.

    The functions of the *catalogue* are the ones whose boundaries both
    methods agree on, and they are not all of them: the prologue scan sees
    the functions the SDK opens with a frame, and the call scan sees the
    functions that are called.  A function that is only called — a leaf of
    the SDK, a function the compiler gave no frame — is a function all the
    same, and the call graph needs it.  The table therefore holds every
    address either method found, and the size of the catalogue when it
    knows it.
    """
    from ppu_funcs import build_catalogue

    entries = {address for address, _kind, _evidence in build_catalogue(elf)}
    out = []
    for address in sorted(entries):
        end, _why, body = function_body(elf, address, entries=entries, full=True)
        size = catalogue.get(address, max(0, end - address))
        out.append((address, size, call_targets(elf, body)))
    return out


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("elf", help="path to the decrypted PPU ELF")
    parser.add_argument("--catalogue", required=True,
                        help="config/functions.tsv, to name the functions")
    parser.add_argument("--program", required=True,
                        help="the program of the catalogue to use")
    parser.add_argument("--out", required=True, help="the file to write")
    args = parser.parse_args(argv)

    try:
        with open(args.elf, "rb") as handle:
            elf = PpuElf(handle.read(), args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    functions = read_catalogue(args.catalogue, args.program)
    if not functions:
        print(f"error: no function of {args.program} in {args.catalogue}", file=sys.stderr)
        return 1
    rows = program_table(elf, functions)
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("program\tfunction\tsize\tcalls\n")
        for address, size, calls in rows:
            targets = " ".join(f"0x{target:08X}" for target in calls)
            out.write(f"{args.program}\t0x{address:08X}\t{size}\t{targets}\n")
    print(f"wrote {args.out}: {len(rows)} functions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
