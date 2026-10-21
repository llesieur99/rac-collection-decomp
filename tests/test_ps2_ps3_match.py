"""Tests for the correspondence between the PS2 and the PS3, on synthetic data.

The two sides are built here: a few functions, a few messages, a few calls.
No byte of a game and no address of a game is in the tests.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import ps2_ps3_match  # noqa: E402


def side(name, functions, calls=None, strings=None):
    """A side of the matching, built by hand."""
    out = ps2_ps3_match.Side(name)
    for address, size in functions.items():
        out.functions[address] = size
        out.calls[address] = list((calls or {}).get(address, ()))
    for address, texts in (strings or {}).items():
        out.strings[address] = set(texts)
    out.finish()
    return out


class StringKeyTest(unittest.TestCase):
    """The key of the message that only one function reads."""

    def setUp(self):
        self.ps2 = side("PS2",
                        {0x100: 10, 0x200: 10, 0x300: 10},
                        strings={0x100: {"a message of the game"},
                                 0x200: {"another message"}})
        self.ps3 = side("PS3",
                        {0x10: 10, 0x20: 10},
                        strings={0x10: {"a message of the game"},
                                 0x20: {"another message"}})

    def test_a_rare_message_anchors_a_pair(self):
        pairs = ps2_ps3_match.key_string(self.ps2, self.ps3, 8)
        self.assertEqual(pairs[0x100], (0x10, "a message of the game"))
        self.assertEqual(pairs[0x200], (0x20, "another message"))

    def test_a_short_message_anchors_nothing(self):
        pairs = ps2_ps3_match.key_string(self.ps2, self.ps3, 32)
        self.assertEqual(pairs, {})

    def test_a_message_that_several_functions_read_anchors_nothing(self):
        self.ps2.strings[0x300] = {"a message of the game"}
        self.ps2.finish()
        pairs = ps2_ps3_match.key_string(self.ps2, self.ps3, 8)
        self.assertNotIn(0x100, pairs)
        self.assertNotIn(0x300, pairs)


class ProfileKeyTest(unittest.TestCase):
    """The key of the whole set of messages of a function."""

    def test_the_best_candidate_wins(self):
        ps2 = side("PS2", {0x100: 10, 0x200: 10},
                   strings={0x100: {"one", "two"}, 0x200: {"three"}})
        ps3 = side("PS3", {0x10: 10, 0x20: 10},
                   strings={0x10: {"one", "two", "three"}, 0x20: {"three"}})
        pairs = ps2_ps3_match.key_profile(ps2, ps3)
        self.assertEqual(pairs[0x100][0], 0x10)
        self.assertEqual(pairs[0x200][0], 0x20)

    def test_a_margin_silences_the_key(self):
        ps2 = side("PS2", {0x100: 10},
                   strings={0x100: {"one", "two"}})
        ps3 = side("PS3", {0x10: 10, 0x20: 10},
                   strings={0x10: {"one", "two"}, 0x20: {"one", "three"}})
        pairs = ps2_ps3_match.key_profile(ps2, ps3, margin=0.0)
        self.assertEqual(pairs[0x100][0], 0x10)
        # the second candidate is a third of the share: a margin of
        # two thirds silences the key
        pairs = ps2_ps3_match.key_profile(ps2, ps3, margin=0.7)
        self.assertNotIn(0x100, pairs)


class CallsKeyTest(unittest.TestCase):
    """The key of the shape of the call graph."""

    def test_the_callee_of_an_anchor_is_proposed(self):
        ps2 = side("PS2", {0x100: 10, 0x110: 10}, calls={0x100: [0x110]})
        ps3 = side("PS3", {0x10: 10, 0x11: 10}, calls={0x10: [0x11]})
        pairs = ps2_ps3_match.key_calls(ps2, ps3, [(0x100, 0x10)])
        self.assertEqual(pairs[0x110], (0x11, 0))

    def test_the_walk_stops_when_the_counts_differ(self):
        ps2 = side("PS2", {0x100: 10, 0x110: 10}, calls={0x100: [0x110]})
        ps3 = side("PS3", {0x10: 10, 0x11: 10, 0x12: 10}, calls={0x10: [0x11, 0x12]})
        pairs = ps2_ps3_match.key_calls(ps2, ps3, [(0x100, 0x10)])
        self.assertEqual(pairs, {})

    def test_the_caller_of_an_anchor_is_proposed_when_there_is_one(self):
        ps2 = side("PS2", {0x100: 10, 0x110: 10}, calls={0x110: [0x100]})
        ps3 = side("PS3", {0x10: 10, 0x11: 10}, calls={0x11: [0x10]})
        pairs = ps2_ps3_match.key_callers(ps2, ps3, [(0x100, 0x10)])
        self.assertEqual(pairs[0x110], (0x11, 0))

    def test_the_caller_is_not_proposed_when_there_are_several(self):
        ps2 = side("PS2", {0x100: 10, 0x110: 10, 0x120: 10},
                   calls={0x110: [0x100], 0x120: [0x100]})
        ps3 = side("PS3", {0x10: 10, 0x11: 10, 0x12: 10},
                   calls={0x11: [0x10], 0x12: [0x10]})
        pairs = ps2_ps3_match.key_callers(ps2, ps3, [(0x100, 0x10)])
        self.assertEqual(pairs, {})


class GraphKeyTest(unittest.TestCase):
    """The key of the refinement of the call graph."""

    def test_the_anchors_are_found_again(self):
        ps2 = side("PS2", {0x100: 10, 0x110: 10}, calls={0x100: [0x110]})
        ps3 = side("PS3", {0x10: 10, 0x11: 10}, calls={0x10: [0x11]})
        pairs = ps2_ps3_match.key_graph(ps2, ps3, [(0x100, 0x10)], 2)
        self.assertEqual(pairs[0x100][0], 0x10)

    def test_a_function_of_a_different_shape_is_not_proposed(self):
        # the PS2 function is alone, the PS3 one is in a chain
        ps2 = side("PS2", {0x100: 10, 0x110: 10}, calls={0x100: [0x110]})
        ps3 = side("PS3", {0x10: 10, 0x11: 10, 0x12: 10},
                   calls={0x10: [0x11], 0x11: [0x12]})
        pairs = ps2_ps3_match.key_graph(ps2, ps3, [(0x100, 0x10)], 2)
        # the anchor is kept, but nothing else is unique on both sides
        self.assertNotIn(0x110, pairs)


class MeasureTest(unittest.TestCase):
    """The measure of the keys: the conflicts and the collisions."""

    def test_a_conflict_is_counted(self):
        keys = {
            "string": {0x100: (0x10, "one")},
            "profile": {0x100: (0x20, 0.5)},
        }
        report = ps2_ps3_match.evaluate(keys)
        rows = {row["key"]: row for row in report["keys"]}
        self.assertEqual(rows["string"]["conflicts"], 1)
        self.assertEqual(rows["profile"]["conflicts"], 1)

    def test_a_collision_is_counted(self):
        keys = {
            "string": {0x100: (0x10, "one")},
            "profile": {0x200: (0x10, 0.5)},
        }
        report = ps2_ps3_match.evaluate(keys)
        rows = {row["key"]: row for row in report["keys"]}
        self.assertEqual(rows["string"]["collisions"], 1)
        self.assertEqual(rows["profile"]["collisions"], 1)

    def test_a_pair_of_two_keys_is_confirmed(self):
        keys = {
            "string": {0x100: (0x10, "one")},
            "profile": {0x100: (0x10, 0.5)},
        }
        report = ps2_ps3_match.evaluate(keys)
        rows = {row["key"]: row for row in report["keys"]}
        self.assertEqual(rows["string"]["confirmed"], 1)
        self.assertEqual(rows["string"]["unverified"], 0)


class ReachTest(unittest.TestCase):
    """The test of the messages the two functions reach."""

    def test_the_reach_grows_with_the_calls(self):
        ps2 = side("PS2", {0x100: 10, 0x110: 10},
                   calls={0x100: [0x110]},
                   strings={0x110: {"the message"}})
        ps3 = side("PS3", {0x10: 10, 0x11: 10},
                   calls={0x10: [0x11]},
                   strings={0x11: {"the message"}})
        ps2.build_reach(1)
        ps3.build_reach(1)
        # neither function reads the message, but they both reach it
        self.assertFalse(ps2.strings.get(0x100, set()) & ps3.strings.get(0x10, set()))
        self.assertTrue(ps2.reach[0x100] & ps3.reach[0x10])


class NamesTest(unittest.TestCase):
    """The table of the PS2 names, sources and places."""

    def test_the_table_is_read(self):
        rows = ps2_ps3_match.read_names(NAMES)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "FUN_001e9168")
        self.assertEqual(rows[0]["source"],
                         "assembly/textbin/rendering/texture/load_pif_as_psmt8_h")
        self.assertEqual(rows[0]["places"], [("00", 0x100), ("01", 0x200)])

    def test_the_names_are_attached_to_the_functions(self):
        levels = {"00": "LVL00", "01": "LVL01"}
        ps2 = side("LVL00", {0x100: 10})
        attached = ps2_ps3_match.attach_names(ps2, ps2_ps3_match.read_names(NAMES), levels)
        self.assertEqual(attached, 1)
        self.assertEqual(ps2.names[0x100], "FUN_001e9168")
        self.assertEqual(ps2.sources[0x100],
                         "assembly/textbin/rendering/texture/load_pif_as_psmt8_h")


NAMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                     "ps2-names.tsv")


if __name__ == "__main__":
    unittest.main()
