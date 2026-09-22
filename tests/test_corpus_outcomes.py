"""What the product reports on every approved corpus label, pinned.

`eval/corpus_check.py` runs each of the 30 real labels through
`Evaluator.evaluate` with the real rule pack and the production reader, with
only the OCR stood in for by the label's frozen readings. This file holds the
product to what that run reports today, check by check, so that a change to
the reader or the rules shows up as a named difference in the outcome of a
real label rather than as a unit test that still passes.

Every corpus label was approved by TTB, so a mismatch is either a difference
the label genuinely carries or the product reading the label wrong. Both lists
are written out below. A wrong mismatch that a fix removes fails here until its
line is deleted, and a new one fails until it is either fixed or listed with
its cause.

`tests/fixtures/corpus_outcomes.json` is the whole of today's run: every
label's outcome, every check's outcome and reason code, and the scoreboard.
When a change moves any of it on purpose, rewrite it with

    uv run python -m eval.corpus_check --json tests/fixtures/corpus_outcomes.json

and say in the commit which outcomes moved and why.
"""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from pathlib import Path

from eval.corpus_check import LabelOutcome, _as_json, check, corpus_cases, scoreboard

EXPECTED = Path("tests/fixtures/corpus_outcomes.json")

# The label prints a warning that differs from 27 CFR 16.21, and the reader
# read it right. The warning "has to be exact", so these stay mismatches.
GENUINE_MISMATCHES = {
    ("ttb-26212001000085", "common.warning.verbatim"): "prints 'beverage' for 'beverages'",
    ("ttb-26229001000034", "common.warning.verbatim"): "prints 'risks' for 'risk'",
}

# The product reports a mismatch on an approved label because it read the
# label wrong. Each line names the cause. When a fix lands, delete its line.
WRONG_MISMATCHES = {
    (
        "ttb-26240001000454",
        "malt.class_type.matches_application",
    ): "'Double India Pale Ale' is handwritten and not read; another collar line is picked",
}


@lru_cache(maxsize=1)
def _outcomes() -> tuple[LabelOutcome, ...]:
    return tuple(asyncio.run(check(corpus_cases())))


def _mismatches() -> set[tuple[str, str]]:
    return {
        (o.label_id, rule_id)
        for o in _outcomes()
        for rule_id, r in o.rules.items()
        if r.disposition == "fail"
    }


def test_every_corpus_label_is_checked() -> None:
    assert len(_outcomes()) == 30
    assert all(o.rules for o in _outcomes())


def test_every_mismatch_is_named_with_its_cause() -> None:
    """A mismatch on an approved label that nobody has explained is a
    regression until it is fixed or listed."""
    unexplained = _mismatches() - GENUINE_MISMATCHES.keys() - WRONG_MISMATCHES.keys()
    assert not unexplained, f"mismatches with no recorded cause: {sorted(unexplained)}"


def test_every_listed_mismatch_is_still_one() -> None:
    """A fixed mismatch fails here until its line is deleted, so the lists
    never claim a fault the product no longer has."""
    gone = (GENUINE_MISMATCHES.keys() | WRONG_MISMATCHES.keys()) - _mismatches()
    assert not gone, f"no longer a mismatch; delete the line: {sorted(gone)}"


def test_every_outcome_is_what_the_product_reported_before() -> None:
    """Every label's outcome and every check's outcome and reason code, against
    the committed run. The assertion names each difference."""
    expected = json.loads(EXPECTED.read_text())
    actual = _as_json(list(_outcomes()))
    differences = []
    for label_id in sorted(expected["labels"].keys() | actual["labels"].keys()):
        was = expected["labels"].get(label_id, {})
        now = actual["labels"].get(label_id, {})
        if was.get("disposition") != now.get("disposition"):
            differences.append(f"{label_id}: {was.get('disposition')} -> {now.get('disposition')}")
        for rule_id in sorted(was.get("rules", {}).keys() | now.get("rules", {}).keys()):
            before, after = was.get("rules", {}).get(rule_id), now.get("rules", {}).get(rule_id)
            if before != after:
                differences.append(f"{label_id} {rule_id}: {before} -> {after}")
    assert not differences, "\n".join(differences)
    assert actual["scoreboard"] == expected["scoreboard"]


def test_the_scoreboard_counts_only_checks_that_applied() -> None:
    """A check that did not apply was not a question, so it is in no count."""
    board = scoreboard(list(_outcomes()))
    applied = sum(
        1 for o in _outcomes() for r in o.rules.values() if r.disposition != "not_applicable"
    )
    assert board["checks"] == applied
    assert sum(board["check_outcomes"].values()) == applied
    assert sum(board["label_outcomes"].values()) == 30
