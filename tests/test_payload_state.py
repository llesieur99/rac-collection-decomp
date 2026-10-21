"""Tests of the payload state reader, on synthetic data only."""

from __future__ import annotations

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from payload_state import ENCRYPTED, entropy, segments_of  # noqa: E402
from self_header import Self  # noqa: E402
from test_self_header import build_self  # noqa: E402


class EntropyTest(unittest.TestCase):
    def test_constant_data_has_no_entropy(self):
        self.assertAlmostEqual(entropy(b"\x00" * 4096), 0.0, places=6)

    def test_every_byte_value_has_eight_bits(self):
        self.assertAlmostEqual(entropy(bytes(range(256))), 8.0, places=6)

    def test_a_half_and_a_half_has_one_bit(self):
        self.assertAlmostEqual(entropy(b"\x00" * 100 + b"\xff" * 100), 1.0, places=6)


class PayloadStateTest(unittest.TestCase):
    def test_reads_the_segments_of_the_elf(self):
        container = Self(build_self(), "synthetic")
        elf = container.rebuild_elf()
        segments = segments_of(elf)
        self.assertEqual(len(segments), 1)
        ptype, off, vaddr, size = segments[0]
        self.assertEqual(ptype, 1)
        self.assertEqual(off, 0)
        self.assertEqual(vaddr, 0x10000)

    def test_a_cipher_payload_measures_above_the_threshold(self):
        # 4 KiB of every byte value repeated is not the payload of a program,
        # but it measures like one.
        block = bytes(range(256)) * 16
        self.assertGreaterEqual(entropy(block), ENCRYPTED)


if __name__ == "__main__":
    unittest.main()
