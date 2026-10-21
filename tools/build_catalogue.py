"""Build the catalogue of the functions, from the boundaries of the programs.

The catalogue is the index of the functions of the four programs: where they
are, how long they are, and what evidence backs the claim.  The names are
not known yet, so every function carries the placeholder of its address.

    python tools/build_catalogue.py --work <directory of the rebuilt ELFs> \\
        --out config/functions.tsv

The boundaries come from
[`tools/ppu_funcs.py`](ppu_funcs.py): a function starts where the SDK's
prologue appears, where a call lands, where the flow cannot fall in, or
where the walk ends on a return; **two of these signals have to agree** for
the address to be a function.  An address that only one signal sees is a
**candidate**, and it is published with the state ``candidate``: it is not a
function, and it is not counted as one.

The end of a function is found by walking its control flow: the function
ends at the return that no path falls through from.  The extent of a
candidate is **provisional**: it is the block the walk covers from the
candidate, and it is not a claim about the size of a function.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import PpuElf  # noqa: E402
from ppu_funcs import (  # noqa: E402
    build_catalogue, call_targets, entry_candidates, entry_evidence,
    function_body, walk_bound,
)

# The programs of the release, and the name each function gets in the
# catalogue.
PROGRAMS = (
    ("EBOOT", "eboot.elf", "collection launcher"),
    ("RC1", "RC1.elf", "Ratchet & Clank (2002)"),
    ("RC2", "RC2.elf", "Ratchet & Clank 2: Going Commando"),
    ("RC3", "RC3.elf", "Ratchet & Clank 3: Up Your Arsenal"),
)

# The states a function can be in.
STATE_BOUNDED = "bounded"
STATE_CANDIDATE = "candidate"
STATE_REJECTED = "rejected"
STATE_NAMED = "named"
STATE_MATCHING = "matching"


def read_decisions(path: str) -> dict[tuple[str, int], dict]:
    """The decision of the lot on the candidates, keyed by program and address.

    The table is published in config/candidates.tsv: an address the
    catalogue sees with one signal was measured, one by one, and the table
    says what it is.  The catalogue applies the decision: a confirmed
    candidate is a function, a rejected one is not.
    """
    out: dict[tuple[str, int], dict] = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            key = (row["program"], int(row["address"], 0))
            out[key] = row
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", required=True,
                        help="directory that holds the rebuilt ELFs")
    parser.add_argument("--out", required=True, help="file to write")
    parser.add_argument("--narrow", action="store_true",
                        help="use the two narrow methods only (the old catalogue)")
    parser.add_argument("--decisions", default=None,
                        help="the table of the decisions on the candidates")
    args = parser.parse_args()

    decisions = read_decisions(args.decisions) if args.decisions else {}

    rows = []
    for program, filename, role in PROGRAMS:
        path = os.path.join(args.work, filename)
        if not os.path.exists(path):
            print(f"skipping {program}: {path} is missing")
            continue
        with open(path, "rb") as handle:
            elf = PpuElf(handle.read(), path)

        if args.narrow:
            catalogue = build_catalogue(elf)
            entries = {address for address, _kind, _evidence in catalogue}
            confirmed = {address for address, _k, evidence in catalogue
                         if evidence == "both"}
            evidence = {address: evidence.split("+")
                        for address, _k, evidence in catalogue}
        else:
            evidence, confirmed = entry_evidence(elf)
            entries = walk_bound(confirmed,
                                 {c.address for c in call_targets(elf)},
                                 {c.address for c in entry_candidates(elf)})

        kept = 0
        candidates = 0
        rejected = 0
        for address in sorted(evidence):
            if args.narrow and address not in confirmed:
                continue
            end, why, body = function_body(elf, address, entries=entries)
            if end <= address:
                continue
            decision = decisions.get((program, address))
            if address in confirmed:
                state = STATE_BOUNDED
                note = ""
                kept += 1
            elif decision is not None and decision.get("decision") == "confirmed":
                # the lot measured this address, one by one
                state = STATE_BOUNDED
                note = f";decided:{decision.get('rule', '')}"
                kept += 1
            elif decision is not None and decision.get("decision") == "rejected":
                state = STATE_REJECTED
                note = f";rejected:{decision.get('rule', '')}"
                rejected += 1
            else:
                state = STATE_CANDIDATE
                note = ";provisional"
                candidates += 1
            rows.append((program, address, end - address, len(body),
                         f"func_{address:08X}", state,
                         f"{'+'.join(evidence[address])};end:{why}{note}"))
        print(f"{program:6s} {kept:6d} functions, {candidates:6d} candidates, "
              f"{rejected:6d} rejected ({role})")

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("program\taddress\tsize\tinstructions\tname\tstate\tevidence\n")
        for program, address, size, instructions, name, state, note in rows:
            out.write(f"{program}\t0x{address:08X}\t{size}\t{instructions}"
                      f"\t{name}\t{state}\t{note}\n")
    print(f"wrote {args.out}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
