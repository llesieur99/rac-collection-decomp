"""Read the engine's identity out of the programs of the release.

The engine names itself: it leaves a build stamp, the paths of the save data
and the names of its own symbols in the data of the program.  Those three are
what ties a program to a game, to a date and to a family.

    python tools/engine_identity.py --work <directory of the rebuilt ELFs> \\
        --out config/engine.tsv

The tool reads the rebuilt PPU ELFs, so it needs the decryption to have been
done first.  Every ``.elf`` of the directory is read, and the program is
named after its file.  Only metadata is written: no game bytes.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402

# The build stamp of the engine: a name, a version, a date.
STAMP = re.compile(rb"rt_[a-z]+ [0-9][0-9.\- ]*[0-9]")
# The paths of the save data: they name the title of the original game.
SAVE_PATH = re.compile(rb"/BESCES-[0-9A-Z]+/[A-Za-z0-9%.*_/-]*")
# The names of the engine's own symbols.
ENGINE_SYMBOL = re.compile(rb"rt_[a-z_][a-z0-9_]{2,40}")


def strings_of(path: str) -> set[bytes]:
    """Every printable run of every loaded segment of an ELF."""
    with open(path, "rb") as handle:
        elf = PpuElf(handle.read(), path)
    out: set[bytes] = set()
    for ph in elf.program_headers():
        if not ph.is_load or not ph.filesz:
            continue
        blob = elf.read_vaddr(ph.vaddr, ph.filesz)
        for match in re.finditer(rb"[\x20-\x7e]{4,}", blob):
            out.add(match.group())
    return out


def identity(path: str) -> dict:
    """The engine's identity, as it is written in the program."""
    found = strings_of(path)
    stamps = sorted(s.decode("ascii", "replace") for s in found if STAMP.fullmatch(s))
    paths = sorted({s.decode("ascii", "replace") for s in found
                    if SAVE_PATH.fullmatch(s) and s.count(b"/") >= 2})
    symbols = sorted({s.decode("ascii", "replace") for s in found
                      if ENGINE_SYMBOL.fullmatch(s)})
    titles = sorted({re.search(r"/(BESCES-[0-9A-Z]+)/", path).group(1)
                     for path in paths if re.search(r"/(BESCES-[0-9A-Z]+)/", path)})
    return {
        "build_stamp": stamps[0] if stamps else None,
        "save_paths": paths,
        "original_titles": titles,
        "engine_symbols": symbols,
    }


# The programs of the release, and the game each one is.  The names are not
# the series numbers: the collection numbers its own titles rc1, rc2 and rc3,
# and rc1 is the first game of the series, not the sixth.
ROLES = {
    "EBOOT": "collection launcher",
    "RC1": "Ratchet & Clank (2002)",
    "RC2": "Ratchet & Clank 2: Going Commando",
    "RC3": "Ratchet & Clank 3: Up Your Arsenal",
}


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", required=True,
                        help="directory that holds the rebuilt ELFs")
    parser.add_argument("--out", required=True, help="file to write")
    args = parser.parse_args(argv)

    rows = []
    for filename in sorted(os.listdir(args.work)):
        if not filename.endswith(".elf"):
            continue
        program = filename[:-4]
        path = os.path.join(args.work, filename)
        try:
            found = identity(path)
        except (OSError, ElfError) as exc:
            print(f"skipping {program}: {exc}")
            continue
        role = ROLES.get(program) or ROLES.get(program.upper()) or program
        rows.append((program.upper() if program.upper() in ROLES else program,
                     role, found))

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("program\trole\tbuild_stamp\toriginal_titles\tengine_symbols\tsave_paths\n")
        for program, role, found in rows:
            out.write(f"{program}\t{role}\t{found['build_stamp'] or ''}\t"
                      f"{' '.join(found['original_titles'])}\t"
                      f"{' '.join(found['engine_symbols'])}\t"
                      f"{' '.join(found['save_paths'])}\n")

    for program, role, found in rows:
        print(f"{program:6s} {role:24s} {found['build_stamp'] or '-'}")
        print(f"       the original titles : {', '.join(found['original_titles']) or '-'}")
        print(f"       the engine symbols  : {', '.join(found['engine_symbols']) or '-'}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
