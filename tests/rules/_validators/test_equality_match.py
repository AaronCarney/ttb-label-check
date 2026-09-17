"""equality_match.py registers one name: 'enumerated_match', a lookup against
an allow-list provided in `rule.parameters['allowed_values']`.

The module's other name, 'equality_match', went when the only rule using it was
deleted (docs/decisions.md#0013); its cases went with it.
"""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.equality_match import (
    enumerated_match,
)
from app.schemas.rejection import Outcome
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


def test_enumerated_match_registered() -> None:
    assert "enumerated_match" in VALIDATOR_REGISTRY
    assert "equality_match" not in VALIDATOR_REGISTRY
