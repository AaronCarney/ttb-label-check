"""Wine-pack rules: a positive and a negative case for each, including the
§4.36(c) class-boundary anti-overlap edge."""

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


def test_wine_brand_matches_application_pos(ruleset) -> None:
    rule = _r(ruleset, "wine.brand.matches_application")
    obs = make_obs(field_id="brand", value="Acme Vineyards", beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="brand", value="Acme Vineyards")
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.PASS


def test_wine_brand_matches_application_neg(ruleset) -> None:
    rule = _r(ruleset, "wine.brand.matches_application")
    obs = make_obs(field_id="brand", value="Acme", beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="brand", value="Bizmark")
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL


def test_wine_class_type_pos(ruleset) -> None:
    rule = _r(ruleset, "wine.class_type.present")
    obs = make_obs(field_id="class_type", value="Table Wine", beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.PASS


def test_wine_class_type_accepts_a_varietal_designation(ruleset) -> None:
    # §4.34(b) lets a varietal name be the designation in lieu of a class, and
    # TTB approved this label. The rule asks whether a designation is on the
    # label, so one that no allow-list carries still passes. docs/decisions.md#0012.
    rule = _r(ruleset, "wine.class_type.present")
    obs = make_obs(field_id="class_type", value="SANGIOVESE", beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.PASS


def test_wine_class_type_neg(ruleset) -> None:
    # Absence is the only failure this rule reports.
    rule = _r(ruleset, "wine.class_type.present")
    obs = make_obs(field_id="class_type", value=None, beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)
    )
    # An observation with no reading, no box and no extracted text is the reader
    # saying it did not find the element, which is not the finding that the label
    # lacks it. This rule does not set `unlocated_is_absent`, so it goes to a
    # reviewer. `common.warning.present` is the one rule that does set it, and its
    # own test still asserts a rejection.
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"


def test_wine_class_type_champagne_matches_a_sparkling_wine_application(ruleset) -> None:
    # §4.34(a): the type designation "champagne" may appear in lieu of the
    # class designation "sparkling wine", so the two name the same wine.
    # rules/tables/wine_designations.yaml records it.
    rule = _r(ruleset, "wine.class_type.matches_application")
    obs = make_obs(field_id="class_type", value="CHAMPAGNE", beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="class_type", value="SPARKLING WINE")
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.PASS


def test_wine_class_type_sparkling_wine_matches_a_champagne_application(ruleset) -> None:
    # The same permitted substitution the other way round, which is why the
    # table carries both directions.
    rule = _r(ruleset, "wine.class_type.matches_application")
    obs = make_obs(field_id="class_type", value="SPARKLING WINE", beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="class_type", value="CHAMPAGNE")
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.PASS


def test_wine_alcohol_present_or_table_pos(ruleset) -> None:
    rule = _r(ruleset, "wine.alcohol.present_or_table")
    obs = make_obs(
        field_id="alc_text", value="Alcohol 12.5% by volume", beverage_class=BeverageClass.WINE
    )
    exp = make_expected(field_id="alc_text", parameters={"abv_required": True})
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.PASS


def test_wine_alcohol_present_or_table_neg(ruleset) -> None:
    rule = _r(ruleset, "wine.alcohol.present_or_table")
    obs = make_obs(field_id="alc_text", value=None, beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": True})
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    # An observation with no reading, no box and no extracted text is the reader
    # saying it did not find the element, which is not the finding that the label
    # lacks it. This rule does not set `unlocated_is_absent`, so it goes to a
    # reviewer. `common.warning.present` is the one rule that does set it, and its
    # own test still asserts a rejection.
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"


def test_wine_alcohol_format_is_on_and_warns(ruleset) -> None:
    # On, and it cannot reject: a statement its pattern does not list goes to a
    # reviewer (docs/decisions.md#0011). tests/rules/_validators/test_format_check.py
    # holds the pattern to the regulation's forms and examples.
    rule = _r(ruleset, "wine.alcohol.format")
    assert rule.disabled is False
    assert rule.severity is Severity.WARN
    assert rule.validator in VALIDATOR_REGISTRY


def test_wine_name_address_pos(ruleset) -> None:
    rule = _r(ruleset, "wine.name_address.present")
    obs = make_obs(
        field_id="bottler", value="Acme Vineyards, Napa, CA", beverage_class=BeverageClass.WINE
    )
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="bottler"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.PASS


def test_wine_name_address_neg(ruleset) -> None:
    rule = _r(ruleset, "wine.name_address.present")
    obs = make_obs(field_id="bottler", value=None, beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="bottler"), rule, _ctx(ruleset)
    )
    # An observation with no reading, no box and no extracted text is the reader
    # saying it did not find the element, which is not the finding that the label
    # lacks it. This rule does not set `unlocated_is_absent`, so it goes to a
    # reviewer. `common.warning.present` is the one rule that does set it, and its
    # own test still asserts a rejection.
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"


def test_wine_net_contents_pos(ruleset) -> None:
    rule = _r(ruleset, "wine.net_contents.present")
    obs = make_obs(field_id="net_contents", value="750 mL", beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.PASS


def test_wine_net_contents_neg(ruleset) -> None:
    rule = _r(ruleset, "wine.net_contents.present")
    obs = make_obs(field_id="net_contents", value=None, beverage_class=BeverageClass.WINE)
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
