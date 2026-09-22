"""Malt-pack rules: a positive and a negative case for each, including the
§7.65(c) 0.5% alcohol hard floor."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules.loader import YamlRuleLoader
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome, Severity
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
    rule = _r(ruleset, "malt.brand.matches_application")
    obs = make_obs(field_id="brand", value="Acme Lager", beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="brand", value="Acme Lager")
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_brand_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.brand.matches_application")
    obs = make_obs(field_id="brand", value="Acme", beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="brand", value="Bizmark")
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    # A different name the search finds nowhere goes to a reviewer, never to a
    # mismatch (docs/decisions.md#0052).
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "BRAND.IDENTIFY.UNCERTAIN"


def test_class_type_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.class_type.present")
    obs = make_obs(field_id="class_type", value="Lager", beverage_class=BeverageClass.MALT)
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_class_type_accepts_a_style_no_list_carries(ruleset) -> None:
    # §7.63(a)(2) asks that a designation appear on the label, not that it be
    # one of a short set. Checking presence against an allow-list rejected any
    # style the list did not happen to carry. docs/decisions.md#0012.
    rule = _r(ruleset, "malt.class_type.present")
    obs = make_obs(field_id="class_type", value="MÄRZEN", beverage_class=BeverageClass.MALT)
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_class_type_neg(ruleset) -> None:
    # Absence is the only failure this rule reports.
    rule = _r(ruleset, "malt.class_type.present")
    obs = make_obs(field_id="class_type", value=None, beverage_class=BeverageClass.MALT)
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


@pytest.mark.parametrize("designation", ["BOCK", "CERVEZA", "IPA"])
def test_class_type_style_matches_a_beer_application(ruleset, designation) -> None:
    # A registry application routinely declares the bare class BEER where the
    # label designates the style it is sold as. rules/tables/malt_designations.yaml
    # places each style within that class, one way only.
    rule = _r(ruleset, "malt.class_type.matches_application")
    obs = make_obs(field_id="class_type", value=designation, beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="class_type", value="BEER")
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_alcohol_conditional_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.conditional_required")
    obs = make_obs(
        field_id="alc_text", value="Alcohol 5.5% by volume", beverage_class=BeverageClass.MALT
    )
    exp = make_expected(field_id="alc_text", parameters={"abv_required": True})
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_alcohol_conditional_not_applicable(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.conditional_required")
    obs = make_obs(field_id="alc_text", value=None, beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": False})
    assert (
        VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome
        is Outcome.NOT_APPLICABLE
    )


def test_format_is_on_and_warns(ruleset) -> None:
    # On, and it cannot reject: a statement its pattern does not list goes to a
    # reviewer (docs/decisions.md#0011). tests/rules/_validators/test_format_check.py
    # holds the pattern to the regulation's forms and examples.
    rule = _r(ruleset, "malt.alcohol.format")
    assert rule.disabled is False
    assert rule.severity is Severity.WARN
    assert rule.validator in VALIDATOR_REGISTRY


def test_name_address_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.name_address.present")
    obs = make_obs(
        field_id="bottler", value="Acme Brewing, Milwaukee, WI", beverage_class=BeverageClass.MALT
    )
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="bottler"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_name_address_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.name_address.present")
    obs = make_obs(field_id="bottler", value=None, beverage_class=BeverageClass.MALT)
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
    rule = _r(ruleset, "malt.net_contents.present")
    obs = make_obs(field_id="net_contents", value="12 fl oz", beverage_class=BeverageClass.MALT)
    assert (
        VALIDATOR_REGISTRY[rule.validator](
            obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset)
        ).outcome
        is Outcome.PASS
    )


def test_net_contents_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.net_contents.present")
    obs = make_obs(field_id="net_contents", value=None, beverage_class=BeverageClass.MALT)
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
