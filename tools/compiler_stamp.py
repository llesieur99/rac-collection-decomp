"""Read the compiler identification out of a retail PPU executable.

A GCC-built program carries the compiler's identification in the ``.comment``
section, once per linked object.  When it is there, it names the exact
compiler and the exact SDK revision that produced the program, which is the
first thing a matching decompilation needs.

The tool reads a SELF container or a rebuilt PPU ELF, and it never decodes
code.

    python tools/compiler_stamp.py <file.self> [--libraries] [--modules]

The exit status is 0 when a stamp was found and 1 when none was, so that a
negative result is visible in a script and not silently ignored.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402
from self_header import Self, SelfError  # noqa: E402

# The stamp of a GCC-built object.
STAMP = re.compile(rb"GCC: \([^\x00]{0,160}\)")

# The other identifications a retail executable usually carries.
LIBRARIES = (
    rb"Dinkumware[^\x00]{0,60}",
    rb"Lua 5\.[0-9.]+[^\x00]{0,40}",
    rb"zlib [0-9.]+[^\x00]{0,30}",
    rb"inflate [0-9.]+[^\x00]{0,30}",
    rb"deflate [0-9.]+[^\x00]{0,30}",
    rb"Copyright \(c\) [0-9]{4}-[0-9]{4} by P\.J\. Plauger[^\x00]{0,40}",
)

# The name of an SCE module, as the section string table of a retail
# executable spells it: a fixed prefix and the name of the library.
MODULE = re.compile(rb"p[0-9]{6}([A-Za-z0-9_+.\-]{2,40})")

# The strings that would name a toolchain, if the program carried one.
TOOLCHAIN = re.compile(
    r"(sdk[0-9]{3,4}|gcc:|gnu|clang|ps3gcc|rev:|cell |playstation|insomniac)",
    re.IGNORECASE,
)

PRINTABLE = re.compile(rb"[\x20-\x7e]{8,}")


def load_elf(path: str) -> tuple[bytes, dict]:
    """Return the ELF of a file, and what is known about its container."""
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw[:4] == b"\x7fELF":
        return raw, {}
    container = Self(raw, path)
    info = {
        "key_revision": f"0x{container.key_revision:04X}",
        "header_size": f"0x{container.header_size:X}",
        "elf_size": container.elf_size,
    }
    return container.rebuild_elf(), info


def compiler_stamps(data: bytes) -> Counter:
    """The distinct compiler stamps, with how many times each appears."""
    return Counter(match.group().decode("latin1") for match in STAMP.finditer(data))


def library_stamps(data: bytes) -> Counter:
    """The distinct library identification strings."""
    found = Counter()
    for pattern in LIBRARIES:
        for match in re.finditer(pattern, data):
            found[match.group().decode("latin1")] += 1
    return found


def module_names(data: bytes) -> Counter:
    """The SCE modules the program is linked against."""
    found = Counter()
    for match in MODULE.finditer(data):
        found[match.group(1).decode("latin1")] += 1
    return found


def toolchain_strings(data: bytes) -> list[str]:
    """The strings that would name a toolchain."""
    out = []
    for match in PRINTABLE.finditer(data):
        text = match.group().decode("ascii")
        if TOOLCHAIN.search(text):
            out.append(text)
    return out


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("executable", help="path to a SELF container or to a PPU ELF")
    parser.add_argument("--libraries", action="store_true",
                        help="also report the libraries the executable carries")
    parser.add_argument("--modules", action="store_true",
                        help="also report the SCE modules it is linked against")
    args = parser.parse_args(argv)

    try:
        data, info = load_elf(args.executable)
    except (OSError, ElfError, SelfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"file        : {args.executable}")
    print(f"elf size    : {len(data)}")
    for key, value in info.items():
        print(f"{key:12s} : {value}")

    stamps = compiler_stamps(data)
    if stamps:
        print(f"{len(stamps)} distinct compiler stamp(s):")
        for stamp, count in stamps.most_common():
            print(f"  {count:5d} x {stamp}")
    else:
        print("compiler stamp: NONE FOUND")
        strings = toolchain_strings(data)
        if strings:
            print("strings that name a toolchain:")
            for text in sorted(set(strings)):
                print(f"  {text!r}")
        else:
            print("strings that name a toolchain: NONE FOUND")

    if args.libraries:
        print("libraries:")
        found = library_stamps(data)
        if found:
            for name, count in found.most_common():
                print(f"  {count:5d} x {name}")
        else:
            print("  NONE FOUND")

    if args.modules:
        print("modules:")
        found = module_names(data)
        for name, count in found.most_common():
            print(f"  {count:5d} x {name}")

    return 0 if stamps else 1


if __name__ == "__main__":
    raise SystemExit(main())
