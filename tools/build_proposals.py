"""Build the table of the proposed names of the functions.

Two sources of proposals, both measured, both hypotheses until the body gate
proves them:

* the **PlayStation 2 decompilation**: a function of the PlayStation 3 build
  and a function of the PlayStation 2 build that print the same message are
  the same function, and the PlayStation 2 name comes with it.  The table of
  the pairs is written by ``tools/ps2_ps3_match.py``.
* the **assert messages**: a function that asserts names its source file and
  its line, and the text of the condition or of the message often names the
  method itself.  The table of the names is written by the lot that reads
  them.

The table that comes out is published in ``config/proposals.tsv``.

    python tools/build_proposals.py \\
        --pair work/ps2-ps3-pairs-RC1.tsv --pair work/ps2-ps3-pairs-RC2.tsv \\
        --name work/lots/wave1-lobby/names.tsv --name-program RC3 \\
        --out config/proposals.tsv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from typing import Sequence

COLUMNS = ["program", "address", "name", "strength", "origin",
           "origin_detail", "evidence", "state"]

# A literal quoted in a justification, in double quotes.
LITERAL = re.compile(r'"([^"]{2,})"')

# The strengths, in the language the repository speaks.
STRENGTH = {
    "fort": "strong",
    "moyen": "medium",
    "faible": "weak",
    "fort/": "strong",
    "indecis": "undecided",
    "undecided": "undecided",
}


def read_pairs(path: str) -> list[dict]:
    """The pairs of the PlayStation 2 match, the verified ones."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row.get("confidence") != "verified":
                continue
            rows.append(row)
    return rows


def read_names(path: str, program: str) -> list[dict]:
    """The names of a lot: address, name, strength, justification."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            address, name, strength = parts[0], parts[1], parts[2]
            note = parts[3] if len(parts) > 3 else ""
            rows.append({"program": program, "address": address,
                         "name": name, "strength": strength, "note": note})
    return rows


def read_vocab(path: str) -> list[dict]:
    """The names a lot of vocabulary read from the sibling projects.

    The table has a header: program, address, name, source_project,
    source_path, ps2_function, name_kind, name_ambiguity, evidence_strings,
    evidence_assert, evidence_other_games, keys, confidence, state,
    in_catalogue.
    """
    rows = []
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rows.append(row)
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pair", action="append", default=[],
                        help="a table of the pairs of the PlayStation 2 match")
    parser.add_argument("--name", action="append", default=[],
                        help="a table of the names of a lot")
    parser.add_argument("--vocab", action="append", default=[],
                        help="a table of the names read from the sibling "
                             "projects")
    parser.add_argument("--name-program", default="",
                        help="the program the names belong to")
    parser.add_argument("--out", required=True, help="the table to write")
    args = parser.parse_args(argv)

    rows = []
    for path in args.pair:
        for row in read_pairs(path):
            source = row.get("ps2_source", "")
            name = source.rsplit("/", 1)[-1] if source else ""
            rows.append({
                "program": row["ps3_program"],
                "address": row["ps3_function"],
                "name": name,
                "strength": "verified",
                "origin": "ps2",
                "origin_detail": source,
                "evidence": row.get("evidence", ""),
                "state": "proposed" if name else "matched",
            })
    for path in args.name:
        for row in read_names(path, args.name_program):
            literals = " | ".join(LITERAL.findall(row["note"]))
            rows.append({
                "program": row["program"],
                "address": row["address"],
                "name": row["name"],
                "strength": STRENGTH.get(row["strength"], row["strength"]),
                "origin": "assert",
                "origin_detail": "",
                "evidence": literals,
                "state": "proposed" if row["name"] else "undecided",
            })

    for path in args.vocab:
        for row in read_vocab(path):
            name = row.get("name", "")
            ambiguity = row.get("name_ambiguity", "")
            detail = row.get("source_path", "")
            project = row.get("source_project", "")
            rows.append({
                "program": row["program"],
                "address": row["address"],
                "name": name,
                "strength": ("ambiguous" if ambiguity not in ("", "0")
                             else row.get("confidence", "")),
                "origin": "vocabulary",
                "origin_detail": f"{project}: {detail}" if detail else project,
                "evidence": row.get("evidence_strings", ""),
                "state": row.get("state", "proposed") if name else "undecided",
            })

    rows.sort(key=lambda row: (row["program"], row["address"]))
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("\t".join(COLUMNS) + "\n")
        for row in rows:
            out.write("\t".join(str(row[column]) for column in COLUMNS) + "\n")

    by_origin = {}
    for row in rows:
        by_origin[row["origin"]] = by_origin.get(row["origin"], 0) + 1
    print(f"wrote {args.out}: {len(rows)} proposals ({by_origin})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
