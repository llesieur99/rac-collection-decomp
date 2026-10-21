"""Tests of the PPU disassembler, on synthetic words."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from ppu_disasm import decode, signed  # noqa: E402


class DisasmTest(unittest.TestCase):
    def test_the_return(self):
        self.assertEqual(decode(0x4E800020, 0x1000), "blr")
        self.assertEqual(decode(0x4E800420, 0x1000), "bctr")
        self.assertEqual(decode(0x4E800421, 0x1000), "bctrl")
        self.assertEqual(decode(0x60000000, 0x1000), "nop")

    def test_the_frame_of_the_sdk(self):
        # stdu r1, -0x6F(r1) — the frame of a function
        self.assertEqual(decode(0xF821FF91, 0x1000), "stdu r1,-111(r1)")
        # stw r0, 0x10(r1) — the link register is saved
        self.assertEqual(decode(0xF8010080, 0x1000), "stw r0,128(r1)")
        # mflr r0
        self.assertEqual(decode(0x7C0802A6, 0x1000), "mflr r0")
        # mtlr r0
        self.assertEqual(decode(0x7C0803A6, 0x1000), "mtlr r0")
        # mtlr r5
        self.assertEqual(decode(0x7CA903A6, 0x1000), "mtlr r5")

    def test_the_doubleword_load_of_the_sdk(self):
        # ld r0, 0x80(r1) — the link register is restored from the frame
        self.assertEqual(decode(0xE8010080, 0x1000), "ld r0,128(r1)")
        # ld r2, 0x28(r1) — the TOC is restored from the frame
        self.assertEqual(decode(0xE8410028, 0x1000), "ld r2,40(r1)")

    def test_the_branch_to_the_link_register(self):
        self.assertEqual(decode(0x4E800020, 0x1000), "blr")
        self.assertEqual(decode(0x4E9E0421, 0x1000), "bnelr")
        self.assertEqual(decode(0x4E800420, 0x1000), "bctr")

    def test_the_loads_and_the_stores(self):
        # lwz r0, -0x7FC0(r2)
        self.assertEqual(decode(0x80028040, 0x1000), "lwz r0,-32704(r2)")
        # lwz r3, -0x7FC4(r2)
        self.assertEqual(decode(0x8062803C, 0x1000), "lwz r3,-32708(r2)")

    def test_the_branches(self):
        # bl +0x45A4
        self.assertEqual(decode(0x480045A5, 0x1020C), "bl 0x000147B0")
        # bc +0x14
        self.assertEqual(decode(0x41DE0014, 0x147C4), "bc 0x000147D8")

    def test_the_immediates(self):
        # addi r1, r1, 0x70 — the frame is torn down
        self.assertEqual(decode(0x38210070, 0x1024), "addi r1,r1,112")
        # li r4, 0
        self.assertEqual(decode(0x38800000, 0x1024), "li r4,0")
        # cmpwi r0, 0 — the condition register is in the split field of the
        # 64-bit form, where the SCE encodes it in a way this reader does
        # not decode; the SCE's own binutils prints it.
        self.assertEqual(decode(0x2F800000, 0x147C0), "cmpwi r0,0")

    def test_an_unknown_word_is_shown_as_it_is(self):
        self.assertEqual(decode(0x08000000, 0x1000), ".long 0x08000000")

    def test_the_signed_value(self):
        self.assertEqual(signed(0xFF91, 16), -111)
        self.assertEqual(signed(0x0070, 16), 112)


if __name__ == "__main__":
    unittest.main()
