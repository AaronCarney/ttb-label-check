"""The two spirits rules with matching logic of their own: the standard-of-identity
candidate match, and the age-statement floor."""
from __future__ import annotations

from pathlib import Path

import pytest

import app.rules._validators.equality_match  # noqa: F401
import app.rules._validators.unmeasurable  # noqa: F401
import app.rules._validators.format_check  # noqa: F401
import app.rules._validators.fuzzy_brand  # noqa: F401
import app.rules._validators.heading_style_check  # noqa: F401
import app.rules._validators.layout_check  # noqa: F401
import app.rules._validators.presence_check  # noqa: F401
import app.rules._validators.verbatim_hash  # noqa: F401
from app.rules._validators import VALIDATOR_REGISTRY
from app.rules.loader import YamlRuleLoader
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome, Severity
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


@pytest.mark.parametrize("designation", ["Cognac XO", "CRÈME DE CASSIS LIQUEUR"])
def test_soi_match_accepts_a_class_carried_inside_the_designation(ruleset, designation) -> None:
    # Both are TTB-approved labels in the fixture set. Subpart I names Cognac
    # and Liqueur, and the designation carries the class rather than equalling
    # it (docs/decisions/0007), so the qualifiers around it do not matter.
    rule = _r(ruleset, "spirits.class_type.matches_soi")
    obs = make_obs(field_id="class_type", value=designation, beverage_class=BeverageClass.SPIRITS)
    assert VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset)).outcome is Outcome.PASS


def test_soi_match_neg(ruleset) -> None:
    # A designation Subpart I does not name is a reviewer's finding, not a
    # rejection: Subpart I lets a spirit with no standard of identity be
    # designated by a fanciful name with a statement of composition, so an
    # unrecognised designation is no evidence the label is wrong.
    # docs/decisions/0012.
    rule = _r(ruleset, "spirits.class_type.matches_soi")
    obs = make_obs(field_id="class_type", value="Mystery Hooch", beverage_class=BeverageClass.SPIRITS)
    res = VALIDATOR_REGISTRY[rule.validator](obs, make_expected(field_id="class_type"), rule, _ctx(ruleset))
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "CLASS_TYPE.SOI.NO_MATCH"
    assert res.severity is Severity.WARN


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
