"""Match the functions of a PS2 game with the functions of its PS3 port.

The PlayStation 3 release of a PlayStation 2 game is a **port**: the game is
the same, but the program is not.  The functions sit at other addresses, the
compiler is another one, the SDK is four years newer, and the instruction
signature that ``tools/build_correspondence.py`` uses cannot cross the
architectures.  What the two builds have in common is the *source*: the same
functions, called the same way, reading the same messages.

The tool therefore matches on **keys** that do not depend on the machine,
and it measures each key separately, because a key that proposes a pair
without being able to tell a true pair from a false one is worth nothing.

**The two sides**

A PS2 game is not one program: the *core* executable holds the shared code
and every level ships its own **overlay**, an ELF of its own that carries a
copy of the game code at other addresses.  The table of the sibling project
says which address of which overlay holds the same function, so the tool
rebuilds the *game function*: one entity that sits at nineteen addresses,
reads the same messages, and calls the same functions.  That entity is the
left side of the matching.

The right side is the program of the PS3, and its functions are the ones of
``config/functions.tsv``.

**The keys**

``string``
    a message that only one function of each side reaches.  The message is
    the same on both sides, and it is rare: that is what makes the pair
    verifiable.  The rare-ness is the point — a short message like ``AMMO``
    is read by a dozen functions and says nothing.
``profile``
    the whole set of messages of a function, compared with the set of every
    other function by the share they have in common.
``order``
    the rank of the function in its program.  The same source is linked in
    the same order in the two builds, so the rank of a function is an
    indication of where its counterpart sits.  The rank of the anchors
    draws the line, and the key only speaks when the line leaves no choice.
``calls``
    the shape of the call graph.  The graph is the same graph at other
    addresses: the neighbours of a function are the neighbours of its
    counterpart.  The key starts from the pairs the string key has
    established and walks the graph outwards.
``source``
    the name of the source file.  The PS2 table carries it; the PS3
    catalogue does not yet, but the messages of the PS3 name their own
    source files, so the key is measured on what the code says and not on
    a catalogue.

Every pair the tool reports says **how** it was found and **how many keys
agree** on it.  A pair that only one key proposes is reported as
unverified: it is a hypothesis, and it is counted as such.

    python tools/ps2_ps3_match.py \\
        --ps2-funcs work/ps2/LVL00.funcs.tsv \\
        --ps2-strings work/ps2/LVL00.strings.tsv \\
        --ps3-funcs work/ps3/RC1.funcs.tsv \\
        --ps3-strings work/ps3/RC1.strings.tsv \\
        --names work/lombyte-functions.tsv \\
        --out work/ps2-ps3-pairs.tsv --report work/ps2-ps3-keys.tsv

Only metadata is written: addresses, names, messages and scores.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Sequence

# The keys, in the order they are reported.
KEYS = ("string", "profile", "order", "calls", "source")

# A message shorter than this is not used to anchor a pair: the short
# messages are the ones that several functions share.
MINIMUM_ANCHOR = 8

# A message that names a source file: the game keeps the name of the file
# in the message of its assertions.
SOURCE_FILE = re.compile(r"([\w./\\-]+\.(?:cpp|c|cc|s|S))")


@dataclass
class Side:
    """One side of the matching: the functions, their messages and their calls.

    The key of a function is an integer: the address on the PS3 side, the
    index of the game function on the PS2 side.
    """

    name: str
    functions: dict[int, int] = field(default_factory=dict)
    order: list[int] = field(default_factory=list)
    rank: dict[int, int] = field(default_factory=dict)
    calls: dict[int, list[int]] = field(default_factory=dict)
    callers: dict[int, list[int]] = field(default_factory=dict)
    strings: dict[int, set[str]] = field(default_factory=dict)
    string_functions: dict[str, set[int]] = field(default_factory=dict)
    names: dict[int, str] = field(default_factory=dict)
    sources: dict[int, str] = field(default_factory=dict)
    source_files: dict[int, set[str]] = field(default_factory=dict)
    reach: dict[int, set[str]] = field(default_factory=dict)

    def build_reach(self, depth: int) -> None:
        """The messages a function reaches, through the calls it makes.

        A function reads its own messages, and the messages of the functions
        it calls and of the functions that call it: the deeper the reach,
        the more functions read the same message, and the less the message
        tells.  The reach is what tells a pair of functions that read no
        message in common apart: the two of them may still reach the same
        message, one hop away.
        """
        self.reach = {address: set(texts) for address, texts in self.strings.items()}
        for _step in range(depth):
            grown: dict[int, set[str]] = {a: set(t) for a, t in self.reach.items()}
            for address in self.functions:
                texts = grown.setdefault(address, set())
                for neighbour in (list(self.calls.get(address, ()))
                                  + list(self.callers.get(address, ()))):
                    texts |= self.reach.get(neighbour, set())
            self.reach = grown

    def finish(self) -> None:
        """The order of the functions, the callers, and the message index."""
        self.order = sorted(self.functions)
        self.rank = {address: index for index, address in enumerate(self.order)}
        callers: dict[int, list[int]] = defaultdict(list)
        for address, targets in self.calls.items():
            for target in targets:
                callers[target].append(address)
        self.callers = dict(callers)
        index: dict[str, set[int]] = defaultdict(set)
        for address, texts in self.strings.items():
            for text in texts:
                index[text].add(address)
        self.string_functions = dict(index)
        files: dict[int, set[str]] = {}
        for address, texts in self.strings.items():
            found = set()
            for text in texts:
                for name in SOURCE_FILE.findall(text):
                    found.add(name.replace("\\", "/").rsplit("/", 1)[-1])
            if found:
                files[address] = found
        self.source_files = files


# -- the PS2 side ----------------------------------------------------------


def read_program_table(paths: Iterable[str], program: str | None) -> dict[str, dict[int, tuple[int, list[int]]]]:
    """The function tables written by ``mips_program.py`` and ``ppu_program.py``."""
    programs: dict[str, dict[int, tuple[int, list[int]]]] = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                name = row["program"]
                if program and name != program:
                    continue
                address = int(row["function"], 16)
                calls = [int(x, 16) for x in row["calls"].split()] if row["calls"] else []
                programs.setdefault(name, {})[address] = (int(row["size"]), calls)
    return programs


def read_string_table(paths: Iterable[str], program: str | None) -> dict[str, dict[int, set[str]]]:
    """The string tables written by ``strings_xref.py`` and ``mips_strings_xref.py``."""
    programs: dict[str, dict[int, set[str]]] = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                name = row["program"]
                if program and name != program:
                    continue
                if not row["function"]:
                    continue
                address = int(row["function"], 16)
                programs.setdefault(name, {}).setdefault(address, set()).add(row["string"])
    return programs


def read_names(path: str) -> list[dict]:
    """The table of the PS2 functions, their source, and where they sit.

    The table of the sibling project gives, for every function of the PS2,
    the name of the source file it was compiled from, and the address it
    sits at in each of the levels.
    """
    rows: list[dict] = []
    with open(path, encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = list(reader.fieldnames or [])
        name_field = "# name" if "# name" in fields else fields[0]
        for row in reader:
            places = []
            for item in (row.get("places (level:address)") or "").split(","):
                item = item.strip()
                if not item or ":" not in item:
                    continue
                level, _, address = item.partition(":")
                places.append((level, int(address, 16)))
            rows.append({
                "name": row[name_field].strip(),
                "source": (row.get("exe unit") or "").strip(),
                "kind": row.get("kind", ""),
                "size": int(row["size"]) if row.get("size", "").isdigit() else 0,
                "places": places,
            })
    return rows


def attach_names(side: Side, rows: list[dict], levels: dict[str, str]) -> int:
    """Give the name and the source of the functions of one program.

    The table of the sibling project gives, for every function of the PS2,
    the source file it was compiled from and the address it sits at in each
    of the levels.  Only the rows that name a source file are of use, and
    only the address that sits in the program at hand.
    """
    attached = 0
    for row in rows:
        if not row["source"]:
            continue
        for level, address in row["places"]:
            if levels.get(level, "") != side.name:
                continue
            if address not in side.functions:
                continue
            side.names.setdefault(address, row["name"])
            side.sources.setdefault(address, row["source"])
            attached += 1
            break
    return attached


def build_ps2_side(programs: dict[str, dict[int, tuple[int, list[int]]]],
                   strings: dict[str, dict[int, set[str]]],
                   names: list[dict],
                   levels: dict[str, str]) -> tuple[Side, dict[int, str], int]:
    """The game functions of the PS2, seen across the levels.

    The key of a function is its index in the table of the sibling project:
    the same function, at nineteen addresses, is one function of the game.
    """
    side = Side("PS2")
    identity: dict[tuple[str, int], int] = {}
    label: dict[int, str] = {}
    for index, row in enumerate(names):
        label[index] = row["name"]
        for level, address in row["places"]:
            program = levels.get(level, "")
            if not program:
                continue
            identity.setdefault((program, address), index)
        if row["source"]:
            side.sources[index] = row["source"]
        side.names[index] = row["name"]
    for index, row in enumerate(names):
        side.functions[index] = row["size"] or 0

    resolved = 0
    for program, table in programs.items():
        for address, (size, calls) in table.items():
            index = identity.get((program, address))
            if index is None:
                continue
            resolved += 1
            side.functions.setdefault(index, size)
            if size:
                side.functions[index] = size
            targets = []
            for callee in calls:
                other = identity.get((program, callee))
                if other is not None and other != index:
                    targets.append(other)
            side.calls.setdefault(index, [])
            for other in targets:
                if other not in side.calls[index]:
                    side.calls[index].append(other)
    for program, table in strings.items():
        for address, texts in table.items():
            index = identity.get((program, address))
            if index is None:
                continue
            side.strings.setdefault(index, set()).update(texts)
    side.finish()
    return side, label, resolved


def build_ps3_side(programs: dict[str, dict[int, tuple[int, list[int]]]],
                   strings: dict[str, dict[int, set[str]]],
                   program: str) -> Side:
    """The functions of one program of the PS3."""
    side = Side(program)
    for address, (size, calls) in programs.get(program, {}).items():
        side.functions[address] = size
        side.calls[address] = list(calls)
    for address, texts in strings.get(program, {}).items():
        side.strings.setdefault(address, set()).update(texts)
    side.finish()
    return side


# -- the keys --------------------------------------------------------------


def key_string(ps2: Side, ps3: Side, minimum: int = MINIMUM_ANCHOR) -> dict[int, tuple[int, str]]:
    """A message that only one function of each side reads.

    The pair is verifiable by the message itself: the same text, read by one
    function and by one function only, on both sides.  The messages shorter
    than ``minimum`` are left out — they are shared by too many functions
    and the pair they suggest cannot be told from a coincidence.
    """
    pairs: dict[int, tuple[int, str]] = {}
    for text, sources in ps2.string_functions.items():
        if len(text) < minimum:
            continue
        targets = ps3.string_functions.get(text)
        if not targets:
            continue
        if len(sources) != 1 or len(targets) != 1:
            continue
        pairs[next(iter(sources))] = (next(iter(targets)), text)
    return pairs


def key_profile(ps2: Side, ps3: Side, margin: float = 0.0) -> dict[int, tuple[int, float]]:
    """The set of messages of a function, compared with the set of the others.

    The share is the number of messages the two functions have in common,
    over the number of messages the two of them hold together.  A function
    that reads many messages has a profile that no other function has; a
    function that reads one short message has none.

    The key only speaks when the best candidate is **clearly** the best:
    the share of the second candidate must be lower by at least ``margin``,
    or the two candidates are told apart by nothing and the key stays
    silent.
    """
    scores: dict[int, dict[int, int]] = defaultdict(dict)
    for text, sources in ps2.string_functions.items():
        targets = ps3.string_functions.get(text)
        if not targets:
            continue
        for source in sources:
            row = scores[source]
            for target in targets:
                row[target] = row.get(target, 0) + 1
    pairs: dict[int, tuple[int, float]] = {}
    for source, row in scores.items():
        left = len(ps2.strings.get(source, ()))
        ranked = []
        for target, common in row.items():
            right = len(ps3.strings.get(target, ()))
            union = left + right - common
            if union <= 0:
                continue
            ranked.append((common / union, target))
        if not ranked:
            continue
        ranked.sort(reverse=True)
        share, target = ranked[0]
        if len(ranked) > 1 and ranked[1][0] >= share - margin:
            # the second candidate is as good: the key cannot tell them
            # apart, and it says nothing
            continue
        pairs[source] = (target, share)
    return pairs


def _interpolate(points: list[tuple[int, int]], rank: int) -> float | None:
    """The rank a function should sit at, from the anchored ranks.

    The anchored pairs draw a broken line: between two anchors the rank is
    carried over proportionally, and outside of them the line of the first
    (or of the last) anchor is followed.
    """
    if len(points) < 2:
        return None
    points = sorted(points)
    if rank <= points[0][0]:
        first, second = points[0], points[1]
    elif rank >= points[-1][0]:
        first, second = points[-2], points[-1]
    else:
        first, second = points[0], points[1]
        for left, right in zip(points, points[1:]):
            if left[0] <= rank <= right[0]:
                first, second = left, right
                break
    if second[0] == first[0]:
        return float(first[1])
    return first[1] + (rank - first[0]) * (second[1] - first[1]) / (second[0] - first[0])


def key_order(ps2: Side, ps3: Side, anchors: list[tuple[int, int]],
              tolerance: int) -> dict[int, tuple[int, float]]:
    """The rank of the function in its program, carried over to the other.

    The anchored pairs draw the line; the function that should sit where
    the line says is the pair the key proposes.  The key only speaks when
    the line leaves no choice: when a single function of the other program
    sits in the window, the pair is proposed; when several do, the key has
    nothing to say and stays silent.

    The line is fitted on the anchored pairs, and the anchor that is
    measured is left out of the fit, so that the key is not graded on what
    it was given.
    """
    pairs: dict[int, tuple[int, float]] = {}
    for source in ps2.functions:
        points = [(ps2.rank[a], ps3.rank[b]) for a, b in anchors
                  if a != source and a in ps2.rank and b in ps3.rank]
        expected = _interpolate(points, ps2.rank[source])
        if expected is None:
            continue
        window = [target for target in ps3.functions
                  if abs(ps3.rank[target] - expected) <= tolerance]
        if len(window) != 1:
            continue
        pairs[source] = (window[0], 1.0)
    return pairs


def key_calls(ps2: Side, ps3: Side, anchors: list[tuple[int, int]]) -> dict[int, tuple[int, int]]:
    """The shape of the call graph, walked from the anchored pairs.

    The call graph of the two builds is the same graph at other addresses:
    the neighbours of a function are the neighbours of its counterpart.  The
    key therefore starts from the pairs the string key has established and
    walks the graph outwards, one hop at a time.

    A hop is proposed when the two sides agree on the number of
    **callees**: the *n*-th callee of the function is the *n*-th callee of
    its counterpart.  The order of the calls in the body comes from the
    source, and it is what tells two callees apart when there are several.
    """
    return _walk(ps2, ps3, anchors, "callee")


def key_callers(ps2: Side, ps3: Side, anchors: list[tuple[int, int]]) -> dict[int, tuple[int, int]]:
    """The callers of a function, walked from the anchored pairs.

    The callers of a function are the callers of its counterpart, but the
    order of the callers is the order of the addresses, and that order is
    the order of the linker, not the order of the source.  The key
    therefore only speaks when there is **one** caller on each side: then
    the two are the same function.
    """
    return _walk(ps2, ps3, anchors, "caller")


def key_graph(ps2: Side, ps3: Side, anchors: list[tuple[int, int]],
              rounds: int = 4) -> dict[int, tuple[int, str]]:
    """The shape of the call graph, refined from the anchored pairs.

    The call graph of the two builds is the same graph at other addresses.
    The walk of the graph (``key_calls``) only moves when the two sides
    agree on the number of neighbours, and the port rarely agrees: the
    PS3 calls into a newer SDK and calls a few functions more or less.

    The **refinement** is the same idea as the walk, but it uses the whole
    neighbourhood at once.  Every function gets a colour, and the colour
    of a function is the colour of the function together with the colours
    of the functions it calls and of the functions that call it.  The
    anchored pairs get a colour of their own, one colour per pair, so that
    the two sides are tied together.  After a few rounds, the functions
    whose colour is **unique on both sides** are the ones the graph has
    identified: they are proposed, and the colour that identified them is
    the evidence.

    A colour that is unique on one side and shared on the other says
    nothing, and the key stays silent about it.
    """
    colour2: dict[int, str] = {f: "" for f in ps2.functions}
    colour3: dict[int, str] = {f: "" for f in ps3.functions}
    for index, (source, target) in enumerate(anchors):
        colour2[source] = f"anchor{index}"
        colour3[target] = f"anchor{index}"
    pairs: dict[int, tuple[int, str]] = {}
    for _round in range(rounds):
        colour2 = _refine(ps2, colour2)
        colour3 = _refine(ps3, colour3)
        count2: dict[str, int] = defaultdict(int)
        count3: dict[str, int] = defaultdict(int)
        for value in colour2.values():
            count2[value] += 1
        for value in colour3.values():
            count3[value] += 1
        for source, value in colour2.items():
            if count2[value] != 1 or count3.get(value, 0) != 1:
                continue
            target = next(f for f, v in colour3.items() if v == value)
            pairs[source] = (target, value)
    return pairs


def _refine(side: Side, colour: dict[int, str]) -> dict[int, str]:
    """The colours of the functions, after one round of refinement."""
    out: dict[int, str] = {}
    for address in side.functions:
        below = sorted(colour.get(c, "") for c in side.calls.get(address, ()))
        above = sorted(colour.get(c, "") for c in side.callers.get(address, ()))
        digest = hashlib.sha1(
            ("\x1f".join([colour.get(address, "")] + below + ["^"] + above))
            .encode("utf-8")).hexdigest()[:16]
        out[address] = digest
    return out


def _walk(ps2: Side, ps3: Side, anchors: list[tuple[int, int]],
          kind: str) -> dict[int, tuple[int, int]]:
    """The walk of the call graph from the anchored pairs.

    The walk is **constrained** by the pairs it has already established: a
    neighbour that is already matched must be matched to the neighbour that
    is already on the other side, or the pair is contradictory and the walk
    says nothing.  That is what makes a derived pair trustworthy: it is
    consistent with every pair the tool has already established.
    """
    pairs: dict[int, tuple[int, int]] = {}
    known = dict(anchors)
    used = set(known.values())
    frontier = list(anchors)
    while frontier:
        following: list[tuple[int, int]] = []
        for source, target in frontier:
            for side in ("callee", "caller"):
                left = ps2.calls.get(source, []) if side == "callee" else ps2.callers.get(source, [])
                right = ps3.calls.get(target, []) if side == "callee" else ps3.callers.get(target, [])
                if len(left) != len(right) or not left:
                    continue
                if side == "caller":
                    # the order of the callers is the order of the linker,
                    # not the order of the source: the callers are matched
                    # by the pairs already established, and the hop is only
                    # proposed when one caller is left on each side.
                    unknown_left = []
                    unknown_right = list(right)
                    for neighbour in left:
                        if neighbour in known:
                            other = known[neighbour]
                            if other not in unknown_right:
                                unknown_right = []
                                break
                            unknown_right.remove(other)
                        else:
                            unknown_left.append(neighbour)
                    if not unknown_right:
                        continue
                    if len(unknown_left) != 1 or len(unknown_right) != 1:
                        continue
                    left = unknown_left
                    right = unknown_right
                else:
                    # the order of the calls in the body comes from the
                    # source: the n-th callee is the n-th callee.  A
                    # callee that is already matched must land on the
                    # callee it is matched to, or the pair contradicts.
                    for index, neighbour in enumerate(left):
                        if neighbour in known and known[neighbour] != right[index]:
                            left = []
                            break
                    if not left:
                        continue
                for neighbour, other in zip(left, right):
                    if neighbour in known or other in used:
                        continue
                    known[neighbour] = other
                    used.add(other)
                    pairs[neighbour] = (other, 0)
                    following.append((neighbour, other))
        frontier = following
    return pairs


def key_source(ps2: Side, ps3: Side) -> dict[int, tuple[int, str]]:
    """The name of the source file, when both sides know it.

    The PS2 table gives the source file of every named function.  The PS3
    catalogue has none, but the code of the PS3 names its own source files
    in the messages of its assertions, and the key uses them.  The key is
    measured and reported even when it comes out nearly empty, so that the
    gap is visible and not silently filled by a guess.
    """
    pairs: dict[int, tuple[int, str]] = {}
    for address, files in ps3.source_files.items():
        if len(files) != 1:
            continue
        name = next(iter(files))
        for source, origin in ps2.sources.items():
            if not origin:
                continue
            if origin.rsplit("/", 1)[-1].lower() == name.lower():
                pairs[source] = (address, name)
                break
    return pairs


# -- the measure -----------------------------------------------------------


def evaluate(keys: dict[str, dict[int, tuple]]) -> dict:
    """How many pairs each key finds, and how many of them are confirmed.

    A pair is **confirmed** when another key proposes it as well: two
    independent keys that land on the same pair are unlikely to be wrong at
    the same time.  A pair that only one key proposes is **unverified** and
    is counted as such.  When two keys propose two different counterparts
    for the same function, one of them is wrong: the conflict is a
    verifiable false positive.

    A pair is also a **collision** when another function of the other side
    claims the same counterpart: a function of the PS3 is the counterpart
    of one function of the PS2 and of one only, so one of the two claims
    is wrong.  The collision is the false positive that can be shown.
    """
    votes: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for name, pairs in keys.items():
        for source, (target, _evidence) in pairs.items():
            votes[source][target].append(name)
    claims: dict[int, list[int]] = defaultdict(list)
    for source, row in votes.items():
        for target in row:
            claims[target].append(source)
    rows = []
    for name, pairs in keys.items():
        confirmed = 0
        unverified = 0
        conflicts = 0
        collisions = 0
        for source, (target, _evidence) in pairs.items():
            row = votes[source]
            if len(row) == 1:
                if len(row[target]) > 1:
                    confirmed += 1
                else:
                    unverified += 1
            else:
                best = max(len(names) for names in row.values())
                if len(row[target]) == best and best > 1:
                    confirmed += 1
                else:
                    # the keys disagree, and this pair is not the one they
                    # agree on: one of the two is wrong
                    conflicts += 1
            if len(claims[target]) > 1:
                collisions += 1
        rows.append({
            "key": name,
            "pairs": len(pairs),
            "confirmed": confirmed,
            "unverified": unverified,
            "conflicts": conflicts,
            "collisions": collisions,
        })
    return {"keys": rows, "votes": votes, "claims": claims}


def shared_messages(ps2: Side, ps3: Side, pairs: dict[int, tuple]) -> int:
    """How many of the pairs read a message in common.

    This is the **message test**: a pair whose two functions read the same
    message is supported by the code, whatever key proposed it.  A pair
    that reads no message in common is not disproved — two functions of
    the same game do not have to read the same message — but it has no
    support either, and it is counted apart from the ones that have.
    """
    count = 0
    for source, (target, _evidence) in pairs.items():
        if set(ps2.strings.get(source, ())) & set(ps3.strings.get(target, ())):
            count += 1
    return count


def reach_pairs(ps2: Side, ps3: Side, pairs: dict[int, tuple]) -> int:
    """How many of the pairs reach a message in common.

    A function reads its own messages and the messages of the functions it
    calls.  Two functions of the same game that read no message in common
    may still reach the same message, one hop away: the function that
    prints the message of the game is not the function that owns it.

    The yardstick is the rate of the random pairs, which the tool
    measures: a pair that reaches the same message as a random pair does
    not is not supported by anything.
    """
    count = 0
    for source, (target, _evidence) in pairs.items():
        if ps2.reach.get(source, set()) & ps3.reach.get(target, set()):
            count += 1
    return count


def random_reach(ps2: Side, ps3: Side, samples: int = 20000,
                 seed: int = 20261021) -> float:
    """The rate of the random pairs that reach a message in common.

    The measure is the yardstick of the reach test: a pair that reaches
    the same message as a random pair does not is not supported by
    anything.
    """
    import random as _random

    left = [f for f in ps2.functions if ps2.reach.get(f)]
    right = [f for f in ps3.functions if ps3.reach.get(f)]
    if not left or not right:
        return 0.0
    generator = _random.Random(seed)
    hits = 0
    for _index in range(samples):
        a = generator.choice(left)
        b = generator.choice(right)
        if ps2.reach.get(a, set()) & ps3.reach.get(b, set()):
            hits += 1
    return hits / samples


def leave_one_out(ps2: Side, ps3: Side, anchors: list[tuple[int, int]],
                  key) -> tuple[int, int]:
    """How many of the anchored pairs a key finds when it is not given them.

    The anchors are the pairs the message key has established, and they
    are the only pairs whose rightness can be checked.  A key is measured
    by taking one anchor away and asking whether the key finds it again.
    A key that never finds it back says nothing that the anchors did not
    already say.
    """
    if len(anchors) < 2:
        return 0, 0
    hits = 0
    for index, (source, target) in enumerate(anchors):
        rest = anchors[:index] + anchors[index + 1:]
        pairs = key(rest)
        found = pairs.get(source)
        if found is not None and found[0] == target:
            hits += 1
    return hits, len(anchors)


def merge_proposals(paths: list[str], out_path: str) -> int:
    """Merge the tables of the pairs, and keep the verified ones.

    A pair that the *string* key verified is a proposal of a name: the name
    comes from the PlayStation 2 decompilation, and the message the two
    functions share is the proof that they are the same function.  A pair
    that only the graph or the profile proposed stays out: it is a
    hypothesis, and the table of the hypotheses is the table of the keys.
    """
    rows = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                if row.get("confidence") != "verified":
                    continue
                rows.append(row)
    rows.sort(key=lambda row: (row["ps3_program"], row["ps3_function"]))

    columns = ["program", "address", "name", "ps2_source", "ps2_name",
               "evidence", "keys", "state"]
    with open(out_path, "w", encoding="utf-8", newline="\n") as out:
        out.write("\t".join(columns) + "\n")
        for row in rows:
            source = row.get("ps2_source", "")
            name = source.rsplit("/", 1)[-1] if source else ""
            out.write("\t".join([
                row["ps3_program"], row["ps3_function"], name,
                source, row.get("ps2_name", ""),
                row.get("evidence", ""), row.get("keys", ""),
                "proposed" if name else "matched",
            ]) + "\n")
    named = sum(1 for row in rows if row.get("ps2_source"))
    print(f"wrote {out_path}: {len(rows)} verified pairs, {named} with a name")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ps2-funcs", action="append", default=[],
                        help="a PS2 function table")
    parser.add_argument("--ps2-strings", action="append", default=[],
                        help="a PS2 string table")
    parser.add_argument("--ps2-dir", default=None,
                        help="a directory of PS2 tables, read as a whole")
    parser.add_argument("--ps3-funcs", action="append", default=[],
                        help="a PS3 function table")
    parser.add_argument("--ps3-strings", action="append", default=[],
                        help="a PS3 string table")
    parser.add_argument("--ps3-dir", default=None,
                        help="a directory of PS3 tables, read as a whole")
    parser.add_argument("--ps3-program", default=None,
                        help="the PS3 program to use (default: the biggest)")
    parser.add_argument("--names", required=True,
                        help="the table of the PS2 names, sources and places")
    parser.add_argument("--levels", required=True,
                        help="a table that gives the name of a level program")
    parser.add_argument("--minimum", type=int, default=MINIMUM_ANCHOR,
                        help="the shortest message that may anchor a pair")
    parser.add_argument("--tolerance", type=int, default=4,
                        help="the rank distance the order key accepts")
    parser.add_argument("--margin", type=float, default=0.0,
                        help="the share the profile key wants between its "
                             "best candidate and its second")
    parser.add_argument("--rounds", type=int, default=4,
                        help="the rounds of the refinement of the graph")
    parser.add_argument("--reach", type=int, default=1,
                        help="the hops of the call graph the reach test walks")
    parser.add_argument("--threshold", type=float, default=0.05,
                        help="the share of the messages the reach test wants")
    parser.add_argument("--out", required=True, help="the table of the pairs")
    parser.add_argument("--report", default=None,
                        help="the table of the keys")
    parser.add_argument("--merge", action="append", default=[],
                        metavar="PAIRS.tsv",
                        help="merge the tables of the pairs already measured, "
                             "and keep the verified ones as the proposals")
    args = parser.parse_args(argv)

    if args.merge:
        return merge_proposals(args.merge, args.out)

    levels: dict[str, str] = {}
    with open(args.levels, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            levels[row["level"]] = row["program"]

    ps2_func_paths = list(args.ps2_funcs)
    ps2_string_paths = list(args.ps2_strings)
    if args.ps2_dir:
        ps2_func_paths += sorted(glob.glob(os.path.join(args.ps2_dir, "*.funcs.tsv")))
        ps2_string_paths += sorted(glob.glob(os.path.join(args.ps2_dir, "*.strings.tsv")))
    ps3_func_paths = list(args.ps3_funcs)
    ps3_string_paths = list(args.ps3_strings)
    if args.ps3_dir:
        ps3_func_paths += sorted(glob.glob(os.path.join(args.ps3_dir, "*.funcs.tsv")))
        ps3_string_paths += sorted(glob.glob(os.path.join(args.ps3_dir, "*.strings.tsv")))

    ps2_programs = read_program_table(ps2_func_paths, None)
    ps2_strings = read_string_table(ps2_string_paths, None)
    names = read_names(args.names)
    ps2, label, resolved = build_ps2_side(ps2_programs, ps2_strings, names, levels)
    print(f"PS2: {len(names)} game functions, {resolved} of their addresses "
          f"resolved in the tables, {len(ps2.string_functions)} messages")

    ps3_programs = read_program_table(ps3_func_paths, args.ps3_program)
    ps3_strings = read_string_table(ps3_string_paths, args.ps3_program)
    if not ps3_programs:
        print("error: no PS3 program", file=sys.stderr)
        return 1
    program = args.ps3_program or max(ps3_programs, key=lambda p: len(ps3_programs[p]))
    ps3 = build_ps3_side(ps3_programs, ps3_strings, program)
    print(f"PS3 program {program}: {len(ps3.functions)} functions, "
          f"{len(ps3.string_functions)} messages")

    anchors = key_string(ps2, ps3, args.minimum)
    print(f"{len(anchors)} pairs anchored by a message of at least {args.minimum} characters")
    anchor_list = [(source, target) for source, (target, _text) in anchors.items()]

    keys = {
        "string": anchors,
        "profile": key_profile(ps2, ps3, args.margin),
        "order": key_order(ps2, ps3, anchor_list, args.tolerance),
        "calls": key_calls(ps2, ps3, anchor_list),
        "callers": key_callers(ps2, ps3, anchor_list),
        "graph": key_graph(ps2, ps3, anchor_list, args.rounds),
        "source": key_source(ps2, ps3),
    }
    report = evaluate(keys)
    ps2.build_reach(args.reach)
    ps3.build_reach(args.reach)
    baseline = random_reach(ps2, ps3)
    print(f"  a random pair reaches a message in common {baseline * 100:.2f}% "
          f"of the time")
    for row in report["keys"]:
        named = sum(1 for source in keys[row["key"]] if ps2.sources.get(source))
        row["named"] = named
        row["shared"] = shared_messages(ps2, ps3, keys[row["key"]])
        row["reach"] = reach_pairs(ps2, ps3, keys[row["key"]])
        print(f"  {row['key']:8s} {row['pairs']:6d} pairs ({named} named), "
              f"{row['confirmed']:6d} confirmed, {row['unverified']:6d} unverified, "
              f"{row['conflicts']:6d} in conflict, {row['collisions']:6d} in collision, "
              f"{row['shared']:6d} share a message, {row['reach']:6d} reach one")
    monotone = _monotone(ps2, ps3, anchor_list)
    print(f"  the order of the {len(anchor_list)} anchors keeps its order "
          f"{monotone} time(s) out of {max(len(anchor_list) - 1, 0)}")
    for name, key in (("graph", lambda a: key_graph(ps2, ps3, a, args.rounds)),
                      ("order", lambda a: key_order(ps2, ps3, a, args.tolerance)),
                      ("calls", lambda a: key_calls(ps2, ps3, a)),
                      ("callers", lambda a: key_callers(ps2, ps3, a))):
        hits, total = leave_one_out(ps2, ps3, anchor_list, key)
        print(f"  the {name} key finds {hits} of the {total} anchors back "
              f"when it is not given them")

    votes = report["votes"]
    claims = report["claims"]
    # When several functions of one side claim the same function of the
    # other, one of them is right and the others are refuted: the claim
    # that the most keys make wins, and the string key wins the tie.
    winner: dict[int, tuple[int, int]] = {}
    for target, sources in claims.items():
        best = None
        for source in sources:
            row = votes[source]
            score = (len(row[target]), 1 if "string" in row[target] else 0)
            if best is None or score > best[0]:
                best = (score, source)
        if best is not None:
            winner[target] = best
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("ps2_name\tps2_source\tps2_size\tps3_program\tps3_function"
                   "\tps3_size\tkeys\tvotes\tconfidence\tevidence\tcollision\n")
        for source in sorted(votes):
            row = votes[source]
            target = max(row.items(), key=lambda item: (len(item[1]), -item[0]))[0]
            names_here = sorted(row[target])
            common = sorted(set(ps2.strings.get(source, ()))
                            & set(ps3.strings.get(target, ())))
            reached = bool(ps2.reach.get(source, set())
                           & ps3.reach.get(target, set()))
            if common:
                confidence = "verified"
            elif reached:
                confidence = "reachable"
            elif names_here and set(names_here) & {"calls", "callers", "graph"}:
                confidence = "derived"
            else:
                confidence = "hypothesis"
            if len(claims[target]) > 1 and winner[target][1] != source:
                # another function of the PS2 claims the same function of
                # the PS3, and it is the one the keys agree on
                confidence = "refuted"
            evidence = " | ".join(text.replace("\n", "\\n")[:60] for text in common[:3])
            out.write(f"{ps2.names.get(source, label.get(source, ''))}"
                      f"\t{ps2.sources.get(source, '')}\t{ps2.functions.get(source, 0)}"
                      f"\t{program}\t0x{target:08X}\t{ps3.functions.get(target, 0)}"
                      f"\t{','.join(names_here)}\t{len(names_here)}"
                      f"\t{confidence}\t{evidence}\t{len(claims[target])}\n")
    print(f"wrote {args.out}")

    if args.report:
        with open(args.report, "w", encoding="utf-8", newline="\n") as out:
            out.write("key\tpairs\tnamed\tconfirmed\tunverified\tconflicts"
                      "\tcollisions\tshared_message\treach\n")
            for row in report["keys"]:
                out.write(f"{row['key']}\t{row['pairs']}\t{row['named']}"
                          f"\t{row['confirmed']}\t{row['unverified']}\t{row['conflicts']}"
                          f"\t{row['collisions']}\t{row['shared']}\t{row['reach']}\n")
        print(f"wrote {args.report}")
    return 0


def _monotone(ps2: Side, ps3: Side, anchors: list[tuple[int, int]]) -> int:
    """How many times the anchors keep their order from one to the next.

    The order key is worth nothing when the anchors do not keep their
    order: the linker of the two builds lays the functions out in
    different orders, and the rank of a function says nothing about the
    rank of its counterpart.
    """
    points = sorted((ps2.rank[a], ps3.rank[b]) for a, b in anchors
                     if a in ps2.rank and b in ps3.rank)
    return sum(1 for left, right in zip(points, points[1:]) if left[1] < right[1])


if __name__ == "__main__":
    raise SystemExit(main())
