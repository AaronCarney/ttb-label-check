"""equality_match supports two registered names: 'equality_match' (single-value
exact / case-insensitive / normalized) and 'enumerated_match' (lookup against
an allow-list provided in `rule.parameters['allowed_values']`).
"""
from __future__ import annotations

import pytest

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.equality_match import equality_match, enumerated_match  # noqa: F401  (forces import / registration)
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _rule(validator: str, params: dict | None = None, policy: MatchPolicy = MatchPolicy.EXACT):
    return make_rule(
        rule_id=f"x.{validator}",
        cfr_citation="27 CFR §0.0",
        validator=validator,
        reason_code="BRAND.PRESENCE.MISSING",
        match_policy=policy,
        parameters=params or {},
    )


def test_equality_match_pass_normalized() -> None:
    obs = make_obs(field_id="brand", value="STONE'S THROW")
    exp = make_expected(field_id="brand", value="Stone's Throw")
    rule = _rule("equality_match", policy=MatchPolicy.NORMALIZED)
    result = equality_match(obs, exp, rule, make_context())
    assert result.outcome is Outcome.PASS


def test_equality_match_fail_when_different() -> None:
    obs = make_obs(field_id="brand", value="ACME")
    exp = make_expected(field_id="brand", value="Bizmark")
    rule = _rule("equality_match")
    result = equality_match(obs, exp, rule, make_context())
    assert result.outcome is Outcome.FAIL
    assert result.reason_code == "BRAND.PRESENCE.MISSING"


def test_enumerated_match_pass_when_in_allow_list() -> None:
    obs = make_obs(field_id="class_type", value="Bourbon Whisky")
    exp = make_expected(field_id="class_type", value=None)
    rule = _rule("enumerated_match", params={"allowed_values": ["Bourbon Whisky", "Rye Whisky"]}, policy=MatchPolicy.LOOKUP)
    result = enumerated_match(obs, exp, rule, make_context())
    assert result.outcome is Outcome.PASS


def test_enumerated_match_fail_when_not_in_allow_list() -> None:
    obs = make_obs(field_id="class_type", value="Mystery Hooch")
    exp = make_expected(field_id="class_type", value=None)
    rule = _rule("enumerated_match", params={"allowed_values": ["Bourbon Whisky", "Rye Whisky"]}, policy=MatchPolicy.LOOKUP)
    result = enumerated_match(obs, exp, rule, make_context())
    assert result.outcome is Outcome.FAIL


def test_equality_match_registered() -> None:
    assert "equality_match" in VALIDATOR_REGISTRY
    assert "enumerated_match" in VALIDATOR_REGISTRY
