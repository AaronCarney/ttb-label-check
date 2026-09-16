"""presence_check fails when observed_value is None or empty string. The
'conditional_presence' alias enforces presence only when the precondition in
rule.parameters['precondition'] is satisfied (a Python expression evaluated
against expected.parameters and observed_value)."""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.presence_check import presence_check, conditional_presence  # noqa: F401
from app.schemas.rejection import Outcome
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _rule(validator: str, **kw):
    return make_rule(
        rule_id=f"x.{validator}",
        cfr_citation="27 CFR §0.0",
        validator=validator,
        reason_code="BRAND.PRESENCE.MISSING",
        **kw,
    )


def test_presence_check_pass_with_value() -> None:
    obs = make_obs(field_id="brand", value="Foo")
    exp = make_expected(field_id="brand")
    res = presence_check(obs, exp, _rule("presence_check"), make_context())
    assert res.outcome is Outcome.PASS


def test_presence_check_fail_when_none() -> None:
    obs = make_obs(field_id="brand", value=None)
    exp = make_expected(field_id="brand")
    res = presence_check(obs, exp, _rule("presence_check"), make_context())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "BRAND.PRESENCE.MISSING"


def test_presence_check_fail_when_empty_string() -> None:
    obs = make_obs(field_id="brand", value="   ")
    exp = make_expected(field_id="brand")
    res = presence_check(obs, exp, _rule("presence_check"), make_context())
    assert res.outcome is Outcome.FAIL


def test_conditional_presence_not_applicable_when_predicate_false() -> None:
    obs = make_obs(field_id="alc_text", value=None)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": False})
    rule = _rule(
        "conditional_presence",
        parameters={"required_when": "abv_required"},
    )
    res = conditional_presence(obs, exp, rule, make_context())
    assert res.outcome is Outcome.NOT_APPLICABLE


def test_conditional_presence_fail_when_predicate_true_and_missing() -> None:
    obs = make_obs(field_id="alc_text", value=None)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": True})
    rule = _rule(
        "conditional_presence",
        parameters={"required_when": "abv_required"},
    )
    res = conditional_presence(obs, exp, rule, make_context())
    assert res.outcome is Outcome.FAIL


def test_validators_registered() -> None:
    assert "presence_check" in VALIDATOR_REGISTRY
    assert "conditional_presence" in VALIDATOR_REGISTRY
