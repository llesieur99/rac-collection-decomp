"""Tests for the correspondence between two builds, on a synthetic program.

The test builds the same program twice, at two different addresses, and
checks that the tool matches the functions of the two builds: that is the
whole point of the tool — the address is not the identity.
"""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import build_correspondence  # noqa: E402

STDU = 0xF821FF90
MFLR = 0x7C0802A6
NOP = 0x60000000
BLR = 0x4E800020


def build_elf(base):
    """An ELF with three functions: one calls the second, which calls the third.

    The three functions are twenty bytes long each, and the calls use the
    real encoding of a branch: the displacement is relative to the branch.
    """
    def bl(at, target):
        return 0x48000001 | ((target - at) & 0x03FFFFFC)

    code = b"".join(struct.pack(">I", w) for w in (
        0xF821FFC0,          # stdu r1, -0x40(r1)
        MFLR,                # mflr r0
        bl(base + 0x08, base + 0x14),
        NOP,
        BLR,                 # blr
        0xF821FF90,          # stdu r1, -0x70(r1)
        MFLR,                # mflr r0
        bl(base + 0x1C, base + 0x28),
        NOP,
        BLR,                 # blr
        0xF821FFB0,          # stdu r1, -0x50(r1)
        MFLR,                # mflr r0
        BLR,                 # blr
        NOP,
        NOP,
    ))
    off = 0x200
    out = bytearray(0x400)
    out[0:16] = b"\x7fELF\x02\x02\x01\x66" + b"\x00" * 8
    struct.pack_into(">HH", out, 0x10, 2, 0x15)
    struct.pack_into(">Q", out, 0x18, base)
    struct.pack_into(">Q", out, 0x20, 0x40)
    struct.pack_into(">Q", out, 0x28, 0x100)
    struct.pack_into(">HHH", out, 0x34, 64, 56, 1)
    struct.pack_into(">HHH", out, 0x3A, 64, 1, 0)
    out[0x40:0x40 + 56] = (struct.pack(">II", 1, 0x5)
                           + struct.pack(">6Q", off, base, base, len(code), len(code), 0x10000))
    out[off:off + len(code)] = code
    return bytes(out)


def program(name, blob, directory):
    path = os.path.join(directory, f"{name}.elf")
    with open(path, "wb") as handle:
        handle.write(blob)
    item = build_correspondence.Program(name, path)
    item.analyse()
    return item


class CorrespondenceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.left = program("left", build_elf(0x10000), self.directory)
        self.right = program("right", build_elf(0x20000), self.directory)

    def test_the_three_functions_are_found(self):
        # the wide catalogue sees the first function too: the narrow one
        # only saw the two that are called
        self.assertEqual(len(self.left.functions), 3)
        self.assertEqual(len(self.right.functions), 3)

    def test_the_functions_are_matched_across_the_addresses(self):
        rows, summary = build_correspondence.match(self.left, self.right)
        self.assertEqual(summary["matched"], 3)
        for row in rows:
            self.assertEqual(row["size_a"], row["size_b"])
            self.assertEqual(row["identity"], 1.0)
            self.assertNotEqual(row["address_a"], row["address_b"])

    def test_the_match_keeps_the_order(self):
        rows, _summary = build_correspondence.match(self.left, self.right)
        self.assertEqual([row["address_a"] for row in rows], sorted(
            row["address_a"] for row in rows))
        self.assertEqual([row["address_b"] for row in rows], sorted(
            row["address_b"] for row in rows))

    def test_a_branch_displacement_is_not_an_immediate(self):
        # the displacement of a branch is an address: it must not enter the
        # signature, or the two builds would never match
        branch = 0x4800001D          # bl +0x1C
        self.assertEqual(build_correspondence.immediate(branch), 0)
        self.assertEqual(build_correspondence.token(branch), ("b", 1))
        self.assertEqual(build_correspondence.registers(branch), ())


class SignatureTest(unittest.TestCase):
    def test_the_signature_ignores_the_immediates_that_are_addresses(self):
        self.assertEqual(build_correspondence.immediate(0x3C600000), 0)   # li r3, 0
        self.assertEqual(build_correspondence.immediate(0x38600100), 256)  # li r3, 0x100

    def test_the_registers_of_an_extended_instruction(self):
        # mflr r0
        self.assertEqual(build_correspondence.registers(0x7C0802A6), (0, 0, 0))
        self.assertEqual(build_correspondence.token(0x7C0802A6), ("x", 339))

    def test_the_identity_counts_the_instructions_that_are_the_same(self):
        self.assertEqual(build_correspondence.identity([1, 2, 3], [1, 2, 4]), 2 / 3)
        self.assertEqual(build_correspondence.identity([], []), 0.0)


if __name__ == "__main__":
    unittest.main()
