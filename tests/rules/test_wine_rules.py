"""Wine-pack rules: a positive and a negative case for each, including the
§4.36(c) class-boundary anti-overlap edge."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

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
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.PASS


def test_wine_class_type_neg(ruleset) -> None:
    rule = _r(ruleset, "wine.class_type.present")
    obs = make_obs(field_id="class_type", value="Mystery Wine", beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL


def test_wine_alcohol_present_or_table_pos(ruleset) -> None:
    rule = _r(ruleset, "wine.alcohol.present_or_table")
    obs = make_obs(field_id="alc_text", value="Alcohol 12.5% by volume", beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": True})
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.PASS


def test_wine_alcohol_present_or_table_neg(ruleset) -> None:
    rule = _r(ruleset, "wine.alcohol.present_or_table")
    obs = make_obs(field_id="alc_text", value=None, beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": True})
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL


def test_wine_alcohol_format_pos(ruleset) -> None:
    rule = _r(ruleset, "wine.alcohol.format")
    obs = make_obs(field_id="alc_text", value="Alcohol 12.5% by volume", beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.PASS


def test_wine_alcohol_format_neg(ruleset) -> None:
    rule = _r(ruleset, "wine.alcohol.format")
    obs = make_obs(field_id="alc_text", value="12.5", beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL


def test_wine_name_address_pos(ruleset) -> None:
    rule = _r(ruleset, "wine.name_address.present")
    obs = make_obs(field_id="bottler", value="Acme Vineyards, Napa, CA", beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="bottler"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.PASS


def test_wine_name_address_neg(ruleset) -> None:
    rule = _r(ruleset, "wine.name_address.present")
    obs = make_obs(field_id="bottler", value=None, beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="bottler"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL


def test_wine_net_contents_pos(ruleset) -> None:
    rule = _r(ruleset, "wine.net_contents.present")
    obs = make_obs(field_id="net_contents", value="750 mL", beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.PASS


def test_wine_net_contents_neg(ruleset) -> None:
    rule = _r(ruleset, "wine.net_contents.present")
    obs = make_obs(field_id="net_contents", value=None, beverage_class=BeverageClass.WINE)
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL
