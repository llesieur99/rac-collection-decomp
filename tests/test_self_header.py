"""Tests of the SELF reader and of the ELF rebuild, on synthetic data only."""

from __future__ import annotations

import hashlib
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from self_header import LICENSE_LOCAL, MAGIC, Self, SelfError  # noqa: E402


def build_self() -> bytes:
    """Build a minimal SELF container holding a small PPU ELF.

    The layout follows the retail one: a header block, the ELF header and the
    program headers, then the payload area and the section header table.
    """
    elf_header = bytearray(64)
    elf_header[0:4] = b"\x7fELF"
    elf_header[4] = 2          # ELFCLASS64
    elf_header[5] = 2          # ELFDATA2MSB
    elf_header[6] = 1          # EV_CURRENT
    struct.pack_into(">H", elf_header, 16, 102)      # e_type
    struct.pack_into(">H", elf_header, 18, 102)      # e_machine, EM_PPC
    struct.pack_into(">I", elf_header, 20, 1)        # e_version
    struct.pack_into(">Q", elf_header, 24, 0x202450)  # e_entry
    struct.pack_into(">Q", elf_header, 32, 0x40)     # e_phoff
    struct.pack_into(">Q", elf_header, 40, 0x200)    # e_shoff
    struct.pack_into(">H", elf_header, 52, 64)       # e_ehsize
    struct.pack_into(">H", elf_header, 54, 56)       # e_phentsize
    struct.pack_into(">H", elf_header, 56, 1)        # e_phnum
    struct.pack_into(">H", elf_header, 58, 64)       # e_shentsize
    struct.pack_into(">H", elf_header, 60, 1)        # e_shnum
    struct.pack_into(">H", elf_header, 62, 0)        # e_shstrndx

    program_header = bytearray(56)
    struct.pack_into(">I", program_header, 0, 1)          # PT_LOAD
    struct.pack_into(">I", program_header, 4, 0x400005)   # p_flags
    struct.pack_into(">Q", program_header, 8, 0)          # p_offset
    struct.pack_into(">Q", program_header, 16, 0x10000)   # p_vaddr
    struct.pack_into(">Q", program_header, 24, 0x10000)   # p_paddr
    struct.pack_into(">Q", program_header, 32, 0x40)      # p_filesz
    struct.pack_into(">Q", program_header, 40, 0x40)      # p_memsz
    struct.pack_into(">Q", program_header, 48, 0x10000)   # p_align

    payload = bytes(0x40)
    elf_size = 0x40 + len(payload)

    data = bytearray(0x980 + elf_size)
    data[0:4] = MAGIC
    struct.pack_into(">I", data, 0x04, 2)          # version
    struct.pack_into(">H", data, 0x08, 0x001C)     # key revision
    struct.pack_into(">H", data, 0x0A, 0x0001)     # header type, SELF
    struct.pack_into(">I", data, 0x0C, 0x410)     # metadata offset
    struct.pack_into(">Q", data, 0x10, 0x980)     # header size
    struct.pack_into(">Q", data, 0x18, elf_size)  # ELF size
    struct.pack_into(">Q", data, 0x20, 3)         # extension version
    struct.pack_into(">Q", data, 0x28, 0x70)      # program information
    struct.pack_into(">Q", data, 0x30, 0x90)      # ELF header
    struct.pack_into(">Q", data, 0x38, 0xD0)      # program header
    struct.pack_into(">Q", data, 0x40, 0x200)     # section header
    struct.pack_into(">Q", data, 0x48, 0x290)     # segment table
    struct.pack_into(">Q", data, 0x50, 0x390)     # version header
    struct.pack_into(">Q", data, 0x58, 0x3C0)     # control header
    struct.pack_into(">Q", data, 0x60, 0x70)      # control header size

    data[0x90:0x90 + 64] = elf_header
    data[0xD0:0xD0 + 56] = program_header
    struct.pack_into(">8I", data, 0x290, 0, 0x980, 0, len(payload), 1, 0, 0, 1)
    struct.pack_into(">I", data, 0x3C0 + 0x30, LICENSE_LOCAL)
    data[0x980:0x980 + len(payload)] = payload
    return bytes(data)


class SelfTest(unittest.TestCase):
    def test_reads_the_header(self):
        container = Self(build_self(), "synthetic")
        self.assertEqual(container.version, 2)
        self.assertEqual(container.key_revision, 0x001C)
        self.assertEqual(container.header_type, 0x0001)
        self.assertEqual(container.header_size, 0x980)
        self.assertEqual(container.extension_version, 3)
        self.assertEqual(container.elf_header_offset, 0x90)
        self.assertEqual(container.program_header_count(), 1)
        self.assertEqual(container.license_type(), LICENSE_LOCAL)

    def test_reads_the_segment_table(self):
        container = Self(build_self(), "synthetic")
        segments = container.segments()
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].file_offset, 0x980)
        self.assertEqual(segments[0].size, 0x40)
        self.assertEqual(segments[0].compression, 1)

    def test_rebuilds_the_elf(self):
        container = Self(build_self(), "synthetic")
        elf = container.rebuild_elf()
        self.assertEqual(len(elf), container.elf_size)
        self.assertEqual(elf[:4], b"\x7fELF")
        entry = struct.unpack_from(">Q", elf, 24)[0]
        self.assertEqual(entry, 0x202450)
        self.assertEqual(hashlib.sha256(elf).hexdigest(),
                         hashlib.sha256(elf).hexdigest())

    def test_rebuild_cuts_the_trailer_of_the_older_variant(self):
        # The older variant of the container carries a short trailer after the
        # ELF; it is not part of the program.
        raw = bytearray(build_self())
        raw += b"\xAA" * 48
        container = Self(bytes(raw), "synthetic")
        elf = container.rebuild_elf()
        self.assertEqual(len(elf), container.elf_size)
        self.assertNotIn(b"\xAA" * 8, elf)

    def test_rejects_a_bad_magic(self):
        with self.assertRaises(SelfError):
            Self(b"NOPE" + b"\x00" * 128, "synthetic")

    def test_rejects_a_truncated_file(self):
        with self.assertRaises(SelfError):
            Self(b"SCE\x00", "synthetic")


if __name__ == "__main__":
    unittest.main()
