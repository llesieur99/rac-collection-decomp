"""Tests for the string references of the code, on a synthetic program."""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import strings_xref  # noqa: E402

STDU = 0xF821FF90
MFLR = 0x7C0802A6
BLR = 0x4E800020

CODE = 0x10000
DATA = 0x200000


def build_elf():
    """An ELF with a code segment and a data section that holds a string."""
    # lis r3, 0x0020 ; addi r3, r3, 0 ; lwz r4, 0(r3) ; blr
    code = b"".join(struct.pack(">I", w) for w in (
        STDU,
        MFLR,
        0x3C600020,      # addis r3, r0, 0x0020
        0x38630000,      # addi  r3, r3, 0
        0x80030000,      # lwz   r4, 0(r3)
        BLR,
    ))
    text = b"the string of the test\x00"
    out = bytearray(0x600)
    out[0:16] = b"\x7fELF\x02\x02\x01\x66" + b"\x00" * 8
    struct.pack_into(">HH", out, 0x10, 2, 0x15)          # ET_EXEC, EM_PPC
    struct.pack_into(">Q", out, 0x18, CODE)              # e_entry
    struct.pack_into(">Q", out, 0x20, 0x40)              # e_phoff
    struct.pack_into(">Q", out, 0x28, 0x100)             # e_shoff
    struct.pack_into(">HHH", out, 0x34, 64, 56, 2)       # e_ehsize, e_phentsize, e_phnum
    struct.pack_into(">HHH", out, 0x3A, 64, 3, 2)        # e_shentsize, e_shnum, e_shstrndx
    # two program headers: the code, and the data
    out[0x40:0x40 + 56] = (struct.pack(">II", 1, 0x5)
                           + struct.pack(">6Q", 0x200, CODE, CODE, len(code), len(code), 0x10000))
    out[0x78:0x78 + 56] = (struct.pack(">II", 1, 0x6)
                           + struct.pack(">6Q", 0x400, DATA, DATA, len(text), len(text), 0x10000))
    out[0x200:0x200 + len(code)] = code
    out[0x400:0x400 + len(text)] = text
    # two section headers: the code, and the data
    def shdr(name, sh_type, flags, addr, offset, size):
        return (struct.pack(">II", name, sh_type) + struct.pack(">QQQQ", flags, addr, offset, size)
                + struct.pack(">II", 0, 0) + struct.pack(">QQ", 1, 0))
    out[0x100:0x100 + 64] = shdr(0, 1, 0x6, CODE, 0x200, len(code))
    out[0x140:0x140 + 64] = shdr(1, 1, 0x2, DATA, 0x400, len(text))
    out[0x180:0x180 + 64] = shdr(2, 3, 0, 0, 0, 0)
    return bytes(out)


class StringsXrefTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.path = os.path.join(self.directory, "synthetic.elf")
        with open(self.path, "wb") as handle:
            handle.write(build_elf())

    def test_the_string_is_found_in_the_data(self):
        from ppu_elf import PpuElf
        with open(self.path, "rb") as handle:
            elf = PpuElf(handle.read(), self.path)
        code, data = strings_xref.segments(elf)
        table = strings_xref.StringTable(data)
        self.assertEqual(len(table), 1)
        self.assertEqual(table.at(DATA), "the string of the test")

    def test_the_code_that_points_at_the_string_is_found(self):
        from ppu_elf import PpuElf
        with open(self.path, "rb") as handle:
            elf = PpuElf(handle.read(), self.path)
        code, data = strings_xref.segments(elf)
        table = strings_xref.StringTable(data)
        found = strings_xref.addresses(code, table, data)
        self.assertEqual(len(found), 1)
        address, entries = list(found.items())[0]
        self.assertEqual(address, CODE + 12)
        self.assertEqual(entries, [(DATA, "the string of the test")])

    def test_a_run_that_is_not_terminated_is_not_a_string(self):
        # a run of printable bytes that does not end on a NUL is not a string
        blob = bytearray(b"abc\x00")
        table = strings_xref.StringTable([(0, bytes(blob))])
        self.assertEqual(len(table), 0)


if __name__ == "__main__":
    unittest.main()
