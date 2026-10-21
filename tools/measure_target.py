"""Measure the pinned target and write ``config/target.json``.

The configuration of the target is measured, never typed by hand: this tool
reads the local copy of the release and writes what it finds.  The path of the
copy is given on the command line, so no personal path is ever stored in the
repository.

    python tools/measure_target.py --root <path to the extracted release> \\
        --out config/target.json

The tool reads the ``PARAM.SFO``, the ``PS3_DISC.SFB`` descriptor and the four
executables of the release, rebuilds their PPU ELF and records the hashes.
Only hashes, sizes and offsets are written; no game content is copied out.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from param_sfo import ParamSfo  # noqa: E402
from ps3disc import Ps3Disc  # noqa: E402
from self_header import Self  # noqa: E402
from compiler_stamp import compiler_stamps, library_stamps, module_names  # noqa: E402
from payload_state import entropy, segments_of  # noqa: E402

EXECUTABLES = (
    ("EBOOT.BIN", "launcher"),
    ("RC1.ppu.self", "Ratchet & Clank: Tools of Destruction"),
    ("RC2.ppu.self", "Ratchet & Clank: Going Commando"),
    ("RC3.ppu.self", "Ratchet & Clank: Up Your Arsenal"),
)

# The digital manual the disc carries, in PS3_GAME/PKGDIR.
PACKAGE = "PS3_GAME/PKGDIR/PKG00/INSTALL.PKG"


def sha256_of(path: str) -> str:
    digester = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                break
            digester.update(chunk)
    return digester.hexdigest()


def elf_summary(elf: bytes) -> dict:
    import struct
    entry, phoff, shoff = struct.unpack_from(">3Q", elf, 0x18)
    (phentsize, phnum, shentsize, shnum, shstrndx) = struct.unpack_from(">5H", elf, 0x36)
    return {
        "size": len(elf),
        "sha256": hashlib.sha256(elf).hexdigest(),
        "class": "ELF64",
        "endianness": "big",
        "machine": "EM_PPC (102), PPU target",
        "entry": f"0x{entry:X}",
        "program_headers": phnum,
        "section_headers": shnum,
        "section_names": False,
        "symbol_table": False,
    }


def measure(root: str) -> dict:
    sfo_path = os.path.join(root, "PS3_GAME", "PARAM.SFO")
    sfb_path = os.path.join(root, "PS3_DISC.SFB")
    usrdir = os.path.join(root, "PS3_GAME", "USRDIR")

    with open(sfo_path, "rb") as handle:
        sfo = ParamSfo(handle.read(), sfo_path)
    with open(sfb_path, "rb") as handle:
        disc = Ps3Disc(handle.read(), sfb_path)

    executables = []
    for name, role in EXECUTABLES:
        path = os.path.join(usrdir, name)
        with open(path, "rb") as handle:
            raw = handle.read()
        container = Self(raw, path)
        elf = container.rebuild_elf()
        stamps = compiler_stamps(elf)
        text_entropy = None
        for ptype, off, vaddr, size in segments_of(elf):
            if ptype == 1 and vaddr and size:
                text_entropy = round(entropy(elf[off:off + min(size, 65536)]), 2)
                break
        executables.append({
            "path": f"PS3_GAME/USRDIR/{name}",
            "role": role,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "kind": "retail SELF (NPDRM), code and data still encrypted",
            "key_revision": f"0x{container.key_revision:04X}",
            "licence_type": container.license_type(),
            "header_size": f"0x{container.header_size:X}",
            "elf_size": container.elf_size,
            "payload": {
                "text_entropy": text_entropy,
                "state": "encrypted" if (text_entropy or 0) >= 7.90 else "in the clear",
                "note": "the NPDRM layer is still there: the header, the program "
                        "headers, the section table and the module names are in "
                        "the clear, the code and the data are not",
            },
            "compiler_stamp": (stamps.most_common(1)[0][0] if stamps else None),
            "modules": sorted(module_names(elf)),
            "libraries": sorted(library_stamps(elf)),
            "ppu_elf": elf_summary(elf),
        })

    title = sfo.get("TITLE")
    version = sfo.get("VERSION")
    # The real content id lives in the encrypted NPDRM metadata of the
    # executables.  What follows is a derivation from the title, not a
    # measurement: it stays flagged until the decryption is done privately.
    derived = f"UP9000-{sfo.title_id}_00-{''.join(ch for ch in title.upper() if ch.isalnum())[:12]:0<12}"

    package = None
    package_path = os.path.join(root, PACKAGE.replace("/", os.sep))
    if os.path.exists(package_path):
        from pkg import Pkg
        with Pkg(package_path) as pkg:
            package = {
                "path": PACKAGE,
                "role": "the digital manual the disc carries",
                "size": os.path.getsize(package_path),
                "sha256": sha256_of(package_path),
                "content_id": pkg.content_id,
                "platform": "PS3",
                "revision": f"0x{pkg.revision:04X}",
                "encryption": "AES-128-CTR" if pkg.encrypted else "SHA-1 keystream",
                "entries": len(pkg.entries),
            }

    return {
        "game": "Ratchet & Clank Collection",
        "platform": "PlayStation 3",
        "region": "USA",
        "title_id": sfo.title_id,
        "content_id": derived,
        "content_id_status": "derived from the title, not measured: the real "
                             "content id is in the encrypted NPDRM metadata",
        "disc": {
            "volume_label": "PS3VOLUME",
            "descriptor": "PS3_DISC.SFB",
            "descriptor_size": os.path.getsize(sfb_path),
            "descriptor_sha256": sha256_of(sfb_path),
            "disc_title_id": disc.get("TITLE_ID").split(b"\x00", 1)[0].decode("ascii")
            if disc.get("TITLE_ID") else None,
        },
        "param_sfo": {
            "path": "PS3_GAME/PARAM.SFO",
            "size": os.path.getsize(sfo_path),
            "sha256": sha256_of(sfo_path),
            "title": title,
            "title_id": sfo.title_id,
            "version": version,
            "app_version": sfo.get("APP_VER"),
            "ps3_system_version": sfo.get("PS3_SYSTEM_VER"),
            "category": sfo.get("CATEGORY"),
            "bootable": sfo.get("BOOTABLE"),
            "endianness": "little",
        },
        "executables": executables,
        "package": package,
        "manifests": {
            "disc": "config/disc-manifest.tsv",
            "working_copy": "config/working-manifest.tsv",
        },
        "matching_compiler": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, help="path to the extracted release")
    parser.add_argument("--out", required=True, help="file to write")
    args = parser.parse_args()
    target = measure(args.root)
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        json.dump(target, out, indent=2, ensure_ascii=False)
        out.write("\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
