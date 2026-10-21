"""Tests for the PPU function-boundary scanner, on a synthetic code segment."""

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import ppu_elf  # noqa: E402
import ppu_funcs  # noqa: E402

# stdu r1, -0x70(r1) / mflr r0 / stdu r1, -0x50(r1) / bl +0x20
STDU = 0xF821FF90
MFLR = 0x7C0802A6
BL = 0x48000021


def shdr(name_off, sh_type, flags, addr, offset, size):
    return (struct.pack(">II", name_off, sh_type)
            + struct.pack(">QQQQ", flags, addr, offset, size)
            + struct.pack(">II", 0, 0)
            + struct.pack(">QQ", 1, 0))


def build_elf():
    """An ELF with one executable segment holding a few instructions."""
    code = b"".join(struct.pack(">I", w) for w in (
        0x38600000,      # li r3, 0
        STDU,            # stdu r1, -0x70(r1)
        MFLR,            # mflr r0
        0x4E800020,      # blr
        0x60000000,      # nop
        MFLR,            # mflr r0
        STDU,            # stdu r1, -0x60(r1)
        BL,              # bl +0x20
        0x60000000,      # nop
    ))
    off = 0x200
    out = bytearray(0x400)
    out[0:16] = b"\x7fELF\x02\x02\x01\x66" + b"\x00" * 8
    struct.pack_into(">HH", out, 0x10, 2, 0x15)
    struct.pack_into(">Q", out, 0x18, 0x10000)
    struct.pack_into(">Q", out, 0x20, 0x40)
    struct.pack_into(">Q", out, 0x28, 0x100)
    struct.pack_into(">HHH", out, 0x34, 64, 56, 1)
    struct.pack_into(">HHH", out, 0x3A, 64, 1, 0)
    # one program header: PT_LOAD, read + execute
    out[0x40:0x40 + 56] = (struct.pack(">II", 1, 0x5)
                           + struct.pack(">6Q", off, 0x10000, 0x10000, len(code), len(code), 0x10000))
    out[off:off + len(code)] = code
    return bytes(out)


# -- the code of the second synthetic program ------------------------------
#
# 0x10000  blr                  the end of something
# 0x10004  li r3,0              A: a leaf, called at 0x10050
# 0x10008  blr
# 0x1000C  nop
# 0x10010  stdu r1,-0x70(r1)    B: the frame first
# 0x10014  mflr r0
# 0x10018  stw r0,0x80(r1)
# 0x1001C  bl 0x10044
# 0x10020  nop
# 0x10024  blr
# 0x10028  mflr r0              C: the link register first
# 0x1002C  stdu r1,-0x60(r1)
# 0x10030  stw r0,0x70(r1)
# 0x10034  blr
# 0x10038  stdu r1,-0x50(r1)    D: the frame alone, no link register
# 0x1003C  blr
# 0x10040  nop
# 0x10044  li r3,1              E: the target of the call of B, the flow falls in
# 0x10048  blr
# 0x1004C  nop
# 0x10050  bl 0x10004           the call to A
# 0x10054  nop
PROGRAM = (
    0x4E800020,      # blr
    0x38600000,      # li r3, 0
    0x4E800020,      # blr
    0x60000000,      # nop
    0xF821FF90,      # stdu r1, -0x70(r1)
    0x7C0802A6,      # mflr r0
    0xF8010080,      # stw r0, 0x80(r1)
    0x48000029,      # bl 0x10044
    0x60000000,      # nop
    0x4E800020,      # blr
    0x7C0802A6,      # mflr r0
    0xF821FFA0,      # stdu r1, -0x60(r1)
    0xF8010070,      # stw r0, 0x70(r1)
    0x4E800020,      # blr
    0xF821FFB0,      # stdu r1, -0x50(r1)
    0x4E800020,      # blr
    0x60000000,      # nop
    0x38600001,      # li r3, 1
    0x4E800020,      # blr
    0x60000000,      # nop
    0x4BFFFFB5,      # bl 0x10004
    0x60000000,      # nop
)


def build_program():
    """An ELF whose code segment holds the program above."""
    code = b"".join(struct.pack(">I", w) for w in PROGRAM)
    off = 0x200
    out = bytearray(0x400)
    out[0:16] = b"\x7fELF\x02\x02\x01\x66" + b"\x00" * 8
    struct.pack_into(">HH", out, 0x10, 2, 0x15)
    struct.pack_into(">Q", out, 0x18, 0x10000)
    struct.pack_into(">Q", out, 0x20, 0x40)
    struct.pack_into(">Q", out, 0x28, 0x100)
    struct.pack_into(">HHH", out, 0x34, 64, 56, 1)
    struct.pack_into(">HHH", out, 0x3A, 64, 1, 0)
    out[0x40:0x40 + 56] = (struct.pack(">II", 1, 0x5)
                           + struct.pack(">6Q", off, 0x10000, 0x10000,
                                         len(code), len(code), 0x10000))
    out[off:off + len(code)] = code
    return bytes(out)


