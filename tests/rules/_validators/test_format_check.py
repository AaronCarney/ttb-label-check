"""format_check (registered as 'regex_match') tests observed string against
the regex in rule.parameters['pattern']. Used by the alcohol-content format
rules in the wine, spirits and malt packs.
"""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.format_check import regex_match  # noqa: F401
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


PAT = r"^\s*(?:alcohol|alc\.?)\s*[0-9]{1,2}(?:\.[0-9]+)?\s*%?\s*(?:by\s+volume|/\s*vol\.?|vol\.?)\s*$"


def _rule():
    return make_rule(
        rule_id="x.format",
        cfr_citation="27 CFR §0.0",
        validator="regex_match",
        reason_code="ALCOHOL_CONTENT.FORMAT.INVALID",
        match_policy=MatchPolicy.REGEX,
        parameters={"pattern": PAT, "ignore_case": True},
    )


def test_format_check_pass_canonical_form() -> None:
    obs = make_obs(field_id="alc_text", value="ALCOHOL 12.5% BY VOLUME")
    res = regex_match(obs, make_expected(field_id="alc_text"), _rule(), make_context())
    assert res.outcome is Outcome.PASS


def test_format_check_fail_missing_unit() -> None:
    obs = make_obs(field_id="alc_text", value="12.5")
    res = regex_match(obs, make_expected(field_id="alc_text"), _rule(), make_context())
    assert res.outcome is Outcome.FAIL


def test_format_check_registered() -> None:
    assert "regex_match" in VALIDATOR_REGISTRY
