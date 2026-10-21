"""Match the functions of two builds of the same game.

The collection and the standalone PlayStation Network title of a game are two
builds of the same program.  Their functions sit at different addresses, so
an address says nothing about the identity of a function: only the *body* of
the function does.

The tool therefore gives every function a **signature** that does not depend
on where the function sits, and matches the signatures.  Four signatures are
computed, from the strictest to the loosest, and the strictest one that
matches is the one that is reported:

``ops+imm``
    the sequence of the instructions, with the registers and the immediates.
    The strictest: it fails as soon as the two builds differ by one bit in
    one operand.
``ops``
    the same, without the immediates.  The immediates of the code hold the
    offsets of the data, and the data of the two builds does not sit at the
    same place.
``ops+calls``
    the instructions, plus the identity of each callee.  Two functions that
    call the same things in the same order are the same function.
``shape``
    the opcodes alone, with neither the registers nor the immediates.  The
    loosest: it survives a change of the register allocation.

The identity of a callee is the *shape* of the callee, one level deep.  The
shape of the callee is stable across the builds even when the immediates of
the callee are not, and it does not depend on the order of the functions in
the program — which the address of a function does.

    python tools/build_correspondence.py \\
        --collection-dir work/decrypted \\
        --standalone RC1=NPUA80643=work/remaster/rc1/rc1remaster.elf \\
        --standalone RC2=NPUA80644=work/decrypted-standalone/gc.elf \\
        --standalone RC3=NPUA80645=work/decrypted-standalone/uya.elf \\
        --out config/correspondence.tsv

The tool writes two files:

* ``config/correspondence.tsv`` — the matched functions, one row per pair;
* ``config/builds.tsv`` — the builds themselves, and what was measured of
  them.

Nothing of the game is written: only addresses, sizes and hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402
from ppu_funcs import BRANCH_LINK, BRANCH_MASK, branch_target  # noqa: E402
from ppu_funcs import build_catalogue, function_body, text_code  # noqa: E402

# The programs of the collection, and the file of each of them.
COLLECTION = (
    ("EBOOT", "eboot.elf"),
    ("RC1", "RC1.elf"),
    ("RC2", "RC2.elf"),
    ("RC3", "RC3.elf"),
)

# The signatures, from the strictest to the loosest.
SIGNATURES = ("ops+imm", "ops", "ops+calls", "shape")

# The opcodes of the D-form: an immediate, a destination, a first operand.
D_FORM = frozenset({
    7, 8, 10, 11, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29,
    32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45,
    46, 47, 48, 49, 50, 51, 52, 53, 58, 62,
})


def token(word: int) -> tuple:
    """The family of an instruction, without its operands.

    The families are read per opcode, because the same bits mean different
    things in different instructions: in a branch the bits 6-10 hold the
    condition, not a register.
    """
    opcode = word >> 26
    if opcode == 18:
        # b / bl: the link bit and the absolute bit.
        return ("b", word & 3)
    if opcode == 16:
        # bc: the branch condition, and the index of the branch.
        return ("bc", (word >> 21) & 0x1F, (word >> 16) & 0x1F)
    if opcode == 19:
        # bclr, bctr and their relatives: the condition and the branch index.
        return ("bcx", (word >> 21) & 0x1F, (word >> 16) & 0x1F)
    if opcode == 31:
        # the extended form: the operation.
        return ("x", (word >> 1) & 0x3FF)
    return ("o", opcode)


def registers(word: int) -> tuple:
    """The registers an instruction names, in a fixed order."""
    opcode = word >> 26
    if opcode == 31:
        xo = (word >> 1) & 0x3FF
        if xo in (19, 339, 467, 536):
            # the move of a special purpose register: the field holds the
            # number of the register, not a general purpose one
            return ((word >> 21) & 0x1F, 0, 0)
        # the extended form: destination, first operand, second operand.
        return ((word >> 21) & 0x1F, (word >> 16) & 0x1F, (word >> 11) & 0x1F)
    if opcode in D_FORM:
        # the destination (or the source of a store) and the first operand.
        return ((word >> 21) & 0x1F, (word >> 16) & 0x1F)
    return ()


def immediate(word: int) -> int:
    """The immediate of an instruction, signed.

    The displacement of a branch is not an immediate: it is an address, and
    it points somewhere else in the other build.  Leaving it out is what
    lets the strict signature survive the move of the code.
    """
    opcode = word >> 26
    if opcode in (16, 18, 19, 31):
        return 0
    value = word & 0xFFFF
    if value & 0x8000:
        value -= 0x10000
    return value


def digest(items) -> str:
    """A short, stable digest of a sequence."""
    blob = "\x1f".join(str(item) for item in items).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:16]


def identity(left: list[int], right: list[int]) -> float:
    """The share of the instructions that are the same in the two builds.

    Two functions of the same game, in two builds, are not the same bytes:
    the branches point elsewhere and the data sits elsewhere.  The
    instructions that are the same are still the majority, and the share says
    how much of the function is untouched by the rebuild.
    """
    if not left or not right:
        return 0.0
    common = min(len(left), len(right))
    same = sum(1 for index in range(common) if left[index] == right[index])
    return same / max(len(left), len(right))


class Program:
    """One build of a program: its functions and their signatures."""

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        with open(path, "rb") as handle:
            blob = handle.read()
        self.sha256 = hashlib.sha256(blob).hexdigest()
        self.elf = PpuElf(blob, path)
        self.functions: list[tuple[int, int]] = []
        self.bodies: list[list[int]] = []
        self.signatures: dict[str, list[str]] = {}
        self.call_lists: list[tuple[str, ...]] = []

    # -- the code -----------------------------------------------------------

    def _text(self):
        best = None
        for ph in self.elf.program_headers():
            if not ph.is_load or (ph.flags & 0x4) == 0:
                continue
            if best is None or ph.filesz > best.filesz:
                best = ph
        if best is None:
            raise ElfError("no executable segment found")
        return best.vaddr, best.filesz

    def _words(self, start: int, end: int) -> list[int]:
        data = self.elf.read_vaddr(start, end - start)
        return [struct.unpack_from(">I", data, offset)[0]
                for offset in range(0, len(data) - 3, 4)]

    def _word(self, address: int) -> int:
        base, data = text_code(self.elf)
        offset = address - base
        return struct.unpack_from(">I", data, offset)[0]

    # -- the analysis -------------------------------------------------------

    def analyse(self) -> None:
        """Recover the functions and compute their signatures."""
        # The wide catalogue: the confirmed functions of the release, with
        # the four signals of an entry instead of the two of the narrow
        # method.  The correspondence covers the whole confirmed corpus.
        catalogue = build_catalogue(self.elf, wide=True)
        entries = {address for address, _kind, _evidence in catalogue}
        self.functions = []
        self.bodies = []
        for address, _kind, evidence in catalogue:
            if evidence != "both":
                continue
            end, _why, body = function_body(self.elf, address, entries=entries)
            if end > address:
                self.functions.append((address, end))
                self.bodies.append([self._word(at) for at in body])

        shapes: list[str] = []
        ops: list[str] = []
        ops_imm: list[str] = []
        calls: list[tuple[str, ...]] = []
        for (start, _end), words in zip(self.functions, self.bodies):
            shape_items = [token(word) for word in words]
            ops_items = [shape_items[i] + registers(words[i])
                         for i in range(len(words))]
            imm_items = [ops_items[i] + (immediate(words[i]),)
                         for i in range(len(words))]
            shapes.append(digest(shape_items))
            ops.append(digest(ops_items))
            ops_imm.append(digest(imm_items))
            calls.append(tuple(self._call_targets(words, start)))

        # The identity of a callee is the shape of the callee, one level
        # deep: stable across the builds, and free of any address.
        index = {address: position for position, (address, _end) in
                 enumerate(self.functions)}
        callee_shapes: list[tuple[str, ...]] = []
        for position, _ in enumerate(self.functions):
            row = []
            for target in calls[position]:
                other = index.get(target)
                row.append(shapes[other] if other is not None else "?")
            callee_shapes.append(tuple(row))

        self.call_lists = callee_shapes
        self.signatures = {
            "ops+imm": ops_imm,
            "ops": ops,
            "ops+calls": [digest((ops[i], callee_shapes[i]))
                          for i in range(len(self.functions))],
            "shape": shapes,
        }

    def _call_targets(self, words: list[int], start: int) -> list[int]:
        out = []
        for offset, word in enumerate(words):
            if word & BRANCH_MASK != BRANCH_LINK:
                continue
            out.append(branch_target(word, start + offset * 4))
        return out

    # -- the cache ----------------------------------------------------------

    def save_cache(self, directory: str) -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{self.name}.json")
        flat: list[int] = []
        lengths: list[int] = []
        for body in self.bodies:
            flat.extend(body)
            lengths.append(len(body))
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"name": self.name, "sha256": self.sha256,
                       "functions": self.functions,
                       "signatures": self.signatures,
                       "calls": self.call_lists,
                       "bodies": flat, "body_lengths": lengths}, handle)
        return path

    def load_cache(self, directory: str) -> bool:
        path = os.path.join(directory, f"{self.name}.json")
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as handle:
            blob = json.load(handle)
        if blob.get("sha256") != self.sha256:
            return False
        self.functions = [tuple(row) for row in blob["functions"]]
        self.signatures = blob["signatures"]
        self.call_lists = [tuple(row) for row in blob["calls"]]
        flat = blob.get("bodies")
        if flat is not None:
            self.bodies = []
            at = 0
            for length in blob["body_lengths"]:
                self.bodies.append(flat[at:at + length])
                at += length
        return True

    @property
    def text_size(self) -> int:
        _vaddr, size = self._text()
        return size


def match(programs_a: Program, programs_b: Program) -> tuple[list[dict], dict]:
    """Match the functions of two builds, and report how they were matched.

    A signature that several functions share does not decide anything: the
    candidates are then narrowed by two independent facts — the size of the
    body, which is the same in the two builds for a function that did not
    change, and the order of the addresses, which the two builds keep almost
    everywhere.  The method that decided the pair is the one reported.
    """
    # The index of the signatures of the second build.
    index: dict[str, dict[str, list[int]]] = {}
    for name in SIGNATURES:
        table: dict[str, list[int]] = {}
        for position, signature in enumerate(programs_b.signatures[name]):
            table.setdefault(signature, []).append(position)
        index[name] = table

    sizes_b = [end - start for start, end in programs_b.functions]

    # The candidates of every function of the first build.
    candidates: dict[int, tuple[str, list[int]]] = {}
    for position in range(len(programs_a.functions)):
        for name in SIGNATURES:
            table = index[name].get(programs_a.signatures[name][position], [])
            if table:
                candidates[position] = (name, table)
                break

    resolved: dict[int, tuple[str, int]] = {}
    pending: list[int] = []

    # First the pairs that nothing can dispute: one candidate, and the same
    # size on both sides.
    for position in sorted(candidates):
        name, table = candidates[position]
        size_a = programs_a.functions[position][1] - programs_a.functions[position][0]
        same = [c for c in table if sizes_b[c] == size_a]
        if len(same) == 1 and len(table) == 1:
            resolved[position] = (name + "+size", same[0])
        else:
            pending.append(position)

    def expected(position: int) -> float | None:
        """Where the counterpart of a function should sit.

        The two builds are laid out in blocks, and the shift of the addresses
        is constant inside a block: the counterpart is interpolated between
        the two pairs that surround it.
        """
        here = programs_a.functions[position][0]
        before = after = None
        for other in sorted(resolved):
            if other < position:
                before = other
            elif after is None:
                after = other
                break
        if before is None and after is None:
            return None
        if before is None:
            return resolved[after][1] - (programs_a.functions[after][0] - here)
        if after is None:
            return resolved[before][1] + (here - programs_a.functions[before][0])
        x0 = programs_a.functions[before][0]
        y0 = resolved[before][1]
        x1 = programs_a.functions[after][0]
        y1 = resolved[after][1]
        if x1 == x0:
            return float(y0)
        return y0 + (here - x0) * (y1 - y0) / (x1 - x0)

    # Then the others: the candidates are compared by the share of their
    # instructions that are the same, and the order settles what is left.
    for position in pending:
        name, table = candidates[position]
        size_a = programs_a.functions[position][1] - programs_a.functions[position][0]
        same = [c for c in table if sizes_b[c] == size_a]
        pool = same or table
        left = programs_a.bodies[position]
        scored = sorted(((identity(left, programs_b.bodies[c]), c) for c in pool),
                        key=lambda item: (-item[0], item[1]))
        best, chosen = scored[0]
        runner = scored[1][0] if len(scored) > 1 else -1.0
        target = expected(position)
        if target is not None and len(scored) > 1:
            # the order breaks the tie when the bytes do not
            near = min(pool, key=lambda c: (abs(c - target), c))
            if identity(left, programs_b.bodies[near]) == best:
                chosen = near
        suffix = "+size" if same else "+order"
        decided = len(pool) == 1 or best > runner
        resolved[position] = (name + suffix if decided else name + suffix + "?",
                              chosen)

    rows: list[dict] = []
    counts: dict[str, int] = {}
    detail: dict[str, int] = {}
    for position in sorted(resolved):
        name, other = resolved[position]
        address_a, end_a = programs_a.functions[position]
        address_b, end_b = programs_b.functions[other]
        rows.append({
            "address_a": address_a,
            "address_b": address_b,
            "size_a": end_a - address_a,
            "size_b": end_b - address_b,
            "method": name,
            "identity": identity(programs_a.bodies[position],
                                 programs_b.bodies[other]),
        })
        base = name.split("+")[0].rstrip("?")
        counts[base] = counts.get(base, 0) + 1
        detail[name] = detail.get(name, 0) + 1

    summary = {
        "functions_a": len(programs_a.functions),
        "functions_b": len(programs_b.functions),
        "matched": len(rows),
        "by_method": counts,
        "detail": detail,
    }
    return rows, summary


def offset_report(rows: list[dict]) -> dict:
    """The shape of the difference of the addresses of the matched pairs.

    The two builds of one game are not laid out the same way: the blocks of
    code sit at other addresses, and the shift is constant inside a block.
    The report counts the blocks, which is the number of times the linker
    moved a piece of the program.
    """
    if not rows:
        return {}
    deltas = [row["address_b"] - row["address_a"] for row in rows]
    median = statistics.median(deltas)
    exact = sum(1 for delta in deltas if delta == median)
    sizes_a = [row["size_a"] for row in rows]
    sizes_b = [row["size_b"] for row in rows]
    same_size = sum(1 for a, b in zip(sizes_a, sizes_b) if a == b)
    identities = sorted(row["identity"] for row in rows)
    blocks = 1
    for index in range(1, len(deltas)):
        if deltas[index] != deltas[index - 1]:
            blocks += 1
    return {
        "delta_median": median,
        "delta_exact": exact,
        "delta_min": min(deltas),
        "delta_max": max(deltas),
        "delta_blocks": blocks,
        "same_size": same_size,
        "identity_median": identities[len(identities) // 2],
        "identity_min": identities[0],
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", action="append", default=[],
                        metavar="LABEL=PATH",
                        help="one build of a program, with its label")
    parser.add_argument("--pair", action="append", default=[],
                        metavar="A:B",
                        help="the two builds to match")
    parser.add_argument("--out", help="the correspondence table")
    parser.add_argument("--builds-out", default=None,
                        help="the table of the builds")
    parser.add_argument("--cache", default=None,
                        help="directory for the cache of the analysis")
    args = parser.parse_args()

    builds: dict[str, str] = {}
    for item in args.build:
        label, _, path = item.partition("=")
        if not label or not path:
            parser.error(f"--build wants LABEL=PATH, got {item!r}")
        builds[label] = path
    pairs = []
    for item in args.pair:
        left, _, right = item.partition(":")
        if not left or not right:
            parser.error(f"--pair wants A:B, got {item!r}")
        if left not in builds or right not in builds:
            parser.error(f"--pair {item!r} names a build that was not given")
        pairs.append((left, right))
    if not pairs:
        parser.error("at least one --pair is needed")
    if not args.out:
        parser.error("--out is needed")

    analysed: dict[str, Program] = {}

    def program_of(label: str) -> Program:
        if label not in analysed:
            path = builds[label]
            program = Program(label, path)
            cached = args.cache and program.load_cache(args.cache)
            if not cached:
                program.analyse()
                if args.cache:
                    program.save_cache(args.cache)
            analysed[label] = program
            print(f"  {label:22s} {len(program.functions):6d} functions, "
                  f"text {program.text_size} bytes")
        return analysed[label]

    builds_rows = []
    all_rows = []

    for label_a, label_b in pairs:
        print(f"=== {label_a} <-> {label_b} ===")
        left = program_of(label_a)
        right = program_of(label_b)

        rows, summary = match(left, right)
        report = offset_report(rows)
        summary["offset"] = report
        print(f"  matched {summary['matched']} of {summary['functions_a']} "
              f"({summary['matched'] * 100 // max(summary['functions_a'], 1)}%)")
        print(f"  by method: {summary['detail']}")
        if report:
            print(f"  the median offset is {report['delta_median']} "
                  f"({report['delta_exact']} pairs share it), "
                  f"{report['same_size']} pairs have the same size, "
                  f"{report['identity_median'] * 100:.1f}% of the instructions "
                  f"are the same")

        for row in rows:
            row["program"] = label_a
            row["build_a"] = label_a
            row["build_b"] = label_b
        all_rows.extend(rows)

        builds_rows.append({
            "program": label_a,
            "build_a": label_a,
            "build_b": label_b,
            "functions_a": len(left.functions),
            "functions_b": len(right.functions),
            "text_a": left.text_size,
            "text_b": right.text_size,
            "matched": summary["matched"],
            "by_method": summary["by_method"],
            "detail": summary["detail"],
            "offset": report,
        })

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("game\tbuild_a\taddress_a\tsize_a\tbuild_b\taddress_b\tsize_b"
                  "\tmethod\tidentical\tdelta\n")
        for row in all_rows:
            out.write(f"{row['program']}\t{row['build_a']}\t0x{row['address_a']:08X}"
                      f"\t{row['size_a']}\t{row['build_b']}\t0x{row['address_b']:08X}"
                      f"\t{row['size_b']}\t{row['method']}"
                      f"\t{row['identity'] * 100:.1f}"
                      f"\t{row['address_b'] - row['address_a']}\n")
    print(f"wrote {args.out}: {len(all_rows)} rows")

    if args.builds_out:
        with open(args.builds_out, "w", encoding="utf-8", newline="\n") as out:
            out.write("game\tbuild_a\tbuild_b\tfunctions_a\tfunctions_b\ttext_a"
                      "\ttext_b\tmatched\tshare\tsame_size\tidentical_median"
                      "\tidentical_min\tdelta_median\tdelta_blocks\tmethods\n")
            for row in builds_rows:
                report = row["offset"]
                detail = ";".join(f"{name}={count}"
                                  for name, count in sorted(row["detail"].items()))
                share = row["matched"] * 100 // max(row["functions_a"], 1)
                out.write(f"{row['program']}\t{row['build_a']}\t{row['build_b']}"
                          f"\t{row['functions_a']}\t{row['functions_b']}"
                          f"\t{row['text_a']}\t{row['text_b']}\t{row['matched']}"
                          f"\t{share}\t{report.get('same_size', '')}"
                          f"\t{report.get('identity_median', 0) * 100:.1f}"
                          f"\t{report.get('identity_min', 0) * 100:.1f}"
                          f"\t{report.get('delta_median', '')}"
                          f"\t{report.get('delta_blocks', '')}\t{detail}\n")
        print(f"wrote {args.builds_out}: {len(builds_rows)} builds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
