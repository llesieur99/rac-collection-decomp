"""Build the call graph of a program, and the evidence of the assert functions.

This is a private tool of the lot ``wave1-lobby``.  It measures, for every
bounded function of the program:

* the functions it calls (``calls``),
* the functions that call it (``callers``).

The measurement is the same as the one of ``tools/assert_xref.py``: the owner
of an instruction is the function whose control flow reaches it, not the
function whose extent covers it.  The catalogue of the repository is used for
the boundaries, and the entries the prologue and the calls give are added to
them.

The output is metadata: addresses, sizes, names.  No game byte is copied.

    python callgraph.py --elf work/decrypted/RC3.elf \\
        --catalogue config/functions.tsv --program RC3 --out callgraph-RC3.tsv
"""

from __future__ import annotations

import argparse
import csv
import os
import struct
import sys
import time
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import PpuElf  # noqa: E402
from ppu_funcs import text_code, build_catalogue  # noqa: E402
from assert_xref import function_body  # noqa: E402

BRANCH = 18
MASK32 = 0xFFFFFFFF


def branch_target(word: int, address: int) -> int:
    displacement = word & 0x03FFFFFC
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return (address + displacement) & MASK32


def read_catalogue(path: str, program: str) -> list[tuple[int, int]]:
    out = []
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["program"] != program:
                continue
            if row.get("state", "bounded") != "bounded":
                continue
            out.append((int(row["address"], 0), int(row["size"])))
    out.sort()
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", required=True)
    parser.add_argument("--catalogue", required=True)
    parser.add_argument("--program", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    with open(args.elf, "rb") as handle:
        elf = PpuElf(handle.read(), args.elf)
    base, blob = text_code(elf)

    functions = read_catalogue(args.catalogue, args.program)
    starts = sorted({start for start, _s in functions}
                     | {address for address, _kind, _ev in build_catalogue(elf)})
    entries = set(starts)
    print(f"{len(functions)} bounded functions, {len(starts)} entries", flush=True)

    # The body of every entry, and the owner of every address.
    owner: dict[int, int] = {}
    body_of: dict[int, set[int]] = {}
    t0 = time.time()
    for index, start in enumerate(starts):
        body = function_body(elf, start, entries)
        body_of[start] = body
        for address in body:
            owner.setdefault(address, start)
        if index % 2000 == 0:
            print(f"  body {index}/{len(starts)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"bodies done in {time.time()-t0:.0f}s", flush=True)

    # The calls the program makes.
    calls: dict[int, set[int]] = {}
    callers: dict[int, set[int]] = {}
    for offset in range(0, len(blob) - 3, 4):
        word = struct.unpack_from(">I", blob, offset)[0]
        if word >> 26 != BRANCH or not word & 1:
            continue
        address = base + offset
        target = branch_target(word, address)
        site_owner = owner.get(address)
        if site_owner is None:
            continue
        calls.setdefault(site_owner, set()).add(target)
        callers.setdefault(target, set()).add(site_owner)

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("address\tcalls\tcallers\n")
        for start, _size in functions:
            out.write("0x%08X\t%s\t%s\n" % (
                start,
                " ".join("0x%08X" % t for t in sorted(calls.get(start, ()))),
                " ".join("0x%08X" % c for c in sorted(callers.get(start, ())))))
    print(f"wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
