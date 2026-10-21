"""Tests of the rebuild consistency check, on synthetic data only."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from rebuild_check import check  # noqa: E402
from test_self_header import build_self  # noqa: E402


class RebuildCheckTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.directory = tempfile.mkdtemp(prefix="rac-rebuild-")
        self.addCleanup(__import__("shutil").rmtree, self.directory, True)
        self.path = os.path.join(self.directory, "test.self")
        with open(self.path, "wb") as handle:
            handle.write(build_self())

    def test_accepts_a_consistent_rebuild(self):
        self.assertEqual(check(self.path), [])

    def test_rejects_a_container_that_is_not_a_self(self):
        path = os.path.join(self.directory, "not.self")
        with open(path, "wb") as handle:
            handle.write(b"NOPE" + b"\x00" * 128)
        with self.assertRaises(Exception):
            check(path)

    def test_rejects_a_truncated_container(self):
        path = os.path.join(self.directory, "short.self")
        with open(path, "wb") as handle:
            handle.write(b"SCE\x00")
        with self.assertRaises(Exception):
            check(path)


if __name__ == "__main__":
    unittest.main()
