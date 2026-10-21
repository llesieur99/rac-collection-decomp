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


def read_ghidra(path: str, program: str) -> dict[tuple[str, int], dict]:
    """The exported evidence, keyed by program and address."""
    out: dict[tuple[str, int], dict] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            address = int(row["address"], 16)
            out[(program, address)] = {
                "size": int(row["size"]),
                "strings": row.get("strings", ""),
                "calls": row.get("calls", ""),
                "callers": row.get("callers", ""),
                "data": row.get("data", ""),
            }
    return out


def read_strings(path: str) -> dict[tuple[str, int], list[str]]:
    """The strings the code touches, keyed by program and function."""
    out: dict[tuple[str, int], list[str]] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            function = row.get("function", "")
            if not function:
                continue
            key = (row.get("program", ""), int(function, 0))
            out.setdefault(key, []).append(row.get("string", ""))
    return out


def read_calls(path: str) -> dict[tuple[str, int], dict]:
    """The call graph of a program, keyed by program and address."""
    out: dict[tuple[str, int], dict] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            address = int(row["address"], 0)
            out[(row.get("program", ""), address)] = {
                "calls": row.get("calls", ""),
                "callers": row.get("callers", ""),
            }
    return out


def read_asserts(path: str) -> dict[tuple[str, int], list[str]]:
    """The assert messages a function carries, keyed by program and function."""
    out: dict[tuple[str, int], list[str]] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            function = row.get("address", "")
            if not function:
                continue
            key = (row.get("program", ""), int(function, 0))
            message = row.get("message", "")
            if not message:
                continue
            out.setdefault(key, []).append(message)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalogue", required=True, help="config/functions.tsv")
    parser.add_argument("--ghidra", action="append", default=[],
                        metavar="PROGRAM=PATH",
                        help="the exported evidence of one program")
    parser.add_argument("--strings", action="append", default=[],
                        help="the strings the code touches, one file per program")
    parser.add_argument("--asserts", default=None,
                        help="the assert messages the code carries")
    parser.add_argument("--calls", action="append", default=[],
                        metavar="PROGRAM=PATH",
                        help="the call graph of a program")
    parser.add_argument("--out", required=True, help="the file to write")
    args = parser.parse_args(argv)

    catalogue = read_catalogue(args.catalogue)
    evidence: dict[tuple[str, int], dict] = {}
    for item in args.ghidra:
        program, _, path = item.partition("=")
        if not path:
            parser.error(f"--ghidra wants PROGRAM=PATH, got {item!r}")
        for key, value in read_ghidra(path, program).items():
            evidence.setdefault(key, value)
    strings: dict[tuple[str, int], list[str]] = {}
    for path in args.strings:
        for key, values in read_strings(path).items():
            strings.setdefault(key, []).extend(values)
    asserts: dict[tuple[str, int], list[str]] = {}
    if args.asserts:
        asserts = read_asserts(args.asserts)
    calls: dict[tuple[str, int], dict] = {}
    for item in args.calls:
        program, _, path = item.partition("=")
        if not path:
            parser.error(f"--calls wants PROGRAM=PATH, got {item!r}")
        for key, value in read_calls(path).items():
            calls.setdefault((program, key[1]), value)

    # the addresses of the catalogue, per program, to match the evidence
    by_program: dict[str, list[int]] = {}
    for (program, address) in catalogue:
        by_program.setdefault(program, []).append(address)

    rows = []
    matched = 0
    with_strings = 0
    with_asserts = 0
    for (program, address), entry in sorted(catalogue.items()):
        found = evidence.get((program, address))
        if found:
            matched += 1
        else:
            found = {"size": entry["size"], "strings": "", "calls": "",
                     "callers": "", "data": ""}
        touched = strings.get((program, address), [])
        text = found["strings"]
        if touched:
            text = " | ".join(part for part in ([text] if text else []) + touched)
            with_strings += 1
        messages = asserts.get((program, address), [])
        if messages:
            with_asserts += 1
        graph = calls.get((program, address))
        rows.append((program, address, entry["size"], entry["name"],
                     entry["state"], text, " | ".join(messages),
                     (graph or found)["calls"], (graph or found)["callers"],
                     found["data"]))

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("program\taddress\tsize\tname\tstate\tstrings\tasserts"
                  "\tcalls\tcallers\tdata\n")
        for row in rows:
            out.write("\t".join(str(value) for value in row) + "\n")

    total = len(catalogue)
    print(f"{total} functions in the catalogue")
    print(f"{matched} of them the analysis also found ({100.0 * matched / max(total, 1):.1f}%)")
    print(f"{with_strings} of them touch a string")
    print(f"{with_asserts} of them carry an assert")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