class PpuFuncsTest(unittest.TestCase):
    def setUp(self):
        self.elf = ppu_elf.PpuElf(build_elf(), "synthetic")

    def test_prologue_candidates(self):
        addresses = [c.address for c in ppu_funcs.prologue_candidates(self.elf)]
        # the stdu at +4 (followed by mflr) and the stdu at +0x18 (preceded by mflr)
        self.assertEqual(addresses, [0x10004, 0x10018])

    def test_call_targets(self):
        addresses = [c.address for c in ppu_funcs.call_targets(self.elf)]
        self.assertEqual(addresses, [0x1003C])

    def test_catalogue_merges_both(self):
        rows = ppu_funcs.build_catalogue(self.elf)
        table = {address: evidence for address, _kind, evidence in rows}
        self.assertEqual(table[0x10004], "prologue")
        self.assertEqual(table[0x10018], "prologue")
        self.assertEqual(table[0x1003C], "call")


class InstructionTest(unittest.TestCase):
    """The decoding of the instructions the signals rely on."""

    def test_frame(self):
        self.assertTrue(ppu_funcs.is_frame(0xF821FF90))
        self.assertTrue(ppu_funcs.is_frame(0xF821FF11))
        # the frame moves the stack down: the offset is signed
        self.assertFalse(ppu_funcs.is_frame(0xF8210090))
        # a store of another register is not a frame
        self.assertFalse(ppu_funcs.is_frame(0xF8010080))

    def test_link_save(self):
        self.assertTrue(ppu_funcs.is_link_save(0x7C0802A6))
        # the destination register does not matter
        self.assertTrue(ppu_funcs.is_link_save(0x7CA802A6))
        # mtlr is not mflr
        self.assertFalse(ppu_funcs.is_link_save(0x7C0803A6))

    def test_falls_through(self):
        self.assertFalse(ppu_funcs.falls_through(0x4E800020))   # blr
        self.assertFalse(ppu_funcs.falls_through(0x4E800420))   # bctr
        self.assertFalse(ppu_funcs.falls_through(0x48000020))   # b
        self.assertFalse(ppu_funcs.falls_through(0x43000000))   # bc to itself
        self.assertTrue(ppu_funcs.falls_through(0x48000021))    # bl
        self.assertTrue(ppu_funcs.falls_through(0x4E9E0421))    # bnelr
        self.assertTrue(ppu_funcs.falls_through(0x60000000))    # nop
        self.assertTrue(ppu_funcs.falls_through(0x7C0802A6))    # mflr


class WideTest(unittest.TestCase):
    """The wide prologue, the entries, and the rule of confirmation."""

    def setUp(self):
        self.elf = ppu_elf.PpuElf(build_program(), "synthetic")

    def test_prologue_forms(self):
        forms = ppu_funcs.prologue_forms(self.elf)
        # the block starts at the frame, or at the link register when it
        # comes first; the frame alone is a prologue of its own
        self.assertEqual(forms[0x10010], ppu_funcs.PROLOGUE_FRAME_LR)
        self.assertEqual(forms[0x10028], ppu_funcs.PROLOGUE_FRAME_LR)
        self.assertEqual(forms[0x10038], ppu_funcs.PROLOGUE_FRAME)
        # the frame of C is not a prologue of its own: the block started
        # at the link register, one instruction earlier
        self.assertNotIn(0x1002C, forms)
        self.assertNotIn(0x10014, forms)

    def test_entry_candidates(self):
        entries = {c.address for c in ppu_funcs.entry_candidates(self.elf)}
        # the flow cannot fall into them
        self.assertIn(0x10004, entries)
        self.assertIn(0x1000C, entries)
        self.assertIn(0x10028, entries)
        self.assertIn(0x10038, entries)
        # the flow falls into these
        self.assertNotIn(0x10010, entries)
        self.assertNotIn(0x10044, entries)

    def test_call_targets(self):
        calls = {c.address for c in ppu_funcs.call_targets(self.elf)}
        self.assertEqual(calls, {0x10004, 0x10044})

    def test_entry_evidence(self):
        evidence, confirmed = ppu_funcs.entry_evidence(self.elf)
        # A is called and the flow cannot fall into it
        self.assertEqual(evidence[0x10004], ["call", "entry"])
        # B has the prologue and its walk ends on a return
        self.assertIn(0x10010, confirmed)
        self.assertIn("return", evidence[0x10010])
        # C and D have the prologue and are the start of a block
        self.assertIn(0x10028, confirmed)
        self.assertIn(0x10038, confirmed)
        # E is only called: one signal is a candidate, not a function
        self.assertNotIn(0x10044, confirmed)
        self.assertEqual(evidence[0x10044], ["call"])

    def test_catalogue_wide(self):
        rows = ppu_funcs.build_catalogue(self.elf, wide=True)
        table = {address: (evidence, kind) for address, evidence, kind in rows}
        self.assertEqual(table[0x10004][0], "call+entry")
        self.assertEqual(table[0x10004][1], "both")
        self.assertEqual(table[0x10010][0], "frame+lr+return")
        self.assertEqual(table[0x10028][0], "frame+lr+entry")
        self.assertEqual(table[0x10044][0], "call")
        self.assertEqual(table[0x10044][1], "call")


if __name__ == "__main__":
    unittest.main()
