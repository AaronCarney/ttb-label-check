"""The two spirits rules with matching logic of their own: the standard-of-identity
candidate match, and the age-statement floor."""
from __future__ import annotations

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


def test_soi_match_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.class_type.matches_soi")
    obs = make_obs(field_id="class_type", value="Bourbon Whisky", beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_soi_match_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.class_type.matches_soi")
    obs = make_obs(field_id="class_type", value="Mystery Hooch", beverage_class=BeverageClass.SPIRITS)
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "CLASS_TYPE.SOI.NO_MATCH"


def test_age_statement_pos(ruleset) -> None:
    rule = _r(ruleset, "spirits.age_statement.floor")
    obs = make_obs(field_id="age_statement", value="Aged 4 Years", beverage_class=BeverageClass.SPIRITS)
    exp = make_expected(field_id="age_statement", parameters={"age_required": True})
    assert VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_age_statement_neg(ruleset) -> None:
    rule = _r(ruleset, "spirits.age_statement.floor")
    obs = make_obs(field_id="age_statement", value=None, beverage_class=BeverageClass.SPIRITS)
    exp = make_expected(field_id="age_statement", parameters={"age_required": True})
    res = VALIDATOR_REGISTRY[rule.validator](obs, exp, rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "AGE_STATEMENT.FLOOR.MISSING"
