"""Guards on what the DRC may skip (review M5): hw_kicad.py drops excluded markers, so an exclusion
added in the GUI for a clearance, unconnected or parity marker would pass CI, and an unconditioned
clearance or track width rule in a .kicad_dru overrides every net class (both happened earlier in
rev A). Exclusions may only be silkscreen markers, each with its reason; clearance and track width
rules must name what they apply to."""

import json
import pathlib
import re
import unittest

HARDWARE = pathlib.Path(__file__).resolve().parent.parent.parent / "hardware"
BOARDS = ("owl-mainboard", "perch-dock")
LIMITED = ("clearance", "track_width")


def exclusion_errors(project: dict) -> list[str]:
    """Exclusions that are not silk_* or carry no comment (KiCad stores [key, comment] pairs)."""
    errors = []
    for entry in project["board"]["design_settings"].get("drc_exclusions", []):
        key, comment = (entry, "") if isinstance(entry, str) else (entry[0], entry[1] if len(entry) > 1 else "")
        kind = key.split("|")[0]
        if not kind.startswith("silk_"):
            errors.append(f"{kind} may not be excluded: {key}")
        if not comment.strip():
            errors.append(f"no comment on {key}")
    return errors


def parse(text: str) -> list:
    """The .kicad_dru S-expressions as nested lists (comment lines dropped)."""
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    stack = [[]]
    for token in re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text):
        if token == "(":
            stack.append([])
        elif token == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(token)
    assert len(stack) == 1, "unbalanced parentheses"
    return stack[0]


def dru_errors(text: str) -> list[str]:
    """Rules with a clearance or track_width constraint but no condition."""
    errors = []
    for rule in parse(text):
        if not isinstance(rule, list) or not rule or rule[0] != "rule":
            continue
        parts = [p for p in rule[2:] if isinstance(p, list) and p]
        kinds = {p[1] for p in parts if p[0] == "constraint" and len(p) > 1}
        if kinds & set(LIMITED) and not any(p[0] == "condition" for p in parts):
            errors.append(f"rule {rule[1]} sets {', '.join(sorted(kinds & set(LIMITED)))} with no condition")
    return errors


class RulesGuardTest(unittest.TestCase):
    def test_exclusion_check_catches_wrong_types_and_missing_comments(self):
        project = {"board": {"design_settings": {"drc_exclusions": [
            ["silk_edge_clearance|1|2|a|b", "outline overhangs the edge by design"],
            ["clearance|1|2|a|b", "too close"],
            ["silk_overlap|1|2|a|b", "  "],
            "unconnected_items|1|2|a|b",
        ]}}}
        self.assertEqual(exclusion_errors(project), [
            "clearance may not be excluded: clearance|1|2|a|b",
            "no comment on silk_overlap|1|2|a|b",
            "unconnected_items may not be excluded: unconnected_items|1|2|a|b",
            "no comment on unconnected_items|1|2|a|b",
        ])

    def test_dru_check_catches_unconditioned_clearance_and_track_width(self):
        text = "\n".join([
            "(version 1)",
            "# (rule \"commented out\" (constraint clearance (min 0.09mm)))",
            "(rule \"board-wide clearance\"",
            "\t(constraint clearance (min 0.09mm)))",
            "(rule \"board-wide track\" (layer \"F.Cu\")",
            "\t(constraint track_width (min 0.09mm)))",
            "(rule \"pads only\"",
            "\t(condition \"A.memberOfFootprint('U303') && B.memberOfFootprint('U303')\")",
            "\t(constraint clearance (min 0.15mm)))",
            "(rule \"edge\" (constraint edge_clearance (min 0.3mm)))",
        ])
        self.assertEqual(dru_errors(text), [
            'rule "board-wide clearance" sets clearance with no condition',
            'rule "board-wide track" sets track_width with no condition',
        ])

    def test_both_boards_exclude_only_silkscreen_markers_with_a_reason(self):
        for board in BOARDS:
            project = json.loads((HARDWARE / board / f"{board}.kicad_pro").read_text())
            self.assertEqual(exclusion_errors(project), [], board)

    def test_no_dru_rule_overrides_the_net_classes(self):
        for board in BOARDS:
            self.assertEqual(dru_errors((HARDWARE / board / f"{board}.kicad_dru").read_text()), [], board)


if __name__ == "__main__":
    unittest.main()
