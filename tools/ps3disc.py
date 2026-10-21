"""Reader for the ``PS3_DISC.SFB`` volume descriptor of a PlayStation 3 disc.

On a PS3 disc the root holds a ``PS3_DISC.SFB`` file.  It is a small
descriptor, not a container of the game data: it names the title and says
whether the disc is a hybrid CD/DVD/Blu-ray.  The format is documented in
``docs/DISC-FORMAT.md``.

    python tools/ps3disc.py info     <PS3_DISC.SFB>
    python tools/ps3disc.py entries  <PS3_DISC.SFB>

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from typing import Sequence

MAGIC = b".SFB"
ENTRY_SIZE = 32
NAME_SIZE = 16
ENTRIES_OFFSET = 0x20


class DiscError(Exception):
    """The file is not a readable PS3 volume descriptor."""


@dataclass(frozen=True)
class Entry:
    """One entry of the descriptor table."""

    index: int
    name: str
    offset: int
    length: int
    reserved_a: int
    reserved_b: int

    def payload(self, data: bytes) -> bytes:
        return data[self.offset:self.offset + self.length]


class Ps3Disc:
    """The ``PS3_DISC.SFB`` descriptor of a PS3 disc."""

    def __init__(self, data: bytes, name: str = "<memory>"):
        self.data = data
        self.name = name
        if len(data) < ENTRIES_OFFSET + ENTRY_SIZE:
            raise DiscError("the file is too small to be a PS3 disc descriptor")
        if data[0:4] != MAGIC:
            raise DiscError("bad magic: this is not a .SFB descriptor")

    @property
    def version(self) -> int:
        return struct.unpack_from(">I", self.data, 4)[0]

    def entries(self) -> list[Entry]:
        """The named entries of the table, in file order."""
        out: list[Entry] = []
        offset = ENTRIES_OFFSET
        index = 0
        while offset + ENTRY_SIZE <= len(self.data):
            raw_name = self.data[offset:offset + NAME_SIZE]
            if raw_name == b"\x00" * NAME_SIZE:
                break
            name = raw_name.split(b"\x00", 1)[0].decode("ascii", "replace")
            value_offset, length, reserved_a, reserved_b = \
                struct.unpack_from(">4I", self.data, offset + NAME_SIZE)
            out.append(Entry(index, name, value_offset, length, reserved_a, reserved_b))
            offset += ENTRY_SIZE
            index += 1
        return out

    def get(self, name: str) -> bytes | None:
        """The payload of one entry, or ``None`` when the entry is absent."""
        for entry in self.entries():
            if entry.name == name:
                return entry.payload(self.data)
        return None


def _load(path: str) -> Ps3Disc:
    with open(path, "rb") as handle:
        return Ps3Disc(handle.read(), path)


def cmd_info(disc: Ps3Disc, args: argparse.Namespace) -> int:
    print(f"file       : {disc.name}")
    print(f"size       : {len(disc.data)}")
    print(f"magic      : {disc.data[0:4].decode('ascii', 'replace')}")
    print(f"version    : 0x{disc.version:08X}")
    title = disc.get("TITLE_ID")
    if title is not None:
        print(f"title id   : {title.split(b'\\x00', 1)[0].decode('ascii', 'replace')}")
    print(f"entries    : {len(disc.entries())}")
    return 0


def cmd_entries(disc: Ps3Disc, args: argparse.Namespace) -> int:
    for entry in disc.entries():
        payload = entry.payload(disc.data)
        printable = payload.split(b"\x00", 1)[0]
        try:
            text = printable.decode("ascii")
        except UnicodeDecodeError:
            text = printable.hex()
        print(f"[{entry.index}] {entry.name:16s} offset=0x{entry.offset:04X} "
              f"length=0x{entry.length:04X}  {text!r}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("disc_sfb", help="path to the PS3_DISC.SFB file")
        return p

    add("info", "print the descriptor header").set_defaults(func=cmd_info)
    add("entries", "list the entries of the descriptor table").set_defaults(func=cmd_entries)

    args = parser.parse_args(argv)
    try:
        disc = _load(args.disc_sfb)
    except (OSError, DiscError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return args.func(disc, args)


if __name__ == "__main__":
    raise SystemExit(main())
