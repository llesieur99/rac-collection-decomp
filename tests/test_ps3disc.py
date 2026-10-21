"""Tests of the PS3_DISC.SFB reader, on synthetic data only."""

from __future__ import annotations

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from ps3disc import DiscError, ENTRY_SIZE, ENTRIES_OFFSET, NAME_SIZE, Ps3Disc  # noqa: E402


def build_sfb(entries: list[tuple[str, bytes]], payload_at: int = 0x200) -> bytes:
    """Build a .SFB descriptor with named entries and a payload area."""
    data = bytearray(b"\x00" * 0x600)
    data[0:4] = b".SFB"
    struct.pack_into(">I", data, 4, 0x00010000)
    offset = ENTRIES_OFFSET
    for name, payload in entries:
        data[offset:offset + NAME_SIZE] = name.encode("ascii").ljust(NAME_SIZE, b"\x00")
        struct.pack_into(">4I", data, offset + NAME_SIZE,
                         payload_at, len(payload), 0, 0)
        data[payload_at:payload_at + len(payload)] = payload
        payload_at += len(payload)
        offset += ENTRY_SIZE
    return bytes(data)


class Ps3DiscTest(unittest.TestCase):
    def test_parses_the_named_entries(self):
        raw = build_sfb([("HYBRID_FLAG", b"\x00" * 0x20),
                         ("TITLE_ID", b"BCUS-98282\x00")])
        disc = Ps3Disc(raw, "synthetic")
        self.assertEqual(disc.version, 0x00010000)
        self.assertEqual([e.name for e in disc.entries()],
                         ["HYBRID_FLAG", "TITLE_ID"])
        self.assertEqual(disc.get("TITLE_ID").split(b"\x00", 1)[0], b"BCUS-98282")

    def test_stops_at_the_first_empty_name(self):
        raw = build_sfb([("TITLE_ID", b"BCUS-98282\x00")])
        disc = Ps3Disc(raw, "synthetic")
        self.assertEqual(len(disc.entries()), 1)

    def test_rejects_a_bad_magic(self):
        with self.assertRaises(DiscError):
            Ps3Disc(b"NOPE" + b"\x00" * 64, "synthetic")

    def test_rejects_a_truncated_file(self):
        with self.assertRaises(DiscError):
            Ps3Disc(b".SFB", "synthetic")


if __name__ == "__main__":
    unittest.main()
