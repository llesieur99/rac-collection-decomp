"""Build and verify a SHA-256 manifest of a PlayStation 3 disc tree.

The manifest is the provenance record of the target: it pins the bytes of the
retail files that the project works from.  It holds hashes and sizes only, so
it can be published; the files themselves stay in the contributor's workspace.

    python tools/manifest.py build   <root> --out <manifest.tsv>
    python tools/manifest.py verify  <root> --manifest <manifest.tsv>
    python tools/manifest.py compare <root> <other-root>

The manifest is a tab separated file: ``sha256``, ``size``, ``relative path``.
Paths are relative to the scanned root and use forward slashes.

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from typing import Iterator, Sequence

CHUNK = 1 << 20


def iter_files(root: str) -> Iterator[tuple[str, str, int]]:
    """Yield ``(relative path, absolute path, size)`` for every file below root."""
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            absolute = os.path.join(dirpath, name)
            if not os.path.isfile(absolute):
                continue
            relative = os.path.relpath(absolute, root).replace(os.sep, "/")
            yield relative, absolute, os.path.getsize(absolute)


def digest_of(path: str) -> str:
    digester = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            digester.update(chunk)
    return digester.hexdigest()


def build(root: str) -> list[str]:
    """Return the manifest lines of a tree."""
    lines = []
    for relative, absolute, size in iter_files(root):
        lines.append(f"{digest_of(absolute)}\t{size}\t{relative}")
    return lines


def read_manifest(path: str) -> dict[str, tuple[str, int]]:
    """Return the manifest as ``{relative path: (sha256, size)}``."""
    out: dict[str, tuple[str, int]] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            digest, size, relative = line.split("\t", 2)
            out[relative] = (digest, int(size))
    return out


def cmd_build(args: argparse.Namespace) -> int:
    lines = build(args.root)
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        for line in lines:
            out.write(line + "\n")
    print(f"wrote {args.out}: {len(lines)} files")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    expected = read_manifest(args.manifest)
    seen = 0
    bad = 0
    for relative, absolute, size in iter_files(args.root):
        seen += 1
        want = expected.get(relative)
        if want is None:
            print(f"extra   {relative}")
            bad += 1
            continue
        digest, want_size = want
        if size != want_size:
            print(f"size    {relative}: {size} != {want_size}")
            bad += 1
            continue
        if digest_of(absolute) != digest:
            print(f"digest  {relative}")
            bad += 1
    for relative in expected:
        if not os.path.exists(os.path.join(args.root, relative.replace("/", os.sep))):
            print(f"missing {relative}")
            bad += 1
    print(f"{seen} file(s) checked, {bad} problem(s)")
    return 1 if bad else 0


def cmd_compare(args: argparse.Namespace) -> int:
    left = {rel: (digest, size) for rel, size, digest in
            ((rel, size, digest_of(os.path.join(args.left, rel.replace("/", os.sep))))
             for rel, _, _ in iter_files(args.left))}
    right = {rel: (digest, size) for rel, size, digest in
             ((rel, size, digest_of(os.path.join(args.right, rel.replace("/", os.sep))))
              for rel, _, _ in iter_files(args.right))}
    same = 0
    for relative in sorted(set(left) & set(right)):
        if left[relative] == right[relative]:
            same += 1
        else:
            print(f"differs {relative}")
    for relative in sorted(set(left) - set(right)):
        print(f"only in {args.left}: {relative}")
    for relative in sorted(set(right) - set(left)):
        print(f"only in {args.right}: {relative}")
    print(f"{same} identical file(s), "
          f"{len(set(left) & set(right)) - same} differing, "
          f"{len(set(left) ^ set(right))} unpaired")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="write the manifest of a tree")
    p_build.add_argument("root", help="directory to scan")
    p_build.add_argument("--out", required=True, help="manifest to write")
    p_build.set_defaults(func=cmd_build)

    p_verify = sub.add_parser("verify", help="check a tree against a manifest")
    p_verify.add_argument("root", help="directory to check")
    p_verify.add_argument("--manifest", required=True, help="manifest to check against")
    p_verify.set_defaults(func=cmd_verify)

    p_compare = sub.add_parser("compare", help="compare two trees")
    p_compare.add_argument("left", help="first tree")
    p_compare.add_argument("right", help="second tree")
    p_compare.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
