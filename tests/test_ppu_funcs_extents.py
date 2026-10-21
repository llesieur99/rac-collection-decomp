"""Tests for the repair of the truncated extents.

The tests are on a synthetic code segment, like the ones of
``tests/test_ppu_funcs.py``.

Three things are checked:

* the walk follows the **conditional branch**, whose opcode is 16 — the
  test of the repository never matched it, and matched the loads with an
  offset instead;
* the walk does **not** stop on a target of a call that the control flow
  falls into: a label inside a function is not an entry;
* the bound of the walk holds the entries of the functions.
"""

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import ppu_elf  # noqa: E402
import ppu_funcs  # noqa: E402

# The first synthetic program: a function with a conditional branch.
#
# 0x10000  stdu r1,-0x70(r1)   F: the frame
# 0x10004  mflr r0
# 0x10008  cmpwi cr0,r3,0
# 0x1000C  bc 0x10014          the conditional branch: the "then" block
# 0x10010  b 0x10018           the "else" path jumps over the "then" block
# 0x10014  li r3,1             the "then" block
# 0x10018  blr
PROGRAM_BRANCH = (
    0xF821FF90,      # stdu r1, -0x70(r1)
    0x7C0802A6,      # mflr r0
    0x2F800000,      # cmpwi cr0, r3, 0
    0x40000008,      # bc 0x10014
    0x48000008,      # b 0x10018
    0x38600001,      # li r3, 1
    0x4E800020,      # blr
)

# The second synthetic program: a label inside a function, that the
# control flow branches to and that a call names as well.
#
# 0x10000  stdu r1,-0x70(r1)   F: the frame
# 0x10004  mflr r0
# 0x10008  cmpwi cr0,r3,0
# 0x1000C  bc 0x10014          the branch lands on the label
# 0x10010  bl 0x10014          and a call names it as well
# 0x10014  li r3,2             the label
# 0x10018  blr
PROGRAM_LABEL = (
    0xF821FF90,      # stdu r1, -0x70(r1)
    0x7C0802A6,      # mflr r0
    0x2F800000,      # cmpwi cr0, r3, 0
    0x40000008,      # bc 0x10014
    0x48000005,      # bl 0x10014
    0x38600002,      # li r3, 2
    0x4E800020,      # blr
)


def build_program(words):
    """An ELF whose code segment holds the words above."""
    code = b"".join(struct.pack(">I", w) for w in words)
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


class ConditionalBranchTest(unittest.TestCase):
    """The walk follows the conditional branch, whose opcode is 16."""

    def setUp(self):
        self.elf = ppu_elf.PpuElf(build_program(PROGRAM_BRANCH), "synthetic")

    def test_conditional_target(self):
        # the displacement of the conditional branch is a signed value in
        # the bits 2-15, counted in bytes
        self.assertEqual(ppu_funcs.conditional_target(0x40000008, 0x1000C),
                         0x10014)
        # a branch of the retail code: 0x41DE0014 at 0x147C4
        self.assertEqual(ppu_funcs.conditional_target(0x41DE0014, 0x147C4),
                         0x147D8)

    def test_the_walk_follows_the_conditional_branch(self):
        end, why, body = ppu_funcs.function_body(self.elf, 0x10000)
        # the walk reaches the "then" block and ends on its return
        self.assertEqual(why, "return")
        self.assertIn(0x10014, body)
        self.assertEqual(end, 0x1001C)

    def test_a_load_is_not_a_branch(self):
        # the load with an offset has the opcode 32: the test of the
        # repository read it as a conditional branch and followed the
        # "target" of the load, which is nothing
        end, why, body = ppu_funcs.function_body(self.elf, 0x10000)
        self.assertNotIn(0x10008, [address for address in body
                                    if address > 0x10014])


class LocalLabelTest(unittest.TestCase):
    """A target of a call that the control flow falls into is a label."""

    def setUp(self):
        self.elf = ppu_elf.PpuElf(build_program(PROGRAM_LABEL), "synthetic")
        self.calls = {c.address for c in ppu_funcs.call_targets(self.elf)}
        self.entries = {c.address for c in
                        ppu_funcs.entry_candidates(self.elf)}

    def test_the_label_is_not_an_entry(self):
        self.assertIn(0x10014, self.calls)
        # the flow falls into it: the call at 0x10010 falls through
        self.assertNotIn(0x10014, self.entries)

    def test_the_bound_of_the_repository_stops_on_the_label(self):
        end, why, _body = ppu_funcs.function_body(
            self.elf, 0x10000, entries=self.calls)
        self.assertEqual(why, "entry")
        self.assertEqual(end, 0x10014)

    def test_the_bound_of_the_criterion_goes_through_the_label(self):
        bound = ppu_funcs.walk_bound(set(), self.calls, self.entries)
        self.assertNotIn(0x10014, bound)
        end, why, _body = ppu_funcs.function_body(self.elf, 0x10000,
                                                  entries=bound)
        self.assertEqual(why, "return")
        self.assertEqual(end, 0x1001C)

    def test_walk_bound(self):
        calls = {0x10014}
        entries = {0x10014}
        # the bound holds the confirmed functions and the targets of a
        # call that the flow cannot fall into
        self.assertEqual(ppu_funcs.walk_bound({0x10000}, calls, entries),
                         {0x10000, 0x10014})
        self.assertEqual(ppu_funcs.walk_bound({0x10000}, calls, set()),
                         {0x10000})


if __name__ == "__main__":
    unittest.main()
