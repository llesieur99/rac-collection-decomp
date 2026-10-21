"""Measure the packages of the related titles and write their summary.

The three titles of the collection also exist as separate PlayStation Network
titles, packaged as retail ``.pkg`` files.  Each of them is a second,
independent reference for the same game: a different build of the same
program, and a different content id.

    python tools/measure_package.py --pkg <file.pkg> --out <summary.json> \\
        [--hash-package]

The summary holds the identity of the package and the identity of the
executable it carries, and the way to read it.  Only the header of the
package is read, and only the executable is extracted.

Hashing the whole package is optional: the packages of the related titles run
from 4 to 17 gigabytes, and reading one of them over a network takes hours.
The hash of the executable is always computed, because that is the part the
project measures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compiler_stamp import compiler_stamps, module_names  # noqa: E402
from self_header import Self  # noqa: E402


def sha256_of(path: str) -> str:
    digester = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1 << 22)
            if not chunk:
                break
            digester.update(chunk)
    return digester.hexdigest()


def measure(path: str, hash_package: bool = False) -> dict:
    from pkg import Pkg
    with Pkg(path) as package:
        content_id = package.content_id
        entries = len(package.entries)
        revision = f"0x{package.revision:04X}"
        encrypted = package.encrypted
        summary = {
            "package_size": os.path.getsize(path),
            "package_sha256": sha256_of(path) if hash_package else None,
            "content_id": content_id,
            "platform": "PS3",
            "revision": revision,
            "encryption": "AES-128-CTR" if encrypted else "SHA-1 keystream",
            "entries": entries,
        }
        eboot = None
        for entry in package.find("USRDIR/EBOOT.BIN"):
            if not entry.is_dir:
                eboot = entry
                break
        if eboot is None:
            return summary
        raw = package.read(eboot)
        container = Self(raw, f"{path}!USRDIR/EBOOT.BIN")
        elf = container.rebuild_elf()
        stamps = compiler_stamps(elf)
        summary["executable"] = {
            "path": "USRDIR/EBOOT.BIN",
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "key_revision": f"0x{container.key_revision:04X}",
            "header_size": f"0x{container.header_size:X}",
            "elf_size": container.elf_size,
            "compiler_stamp": (stamps.most_common(1)[0][0] if stamps else None),
            "modules": sorted(module_names(elf)),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pkg", required=True, help="path to the .pkg file")
    parser.add_argument("--out", required=True, help="file to write")
    parser.add_argument("--hash-package", action="store_true",
                        help="also hash the whole package, which is slow")
    args = parser.parse_args()
    summary = measure(args.pkg, args.hash_package)
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        json.dump(summary, out, indent=2, ensure_ascii=False)
        out.write("\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
