#!/usr/bin/env python3
"""Extract the vocabulary of the sibling projects.

The six sibling projects on this machine decompiled the PlayStation 2
(or, for A Crack in Time, the PlayStation 3) versions of the same series.
They established names for their functions.  Those names are the
*vocabulary* of the engine, and the PlayStation 3 build of the Collection
speaks the same vocabulary.

This script only **reads** the sibling projects.  It writes one table:

    vocab.tsv   project, game, program, ps2_address, size, name, source,
                name_kind, note

``name_kind`` says how the name was obtained, which is what makes the
provenance auditable:

    source-path      the base name of the source file the sibling compiled
                     the function from
    assert-label     a structural label the sibling's analyst attached to
                     the function that carries an assertion message
    moby-dispatch    a name read off a moby dispatch table
    body-source      the base name of a body the sibling proved
    method-message   a method name the code itself prints
    string-reached   a name the code of the sibling reaches

Everything that is a placeholder (``FUN_00123456``, ``func_00123456``,
``0026ea00``) is kept but marked, so that the volume of the *real*
vocabulary can be told from the volume of the rows.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# The root of the sibling projects on this machine: the environment says
# where they are, and the repository keeps no path of its own.
SIBLINGS = Path(os.environ.get("RAC_SIBLINGS_ROOT", "D:/"))
LOT = Path(os.environ.get("RAC_LOT", "D:/RAC-COLLECTION/work/lots/wave1-vocabulary"))
WORK = Path(os.environ.get("RAC_WORK", "D:/RAC-COLLECTION/work"))

RAC1 = SIBLINGS / "RAC1"
RAC2 = SIBLINGS / "RAC2/master"
RAC3 = SIBLINGS / "RAC3/ratchet-uya-decomp"
RACSAC = SIBLINGS / "RAC-SAC/master"
RAC8 = SIBLINGS / "RAC8/master"
RAC8W = SIBLINGS / "RAC8/work"

# A placeholder name: FUN_00123456, func_00123456, func_L00_002A3B80,
# jtbl_00123456, D_00123456, 0026ea00.
PLACEHOLDER = re.compile(
    r"^(?:FUN|func|fun|sub|jtbl|D|R)_[0-9A-Fa-f]{1,8}$|"
    r"^(?:FUN|func|fun|sub|jtbl|D|R)_L\d{2}_[0-9A-Fa-f]{1,8}$|"
    r"^(?:FUN|func|fun|sub|jtbl)_[0-9A-Fa-f]{1,8}$|"
    r"^[0-9A-Fa-f]{6,8}$",
    re.IGNORECASE,
)
# The name of a C function, as the sibling projects write them.
C_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# A mechanical name: the sibling read it off a table, and it carries no
# meaning beyond the number it holds.
MECHANICAL = re.compile(r"^(?:Update|Init|Delete|UpdateMoby|InitMoby)_?\d*$")

rows: list[dict] = []


def add(project: str, game: str, program: str, address: str, size: str,
        name: str, source: str, kind: str, note: str = "") -> None:
    if not name:
        return
    rows.append({
        "project": project,
        "game": game,
        "program": program,
        "ps2_address": address,
        "size": size,
        "name": name,
        "source": source,
        "name_kind": kind,
        "note": note,
    })


def is_placeholder(name: str) -> bool:
    if not name:
        return True
    if PLACEHOLDER.match(name):
        return True
    return not C_NAME.match(name)


def base_name(path: str) -> str:
    """The name of a function read off the path of its source file."""
    text = path.split("  [")[0].strip().replace("\\", "/")
    text = text.rsplit("/", 1)[-1]
    if text.endswith(".c"):
        text = text[:-2]
    elif text.endswith(".cpp"):
        text = text[:-4]
    return text


# -- V1/V2: rac1, the lombyte checkout ------------------------------------
# The address table of the lot predecessor: one row per function of the
# core and of the nineteen overlays, with the source file it comes from.

def read_rac1() -> None:
    path = WORK / "ps2-addr-to-source.tsv"
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            source = row["source"]
            if not source:
                continue
            name = base_name(source)
            kind = "source-path"
            note = ""
            if source.startswith("assembly/textbin/"):
                kind = "source-path"
                note = "textbin: the sibling has no C source for it"
            if row["space"] == "core":
                program = "BOOT"
            else:
                program = "LVL" + row["level"]
            add("rac1-lombyte", "RC1", program, row["vaddr"], row["size"],
                name, source, kind, note)


# -- V3: rac1-decomp, the undefined function list --------------------------

def read_rac1_decomp() -> None:
    path = RAC1 / "decomp" / "config" / "undefined_funcs_auto.txt"
    if not path.exists():
        return
    pattern = re.compile(r"^(\w+)\s*=\s*(0x[0-9A-Fa-f]+);")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        add("rac1-decomp", "RC1", "BOOT", match.group(2), "", match.group(1),
            "config/undefined_funcs_auto.txt", "symbol", "placeholder")


# -- V4/V5/V6/V7: rac2 ----------------------------------------------------

def read_rac2() -> None:
    catalogue = RAC2 / "config" / "levels" / "functions.tsv"
    if catalogue.exists():
        with catalogue.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 6:
                    continue
                name, kind, size, _fp, levels, places = parts[:6]
                for item in places.split(","):
                    if ":" not in item:
                        continue
                    level, _, address = item.partition(":")
                    add("rac2", "RC2", "LVL" + level, "0x" + address, size,
                        name, "config/levels/functions.tsv", "symbol",
                        "placeholder")
    boot = RAC2 / "config" / "boot" / "functions.tsv"
    if boot.exists():
        for line in boot.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            add("rac2", "RC2", "BOOT", "0x" + parts[1], parts[2], parts[0],
                "config/boot/functions.tsv", "symbol", "placeholder")

    # The structural labels read off the assertion messages.
    labels = RAC2 / "docs" / "assert-message-names.tsv"
    if labels.exists():
        with labels.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                add("rac2", "RC2", row["program"], row["address"], "",
                    row["name"], "docs/assert-message-names.tsv",
                    "assert-label", "the label the analyst attached")

    # The moby dispatch tables.
    dispatch = RAC2 / "docs" / "moby-dispatch.tsv"
    if dispatch.exists():
        with dispatch.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                if not row.get("proposed_name"):
                    continue
                add("rac2", "RC2", "LVL" + row["level"], row["address"], "",
                    row["proposed_name"], "docs/moby-dispatch.tsv",
                    "moby-dispatch", row.get("class_label", ""))
                label = (row.get("class_label") or "").strip()
                if label:
                    add("rac2", "RC2", "LVL" + row["level"], row["address"], "",
                        label, "docs/moby-dispatch.tsv", "moby-class", "")
    # The symbols the project resolved.
    symbols = RAC2 / "symbol_addrs" / "usa" / "symbol_addrs.txt"
    if symbols.exists():
        pattern = re.compile(r"^(\w+)\s*=\s*(0x[0-9A-Fa-f]+);")
        for line in symbols.read_text(encoding="utf-8",
                                      errors="replace").splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            add("rac2", "RC2", "BOOT", match.group(2), "", match.group(1),
                "symbol_addrs/usa/symbol_addrs.txt", "symbol", "placeholder")


# -- V8/V9: rac3 ----------------------------------------------------------

def read_rac3() -> None:
    path = RAC3 / "symbol_addrs_resolved.txt"
    if path.exists():
        pattern = re.compile(r"^(\w+)\s*=\s*(0x[0-9A-Fa-f]+);")
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            add("rac3", "RC3", "FRONTBIN", match.group(2), "", match.group(1),
                "symbol_addrs_resolved.txt", "symbol", "placeholder")
    remaining = RAC3 / "docs" / "remaining_functions.tsv"
    if remaining.exists():
        with remaining.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                add("rac3", "RC3", "FRONTBIN", row["address"], row.get("size", ""),
                    row["function"], "docs/remaining_functions.tsv", "symbol",
                    "placeholder")


# -- V10/V11: rac-sac -----------------------------------------------------

def read_rac_sac() -> None:
    for kind, game in (("boot", "SAC"), ("levels", "SAC")):
        bodies = RACSAC / "config" / kind / "bodies.tsv"
        sources = RACSAC / "config" / kind / "body_sources.tsv"
        if not bodies.exists() or not sources.exists():
            continue
        index: dict[str, str] = {}
        with sources.open(encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2:
                    index[parts[0]] = parts[1]
        with bodies.open(encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 4:
                    continue
                module, offset, size, source = parts[:4]
                name = base_name(source)
                add("rac-sac", game, module, "0x" + offset.lstrip("0x"), size,
                    name, source, "body-source",
                    "sha256 " + index.get(source, "")[:16])


# -- V12/V13/V14/V15/V16: rac8 --------------------------------------------

def read_rac8() -> None:
    assertions = RAC8W / "analysis" / "ps3_strings" / "assertions.txt"
    if assertions.exists():
        for line in assertions.read_text(encoding="utf-8",
                                          errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            address, filename, number, condition = parts[:4]
            name = base_name(filename) or filename
            add("rac8", "ACT", "EBOOT", address, "", name,
                "work/analysis/ps3_strings/assertions.txt", "assert-label",
                f"{filename}:{number} {condition}")

    reached = RAC8W / "analysis" / "ps3_strings" / "names_reached.tsv"
    if reached.exists():
        with reached.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                text = (row.get("string") or "").strip()
                if not text or " " in text:
                    continue
                add("rac8", "ACT", "EBOOT", row.get("function", ""), "", text,
                    "work/analysis/ps3_strings/names_reached.tsv",
                    "string-reached", "")

    rtti = RAC8W / "analysis" / "riftapart_rtti_demangled.tsv"
    if rtti.exists():
        with rtti.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index == 0:
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 2:
                    continue
                add("rac8", "ACT", "RTTI", "", "", parts[1],
                    "work/analysis/riftapart_rtti_demangled.tsv", "type",
                    "class name of the engine of the series")

    text = RAC8 / "src" / "text"
    if text.exists():
        for path in sorted(text.glob("*.c")):
            add("rac8", "ACT", "EBOOT", "", "", base_name(path.name),
                "src/text/" + path.name, "body-source", "")


# -- V17/V18: the C sources of rac2 and rac3 ------------------------------

C_DEF = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_ \*]*?\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{",
    re.MULTILINE,
)


def read_c_sources(root: Path, project: str, game: str) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*.c")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in C_DEF.finditer(text):
            name = match.group(1)
            if name in {"if", "for", "while", "switch", "return", "sizeof"}:
                continue
            add(project, game, "SRC", "", "", name,
                str(path.relative_to(root)).replace("\\", "/"), "func", "")


def main() -> int:
    read_rac1()
    read_rac1_decomp()
    read_rac2()
    read_rac3()
    read_rac_sac()
    read_rac8()
    read_c_sources(RAC2 / "src", "rac2", "RC2")
    read_c_sources(RAC3 / "src", "rac3", "RC3")

    columns = ["project", "game", "program", "ps2_address", "size", "name",
               "source", "name_kind", "note"]
    out = LOT / "vocab.tsv"
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    # -- the volume, measured ------------------------------------------
    print(f"vocab.tsv: {len(rows)} rows")
    per_project = Counter(r["project"] for r in rows)
    per_kind = Counter(r["name_kind"] for r in rows)
    real = [r for r in rows if not is_placeholder(r["name"])]
    real_per_project = Counter(r["project"] for r in real)
    real_per_kind = Counter(r["name_kind"] for r in real)
    semantic = [r for r in real if not MECHANICAL.match(r["name"])]
    semantic_per_project = Counter(r["project"] for r in semantic)
    semantic_per_kind = Counter(r["name_kind"] for r in semantic)
    print(f"{'project':<16}{'rows':>8}{'names':>8}{'semantic':>9}{'distinct':>10}"
          f"{'dist.sem.':>11}")
    for project in sorted(per_project):
        distinct = len({r["name"] for r in rows if r["project"] == project})
        dsem = len({r["name"] for r in semantic if r["project"] == project})
        print(f"{project:<16}{per_project[project]:>8}"
              f"{real_per_project[project]:>8}"
              f"{semantic_per_project[project]:>9}{distinct:>10}{dsem:>11}")
    print()
    print(f"{'kind':<16}{'rows':>8}{'names':>8}{'semantic':>9}{'dist.sem.':>11}")
    for kind in sorted(per_kind):
        dsem = len({r["name"] for r in semantic if r["name_kind"] == kind})
        print(f"{kind:<16}{per_kind[kind]:>8}{real_per_kind[kind]:>8}"
              f"{semantic_per_kind[kind]:>9}{dsem:>11}")
    print()
    print(f"rows total {len(rows)}, real names {len(real)}, "
          f"semantic names {len(semantic)}, "
          f"distinct real names {len({r['name'] for r in real})}, "
          f"distinct semantic names {len({r['name'] for r in semantic})}")
    summary = {
        "rows": len(rows),
        "real_names": len(real),
        "semantic_names": len(semantic),
        "distinct_real_names": len({r["name"] for r in real}),
        "distinct_semantic_names": len({r["name"] for r in semantic}),
        "per_project": dict(per_project),
        "real_per_project": dict(real_per_project),
        "semantic_per_project": dict(semantic_per_project),
        "per_kind": dict(per_kind),
        "real_per_kind": dict(real_per_kind),
        "semantic_per_kind": dict(semantic_per_kind),
    }
    (LOT / "vocab-volume.json").write_text(
        json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
