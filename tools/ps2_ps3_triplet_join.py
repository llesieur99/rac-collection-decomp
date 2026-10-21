"""Join the assert triplets of the PlayStation 2 and of the PlayStation 3.

The triplet is the strongest naming key that exists: the name of the
source file, the line inside it, and the text of the condition.  A
function of the PlayStation 2 build that asserts says which file it comes
from and where; the same is true of the PlayStation 3 build.

This script joins the two tables on the couple **(file, line)**, and then
runs the control of the method: the pairs of ``config/proposals.tsv``,
which are matched on a **shared message**, must carry the **same
triplet**.  The control is what tells whether the join is right.

Three tables are written:

* the **join**, one row per pair of sites that share the triplet;
* the **file table**, one row per name of source file, with the triplets
  of each build — it shows what the join had to work with;
* the **control**, one row per pair of ``config/proposals.tsv``.

    python ps2_ps3_triplet_join.py --ps2 ps2-asserts.tsv \\
        --ps3 D:\\RAC-COLLECTION\\master\\config\\asserts.tsv \\
        --addresses D:\\RAC-COLLECTION\\work\\ps2-addr-to-source.tsv \\
        --functions D:\\RAC-COLLECTION\\master\\config\\functions.tsv \\
        --proposals D:\\RAC-COLLECTION\\master\\config\\proposals.tsv \\
        --out ps2-ps3-triplets.tsv \\
        --files ps2-ps3-triplets-by-file.tsv \\
        --control ps2-ps3-triplets-control.tsv

Only metadata is written: addresses, file names, lines.  No game byte is
copied.
"""

from __future__ import annotations

import argparse
import csv
import re
from typing import Iterable

# A trailing ":line" in the file column of the PlayStation 3 table: the
# message of the assert carries the file and the line in one literal.
TRAILING_LINE = re.compile(r":(\d+)\Z")


def basename(path: str) -> str:
    """The name of the file, alone, whatever the path that leads to it.

    The PlayStation 2 build names its source files by their name alone
    (``hud.cpp``); the PlayStation 3 build names them by their whole path
    (``j:/Ratchet/rc2/code/game/hud.cpp``).  The join needs the name.
    """
    text = TRAILING_LINE.sub("", path)
    text = text.replace("\\", "/")
    return text.rsplit("/", 1)[-1]


