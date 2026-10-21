"""Repository guard: no game data, no console keys, no build output.

The check is structural, not a substitute for reading a diff, but it catches
the mistakes that happen most often: a committed disc image, an extracted
executable, a licence file, a disassembly listing or a build artefact.

It also checks the pinned metadata of the target: ``config/target.json`` must
stay valid JSON, must name the pinned release, and must not carry a hash that
the repository cannot justify.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files and directories that must never be tracked.
FORBIDDEN_NAMES = {
    "source", "disc", "baserom", "pkg", "eboot", "analysis", "gate", "build",
    ".venv", "venv", "__pycache__", "rap", "klic", "dkeys", "ird",
}

FORBIDDEN_SUFFIXES = (
    ".pkg", ".rap", ".klic", ".iso", ".elf", ".bin", ".self", ".sprx", ".prx",
    ".edat", ".sdat", ".o", ".a", ".map", ".dmp", ".core", ".asm", ".lst",
    ".dis", ".gzf", ".gpr", ".png", ".jpg", ".wav", ".at3", ".m4a", ".ogg",
    ".objdump", ".bik", ".xvag", ".bnk", ".sfb",
)

# The console key material and the NPDRM key vault never belong here.
KEY_PATTERNS = (
    re.compile(r"NP_KLIC_KEY\s*="),
    re.compile(r"NP_KLIC_FREE\s*="),
    re.compile(r"RAP_KEY\s*="),
    re.compile(r"rap_to_rif"),
    re.compile(r"NP_RIF_KEY\s*="),
    re.compile(r"SDAT_KEY\s*="),
    re.compile(r"EDAT_KEY"),
    re.compile(r"[0-9A-Fa-f]{64}\s*,\s*\"[0-9A-Fa-f]{64}\""),
)

# Text files that may legitimately contain the words above (documentation).
KEY_EXEMPT = {
    "docs/SELF-FORMAT.md",
    "docs/STATE.md",
    "docs/ROADMAP.md",
    "docs/DISC-PROVENANCE.md",
    "tools/check_repository.py",
}

TEXT_SUFFIXES = (".py", ".md", ".json", ".yml", ".yaml", ".txt", ".cfg", ".toml", "")

# The placeholders that keep the private directories of the workspace in the
# tree.  They hold nothing.
PLACEHOLDERS = {
    "work/lots/.gitkeep",
    "work/analysis/.gitkeep",
}

# The pinned release of the target.
EXPECTED_TITLE_ID = "BCUS98282"
CONTENT_ID_PREFIX = "UP9000-BCUS98282_00-"


def tracked_files() -> list[str]:
    """Return the repository's tracked files.

    The tracked set is the right thing to look at: the local workspace
    holds the game-derived material on purpose, and the guard must not
    punish a contributor for keeping it there.
    """
    try:
        result = subprocess.run(["git", "-C", ROOT, "ls-files"], check=True,
                                capture_output=True, text=True)
        pending = subprocess.run(
            ["git", "-C", ROOT, "ls-files", "--others", "--exclude-standard"],
            check=False, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        result = None
        pending = None
    if result is not None and result.stdout.strip():
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if pending is not None and pending.stdout.strip():
            # Files that are not ignored yet: they would be committed.
            files += [line.strip() for line in pending.stdout.splitlines() if line.strip()]
        return sorted(set(files))
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".venv", "venv")]
        for name in files:
            path = os.path.join(base, name)
            out.append(os.path.relpath(path, ROOT).replace("\\", "/"))
    return sorted(out)


def check_tree() -> list[str]:
    problems = []
    for rel in tracked_files():
        if rel in PLACEHOLDERS:
            continue
        parts = rel.split("/")
        if any(part in FORBIDDEN_NAMES for part in parts[:-1]):
            problems.append(f"game-derived directory in the tree: {rel}")
        if rel.lower().endswith(FORBIDDEN_SUFFIXES):
            problems.append(f"forbidden file type: {rel}")
        if not rel.endswith(TEXT_SUFFIXES):
            continue
        if rel in KEY_EXEMPT:
            continue
        try:
            with open(os.path.join(ROOT, rel), "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        for pattern in KEY_PATTERNS:
            if pattern.search(text):
                problems.append(f"console key material in {rel} (pattern {pattern.pattern})")
                break
    return problems


def check_target() -> list[str]:
    problems = []
    path = os.path.join(ROOT, "config", "target.json")
    if not os.path.exists(path):
        return ["config/target.json is missing"]
    try:
        with open(path, "r", encoding="utf-8") as handle:
            target = json.load(handle)
    except (OSError, ValueError) as exc:
        return [f"config/target.json is not valid JSON: {exc}"]
    if target.get("title_id") != EXPECTED_TITLE_ID:
        problems.append(f"config/target.json: title id is {target.get('title_id')!r}, "
                        f"expected {EXPECTED_TITLE_ID!r}")
    content_id = target.get("content_id")
    if not isinstance(content_id, str) or not content_id.startswith(CONTENT_ID_PREFIX):
        problems.append(f"config/target.json: content id is {content_id!r}, "
                        f"expected a value starting with {CONTENT_ID_PREFIX!r}")
    executables = target.get("executables")
    if not isinstance(executables, list) or not executables:
        problems.append("config/target.json: the executable table is missing")
        return problems
    for entry in executables:
        for field in ("path", "size", "sha256"):
            if field not in entry:
                problems.append(f"config/target.json: an executable misses {field!r}")
        digest = entry.get("sha256", "")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            problems.append(f"config/target.json: {entry.get('path')!r} has no sha256")
    return problems


def check_docs() -> list[str]:
    """Every document the README points at must exist."""
    problems = []
    readme = os.path.join(ROOT, "README.md")
    if not os.path.exists(readme):
        return ["README.md is missing"]
    with open(readme, "r", encoding="utf-8") as handle:
        text = handle.read()
    for match in re.finditer(r"\]\((docs/[A-Za-z0-9_.-]+)\)", text):
        target = os.path.join(ROOT, match.group(1).replace("/", os.sep))
        if not os.path.exists(target):
            problems.append(f"README.md points at a missing document: {match.group(1)}")
    return problems


def main() -> int:
    problems = check_tree() + check_target() + check_docs()
    if problems:
        print("repository guard: FAILED")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("repository guard: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
