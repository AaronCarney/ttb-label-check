"""Malt-pack rules: a positive and a negative case for each, including the
§7.65(c) 0.5% alcohol hard floor."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

import app.rules._validators.abv_band  # noqa: F401
import app.rules._validators.contrast_ratio_check  # noqa: F401
import app.rules._validators.cpi_lookup  # noqa: F401
import app.rules._validators.equality_match  # noqa: F401
import app.rules._validators.format_check  # noqa: F401
import app.rules._validators.fuzzy_brand  # noqa: F401
import app.rules._validators.heading_style_check  # noqa: F401
import app.rules._validators.layout_check  # noqa: F401
import app.rules._validators.presence_check  # noqa: F401
import app.rules._validators.type_size_check  # noqa: F401
import app.rules._validators.verbatim_hash  # noqa: F401
from app.rules._validators import VALIDATOR_REGISTRY
from app.rules.loader import YamlRuleLoader
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome
from tests.rules.fixtures import make_context, make_expected, make_obs


@pytest.fixture(scope="module")
def ruleset():
    return YamlRuleLoader().load(Path("rules"))


def _r(rs, rid): return next(r for r in rs.rules if r.rule_id == rid)
def _ctx(rs): return make_context(assets=rs.assets, decision_tables=rs.decision_tables)


def test_brand_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.brand.matches_application")
    obs = make_obs(field_id="brand", value="Acme Lager", beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="brand", value="Acme Lager")
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_brand_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.brand.matches_application")
    obs = make_obs(field_id="brand", value="Acme", beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="brand", value="Bizmark")
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_class_type_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.class_type.present")
    obs = make_obs(field_id="class_type", value="Lager", beverage_class=BeverageClass.MALT)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_class_type_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.class_type.present")
    obs = make_obs(field_id="class_type", value="Mystery", beverage_class=BeverageClass.MALT)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_alcohol_conditional_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.conditional_required")
    obs = make_obs(field_id="alc_text", value="Alcohol 5.5% by volume", beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": True})
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_alcohol_conditional_not_applicable(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.conditional_required")
    obs = make_obs(field_id="alc_text", value=None, beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": False})
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.NOT_APPLICABLE


def test_format_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.format")
    obs = make_obs(field_id="alc_text", value="Alcohol 5.5% by volume", beverage_class=BeverageClass.MALT)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_format_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.format")
    obs = make_obs(field_id="alc_text", value="strong", beverage_class=BeverageClass.MALT)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_tolerance_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.tolerance_band")
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("5.0"), abv_actual_pct=Decimal("5.3"))
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_tolerance_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.tolerance_band")
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("5.0"), abv_actual_pct=Decimal("5.5"))
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_hard_floor_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.floor_05")
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("0.4"), abv_actual_pct=Decimal("0.4"))
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "ALCOHOL_CONTENT.TOLERANCE.BELOW_HARD_FLOOR"


def test_hard_floor_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.alcohol.floor_05")
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("0.5"), abv_actual_pct=Decimal("0.5"))
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_name_address_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.name_address.present")
    obs = make_obs(field_id="bottler", value="Acme Brewing, Milwaukee, WI", beverage_class=BeverageClass.MALT)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="bottler"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_name_address_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.name_address.present")
    obs = make_obs(field_id="bottler", value=None, beverage_class=BeverageClass.MALT)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="bottler"), rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_net_contents_pos(ruleset) -> None:
    rule = _r(ruleset, "malt.net_contents.present")
    obs = make_obs(field_id="net_contents", value="12 fl oz", beverage_class=BeverageClass.MALT)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_net_contents_neg(ruleset) -> None:
    rule = _r(ruleset, "malt.net_contents.present")
    obs = make_obs(field_id="net_contents", value=None, beverage_class=BeverageClass.MALT)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset)).outcome is Outcome.FAIL
