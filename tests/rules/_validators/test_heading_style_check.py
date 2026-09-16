"""heading_style_check fails when the GOVERNMENT WARNING heading is not all-caps
and bold. The observation carries `heading_text` and `heading_styles` keys
(populated by the reader in production; supplied directly here).
"""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.heading_style_check import heading_style_check  # noqa: F401
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _rule():
    return make_rule(
        rule_id="common.warning.heading_caps_bold",
        cfr_citation="27 CFR §16.22(a)(2)",
        validator="heading_style_check",
        reason_code="WARNING.STYLE.HEADING_NOT_BOLD_CAPS",
        match_policy=MatchPolicy.LAYOUT,
        parameters={"target_phrase": "GOVERNMENT WARNING", "required_case": "upper", "required_weight": "bold"},
    )


def test_caps_and_bold_passes() -> None:
    obs = make_obs(field_id="warning_block", value={"heading_text": "GOVERNMENT WARNING", "heading_styles": {"weight": "bold", "case": "upper"}})
    assert heading_style_check(obs, make_expected(field_id="warning_block"), _rule(), make_context()).outcome is Outcome.PASS


def test_title_case_fails() -> None:
    obs = make_obs(field_id="warning_block", value={"heading_text": "Government Warning", "heading_styles": {"weight": "bold", "case": "title"}})
    res = heading_style_check(obs, make_expected(field_id="warning_block"), _rule(), make_context())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_not_bold_fails() -> None:
    obs = make_obs(field_id="warning_block", value={"heading_text": "GOVERNMENT WARNING", "heading_styles": {"weight": "regular", "case": "upper"}})
    assert heading_style_check(obs, make_expected(field_id="warning_block"), _rule(), make_context()).outcome is Outcome.FAIL


def test_validator_registered() -> None:
    assert "heading_style_check" in VALIDATOR_REGISTRY
