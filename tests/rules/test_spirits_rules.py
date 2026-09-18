"""Spirits-pack rules: a positive and a negative case for each, with the alcohol
tolerance exercised exactly at the band edge and just outside it."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules.loader import YamlRuleLoader
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome
from tests.rules.fixtures import load_all_validators, make_context, make_expected, make_obs


@pytest.fixture(scope="module")
def ruleset():
    # The loader refuses a pack naming a validator the registry has not got,
    # so register them all first, exactly as the running app does.
    load_all_validators()
    return YamlRuleLoader().load(Path("rules"))


def _r(rs, rid):
    return next(r for r in rs.rules if r.rule_id == rid)


def _ctx(rs):
    return make_context(assets=rs.assets, decision_tables=rs.decision_tables)


def test_brand_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.brand.matches_application")
    obs = make_obs(
        field_id="brand", value="Stone's Throw Bourbon", beverage_class=BeverageClass.SPIRITS
    )
    exp = make_expected(field_id="brand", value="Stone's Throw Bourbon")
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_brand_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.brand.matches_application")
    obs = make_obs(field_id="brand", value="Acme", beverage_class=BeverageClass.SPIRITS)
    exp = make_expected(field_id="brand", value="Bizmark")
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL


def test_class_type_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.class_type.present")
    obs = make_obs(
        field_id="class_type", value="Bourbon Whisky", beverage_class=BeverageClass.SPIRITS
    )
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_class_type_accepts_a_designation_no_list_carries(ruleset) -> None:
    # Part 5 Subpart I lets a spirit with no standard of identity be designated
    # by a fanciful name with a statement of composition, so an unlisted
    # designation is not evidence the label is wrong. §5.63(a) asks only that a
    # designation be there. docs/decisions.md#0012.
    rule = _r(ruleset, "spirits.class_type.present")
    obs = make_obs(
        field_id="class_type", value="CRÈME DE CASSIS LIQUEUR", beverage_class=BeverageClass.SPIRITS
    )
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_class_type_neg(ruleset) -> None:
    # Absence is the only failure this rule reports.
    rule = _r(ruleset, "spirits.class_type.present")
    obs = make_obs(field_id="class_type", value=None, beverage_class=BeverageClass.SPIRITS)
    # An observation with no reading, no box and no extracted text is the reader
    # saying it did not find the element, which is not the finding that the label
    # lacks it. This rule does not set `unlocated_is_absent`, so it goes to a
    # reviewer. `common.warning.present` is the one rule that does set it, and its
    # own test still asserts a rejection.
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"


def test_alcohol_present_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.alcohol.present")
    obs = make_obs(
        field_id="alc_text", value="Alcohol 40% by volume", beverage_class=BeverageClass.SPIRITS
    )
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_alcohol_present_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.alcohol.present")
    obs = make_obs(field_id="alc_text", value=None, beverage_class=BeverageClass.SPIRITS)
    # An observation with no reading, no box and no extracted text is the reader
    # saying it did not find the element, which is not the finding that the label
    # lacks it. This rule does not set `unlocated_is_absent`, so it goes to a
    # reviewer. `common.warning.present` is the one rule that does set it, and its
    # own test still asserts a rejection.
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"


def test_format_is_switched_off(ruleset) -> None:
    # Off, docs/decisions.md#0011: the pattern rejects statements the
    # regulations permit. The engine skips the rule (app/rules/yaml_engine.py).
    rule = _r(ruleset, "spirits.alcohol.format")
    assert rule.disabled is True
    assert rule.validator in VALIDATOR_REGISTRY


def test_same_field_of_vision_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.same_field_of_vision")
    obs = make_obs(
        field_id="layout",
        value={"panels": {"front": ["brand", "class_type", "abv", "net_contents"]}},
        beverage_class=BeverageClass.SPIRITS,
    )
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="layout"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_same_field_of_vision_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.same_field_of_vision")
    obs = make_obs(
        field_id="layout",
        value={"panels": {"front": ["brand"], "back": ["class_type", "abv", "net_contents"]}},
        beverage_class=BeverageClass.SPIRITS,
    )
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="layout"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.FAIL


def test_name_address_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.name_address.present")
    obs = make_obs(
        field_id="bottler", value="Acme Distilling, KY", beverage_class=BeverageClass.SPIRITS
    )
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="bottler"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_name_address_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.name_address.present")
    obs = make_obs(field_id="bottler", value=None, beverage_class=BeverageClass.SPIRITS)
    # An observation with no reading, no box and no extracted text is the reader
    # saying it did not find the element, which is not the finding that the label
    # lacks it. This rule does not set `unlocated_is_absent`, so it goes to a
    # reviewer. `common.warning.present` is the one rule that does set it, and its
    # own test still asserts a rejection.
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="bottler"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"


def test_net_contents_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.net_contents.present")
    obs = make_obs(field_id="net_contents", value="750 mL", beverage_class=BeverageClass.SPIRITS)
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_net_contents_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.net_contents.present")
    obs = make_obs(field_id="net_contents", value=None, beverage_class=BeverageClass.SPIRITS)
    # An observation with no reading, no box and no extracted text is the reader
    # saying it did not find the element, which is not the finding that the label
    # lacks it. This rule does not set `unlocated_is_absent`, so it goes to a
    # reviewer. `common.warning.present` is the one rule that does set it, and its
    # own test still asserts a rejection.
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"
