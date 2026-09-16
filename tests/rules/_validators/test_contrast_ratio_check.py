"""contrast_ratio_check compares the contrast ratio the observation reports
against the rule.parameters['min_contrast_ratio'] threshold: at or above it the
rule passes, below it the rule fails. The validator does not compute the ratio
from the image itself; it reads what the observation carries.
"""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.contrast_ratio_check import contrast_ratio_check  # noqa: F401
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _rule():
    return make_rule(
        rule_id="common.warning.contrasting_bg",
        cfr_citation="27 CFR §16.22(a)(1)",
        validator="contrast_ratio_check",
        reason_code="WARNING.LEGIBILITY.NO_CONTRAST",
        match_policy=MatchPolicy.LAYOUT,
        parameters={"min_contrast_ratio": 4.5},
    )


def test_above_threshold_passes() -> None:
    obs = make_obs(field_id="warning_block", value={"contrast_ratio": 7.2})
    assert contrast_ratio_check(obs, make_expected(field_id="warning_block"), _rule(), make_context()).outcome is Outcome.PASS


def test_below_threshold_fails() -> None:
    obs = make_obs(field_id="warning_block", value={"contrast_ratio": 2.1})
    assert contrast_ratio_check(obs, make_expected(field_id="warning_block"), _rule(), make_context()).outcome is Outcome.FAIL


def test_validator_registered() -> None:
    assert "contrast_ratio_check" in VALIDATOR_REGISTRY
