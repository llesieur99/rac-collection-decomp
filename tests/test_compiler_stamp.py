"""Tests of the compiler stamp reader, on synthetic data only."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from compiler_stamp import compiler_stamps, library_stamps, module_names  # noqa: E402


class CompilerStampTest(unittest.TestCase):
    def test_finds_the_stamp_of_a_gcc_object(self):
        data = (b"pad\x00GCC: (GNU) 4.1.1 (SDK270, $Rev: 3019 $)\x00pad"
                b"GCC: (GNU) 4.1.1 (SDK270, $Rev: 3019 $)\x00")
        stamps = compiler_stamps(data)
        self.assertEqual(len(stamps), 1)
        self.assertEqual(stamps.most_common(1)[0][1], 2)
        self.assertIn("SDK270", stamps.most_common(1)[0][0])

    def test_finds_nothing_in_a_program_without_a_stamp(self):
        data = b"\x00" * 64 + b"p410001libc\x00" + b"\xff" * 64
        self.assertEqual(compiler_stamps(data), {})

    def test_a_looking_sequence_is_not_a_stamp(self):
        # The noise of an encrypted payload must not be read as a stamp.
        data = b"GCC\x0bJ\xc2\x9f\x37\xa4" + b"\x00" * 32
        self.assertEqual(compiler_stamps(data), {})

    def test_finds_the_library_identification(self):
        data = b"Dinkumware C++ Library, Copyright (c) 1994-2002 by P.J. Plauger\x00"
        found = library_stamps(data)
        self.assertTrue(found)
        self.assertIn("Dinkumware", found.most_common(1)[0][0])

    def test_finds_the_module_names(self):
        data = b"p410001libc\x00p410001libstdc++\x00p410001libfs_stub\x00"
        found = module_names(data)
        self.assertEqual(found["libc"], 1)
        self.assertEqual(found["libstdc++"], 1)
        self.assertEqual(found["libfs_stub"], 1)
        self.assertEqual(sum(found.values()), 3)


if __name__ == "__main__":
    unittest.main()
