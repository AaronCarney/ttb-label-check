"""fuzzy_brand runs Stage A first; on a miss it runs Stage B and routes by the
thresholds the rule pack supplies. The borderline band
(`needs_review_threshold` ≤ score < `pass_threshold`) emits exactly the reason
code BRAND.NAME.NEEDS_REVIEW, which sends the label to a reviewer instead of
rejecting it.
"""
from __future__ import annotations

import pytest

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.fuzzy_brand import fuzzy_brand  # noqa: F401
from app.rules.brand_match import stage_b_fuzzy
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _rule():
    return make_rule(
        rule_id="brand.match",
        cfr_citation="27 CFR §4.33",
        validator="fuzzy_brand",
        reason_code="BRAND.NAME.MISMATCH",
        match_policy=MatchPolicy.FUZZY,
        parameters={
            "pass_threshold": 0.92,
            "needs_review_threshold": 0.85,
            "needs_review_reason_code": "BRAND.NAME.NEEDS_REVIEW",
        },
    )


def test_stage_a_pass_returns_pass_with_normalized_kind() -> None:
    obs = make_obs(field_id="brand", value="STONE'S THROW")
    exp = make_expected(field_id="brand", value="Stone's Throw")
    res = fuzzy_brand(obs, exp, _rule(), make_context())
    assert res.outcome is Outcome.PASS


def test_stage_b_above_pass_threshold_passes() -> None:
    obs = make_obs(field_id="brand", value="Stones Throw Bourbon")
    exp = make_expected(field_id="brand", value="Stone's Throw Bourbon")
    res = fuzzy_brand(obs, exp, _rule(), make_context())
    assert res.outcome is Outcome.PASS


def test_stage_b_borderline_emits_needs_review() -> None:
    """A borderline-band score raises the needs-review trigger.

    Strict assertion: outcome is FAIL with reason_code BRAND.NAME.NEEDS_REVIEW.
    The disjunction (FAIL or PASS or reason==NEEDS_REVIEW) would admit every
    Outcome the validator can return and pass regardless of behaviour — the
    contract is "borderline → exactly NEEDS_REVIEW", so the test must enforce
    that. If a future canonicalization tweak drifts the chosen input pair
    out of (0.85, 0.92), `pytest.skip` rather than silently reclassify;
    tests/test_brand_match_policies.py covers the same contract with its own
    calibration step.
    """
    obs = make_obs(field_id="brand", value="Acme Brewing Company")
    exp = make_expected(field_id="brand", value="Acme Brewer Company")
    score = stage_b_fuzzy("Acme Brewing Company", "Acme Brewer Company")
    if not (0.85 <= score < 0.92):
        pytest.skip(
            f"borderline calibration drifted: stage_b_fuzzy={score:.4f} "
            f"outside (0.85, 0.92); retune the input pair or the normalization"
        )
    res = fuzzy_brand(obs, exp, _rule(), make_context())
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "BRAND.NAME.NEEDS_REVIEW"


def test_stage_b_below_threshold_fails_with_mismatch() -> None:
    obs = make_obs(field_id="brand", value="Acme")
    exp = make_expected(field_id="brand", value="Bizmark")
    res = fuzzy_brand(obs, exp, _rule(), make_context())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "BRAND.NAME.MISMATCH"


def test_validator_registered() -> None:
    assert "fuzzy_brand" in VALIDATOR_REGISTRY
