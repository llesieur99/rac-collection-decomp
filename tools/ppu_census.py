"""Measure the population of the functions, and the coverage of the catalogue.

The catalogue of the functions is measured, but the question of the
population is not: how many functions does a program hold?  The tool
answers it with three measurements, all reproducible:

* the **population** — the returns of the program.  Every function ends
  on a return, so the number of the returns is a lower bound of the
  number of the functions;
* the **forms of the prologue** — the shape the SDK gives to the
  functions, with the share of each form and an example of it;
* the **coverage** — the share of the code that the catalogue covers,
  before and after the extended detection, and the share of the retained
  addresses that the bytes do not support.

    python tools/ppu_census.py --work <directory of the rebuilt ELFs>

The tool needs nothing but the Python standard library and the four
executables of the release.
"""

from __future__ import annotations

import argparse
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import PpuElf  # noqa: E402
from ppu_funcs import (  # noqa: E402
    BLR, PROLOGUE_FRAME, PROLOGUE_FRAME_LR, entry_evidence, function_body,
    prologue_candidates, prologue_forms, signals, text_code,
)

# The programs of the release.
PROGRAMS = (
    ("EBOOT", "eboot.elf"),
    ("RC1", "RC1.elf"),
    ("RC2", "RC2.elf"),
    ("RC3", "RC3.elf"),
)

# The opcode 19 is the family of the branches to the link and to the count
# register, and the conditional branch of the PPU.
XO_BCLR = 16
XO_BCCTR = 528
XO_BC = 449


def population(words) -> dict[str, int]:
    """The returns of the program, by form."""
    out = collections.Counter()
    for word in words:
        opcode = word >> 26
        if opcode == 19:
            xo = (word >> 1) & 0x3FF
            bo = (word >> 21) & 0x1F
            if xo == XO_BCLR:
                out["return" if bo == 20 else "return-conditional"] += 1
            elif xo == XO_BCCTR:
                out["indirect-jump" if not (word & 1) else "indirect-call"] += 1
            elif xo == XO_BC:
                out["branch-conditional"] += 1
        elif opcode == 18:
            out["branch" if not (word & 1) else "call"] += 1
    return out


class Cover:
    """The instructions the catalogue owns, as a bitmap of the segment."""

    def __init__(self, size: int):
        self.bits = bytearray(size)

    def add(self, offset: int) -> None:
        if 0 <= offset < len(self.bits):
            self.bits[offset] = 1

    @property
    def size(self) -> int:
        return sum(self.bits)


def missed_forms(elf: PpuElf, forms, calls, narrow) -> dict[str, list[int]]:
    """What the narrow prologue misses, by form.

    The narrow prologue records the address of the **frame**.  The wide
    one records the address of the **block** the frame belongs to.  The
    difference is what this measures:

    * the link register is saved before the frame — the narrow prologue
      records the frame, one instruction after the entry;
    * the frame stands alone — the function calls nothing, so there is no
      link register to save.

    The functions that have no frame at all are the leaves: the call is
    the only signal that sees them.
    """
    out: dict[str, list[int]] = {}
    for address in sorted(set(forms) - narrow):
        form = forms[address]
        if form == PROLOGUE_FRAME_LR:
            key = "the link register is saved before the frame"
        else:
            key = "the frame alone, no link register"
        out.setdefault(key, []).append(address)
    leaves = [address for address in sorted(calls - narrow)
              if address not in forms]
    if leaves:
        out["no frame at all: the leaf function"] = leaves
    return out


def catalogue_of(elf: PpuElf, base: int, count: int, words, forms, calls,
                 entries, wide: bool):
    """The catalogue, the walk of every entry, and the code it owns."""
    if wide:
        evidence, confirmed = entry_evidence(elf)
        universe = set(evidence)
        # the bound of the walk: the entries of the functions, and the
        # targets of the calls
        bound = confirmed | calls
    else:
        narrow = {c.address for c in prologue_candidates(elf)}
        universe = narrow | calls
        confirmed = narrow & calls
        # the bound of the narrow walk: the prologue and the calls
        bound = universe
    table = {}
    cover = Cover(len(words) * 4)
    returns = set()
    for address in sorted(confirmed):
        end, why, body = function_body(elf, address, entries=bound)
        table[address] = (end, why, len(body))
        _e, _w, full = function_body(elf, address, entries=bound, full=True)
        for place in full:
            offset = place - base
            cover.add(offset)
            index = offset // 4
            if 0 <= index < count and words[index] == BLR:
                returns.add(place)
    return confirmed, universe, table, cover, returns


