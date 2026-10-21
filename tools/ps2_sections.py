#!/usr/bin/env python3
"""Measure the strings a PS2 *level* program reads.

The boot executable of a PlayStation 2 game holds the engine; the game
code of each level lives in that level's own program, a set of sections
laid out at fixed addresses.  The sibling project dumps them as one file
per section, with a ``manifest.json`` that gives the address of each.

This script reads those sections and does what
``tools/mips_strings_xref.py`` does for an ELF: it finds the strings of
the data, watches the code build their addresses, and says which function
holds each reference.  The functions come from the catalogue of the
sibling project, which gives the address *and the size* of every
function of every level, so the owner of a reference is known exactly.

It writes the two tables the matching tool reads, in the same format:

    <prefix>.strings.tsv   program, function, string_address, string
    <prefix>.funcs.tsv     program, function, size, calls

The sibling projects are only read.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mips_strings_xref import StringTable, addresses  # noqa: E402

# The MIPS instructions that call.
OP_JAL = 0x03


def escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace("\t", "\\t")
                .replace("\r", "\\r").replace("\n", "\\n"))


def read_catalogue(path: Path) -> dict[str, dict]:
    """The catalogue of the sibling project.

    One row per *game* function: the same function, at nineteen or
    twenty-seven addresses, is one function of the game.  The row gives
    the address of the function in every level and its size.
    """
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 6:
                continue
            name, kind, size, _fp, _levels, places = parts[:6]
            rows = []
            for item in places.split(","):
                if ":" not in item:
                    continue
                level, _, address = item.partition(":")
                rows.append((level, int(address, 16)))
            out[name] = {"kind": kind, "size": int(size) if size.isdigit() else 0,
                         "places": rows}
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--levels", required=True,
                        help="the directory that holds the level directories")
    parser.add_argument("--catalogue", required=True,
                        help="the function catalogue of the sibling project")
    parser.add_argument("--prefix", required=True,
                        help="the prefix of the two tables to write")
    parser.add_argument("--program", default="",
                        help="the program name written in the tables")
    args = parser.parse_args(argv)

    catalogue = read_catalogue(Path(args.catalogue))

    # the functions of every level, by address
    by_level: dict[str, dict[int, tuple[str, int]]] = defaultdict(dict)
    for name, row in catalogue.items():
        for level, address in row["places"]:
            by_level[level][address] = (name, row["size"])

    root = Path(args.levels)
    levels = sorted(p for p in root.iterdir() if p.is_dir())

    strings_rows = []
    funcs_rows = []
    total_refs = 0
    total_owned = 0
    for directory in levels:
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        level = f"{manifest['level']:02d}"
        program = args.program or ("LVL" + level)

        data: list[tuple[int, bytes]] = []
        code: list[tuple[int, bytes]] = []
        for section in manifest["sections"]:
            blob = (directory / (section["name"] + ".bin"))
            if not blob.exists():
                continue
            raw = blob.read_bytes()
            if section["name"] == "text":
                code.append((section["address"], raw))
            elif section["type"] == 1:
                data.append((section["address"], raw))
        if not code:
            continue

        table = StringTable(data)
        found = addresses(code, table, data)
        total_refs += sum(len(v) for v in found.values())

        functions = by_level.get(level, {})
        # the owner of a reference: the function whose body holds it
        owners: dict[int, int] = {}
        for address in found:
            best = None
            for start, (_name, size) in functions.items():
                if start <= address < start + max(size, 4):
                    if best is None or start > best:
                        best = start
            if best is not None:
                owners[address] = best
        total_owned += len(owners)

        for address, entries in sorted(found.items()):
            function = owners.get(address)
            for string_address, text in entries:
                strings_rows.append((
                    program,
                    f"0x{function:08X}" if function is not None else "",
                    f"0x{string_address:08X}",
                    escape(text),
                ))

        # the calls of every function, and the call graph
        for start, (name, size) in sorted(functions.items()):
            blob = None
            for base, raw in code:
                if base <= start < base + len(raw):
                    blob = (base, raw)
                    break
            targets = []
            if blob is not None:
                base, raw = blob
                offset = start - base
                end = offset + max(size, 4)
                while offset + 4 <= min(end, len(raw)):
                    word = struct.unpack_from("<I", raw, offset)[0]
                    if word >> 26 == OP_JAL:
                        target = ((start + offset + 4) & 0xF0000000) \
                            | (word & 0x03FFFFFF) << 2
                        if target not in targets:
                            targets.append(target)
                    offset += 4
            funcs_rows.append((program, f"0x{start:08X}", str(size),
                               " ".join(f"0x{t:08X}" for t in targets)))

    out_strings = Path(args.prefix + ".strings.tsv")
    with out_strings.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("program\tfunction\tstring_address\tstring\n")
        for row in strings_rows:
            handle.write("\t".join(row) + "\n")
    out_funcs = Path(args.prefix + ".funcs.tsv")
    with out_funcs.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("program\tfunction\tsize\tcalls\n")
        for row in funcs_rows:
            handle.write("\t".join(row) + "\n")

    print(f"levels: {len(levels)}")
    print(f"string references: {total_refs}, owned by a function: {total_owned}")
    print(f"wrote {out_strings}: {len(strings_rows)} rows")
    print(f"wrote {out_funcs}: {len(funcs_rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
