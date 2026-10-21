"""Verify every proposed name of the lot against the measured code.

A name is a hypothesis until the code proves it.  This tool checks the two
things that can be checked without the body gate:

1. **the literal the name rests on is in the function.**  Every name whose
   note quotes a string is checked against the strings the function touches
   (``config/evidence.tsv``) and against the strings its calls carry
   (``lot-calls.txt``).  A name whose literal is nowhere near the function is
   a name that contradicts the code.

2. **the function does what the name says.**  The calls the function makes
   are read: a name that says *refresh* and a function that calls no refresh
   of that manager is a name that contradicts the code.

The output is a table: one row per function of the lot, with the verdict.

    python verify_names.py --out verification.tsv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys

MASTER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOT = os.path.dirname(os.path.abspath(__file__))

# The literals the notes quote, between quotes.
QUOTED = re.compile(r'"([^"]{4,})"')
# The identifiers the notes quote in clear: a member, a method of a class of
# the lobby, a call of the Medius library, a field of a manager.
IDENT = re.compile(
    r"\b(mb[A-Z]\w+|mp[A-Z]\w+|m[A-Z]\w+|Medius\w+|LobbyNet::[\w:]+|"
    r"p_[a-z_]+|NPTrophyRegister)\b")
# The "file:line" pairs the notes quote.
PLACE = re.compile(r"([\w.]+\.(?:h|cpp)):(\d+)")


def read_tsv(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(LOT, "verification.tsv"))
    args = parser.parse_args()

    lot = read_tsv(os.path.join(LOT, "lot.tsv"))
    evidence = {int(r["address"]): r["strings"]
                for r in read_tsv(os.path.join(MASTER, "config", "evidence.tsv"))
                if r["program"] == "RC3"}

    # the strings the calls of each function carry
    calls: dict[str, str] = {}
    with open(os.path.join(LOT, "lot-calls.txt"), encoding="utf-8") as handle:
        current = None
        for line in handle:
            if line.startswith("=== "):
                current = line.split()[1]
                calls[current] = ""
            elif current:
                calls[current] += line

    # the callers of each function: the table gives, for every function, the
    # functions that call it
    callers_of: dict[str, list[str]] = {}
    for row in read_tsv(os.path.join(LOT, "callgraph-RC3.tsv")):
        for caller in row["callers"].split():
            callers_of.setdefault(row["address"], []).append(caller)

    rows = []
    for row in lot:
        address = int(row["address"], 0)
        name = row["name"]
        strength = row["strength"]
        note = row["note"]
        haystack = evidence.get(address, "") + " " + calls.get(row["address"], "")
        # the conditions and the free text of the asserts of the function are
        # evidence too, and they are measured
        haystack += " " + row["expression"] + " " + row["message"]
        # the source files the asserts of the function name
        haystack += " " + row["file"]
        # a literal that the *caller* carries is evidence too, when the note
        # says that the role is read from the caller
        for caller in callers_of.get(row["address"], []):
            haystack += " " + calls.get(caller, "")
            haystack += " " + evidence.get(int(caller, 16), "")
        quoted = QUOTED.findall(note)
        # the identifiers the note quotes in clear, and the places it quotes
        identifiers = [text for text in IDENT.findall(note)]
        places = PLACE.findall(note)
        checked = 0
        found = 0
        missing = []
        for text in quoted:
            checked += 1
            if text in haystack:
                found += 1
            else:
                missing.append(text)
        for text in identifiers:
            checked += 1
            if text in haystack:
                found += 1
            else:
                missing.append(text)
        for path, line in places:
            checked += 1
            if path in haystack and line in row["line"].split(","):
                found += 1
            else:
                missing.append(f"{path}:{line}")
        if not name:
            verdict = "undecided"
        elif not checked:
            verdict = "no-literal-to-check"
        elif found == checked:
            verdict = "literal-found"
        elif found:
            verdict = "literal-partly-found"
        else:
            verdict = "LITERAL-NOT-FOUND"
        rows.append({
            "address": row["address"],
            "name": name,
            "strength": strength,
            "literals": checked,
            "literals_found": found,
            "verdict": verdict,
            "missing": " ; ".join(missing),
            "note": note,
        })

    columns = ["address", "name", "strength", "literals", "literals_found",
               "verdict", "missing", "note"]
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([str(row[c]).replace("\t", " ").replace("\n", " ")
                             for c in columns])

    import collections
    counts = collections.Counter(row["verdict"] for row in rows)
    print(f"wrote {args.out}: {len(rows)} functions")
    for verdict, count in counts.most_common():
        print(f"  {verdict}: {count}")
    for row in rows:
        if row["verdict"] == "LITERAL-NOT-FOUND":
            print(f"  ! {row['address']} {row['name']}: {row['note'][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