def report(name: str, path: str) -> dict:
    with open(path, "rb") as handle:
        elf = PpuElf(handle.read(), path)
    base, code = text_code(elf)
    count = len(code) // 4
    words = struct.unpack_from(">%dI" % count, code, 0)
    text_size = len(code)

    pop = population(words)
    found = signals(elf)
    forms = prologue_forms(elf)
    calls = found["call"]
    entries = found["entry"]

    before_set, _ub, before, cover_before, owned_before = catalogue_of(
        elf, base, count, words, forms, calls, entries, wide=False)
    after_set, universe, after, cover_after, owned_after = catalogue_of(
        elf, base, count, words, forms, calls, entries, wide=True)

    def summary(table):
        total = sum(end - address for address, (end, _w, _n) in table.items())
        ends = collections.Counter(why for _a, (_e, why, _n) in table.items())
        return total, ends

    before_total, before_ends = summary(before)
    after_total, after_ends = summary(after)

    def false_positives(table):
        """The retained rows the bytes do not support."""
        tiny = 0
        overlaps = 0
        unproven = 0
        previous = None
        for address, (end, _why, _n) in sorted(table.items()):
            if previous is not None and address < previous:
                overlaps += 1
            previous = max(previous or 0, end)
            if end - address <= 8:
                tiny += 1
            if _why in ("entry", "limit"):
                unproven += 1
        return tiny, overlaps, unproven

    print("=" * 78)
    print("%s   text %d bytes (%d instructions) at 0x%08X" %
          (name, text_size, count, base))
    print("-" * 78)
    print("  the population")
    print("    blr, the return of the SDK            %7d" % pop["return"])
    print("    bclr, the conditional return           %7d" % pop["return-conditional"])
    print("    bctr / bctrl, the indirect jump        %7d" %
          (pop["indirect-jump"] + pop["indirect-call"]))
    print("    the conditional branch of the PPU      %7d" % pop["branch-conditional"])
    print("    bl, the calls                         %7d" % pop["call"])
    print("    the returns bound the population: a function has at least one")
    print("    of them, so they are its upper bound: %d" %
          (pop["return"] + pop["return-conditional"]))
    print("  the signals")
    narrow = {c.address for c in prologue_candidates(elf)}
    print("    the narrow prologue (the frame at the first instruction) %5d"
          % len(narrow))
    by_form = collections.Counter(forms.values())
    for form, n in by_form.most_common():
        example = min(a for a, f in forms.items() if f == form)
        print("    the wide prologue: %-10s %7d   e.g. 0x%08X" % (form, n, example))
    print("    the calls                            %7d" % len(calls))
    print("    the entries (the flow cannot fall in) %6d" % len(entries))
    print("  what the narrow prologue misses")
    for key, addresses in sorted(missed_forms(elf, forms, calls, narrow).items()):
        print("    %-42s %6d   e.g. 0x%08X" %
              (key, len(addresses), addresses[0]))
    print("  the catalogue")
    print("    before: %6d functions, %9d bytes of extent, %5.2f%% of the text"
          % (len(before_set), before_total, 100.0 * before_total / text_size))
    print("            %9d bytes of code owned, %5.2f%% of the text"
          % (cover_before.size, 100.0 * cover_before.size / text_size))
    print("            ends: %s" % dict(before_ends))
    print("            returns owned: %6d (%.1f%% of the returns)"
          % (len(owned_before), 100.0 * len(owned_before) / max(pop["return"], 1)))
    print("    after : %6d functions, %9d bytes of extent, %5.2f%% of the text"
          % (len(after_set), after_total, 100.0 * after_total / text_size))
    print("            %9d bytes of code owned, %5.2f%% of the text"
          % (cover_after.size, 100.0 * cover_after.size / text_size))
    print("            ends: %s" % dict(after_ends))
    print("            returns owned: %6d (%.1f%% of the returns)"
          % (len(owned_after), 100.0 * len(owned_after) / max(pop["return"], 1)))
    print("            the candidates the catalogue still holds: %d"
          % (len(universe) - len(after_set)))
    print("  the false positives")
    print("    before: %d extents of 8 bytes or less, %d overlaps, "
          "%d ends not proven" % false_positives(before))
    print("    after : %d extents of 8 bytes or less, %d overlaps, "
          "%d ends not proven" % false_positives(after))
    print()

    return {
        "program": name,
        "text": text_size,
        "blr": pop["return"],
        "before": len(before_set),
        "after": len(after_set),
        "before_cover": cover_before.size,
        "after_cover": cover_after.size,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", required=True,
                        help="directory that holds the rebuilt ELFs")
    parser.add_argument("--program", action="append", default=[],
                        help="measure only this program (repeatable)")
    args = parser.parse_args(argv)

    wanted = set(args.program)
    for name, filename in PROGRAMS:
        if wanted and name not in wanted:
            continue
        path = os.path.join(args.work, filename)
        if not os.path.exists(path):
            print(f"skipping {name}: {path} is missing")
            continue
        report(name, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
