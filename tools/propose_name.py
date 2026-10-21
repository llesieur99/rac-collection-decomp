"""Propose a name on the other builds, with the measured correspondence.

A name is proved on one build by the body gate.  The other builds of the
same game, and the other games of the series, hold the same function at
another address.  The correspondence table says where, and how sure the
table is.

    python tools/propose_name.py --program collection-RC2 --address 0x00123456

The tool prints the counterpart of the function in every build the table
knows, with the share of the instructions that are the same — the measure of
how much of the function the rebuild left untouched.

With ``--name``, the name is written in the catalogue as a **proposal**: the
state becomes ``proposed`` and the evidence says where the proposal comes
from.  A proposal is not a fact: only the body gate makes a name a fact.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Sequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_correspondence(path: str) -> dict[tuple[str, int], list[dict]]:
    """The table, keyed by the build and the address of the first side."""
    out: dict[tuple[str, int], list[dict]] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            key = (row["build_a"], int(row["address_a"], 16))
            out.setdefault(key, []).append({
                "build_b": row["build_b"],
                "address_b": int(row["address_b"], 16),
                "size_b": int(row["size_b"]),
                "method": row["method"],
                "identical": float(row["identical"]),
            })
    return out


def read_catalogue(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_catalogue(path: str, rows: list[dict]) -> None:
    columns = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(str(row.get(column, "")) for column in columns) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalogue", default=os.path.join(ROOT, "config", "functions.tsv"))
    parser.add_argument("--correspondence",
                        default=os.path.join(ROOT, "config", "correspondence.tsv"))
    parser.add_argument("--program", required=True, help="the build of the function")
    parser.add_argument("--address", required=True, help="the address of the function")
    parser.add_argument("--name", default=None, help="the name to propose")
    parser.add_argument("--write", action="store_true",
                        help="write the proposal in the catalogue")
    args = parser.parse_args(argv)

    address = int(args.address, 0)
    table = read_correspondence(args.correspondence)
    counterparts = table.get((args.program, address))
    if not counterparts:
        print(f"no counterpart for {args.program} 0x{address:08X} in the table")
        return 1

    print(f"{args.program} 0x{address:08X}")
    for entry in counterparts:
        print(f"  -> {entry['build_b']:20s} 0x{entry['address_b']:08X} "
              f"size {entry['size_b']:6d}  {entry['identical']:5.1f}% of the "
              f"instructions are the same  ({entry['method']})")

    if not args.name:
        return 0

    rows = read_catalogue(args.catalogue)
    for row in rows:
        if row["program"] == args.program and int(row["address"], 0) == address:
            print(f"the catalogue says: {row['name']} ({row['state']})")
            if args.write:
                row["name"] = args.name
                row["state"] = "proposed"
                where = ", ".join(f"{entry['build_b']} 0x{entry['address_b']:08X}"
                                  for entry in counterparts)
                row["evidence"] = (f"{row['evidence']};proposed-from:"
                                    f"{args.program} 0x{address:08X} -> {where}")
                write_catalogue(args.catalogue, rows)
                print("the proposal was written in the catalogue")
            return 0
    print("the function is not in the catalogue")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
