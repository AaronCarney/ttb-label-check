"""quantity_match compares a number on the label with a number the application
declared, converting the label's unit first.

The cases that matter are the cross-unit ones. A label prints a customary size
and the application records millilitres, and the customary figure is rounded --
375 mL is 12.68 fluid ounces, which a label prints as 12.7. The two describe one
container, so the check asks what the label would print if it stated the
application's figure, rather than demanding a conversion that rounding has made
impossible.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml

from app.rules._validators.quantity_match import quantity_match
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome
from app.schemas.rules import DecisionTable
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

_TABLE_PATH = Path(__file__).resolve().parents[3] / "rules" / "tables" / "volume_units.yaml"


def _volume_units() -> DecisionTable:
    """The shipped table, not a copy, so a unit missing from it fails here."""
    raw = yaml.safe_load(_TABLE_PATH.read_text())
    return DecisionTable(interpolation=raw["interpolation"], entries=tuple(raw["entries"]))


def _check(label_number: str, label_unit: str, declared_ml: str) -> Outcome:
    obs = make_obs(
        field_id="net_contents",
        value={"net_contents_value": label_number, "unit": label_unit},
        beverage_class=BeverageClass.MALT,
    )
    exp = make_expected(field_id="net_contents", container_volume_ml=Decimal(declared_ml))
    rule = make_rule(
        rule_id="malt.net_contents.matches_application",
        cfr_citation="27 CFR §7.70",
        validator="quantity_match",
        reason_code="NET_CONTENTS.MATCH.APPLICATION_LABEL_DISAGREE",
        applies_to_classes=(BeverageClass.MALT,),
        decision_table_ref="volume_units",
        parameters={
            "amount_field": "container_volume_ml",
            "needs_review_reason_code": "NET_CONTENTS.MATCH.NEEDS_REVIEW",
            "disagreement_reason_code": "NET_CONTENTS.MATCH.APPLICATION_LABEL_DISAGREE",
        },
    )
    ctx = make_context(decision_tables={"volume_units": _volume_units()})
    return quantity_match(obs, exp, rule, ctx).outcome


def test_tenth_of_an_ounce_agrees_with_the_rounded_metric_size() -> None:
    """375 mL stated in fluid ounces to one decimal place is 12.7, which is
    what the label prints. Compared the other way it is 375.58, and the label
    was rejected for it."""
    assert _check("12.7", "FL. OZ.", "375") is Outcome.PASS


def test_whole_ounces_agree_with_the_rounded_metric_size() -> None:
    assert _check("16", "FL OZ", "473") is Outcome.PASS


def test_a_genuinely_different_size_still_fails() -> None:
    """375 mL is 12.7 fluid ounces to the label's precision, not 12."""
    assert _check("12", "FL OZ", "375") is Outcome.FAIL


def test_same_unit_on_both_sides_is_still_compared_exactly() -> None:
    """No conversion means nothing was rounded away, so nothing is forgiven.
    Half a unit must not be rounded into agreement."""
    assert _check("12", "mL", "12.5") is Outcome.FAIL
    assert _check("375", "mL", "375") is Outcome.PASS


def test_the_table_lists_the_words_a_label_prints() -> None:
    """A label reading 11.2 FL. OUNCES converts like any other fluid ounce.
    While the table lacked the spelled-out form the check could not be settled
    and went to a reviewer."""
    assert _check("11.2", "FL. OUNCES", "331") is Outcome.PASS


def test_an_unconvertible_unit_goes_to_a_reviewer_not_to_a_failure() -> None:
    """Reporting a failure would tell the reviewer the label is wrong on
    evidence that says nothing either way."""
    assert _check("1", "HOGSHEAD", "750") is Outcome.INSUFFICIENT_EVIDENCE
