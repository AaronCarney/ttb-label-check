"""name_address_match lines the name the label prints up with the free-text
applicant block the registry holds.

The block runs the applicant's trading name, its legal name, a street, a city,
a State, a ZIP and any trade name together:

    CHATEAU DIANA, CHATEAU DIANA, LLC 6195 DRY CREEK RD HEALDSBURG CA 95448

The label prints one of those names behind a required lead-in phrase, with a
city and a State. The check takes the first two words after the lead-in as the
name, requires them in the block as consecutive words, and requires one more
of the label's words in the block as well, so something corroborates the name
rather than a single common word carrying the match alone.

A State written out and the same State as its postal code are the same State,
and the two sides routinely differ on which they write. Both are folded to the
postal code first, which is what lets "California" corroborate "CA" (PRD FR-7).

Nothing here rejects. A name the block does not carry is not evidence that the
label is wrong — the block need not list every name an applicant may print —
so the check reports that it could not settle the question and a reviewer
reads both.
"""

from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.name_address_match import name_address_match
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

CHATEAU_DIANA_BLOCK = "CHATEAU DIANA, CHATEAU DIANA, LLC 6195 DRY CREEK RD HEALDSBURG CA 95448"


def _rule():
    return make_rule(
        rule_id="wine.name_address.matches_application",
        cfr_citation="27 CFR §4.35",
        validator="name_address_match",
        reason_code="NAME_ADDRESS.MATCH.NEEDS_REVIEW",
        severity=Severity.WARN,
        match_policy=MatchPolicy.NORMALIZED,
        parameters={
            "lead_in_ends_with": "by",
            "lead_in_window_words": 8,
            "anchor_words": 2,
        },
    )


def _verdict(label_statement: str | None, block: str | None):
    obs = make_obs(
        field_id="bottler",
        value={"name": label_statement or "", "city": "", "state": ""},
    )
    exp = make_expected(field_id="name_and_address", value=block)
    return name_address_match(obs, exp, _rule(), make_context())


# ---------------------------------------------------------------------------
# The State name and its postal code are the same State
# ---------------------------------------------------------------------------


def test_a_state_written_out_corroborates_its_postal_code() -> None:
    """The label writes California; the registry block writes CA. Without the
    fold the State corroborates nothing and the city has to carry the match
    alone — which it cannot do when the label prints no city."""
    res = _verdict("CELLARED AND BOTTLED BY CHATEAU DIANA, California", CHATEAU_DIANA_BLOCK)
    assert res.outcome is Outcome.PASS


def test_the_city_and_the_state_together_match() -> None:
    res = _verdict(
        "CELLARED AND BOTTLED BY CHATEAU DIANA, Healdsburg, California",
        CHATEAU_DIANA_BLOCK,
    )
    assert res.outcome is Outcome.PASS


def test_a_two_word_state_name_folds() -> None:
    res = _verdict(
        "PRODUCED AND BOTTLED BY TACONIC DISTILLERY, New York",
        "Taconic Distillery, Taconic Distillery, LLC 179 BOWEN RD Stanfordville NY 12581",
    )
    assert res.outcome is Outcome.PASS


def test_the_longest_state_name_wins() -> None:
    """ "West Virginia" is West Virginia, not Virginia with a word in front."""
    res = _verdict(
        "BOTTLED BY ACME SPIRITS, West Virginia",
        "ACME SPIRITS, ACME SPIRITS LLC 1 MAIN ST CHARLESTON WV 25301",
    )
    assert res.outcome is Outcome.PASS


def test_a_different_state_does_not_corroborate() -> None:
    """Virginia is not West Virginia, and the fold must not blur them."""
    res = _verdict(
        "BOTTLED BY ACME SPIRITS, Virginia",
        "ACME SPIRITS, ACME SPIRITS LLC 1 MAIN ST CHARLESTON WV 25301",
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE


# ---------------------------------------------------------------------------
# What the check does when it cannot line the two sides up
# ---------------------------------------------------------------------------


def test_a_name_the_block_does_not_carry_goes_to_a_reviewer() -> None:
    res = _verdict("BOTTLED BY SOMEONE ELSE, Healdsburg, California", CHATEAU_DIANA_BLOCK)
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == "NAME_ADDRESS.MATCH.NEEDS_REVIEW"


def test_the_name_alone_is_not_enough() -> None:
    """One matching pair of words with nothing corroborating it is a match a
    common word could make on its own."""
    res = _verdict("BOTTLED BY CHATEAU DIANA", CHATEAU_DIANA_BLOCK)
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE


def test_an_empty_reading_goes_to_a_reviewer() -> None:
    assert _verdict("", CHATEAU_DIANA_BLOCK).outcome is Outcome.INSUFFICIENT_EVIDENCE


def test_no_application_block_means_the_check_does_not_apply() -> None:
    res = _verdict("CELLARED AND BOTTLED BY CHATEAU DIANA, Healdsburg, California", None)
    assert res.outcome is Outcome.NOT_APPLICABLE
    assert res.reason_code is None


def test_the_check_never_rejects() -> None:
    for label_statement in ("", "BOTTLED BY SOMEONE ELSE, Nowhere, Alaska", "nonsense"):
        res = _verdict(label_statement, CHATEAU_DIANA_BLOCK)
        assert res.outcome is not Outcome.FAIL, label_statement


def test_validator_registered() -> None:
    assert "name_address_match" in VALIDATOR_REGISTRY
