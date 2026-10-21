"""Write the table of a PS2 program: its functions, the calls and the strings.

The table is the input of the correspondence between the PS2 and the PS3:
it says, for every function of the program, how big it is, which functions
it calls, and which strings of the data it touches.

    python tools/mips_program.py <overlay.elf> --program LVL00 \\
        --out work/ps2/LVL00.funcs.tsv

The table is metadata: addresses, sizes and the addresses of the calls and
of the strings.  No game byte is written.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mips_elf import ElfError, MipsElf  # noqa: E402
from mips_funcs import build_catalogue, function_body  # noqa: E402
from mips_strings_xref import call_targets_of  # noqa: E402


def program_table(elf: MipsElf) -> list[tuple[int, int, list[int]]]:
    """The functions of the program, with the addresses they call.

    The functions come from the prologue scan and the call scan; the walk
    of the control flow says which calls belong to which function.
    """
    catalogue = build_catalogue(elf)
    entries = {address for address, _kind, _evidence in catalogue}
    out = []
    for address, _kind, _evidence in catalogue:
        end, _why, body = function_body(elf, address, entries=entries, full=True)
        if end <= address:
            continue
        out.append((address, end - address, call_targets_of(elf, body)))
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

    rows = program_table(elf)
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("program\tfunction\tsize\tcalls\n")
        for address, size, calls in rows:
            targets = " ".join(f"0x{target:08X}" for target in calls)
            out.write(f"{args.program}\t0x{address:08X}\t{size}\t{targets}\n")
    print(f"wrote {args.out}: {len(rows)} functions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
