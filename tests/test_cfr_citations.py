"""Parsing a citation string into the regulation sections it names.

This is the part `docs/decisions.md#0034` refused the citation panel over, and
the eCFR API does not answer it: the API supplies text for a section a caller
already knows how to name, and the rule pack names its sections in prose. 0034's
words were that the strings "are heterogeneous enough that parsing them into
section URLs would mislink some, and a compliance tool showing the wrong
regulation is worse than one showing none."

So every string the rule pack actually uses is asserted here against the
sections a reader of that string would turn to, and a string the grammar does
not cover parses to nothing rather than to a guess.
"""

from __future__ import annotations

import glob
from pathlib import Path

import pytest
import yaml

from app.cfr.citations import Section, Subpart, parse_citation


def _rule_pack_citations() -> set[str]:
    """Every distinct `cfr_citation` in `rules/`, read from the pack itself.

    Taken from the files rather than listed here, so a citation added to the
    pack is covered by `test_every_rule_pack_citation_parses` on the day it is
    added rather than on the day someone remembers this test.
    """
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "cfr_citation" and isinstance(value, str):
                    found.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for path in glob.glob("rules/**/*.yaml", recursive=True):
        walk(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    return found


# One row per shape the pack uses. The expected side is written out rather than
# computed, because a parser checked against its own logic checks nothing.
CASES: list[tuple[str, list[Section | Subpart]]] = [
    # A bare section.
    ("27 CFR §4.33", [Section(27, "4", "4.33", None)]),
    ("27 CFR §16.21", [Section(27, "16", "16.21", None)]),
    # A section with the paragraph the rule rests on.
    ("27 CFR §16.22(a)(2)", [Section(27, "16", "16.22", "(a)(2)")]),
    ("27 CFR §4.32(a)(1)", [Section(27, "4", "4.32", "(a)(1)")]),
    ("27 CFR §5.63(b)(2)", [Section(27, "5", "5.63", "(b)(2)")]),
    ("27 CFR §4.36(b)", [Section(27, "4", "4.36", "(b)")]),
    # Two sections of one part; the second inherits the title.
    (
        "27 CFR §4.32(a)(1), §4.33",
        [Section(27, "4", "4.32", "(a)(1)"), Section(27, "4", "4.33", None)],
    ),
    (
        "27 CFR §5.63(a), §5.65(a)",
        [Section(27, "5", "5.63", "(a)"), Section(27, "5", "5.65", "(a)")],
    ),
    # A second title, stated in full, resets the title for what follows it.
    (
        "27 CFR §4.35(e), 19 CFR §134.45",
        [Section(27, "4", "4.35", "(e)"), Section(19, "134", "134.45", None)],
    ),
    (
        "27 CFR §7.69, 19 CFR §134.45",
        [Section(27, "7", "7.69", None), Section(19, "134", "134.45", None)],
    ),
    # A whole subpart, named against a part rather than a section.
    ("27 CFR §5 Subpart I", [Subpart(27, "5", "I")]),
    # A subpart after a section inherits that section's part, which is the only
    # reading available: "Subpart I" alone names no part.
    (
        "27 CFR §5.63(a), Subpart I",
        [Section(27, "5", "5.63", "(a)"), Subpart(27, "5", "I")],
    ),
    (
        "27 CFR §7.63(a)(2), Subpart I",
        [Section(27, "7", "7.63", "(a)(2)"), Subpart(27, "7", "I")],
    ),
]


@pytest.mark.parametrize(("citation", "expected"), CASES, ids=[c for c, _ in CASES])
def test_parses_to_the_sections_a_reader_would_turn_to(
    citation: str, expected: list[Section | Subpart]
) -> None:
    assert parse_citation(citation) == expected


def test_every_rule_pack_citation_parses() -> None:
    """No rule in the pack cites something the panel cannot name.

    A citation that parses to nothing is honest at runtime — the panel says the
    text is not held — but in the pack it means a reviewer loses the regulation
    for that finding, so it fails here instead.
    """
    citations = _rule_pack_citations()
    assert citations, "no citations found in rules/ — the test is reading the wrong place"
    unparsed = sorted(c for c in citations if not parse_citation(c))
    assert unparsed == [], f"citations the parser cannot name: {unparsed}"


# A parser that guesses is the failure 0034 named. These are the shapes that
# invite a guess, and each must yield nothing rather than a plausible section.
@pytest.mark.parametrize(
    "citation",
    [
        "",
        "   ",
        "see the regulation",
        "27 CFR",  # a title and no section
        "CFR §4.33",  # no title
        "§4.33",  # no title
        "27 USC §4.33",  # not the CFR
        "Subpart I",  # a subpart with no part to hang it on
        "27 CFR Subpart I",  # still no part
        "27 CFR §4.33 and following",  # trailing prose the grammar does not cover
    ],
    ids=lambda c: repr(c),
)
def test_a_string_the_grammar_does_not_cover_names_nothing(citation: str) -> None:
    assert parse_citation(citation) == []


def test_a_partial_parse_is_refused_whole() -> None:
    """Half a citation is not half an answer.

    If one reference in a comma-separated citation cannot be read, the panel
    must not quietly show the others as though they were the whole of what the
    rule rests on.
    """
    assert parse_citation("27 CFR §4.33, something else entirely") == []
