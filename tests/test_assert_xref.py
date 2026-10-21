"""Tests for the assert cross-reference, on a synthetic program."""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import assert_xref  # noqa: E402
from ppu_elf import PpuElf  # noqa: E402
from strings_xref import StringTable, segments  # noqa: E402

STDU = 0xF821FFC0
MFLR = 0x7C0802A6
BLR = 0x4E800020
NOP = 0x60000000

CODE = 0x10000
DATA = 0x200000
MESSAGE = 0x218000          # a message whose low half has its top bit set

FILE_NAME = b"j:/Ratchet/game/hud.cpp\x00"
WHOLE_MESSAGE = b"j:/Ratchet/game/other.cpp:91 p != NULL\x00"


def build_elf():
    """An ELF with two functions that assert, and the strings they use."""
    # function A: the file, the line, and the condition
    code = b"".join(struct.pack(">I", w) for w in (
        STDU,            # stdu r1, -0x40(r1)
        MFLR,            # mflr r0
        0x3C600020,      # addis r3, r0, 0x0020    the file, at 0x200000
        0x38630000,      # addi  r3, r3, 0
        0x38A0002A,      # li    r5, 42            the line
        0x48000025,      # bl    0x10038           the handler
        NOP,
        BLR,
        # function B: one message, the low half of its address is negative
        STDU,
        MFLR,
        0x3C600022,      # addis r3, r0, 0x0022    the message, at 0x218000
        0x38638000,      # addi  r3, r3, 0x8000
        0x48000009,      # bl    0x10038
        NOP,
        BLR,
        # the handler
        STDU,
        MFLR,
        BLR,
    ))
    data = bytearray(MESSAGE + len(WHOLE_MESSAGE) - DATA)
    data[0:len(FILE_NAME)] = FILE_NAME
    data[MESSAGE - DATA:MESSAGE - DATA + len(WHOLE_MESSAGE)] = WHOLE_MESSAGE

    out = bytearray(0x400 + len(data))
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
    out[0x78:0x78 + 56] = (struct.pack(">II", 1, 0x2)
                           + struct.pack(">6Q", 0x400, DATA, DATA, len(data), len(data), 0x10000))
    out[0x200:0x200 + len(code)] = code
    out[0x400:0x400 + len(data)] = bytes(data)

    def shdr(name, sh_type, flags, addr, offset, size):
        return (struct.pack(">II", name, sh_type) + struct.pack(">QQQQ", flags, addr, offset, size)
                + struct.pack(">II", 0, 0) + struct.pack(">QQ", 1, 0))
    out[0x100:0x100 + 64] = shdr(0, 1, 0x6, CODE, 0x200, len(code))
    out[0x140:0x140 + 64] = shdr(1, 1, 0x2, DATA, 0x400, len(data))
    out[0x180:0x180 + 64] = shdr(2, 3, 0, 0, 0, 0)
    return bytes(out)


class TrackerTest(unittest.TestCase):
    """The register values the code builds."""

    def setUp(self):
        self.tracker = assert_xref.Tracker()

    def test_the_high_half_ignores_the_value_of_r0(self):
        # addis r3, r0, 0x1234 puts 0x12340000 in r3
        self.tracker.step(0x3C601234)
        self.assertEqual(self.tracker.value(3), 0x12340000)

    def test_the_low_half_is_added_with_its_sign(self):
        # lis r3, 0x0022 ; addi r3, r3, 0x8000 : the address is 0x218000
        self.tracker.step(0x3C600022)
        self.tracker.step(0x38638000)
        self.assertEqual(self.tracker.value(3), 0x218000)

    def test_a_store_does_not_change_the_registers(self):
        self.tracker.step(0x3C600020)
        self.tracker.step(0xF8010020)          # std r0, 0x20(r1)
        self.assertEqual(self.tracker.value(3), 0x200000)

    def test_a_move_is_followed(self):
        self.tracker.step(0x3C600020)
        self.tracker.step(0x7C832378)          # mr r4, r3
        self.assertEqual(self.tracker.value(4), 0x200000)


class ConditionalBranchTest(unittest.TestCase):
    """The displacement of the conditional branch."""

    def test_the_displacement_is_a_byte_offset(self):
        # bc +0x78 : the target is 0x78 bytes further
        self.assertEqual(assert_xref.conditional_target(0x41820078, 0x1000), 0x1078)

    def test_the_displacement_is_signed(self):
        # bc -0x10 : the target is 0x10 bytes back
        self.assertEqual(assert_xref.conditional_target(0x4182FFF0, 0x1000), 0x0FF0)


class AssertXrefTest(unittest.TestCase):
    """The messages the tool reads, and the table it writes."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.path = os.path.join(self.directory, "synthetic.elf")
        with open(self.path, "wb") as handle:
            handle.write(build_elf())
        with open(self.path, "rb") as handle:
            self.elf = PpuElf(handle.read(), self.path)
        _code, data = segments(self.elf)
        self.strings = StringTable(data)
        self.loaded = [(low, low + len(blob)) for low, blob in data]

    def test_the_two_strings_are_read(self):
        self.assertEqual(self.strings.at(DATA),
                         "j:/Ratchet/game/hud.cpp")
        self.assertEqual(self.strings.at(MESSAGE),
                         "j:/Ratchet/game/other.cpp:91 p != NULL")

    def test_the_calls_are_found(self):
        found = list(assert_xref.calls(self.elf))
        self.assertEqual([call.address for call in found], [0x10014, 0x10030])
        self.assertEqual([call.target for call in found], [0x10038, 0x10038])

    def test_the_file_and_the_line_are_read(self):
        found = list(assert_xref.calls(self.elf))
        first = assert_xref.classify(found[0], self.strings, self.loaded)
        self.assertIsNotNone(first)
        self.assertEqual(first.file, "j:/Ratchet/game/hud.cpp")
        self.assertEqual(first.line, "42")
        self.assertEqual(first.message, "j:/Ratchet/game/hud.cpp:42")

    def test_the_whole_message_is_read(self):
        found = list(assert_xref.calls(self.elf))
        second = assert_xref.classify(found[1], self.strings, self.loaded)
        self.assertIsNotNone(second)
        self.assertEqual(second.message,
                         "j:/Ratchet/game/other.cpp:91 p != NULL")

    def test_a_call_without_a_message_is_not_an_assert(self):
        call = assert_xref.Call(0x10000, 0x10038, {3: 0x300000, 5: 42})
        self.assertIsNone(assert_xref.classify(call, self.strings, self.loaded))

    def test_the_table_is_written_and_is_the_same_twice(self):
        out = os.path.join(self.directory, "asserts.tsv")
        for _run in range(2):
            code = assert_xref.main([self.path, "--out", out])
            self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertEqual(lines[0].split("\t")[:3],
                         ["program", "address", "message"])
        self.assertEqual(len(lines), 3)
        self.assertIn("j:/Ratchet/game/hud.cpp:42", lines[1])
        self.assertIn("j:/Ratchet/game/other.cpp:91 p != NULL", lines[2])

    def test_the_table_names_the_function_that_holds_the_call(self):
        out = os.path.join(self.directory, "asserts.tsv")
        assert_xref.main([self.path, "--out", out])
        with open(out, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        # the first assert is in the function that starts at 0x10000
        self.assertIn("\t0x00010000\t", lines[1])
        # the second one is in the function that starts at 0x10020
        self.assertIn("\t0x00010020\t", lines[2])


if __name__ == "__main__":
    unittest.main()
