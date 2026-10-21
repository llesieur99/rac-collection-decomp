"""Tests of the PARAM.SFO reader, on synthetic data only."""

from __future__ import annotations

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from param_sfo import FMT_INT32, FMT_UTF8, MAGIC, ParamSfo, SfoError  # noqa: E402


def build_sfo(entries: list[tuple[str, int, object]]) -> bytes:
    """Build a PARAM.SFO image from ``(key, format, value)`` rows."""
    key_table = bytearray()
    data_table = bytearray()
    index = bytearray()
    for key, fmt, value in entries:
        key_offset = len(key_table)
        key_table += key.encode("utf-8") + b"\x00"
        data_offset = len(data_table)
        if fmt == FMT_INT32:
            data_table += struct.pack("<i", value)
            length = max_length = 4
        else:
            raw = value.encode("utf-8") + b"\x00"
            data_table += raw
            length = len(raw)
            max_length = length
        index += struct.pack("<HHIII", key_offset, fmt, length, max_length, data_offset)
    header = struct.pack("<5I", MAGIC, 0x00000101, 20, 20 + len(index),
                          len(entries))
    key_table_start = 20 + len(index)
    data_table_start = key_table_start + len(key_table)
    header = struct.pack("<5I", MAGIC, 0x00000101, key_table_start,
                          data_table_start, len(entries))
    return header + bytes(index) + bytes(key_table) + bytes(data_table)


class ParamSfoTest(unittest.TestCase):
    def test_parses_utf8_and_int32(self):
        raw = build_sfo([
            ("TITLE", FMT_UTF8, "Ratchet & Clank Collection"),
            ("TITLE_ID", FMT_UTF8, "BCUS98282"),
            ("VERSION", FMT_UTF8, "02.00"),
            ("BOOTABLE", FMT_INT32, 1),
            ("ATTRIBUTE", FMT_INT32, 135168),
        ])
        sfo = ParamSfo(raw, "synthetic")
        self.assertEqual(sfo.version, 0x00000101)
        self.assertEqual(sfo.index_entry_count, 5)
        self.assertEqual(sfo.title_id, "BCUS98282")
        self.assertEqual(sfo.get("TITLE"), "Ratchet & Clank Collection")
        self.assertEqual(sfo.get("VERSION"), "02.00")
        self.assertEqual(sfo.get("BOOTABLE"), 1)
        self.assertEqual(sfo.get("ATTRIBUTE"), 135168)
        self.assertIsNone(sfo.get("ABSENT"))

    def test_entry_order_is_the_file_order(self):
        raw = build_sfo([("A", FMT_UTF8, "1"), ("B", FMT_UTF8, "2")])
        sfo = ParamSfo(raw, "synthetic")
        self.assertEqual([e.key for e in sfo.entries()], ["A", "B"])
        self.assertEqual([e.index for e in sfo.entries()], [0, 1])

    def test_rejects_a_bad_magic(self):
        with self.assertRaises(SfoError):
            ParamSfo(b"NOPE" + b"\x00" * 64, "synthetic")

    def test_rejects_a_truncated_file(self):
        with self.assertRaises(SfoError):
            ParamSfo(b"\x00" * 4, "synthetic")


if __name__ == "__main__":
    unittest.main()
