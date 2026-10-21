"""Tests for the PS2 reader, the function scanner and the string references.

The data is synthetic: a MIPS ELF of a few hundred bytes, built here, that
holds two functions and one message.  No byte of a game is in the tests.
"""

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import mips_elf  # noqa: E402
import mips_funcs  # noqa: E402
import mips_strings_xref  # noqa: E402

CODE = 0x00100000
DATA = 0x00200040
TEXT = b"the message of the test\x00"

# addiu $sp, $sp, -0x20
PROLOGUE = 0x27BDFFE0
# lui $at, 0x0020
LUI = 0x3C010020
# addiu $v0, $at, 0x0040
ADDIU = 0x24220040
# lw $v0, 0x0040($at)
LOAD = 0x8C220040
# jr $ra
RETURN = 0x03E00008
NOP = 0x00000000

# the first function builds the address and keeps it; the second one loads
# the word at the address, which is the other way the compiler writes it
PROGRAM = (
    PROLOGUE,
    LUI,
    ADDIU,
    RETURN,
    NOP,
    PROLOGUE,
    LUI,
    LOAD,
    RETURN,
    NOP,
)


def shdr(name_off, sh_type, flags, addr, offset, size):
    return (struct.pack("<II", name_off, sh_type)
            + struct.pack("<IIII", flags, addr, offset, size)
            + struct.pack("<II", 0, 0) + struct.pack("<II", 1, 0))


def build_elf():
    """A MIPS ELF with a code section and a data section."""
    code = b"".join(struct.pack("<I", w) for w in PROGRAM)
    names = b"\x00.text\x00.data\x00.shstrtab\x00"
    out = bytearray(0x500)
    out[0:16] = b"\x7fELF\x01\x01\x01\x00" + b"\x00" * 8
    struct.pack_into("<HH", out, 0x10, 2, 8)      # ET_EXEC, EM_MIPS
    struct.pack_into("<I", out, 0x14, 1)          # e_version
    struct.pack_into("<I", out, 0x18, CODE)       # e_entry
    struct.pack_into("<I", out, 0x1C, 0x34)       # e_phoff
    struct.pack_into("<I", out, 0x20, 0x100)      # e_shoff
    struct.pack_into("<HHH", out, 0x28, 52, 32, 2)   # e_ehsize, e_phentsize, e_phnum
    struct.pack_into("<HHH", out, 0x2E, 40, 4, 2)    # e_shentsize, e_shnum, e_shstrndx
    # two program headers: the code, and the data
    out[0x34:0x34 + 32] = (struct.pack("<I", 1)
                           + struct.pack("<6I", 0x200, CODE, CODE, len(code), len(code), 5))
    out[0x54:0x54 + 32] = (struct.pack("<I", 1)
                           + struct.pack("<6I", 0x300, DATA, DATA, len(TEXT), len(TEXT), 5))
    out[0x200:0x200 + len(code)] = code
    out[0x300:0x300 + len(TEXT)] = TEXT
    out[0x400:0x400 + len(names)] = names
    # four section headers: the code, the data, the names, and the names of
    # the sections
    out[0x100:0x100 + 40] = shdr(1, 1, 0x6, CODE, 0x200, len(code))
    out[0x128:0x128 + 40] = shdr(7, 1, 0x2, DATA, 0x300, len(TEXT))
    out[0x150:0x150 + 40] = shdr(13, 3, 0x0, 0, 0x400, len(names))
    out[0x178:0x178 + 40] = shdr(0, 0, 0x0, 0, 0, 0)
    return bytes(out)


class MipsElfTest(unittest.TestCase):
    def setUp(self):
        self.elf = mips_elf.MipsElf(build_elf(), "synthetic")

    def test_the_header_is_read(self):
        self.assertEqual(self.elf.entry, CODE)
        self.assertEqual(self.elf.machine, 8)

    def test_the_sections_are_told_apart(self):
        names = [section.name for section in self.elf.sections()]
        self.assertEqual(len(self.elf.code_sections()), 1)
        self.assertEqual(len(self.elf.data_sections()), 1)
        self.assertIn(".text", names)
        self.assertIn(".data", names)

    def test_a_file_that_is_not_a_mips_elf_is_refused(self):
        with self.assertRaises(mips_elf.ElfError):
            mips_elf.MipsElf(b"not an elf at all", "synthetic")


class MipsFuncsTest(unittest.TestCase):
    def setUp(self):
        self.elf = mips_elf.MipsElf(build_elf(), "synthetic")

    def test_the_prologue_is_found(self):
        addresses = [c.address for c in mips_funcs.prologue_candidates(self.elf)]
        self.assertEqual(addresses, [CODE, CODE + 20])

    def test_the_catalogue_holds_the_two_functions(self):
        rows = mips_funcs.build_catalogue(self.elf)
        self.assertEqual([address for address, _kind, _e in rows], [CODE, CODE + 20])

    def test_the_body_stops_at_the_return(self):
        end, why, body = mips_funcs.function_body(self.elf, CODE)
        self.assertEqual(why, "return")
        # the delay slot of the return belongs to the function
        self.assertEqual(end, CODE + 20)
        self.assertEqual(body, [CODE, CODE + 4, CODE + 8, CODE + 12, CODE + 16])


class MipsStringsXrefTest(unittest.TestCase):
    def setUp(self):
        self.elf = mips_elf.MipsElf(build_elf(), "synthetic")

    def test_the_message_is_found_in_the_data(self):
        table = mips_strings_xref.StringTable(mips_strings_xref.data_of(self.elf))
        self.assertEqual(len(table), 1)
        self.assertEqual(table.at(DATA), "the message of the test")

    def test_the_code_that_points_at_the_message_is_found(self):
        data = mips_strings_xref.data_of(self.elf)
        table = mips_strings_xref.StringTable(data)
        code = [(section.addr, self.elf.section_data(section))
                for section in self.elf.code_sections()]
        found = mips_strings_xref.addresses(code, table, data)
        # the address is built by addiu, and taken by a load: both are found
        self.assertEqual(len(found), 2)
        entries = {address: value for address, value in found.items()}
        self.assertEqual(entries[CODE + 8], [(DATA, "the message of the test")])
        self.assertEqual(entries[CODE + 28], [(DATA, "the message of the test")])

    def test_a_run_that_is_not_terminated_is_not_a_string(self):
        table = mips_strings_xref.StringTable([(0, b"abc\x00")])
        self.assertEqual(len(table), 0)

    def test_a_string_of_pascal_carries_its_length(self):
        blob = b"\x05hello\x00"
        table = mips_strings_xref.StringTable([(0x1000, blob)])
        self.assertEqual(table.at(0x1001), "hello")


if __name__ == "__main__":
    unittest.main()