def read_tsv(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


class Addresses:
    """The names and the source files of the functions of the PS2 build."""

    def __init__(self, path: str):
        self.core: dict[int, dict[str, str]] = {}
        self.level: dict[tuple[str, int], dict[str, str]] = {}
        self.core_by_source: dict[str, dict[str, str]] = {}
        self.level_by_name: dict[str, list[dict[str, str]]] = {}
        self.level_by_source: dict[str, list[dict[str, str]]] = {}
        for row in read_tsv(path):
            address = int(row["vaddr"], 0)
            source = row["source"].split("  [")[0]
            if row["space"] == "core":
                self.core[address] = row
                self.core_by_source.setdefault(source, row)
            else:
                self.level[(row["level"], address)] = row
                self.level_by_name.setdefault(row["name"], []).append(row)
                self.level_by_source.setdefault(
                    row["source"].split("  [")[0], []).append(row)

    def of(self, level: str, address: int) -> dict[str, str] | None:
        if level == "-":
            return self.core.get(address)
        return self.level.get((level, address))

    def core_equivalent(self, row: dict[str, str] | None) -> dict[str, str] | None:
        """The function of the core that the copy in a level comes from."""
        if row is None:
            return None
        source = row["source"].split("  [")[0]
        return self.core_by_source.get(source)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ps2", required=True)
    parser.add_argument("--ps3", required=True)
    parser.add_argument("--addresses", required=True)
    parser.add_argument("--functions", default="")
    parser.add_argument("--proposals", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--files", default="")
    parser.add_argument("--control", default="")
    parser.add_argument("--ps3-programs", default="",
                        help="keep only these programs of the PS3 table")
    args = parser.parse_args(argv)

    ps2 = read_tsv(args.ps2)
    ps3 = read_tsv(args.ps3)
    if args.ps3_programs:
        wanted = set(args.ps3_programs.split(","))
        ps3 = [row for row in ps3 if row["program"] in wanted]
    addresses = Addresses(args.addresses)

    functions: dict[tuple[str, str], str] = {}
    if args.functions:
        for row in read_tsv(args.functions):
            functions[(row["program"], row["address"])] = row["name"]

    def triplet(row: dict[str, str]) -> tuple[str, str]:
        return (basename(row["file"]), row["line"])

    index: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in ps2:
        index.setdefault(triplet(row), []).append(row)
    ps3_index: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in ps3:
        ps3_index.setdefault(triplet(row), []).append(row)

    # --- the joined table -------------------------------------------------
    rows = []
    for key in sorted(set(index) | set(ps3_index)):
        for one in index.get(key, []):
            for other in ps3_index.get(key, []):
                info = addresses.of(one["level"], int(one["function"], 0))
                core = addresses.core_equivalent(info)
                rows.append((
                    key[0], key[1],
                    one["program"], one["level"], one["function"],
                    info["name"] if info else "",
                    info["source"].split("  [")[0] if info else "",
                    f"0x{core['vaddr']}" if core else "",
                    one["site"], one["file_address"],
                    other["program"], other["address"],
                    functions.get((other["program"], other["address"]), ""),
                    other["site"], other["file"], other["expression"]))

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("file\tline\tps2_program\tps2_level\tps2_function\t"
                  "ps2_name\tps2_source\tps2_core_function\tps2_site\t"
                  "ps2_file_address\tps3_program\tps3_function\tps3_name\t"
                  "ps3_site\tps3_file\tps3_expression\n")
        for row in rows:
            out.write("\t".join(row) + "\n")
    print(f"wrote {args.out}: {len(rows)} joined pairs")

    shared = sorted(set(index) & set(ps3_index))
    print(f"{len(ps2)} PS2 sites in {len(index)} distinct triplets; "
          f"{len(ps3)} PS3 sites in {len(ps3_index)} distinct triplets")
    print(f"{len(shared)} triplets are common to the two builds: {shared}")

    # --- the file table ---------------------------------------------------
    if args.files:
        names = sorted({basename(row["file"]) for row in ps2}
                       | {basename(row["file"]) for row in ps3})
        with open(args.files, "w", encoding="utf-8", newline="\n") as out:
            out.write("file\tps2_triplets\tps3_triplets\tcommon\n")
            for name in names:
                left = sorted({row["line"] for row in ps2
                               if basename(row["file"]) == name},
                              key=lambda value: int(value))
                right = sorted({row["line"] for row in ps3
                                if basename(row["file"]) == name},
                               key=lambda value: int(value))
                common = sorted(set(left) & set(right), key=int)
                out.write(f"{name}\t{','.join(left)}\t{','.join(right)}\t"
                          f"{','.join(common)}\n")
        print(f"wrote {args.files}")

    # --- the control ------------------------------------------------------
    if args.control and args.proposals:
        control_rows = []
        by_level: dict[str, list[dict[str, str]]] = {}
        for row in ps2:
            by_level.setdefault(row["level"], []).append(row)

        for proposal in read_tsv(args.proposals):
            ps2_name = proposal.get("ps2_name", "")
            ps2_source = proposal.get("ps2_source", "")
            if not ps2_source:
                # the current schema of the table: the origin of the name
                # and its detail, which is the source of the PS2 function
                ps2_source = proposal.get("origin_detail", "")
                ps2_name = ""
            ps3_program = proposal["program"]
            ps3_address = proposal["address"]
            ps3_function = functions.get((ps3_program, ps3_address), "")

            ps3_triplets = sorted({triplet(row) for row in ps3
                                   if row["program"] == ps3_program
                                   and row["address"] == ps3_address})
            ps2_triplets = set()
            places = []
            if ps2_name:
                candidates = addresses.level_by_name.get(ps2_name, [])
            else:
                # the PS2 function is named by its source file
                wanted = ps2_source.split("/")[-1]
                candidates = [row for rows in addresses.level_by_source.values()
                              for row in rows
                              if row["source"].split("/")[-1] == wanted]
            for row in candidates:
                places.append(f"{row['level']}:{row['vaddr']}")
                for site in by_level.get(row["level"], []):
                    if site["function"] == row["vaddr"]:
                        ps2_triplets.add(triplet(site))
            control_rows.append((
                ps3_program, ps3_address, ps3_function,
                ps2_source, ps2_name or ps2_source,
                ";".join(f"{f}:{l}" for f, l in ps3_triplets),
                ";".join(f"{f}:{l}" for f, l in sorted(ps2_triplets)),
                str(len(places)), proposal.get("evidence", "")))

        with open(args.control, "w", encoding="utf-8", newline="\n") as out:
            out.write("ps3_program\tps3_address\tps3_function\tps2_source\t"
                      "ps2_name\tps3_triplets\tps2_triplets\tps2_places\t"
                      "proposal_evidence\n")
            for row in control_rows:
                out.write("\t".join(row) + "\n")
        print(f"wrote {args.control}: {len(control_rows)} pairs")
        both = sum(1 for row in control_rows if row[5] and row[6])
        either = sum(1 for row in control_rows if row[5] or row[6])
        print(f"{either} of the pairs carry a triplet on one side or the "
              f"other, {both} on both sides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
