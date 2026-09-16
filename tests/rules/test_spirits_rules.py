"""Spirits-pack rules: a positive and a negative case for each, with the alcohol
tolerance exercised exactly at the band edge and just outside it."""
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
    rule = _r(ruleset, "spirits.brand.matches_application")
    obs = make_obs(field_id="brand", value="Stone's Throw Bourbon", beverage_class=BeverageClass.SPIRITS)
    exp = make_expected(field_id="brand", value="Stone's Throw Bourbon")
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_brand_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.brand.matches_application")
    obs = make_obs(field_id="brand", value="Acme", beverage_class=BeverageClass.SPIRITS)
    exp = make_expected(field_id="brand", value="Bizmark")
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_class_type_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.class_type.present")
    obs = make_obs(field_id="class_type", value="Bourbon Whisky", beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_class_type_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.class_type.present")
    obs = make_obs(field_id="class_type", value="Mystery Hooch", beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_alcohol_present_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.alcohol.present")
    obs = make_obs(field_id="alc_text", value="Alcohol 40% by volume", beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_alcohol_present_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.alcohol.present")
    obs = make_obs(field_id="alc_text", value=None, beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_format_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.alcohol.format")
    obs = make_obs(field_id="alc_text", value="Alcohol 40% by volume", beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_format_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.alcohol.format")
    obs = make_obs(field_id="alc_text", value="40 proof", beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="alc_text"), rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_tolerance_at_boundary_pass(ruleset) -> None:
    rule = _r(ruleset, "spirits.alcohol.tolerance_band")
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.SPIRITS)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("40.0"), abv_actual_pct=Decimal("40.3"))
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_tolerance_just_outside_fail(ruleset) -> None:
    rule = _r(ruleset, "spirits.alcohol.tolerance_band")
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.SPIRITS)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("40.0"), abv_actual_pct=Decimal("40.31"))
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_same_field_of_vision_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.same_field_of_vision")
    obs = make_obs(field_id="layout", value={"panels": {"front": ["brand", "class_type", "abv", "net_contents"]}}, beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="layout"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_same_field_of_vision_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.same_field_of_vision")
    obs = make_obs(field_id="layout", value={"panels": {"front": ["brand"], "back": ["class_type", "abv", "net_contents"]}}, beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="layout"), rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_name_address_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.name_address.present")
    obs = make_obs(field_id="bottler", value="Acme Distilling, KY", beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="bottler"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_name_address_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.name_address.present")
    obs = make_obs(field_id="bottler", value=None, beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="bottler"), rule, _ctx(ruleset)).outcome is Outcome.FAIL


def test_net_contents_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.net_contents.present")
    obs = make_obs(field_id="net_contents", value="750 mL", beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_net_contents_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.net_contents.present")
    obs = make_obs(field_id="net_contents", value=None, beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="net_contents"), rule, _ctx(ruleset)).outcome is Outcome.FAIL
