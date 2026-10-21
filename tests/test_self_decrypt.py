"""Tests of the SELF decryptor, on synthetic data only."""

from __future__ import annotations

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from self_decrypt import DecryptError, SelfDecryptor, npdrm_key_from_rap, rap_to_rif  # noqa: E402

MAGIC = b"SCE\x00"
SCE_HEADER_SIZE = 0x20
META_INFO_SIZE = 0x40

# The constants of the chain are not published here: the test only checks
# that the derivation is well defined, so synthetic values are enough.
CONSTANTS = {
    "NP_KLIC_KEY": bytes(range(16)),
    "RAP_KEY": bytes(range(16, 32)),
    "RAP_PBOX": bytes(range(16)),
    "RAP_E1": bytes(range(16)),
    "RAP_E2": bytes(range(16)),
}


def build_container(*, npdrm: bool = False) -> bytes:
    """Build a minimal retail SELF container with a control information."""
    header_size = 0x400
    elf_size = 0x100
    data = bytearray(header_size + elf_size)

    data[0:4] = MAGIC
    struct.pack_into(">I", data, 0x04, 2)            # version
    struct.pack_into(">H", data, 0x08, 0x001C)       # flags
    struct.pack_into(">H", data, 0x0A, 1)            # type
    struct.pack_into(">I", data, 0x0C, 0x200)        # metadata offset
    struct.pack_into(">Q", data, 0x10, header_size)  # header size
    struct.pack_into(">Q", data, 0x18, elf_size)    # elf size
    struct.pack_into(">9Q", data, 0x20,
                     3,        # extension version
                     0x70,     # program identification header
                     0x90,     # elf header
                     0xD0,     # program headers
                     0x190,    # section headers
                     0x290,    # segment table
                     0x300,    # version header
                     0x320,    # control information
                     0x70)     # control information size
    struct.pack_into(">I", data, 0x70 + 0x0C, 4)    # program type, APP

    # the control information: a plaintext capability header, and optionally
    # an NPDRM header
    struct.pack_into(">IIQ", data, 0x320, 1, 0x30, 0)
    if npdrm:
        struct.pack_into(">IIQ", data, 0x350, 3, 0x90, 0)
        struct.pack_into(">4I", data, 0x350 + 16, 0x4E504400, 0, 2, 1)
        data[0x350 + 32:0x350 + 32 + 48] = b"UP9000-TEST_00-TEST0001".ljust(48, b"\x00")

    # the metadata info: a key, its padding, an iv, its padding
    struct.pack_into(">16s", data, 0x200 + SCE_HEADER_SIZE, bytes(range(16)))
    struct.pack_into(">16s", data, 0x200 + SCE_HEADER_SIZE + 0x20, bytes(range(16)))
    return bytes(data)


class SelfDecryptorTest(unittest.TestCase):
    def test_reads_the_header(self):
        container = SelfDecryptor(build_container(), "synthetic")
        self.assertEqual(container.flags, 0x001C)
        self.assertEqual(container.type, 1)
        self.assertEqual(container.metadata_offset, 0x200)
        self.assertEqual(container.header_size, 0x400)
        self.assertEqual(container.elf_size, 0x100)
        self.assertEqual(container.program_type, 4)
        self.assertEqual(container.key_name(), "APP:0x001C")
        self.assertEqual(container.control_header_offset, 0x320)
        self.assertEqual(container.control_header_size, 0x70)

    def test_reads_the_control_information_chain(self):
        container = SelfDecryptor(build_container(), "synthetic")
        self.assertEqual([e["type"] for e in container.control_information], [1])
        self.assertIsNone(container.npdrm_licence)
        self.assertIsNone(container.content_id)

    def test_reads_an_npdrm_header(self):
        container = SelfDecryptor(build_container(npdrm=True), "synthetic")
        self.assertEqual(container.npdrm_licence, 2)
        self.assertEqual(container.content_id, "UP9000-TEST_00-TEST0001")

    def test_rejects_a_file_that_is_not_a_self(self):
        with self.assertRaises(DecryptError):
            SelfDecryptor(b"NOPE" + bytes(256), "synthetic")

    def test_rejects_a_truncated_file(self):
        with self.assertRaises(DecryptError):
            SelfDecryptor(b"SCE\x00", "synthetic")

    def test_the_key_file_must_hold_the_entry(self):
        container = SelfDecryptor(build_container(), "synthetic")
        with self.assertRaises((DecryptError, OSError)):
            container.load_keys("does-not-exist.json")

    def test_rap_to_rif_is_deterministic(self):
        rap = bytes(range(16))
        first = rap_to_rif(rap, CONSTANTS)
        second = rap_to_rif(rap, CONSTANTS)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 16)
        self.assertNotEqual(first, rap)

    def test_rap_to_rif_needs_a_licence_file_of_sixteen_bytes(self):
        with self.assertRaises(DecryptError):
            rap_to_rif(bytes(8), CONSTANTS)

    def test_the_npdrm_key_is_derived_from_the_licence_file(self):
        key = npdrm_key_from_rap(bytes(range(16)), CONSTANTS)
        self.assertEqual(len(key), 16)
        self.assertNotEqual(key, bytes(range(16)))


if __name__ == "__main__":
    unittest.main()
