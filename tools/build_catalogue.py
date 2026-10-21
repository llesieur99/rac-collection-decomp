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
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import PpuElf  # noqa: E402
from ppu_funcs import (  # noqa: E402
    build_catalogue, call_targets, entry_evidence, function_body,
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
STATE_NAMED = "named"
STATE_MATCHING = "matching"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", required=True,
                        help="directory that holds the rebuilt ELFs")
    parser.add_argument("--out", required=True, help="file to write")
    parser.add_argument("--narrow", action="store_true",
                        help="use the two narrow methods only (the old catalogue)")
    args = parser.parse_args()

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
            entries = confirmed | {c.address for c in call_targets(elf)}

        kept = 0
        candidates = 0
        for address in sorted(evidence):
            if args.narrow and address not in confirmed:
                continue
            end, why, body = function_body(elf, address, entries=entries)
            if end <= address:
                continue
            if address in confirmed:
                state = STATE_BOUNDED
                note = ""
                kept += 1
            else:
                state = STATE_CANDIDATE
                note = ";provisional"
                candidates += 1
            rows.append((program, address, end - address, len(body),
                         f"func_{address:08X}", state,
                         f"{'+'.join(evidence[address])};end:{why}{note}"))
        print(f"{program:6s} {kept:6d} functions, {candidates:6d} candidates ({role})")

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("program\taddress\tsize\tinstructions\tname\tstate\tevidence\n")
        for program, address, size, instructions, name, state, note in rows:
            out.write(f"{program}\t0x{address:08X}\t{size}\t{instructions}"
                      f"\t{name}\t{state}\t{note}\n")
    print(f"wrote {args.out}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
