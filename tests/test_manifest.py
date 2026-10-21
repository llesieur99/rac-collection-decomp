"""Tests of the manifest builder and of the tree comparison."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from manifest import build, iter_files, read_manifest, tree_digests  # noqa: E402


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rac-manifest-")
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "sub"))
        with open(os.path.join(self.root, "a.txt"), "wb") as handle:
            handle.write(b"alpha")
        with open(os.path.join(self.root, "sub", "b.bin"), "wb") as handle:
            handle.write(b"\x00\x01\x02")

    def test_iter_files_lists_every_file(self):
        found = sorted(rel for rel, _, _ in iter_files(self.root))
        self.assertEqual(found, ["a.txt", "sub/b.bin"])

    def test_build_writes_a_hash_and_a_size(self):
        lines = build(self.root)
        self.assertEqual(len(lines), 2)
        row = dict((part.split("\t")[2], part) for part in lines)
        digest, size, relative = row["a.txt"].split("\t")
        self.assertEqual(size, "5")
        self.assertEqual(len(digest), 64)
        self.assertEqual(relative, "a.txt")

    def test_manifest_round_trip(self):
        # The manifest is written outside the scanned tree, so that it does
        # not describe itself.
        manifest_path = os.path.join(tempfile.mkdtemp(prefix="rac-manifest-"), "manifest.tsv")
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
            for line in build(self.root):
                handle.write(line + "\n")
        parsed = read_manifest(manifest_path)
        self.assertEqual(sorted(parsed), ["a.txt", "sub/b.bin"])
        self.assertEqual(parsed["a.txt"][1], 5)

    def test_tree_digests_detects_a_change(self):
        before = tree_digests(self.root)
        with open(os.path.join(self.root, "a.txt"), "wb") as handle:
            handle.write(b"ALPHA")
        after = tree_digests(self.root)
        self.assertNotEqual(before["a.txt"], after["a.txt"])
        self.assertEqual(before["sub/b.bin"], after["sub/b.bin"])


if __name__ == "__main__":
    unittest.main()
