"""Merge the naming evidence into the catalogue of the functions.

The catalogue says where the functions are.  The evidence says what the code
at those addresses says about them: the strings it touches, the functions it
calls, the functions that call it, the data it reads.

This tool merges the two and reports the coverage, which is the third
opinion on the boundaries: the addresses that the prologue scan, the call scan
and the disassembler all agree on are the ones that can be worked on.

    python tools/evidence.py --catalogue config/functions.tsv \\
        --ghidra <evidence.tsv> --out config/evidence.tsv

The evidence is research metadata: addresses, names and strings.  It carries
no game bytes.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Sequence


def read_catalogue(path: str) -> dict[tuple[str, int], dict]:
    """The catalogue, keyed by program and address."""
    out: dict[tuple[str, int], dict] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            address = int(row["address"], 0)
            out[(row["program"], address)] = {
                "size": int(row["size"]),
                "name": row.get("name", ""),
                "state": row.get("state", ""),
                "evidence": row.get("evidence", ""),
            }
    return out


def read_ghidra(path: str) -> dict[int, dict]:
    """The exported evidence, keyed by address."""
    out: dict[int, dict] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            address = int(row["address"], 16)
            out[address] = {
                "size": int(row["size"]),
                "strings": row.get("strings", ""),
                "calls": row.get("calls", ""),
                "callers": row.get("callers", ""),
                "data": row.get("data", ""),
            }
    return out


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalogue", required=True, help="config/functions.tsv")
    parser.add_argument("--ghidra", required=True, help="the exported evidence")
    parser.add_argument("--out", required=True, help="the file to write")
    args = parser.parse_args(argv)

    catalogue = read_catalogue(args.catalogue)
    evidence = read_ghidra(args.ghidra)

    # the addresses of the catalogue, per program, to match the evidence
    by_program: dict[str, list[int]] = {}
    for (program, address) in catalogue:
        by_program.setdefault(program, []).append(address)

    rows = []
    matched = 0
    with_strings = 0
    for (program, address), entry in sorted(catalogue.items()):
        found = evidence.get(address)
        if found:
            matched += 1
            if found["strings"]:
                with_strings += 1
        else:
            found = {"size": entry["size"], "strings": "", "calls": "",
                     "callers": "", "data": ""}
        rows.append((program, address, entry["size"], entry["name"],
                     entry["state"], found["strings"], found["calls"],
                     found["callers"], found["data"]))

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("program\taddress\tsize\tname\tstate\tstrings\tcalls\tcallers\tdata\n")
        for row in rows:
            out.write("\t".join(str(value) for value in row) + "\n")

    total = len(catalogue)
    print(f"{total} functions in the catalogue")
    print(f"{matched} of them the analysis also found ({100.0 * matched / max(total, 1):.1f}%)")
    print(f"{with_strings} of them touch a string")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
