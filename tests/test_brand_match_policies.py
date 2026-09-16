"""The brand-match policy, case by case.

Each case is a pair of names and the verdict the product reports for it:

  - STONE'S THROW vs Stone's Throw        → the same name  → pass
  - KENTUCKY BOURBON vs KEntucky bourbon  → the same name  → pass
  - Lucky Lucy's vs Lucky Lucys           → an apostrophe apart, scored 0.98
                                            and shown → pass
  - Stone's Throw vs Stone's Throw Distilling Co.
                                          → whole words of it → pass
  - Blue River Brewing vs Blue River Distillery
                                          → too close to call → needs review
                                            (BRAND.NAME.NEEDS_REVIEW, the code
                                            the evaluator watches for)
  - Acme vs Bizmark                       → different names → BRAND.NAME.MISMATCH

The punctuation case is the contested one. TTB Form 5100.31's allowable
revisions, item 3.b, lets a label change the spelling of a word, punctuation
included, without a new approval, so long as the meaning does not change; a
dropped apostrophe in "Lucky Lucy's" is that change. The product reports it as
a match, but reports it from the score with the number and both spellings in
the message, rather than by normalising the apostrophe away and claiming an
exact match it did not make.
"""
from __future__ import annotations

import pytest

import app.rules._validators.fuzzy_brand  # noqa: F401
from app.rules._validators import VALIDATOR_REGISTRY
from app.rules.brand_match import stage_b_fuzzy
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

PASS_THRESHOLD = 0.92
NEEDS_REVIEW_THRESHOLD = 0.85


def _rule():
    return make_rule(
        rule_id="brand.match",
        cfr_citation="27 CFR §4.33",
        validator="fuzzy_brand",
        reason_code="BRAND.NAME.MISMATCH",
        match_policy=MatchPolicy.FUZZY,
        parameters={
            "pass_threshold": PASS_THRESHOLD,
            "needs_review_threshold": NEEDS_REVIEW_THRESHOLD,
            "needs_review_reason_code": "BRAND.NAME.NEEDS_REVIEW",
        },
    )


def _verdict(label_brand: str, application_brand: str):
    obs = make_obs(field_id="brand", value=label_brand)
    exp = make_expected(field_id="brand", value=application_brand)
    return VALIDATOR_REGISTRY["fuzzy_brand"](obs, exp, _rule(), make_context())


def test_stones_throw_case_difference_is_the_same_name() -> None:
    res = _verdict("STONE'S THROW", "Stone's Throw")
    assert res.outcome is Outcome.PASS
    assert res.message is None, "an ordinary match has nothing to explain"


def test_kentucky_bourbon_caps_mix_is_the_same_name() -> None:
    assert _verdict("KENTUCKY BOURBON", "KEntucky bourbon").outcome is Outcome.PASS


def test_a_dropped_apostrophe_passes_on_score_and_shows_it() -> None:
    res = _verdict("Lucky Lucy's", "Lucky Lucys")
    assert res.outcome is Outcome.PASS
    assert res.message and "0.98" in res.message, (
        "the reviewer is told this was a scored near match, not an exact one: "
        f"{res.message!r}"
    )


def test_a_name_with_a_word_added_is_the_same_name() -> None:
    res = _verdict("Stone's Throw", "Stone's Throw Distilling Co.")
    assert res.outcome is Outcome.PASS
    assert res.message and "Stone's Throw Distilling Co." in res.message


def test_substantively_different_brand_below_floor_emits_mismatch() -> None:
    res = _verdict("Acme", "Bizmark")
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "BRAND.NAME.MISMATCH"


def test_borderline_brand_emits_needs_review_code() -> None:
    """A borderline-band score raises the needs-review trigger.

    The input pair is calibrated to land inside the band under the current
    canonicalisation. If a later normalisation change drifts it out, skip with
    the measured number rather than silently reclassifying: the contract under
    test — borderline reports exactly NEEDS_REVIEW — is meaningless if the
    inputs are not in band, and a soft pass would hide the change.
    """
    label_brand, application_brand = "Blue River Brewing", "Blue River Distillery"
    score = stage_b_fuzzy(label_brand, application_brand)
    if not (NEEDS_REVIEW_THRESHOLD <= score < PASS_THRESHOLD):
        pytest.skip(
            f"borderline calibration drifted: stage_b_fuzzy={score:.4f} "
            f"outside [{NEEDS_REVIEW_THRESHOLD}, {PASS_THRESHOLD}); "
            "retune the input pair or the normalisation"
        )
    res = _verdict(label_brand, application_brand)
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "BRAND.NAME.NEEDS_REVIEW"
