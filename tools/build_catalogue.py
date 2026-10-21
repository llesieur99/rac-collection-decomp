"""Build the catalogue of the functions, from the boundaries of the programs.

The catalogue is the index of the functions of the four programs: where they
are, how long they are, and what evidence backs the claim.  The names are
not known yet, so every function carries the placeholder of its address.

    python tools/build_catalogue.py --work <directory of the rebuilt ELFs> \\
        --out config/functions.tsv

The boundaries come from
[`tools/ppu_funcs.py`](ppu_funcs.py): a function starts where the SDK's
prologue appears **and** where a call lands, and it ends at the return that no
path falls through from.

Only the functions that both methods agree on are kept: an address that only
one method sees is a candidate, not a function.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402
from ppu_funcs import build_catalogue, function_extent  # noqa: E402

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
STATE_NAMED = "named"
STATE_MATCHING = "matching"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", required=True,
                        help="directory that holds the rebuilt ELFs")
    parser.add_argument("--out", required=True, help="file to write")
    args = parser.parse_args()

    rows = []
    for program, filename, role in PROGRAMS:
        path = os.path.join(args.work, filename)
        if not os.path.exists(path):
            print(f"skipping {program}: {path} is missing")
            continue
        with open(path, "rb") as handle:
            elf = PpuElf(handle.read(), path)
        catalogue = build_catalogue(elf)
        kept = 0
        for address, kind, evidence in catalogue:
            if evidence != "both":
                continue
            end, why = function_extent(elf, address)
            if end <= address:
                continue
            rows.append((program, address, end - address, f"func_{address:08X}",
                         STATE_BOUNDED, f"prologue+call;end:{why}"))
            kept += 1
        print(f"{program:6s} {kept:6d} functions ({role})")

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("program\taddress\tsize\tname\tstate\tevidence\n")
        for program, address, size, name, state, evidence in rows:
            out.write(f"{program}\t0x{address:08X}\t{size}\t{name}\t{state}\t{evidence}\n")
    print(f"wrote {args.out}: {len(rows)} functions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
