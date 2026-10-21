"""Reader for the PlayStation 3 ``PARAM.SFO`` metadata file.

The file is a flat table of typed values with a separate string table for the
keys.  The format is documented in ``docs/PARAM-SFO.md``.

    python tools/param_sfo.py info     <PARAM.SFO>
    python tools/param_sfo.py list     <PARAM.SFO>
    python tools/param_sfo.py get      <PARAM.SFO> <KEY>
    python tools/param_sfo.py to-json  <PARAM.SFO>

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass
from typing import Any, Sequence

MAGIC = 0x46535000  # "\0PSF"

# Data formats, as they appear in the index table.
FMT_UTF8 = 0x0004
FMT_UTF8_SPECIAL = 0x0204
FMT_INT32 = 0x0404

FORMAT_NAMES = {
    FMT_UTF8: "utf8",
    FMT_UTF8_SPECIAL: "utf8-special",
    FMT_INT32: "int32",
}

# The value types that carry an integer rather than a string.
INT_FORMATS = (FMT_INT32,)


class SfoError(Exception):
    """The file is not a readable PARAM.SFO."""


@dataclass(frozen=True)
class Entry:
    """One row of the index table."""

    index: int
    key: str
    fmt: int
    data_length: int
    data_max_length: int
    data_offset: int
    value: Any

    @property
    def format_name(self) -> str:
        return FORMAT_NAMES.get(self.fmt, f"0x{self.fmt:04X}")


class ParamSfo:
    """A parsed ``PARAM.SFO``."""

    def __init__(self, data: bytes, name: str = "<memory>"):
        self.data = data
        self.name = name
        if len(data) < 20:
            raise SfoError("the file is too small to be a PARAM.SFO")
        (self.magic, self.version, self.key_table_start,
         self.data_table_start, self.index_entry_count) = struct.unpack_from("<5I", data, 0)
        if self.magic != MAGIC:
            raise SfoError("bad magic: this is not a PARAM.SFO")
        if self.version >> 8 != 1:
            raise SfoError(f"unsupported version 0x{self.version:08X}")
        self._entries: list[Entry] | None = None

    # -- table -------------------------------------------------------------
    def entries(self) -> list[Entry]:
        """The index table, in file order."""
        if self._entries is not None:
            return self._entries
        out: list[Entry] = []
        for i in range(self.index_entry_count):
            off = 20 + i * 16
            if off + 16 > len(self.data):
                raise SfoError(f"the index table is truncated at entry {i}")
            key_offset, fmt, data_length, data_max, data_offset = \
                struct.unpack_from("<HHIII", self.data, off)
            key = self._key(key_offset)
            value = self._value(fmt, data_offset, data_length)
            out.append(Entry(i, key, fmt, data_length, data_max, data_offset, value))
        self._entries = out
        return out

    def get(self, key: str) -> Any:
        """The value of one key, or ``None`` when the key is absent."""
        for entry in self.entries():
            if entry.key == key:
                return entry.value
        return None

    def as_dict(self) -> dict[str, Any]:
        return {entry.key: entry.value for entry in self.entries()}

    # -- decoding ----------------------------------------------------------
    def _key(self, key_offset: int) -> str:
        start = self.key_table_start + key_offset
        if not 0 <= start < len(self.data):
            raise SfoError(f"the key offset 0x{key_offset:X} is out of range")
        end = self.data.find(b"\x00", start)
        if end < 0:
            raise SfoError("the key table is not terminated")
        return self.data[start:end].decode("utf-8", "replace")

    def _value(self, fmt: int, data_offset: int, data_length: int) -> Any:
        start = self.data_table_start + data_offset
        if fmt in INT_FORMATS:
            if start + 4 > len(self.data):
                raise SfoError("the data table is truncated")
            return struct.unpack_from("<i", self.data, start)[0]
        end = start + data_length
        if end > len(self.data):
            raise SfoError("the data table is truncated")
        raw = self.data[start:end]
        return raw.split(b"\x00", 1)[0].decode("utf-8", "replace")

    # -- identity ----------------------------------------------------------
    @property
    def title_id(self) -> str | None:
        value = self.get("TITLE_ID")
        return value if isinstance(value, str) else None

    @property
    def content_id(self) -> str | None:
        value = self.get("CONTENT_ID")
        return value if isinstance(value, str) else None


def _load(path: str) -> ParamSfo:
    with open(path, "rb") as handle:
        return ParamSfo(handle.read(), path)


def cmd_info(sfo: ParamSfo, args: argparse.Namespace) -> int:
    print(f"file         : {sfo.name}")
    print(f"size         : {len(sfo.data)}")
    print(f"version      : 0x{sfo.version:08X}")
    print(f"key table    : 0x{sfo.key_table_start:X}")
    print(f"data table   : 0x{sfo.data_table_start:X}")
    print(f"entries      : {sfo.index_entry_count}")
    print(f"title id     : {sfo.title_id}")
    print(f"content id   : {sfo.content_id}")
    return 0


def cmd_list(sfo: ParamSfo, args: argparse.Namespace) -> int:
    for entry in sfo.entries():
        print(f"[{entry.index:2d}] {entry.key:28s} {entry.format_name:12s} "
              f"len={entry.data_length:<5d} max={entry.data_max_length:<5d} "
              f"off=0x{entry.data_offset:04X}  {entry.value}")
    return 0


def cmd_get(sfo: ParamSfo, args: argparse.Namespace) -> int:
    value = sfo.get(args.key)
    if value is None:
        print(f"error: no key named {args.key}", file=sys.stderr)
        return 1
    print(value)
    return 0


def cmd_to_json(sfo: ParamSfo, args: argparse.Namespace) -> int:
    print(json.dumps(sfo.as_dict(), indent=2, ensure_ascii=False))
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
        p.add_argument("param_sfo", help="path to the PARAM.SFO file")
        return p

    add("info", "print the header and the identity fields").set_defaults(func=cmd_info)
    add("list", "list every entry of the index table").set_defaults(func=cmd_list)

    p_get = add("get", "print the value of one key")
    p_get.add_argument("key", help="key to read")
    p_get.set_defaults(func=cmd_get)

    add("to-json", "print the table as JSON").set_defaults(func=cmd_to_json)

    args = parser.parse_args(argv)
    try:
        sfo = _load(args.param_sfo)
    except (OSError, SfoError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return args.func(sfo, args)


if __name__ == "__main__":
    raise SystemExit(main())
