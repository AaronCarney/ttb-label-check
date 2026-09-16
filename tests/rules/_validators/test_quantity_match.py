"""quantity_match compares a number on the label with a number the application
declared, converting the label's unit first.

The cases that matter are the cross-unit ones. A label prints a customary size
and the application records millilitres, and the customary figure is the metric
size converted and rounded to a tenth of a fluid ounce: 375 mL is 12.6803 fluid
ounces, which a label prints as `12.7 FL. OZ.`. Converting that back gives
375.58, so demanding equality rejects a compliant label by construction.

The rule is therefore: **two figures in different units agree within the rule
pack's own tolerance; two figures in the same unit must be equal.** Nothing was
rounded away between two figures in the same unit, so nothing is forgiven
there. `docs/decisions/0014` records where the tolerance comes from, and
`test_the_shipped_tolerance_sits_between_its_two_derived_bounds` below
recomputes both of its bounds from the authorized standards of fill, so an edit
that loosens the number fails here with the reason attached.
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

_RULES_ROOT = Path(__file__).resolve().parents[3] / "rules"
_TABLE_PATH = _RULES_ROOT / "tables" / "volume_units.yaml"
_PACKS = ("malt/malt.yaml", "wine/wine.yaml", "spirits/spirits.yaml")

# One US fluid ounce in millilitres, exact by definition. The same factor the
# shipped table carries; repeated here so the derivation below is arithmetic a
# reader can check rather than a lookup.
_FL_OZ_ML = 29.5735295625

# The container sizes 27 CFR §4.72 and §5.203 authorize, as amended by
# T.D. TTB-200, effective 2025-01-10.
# `docs/research/2026-09-15-ttb-regulatory-framework.md` is where they are read
# from. Malt beverages have no standards of fill at all (§7.70), which is why
# the tolerance is derived from these two lists and then applied to all three.
_WINE_SIZES_ML = (
    50, 100, 187, 200, 250, 300, 330, 355, 360, 375, 473, 500, 550, 568,
    600, 620, 700, 720, 750, 1000, 1500, 1800, 2250, 3000,
)
_SPIRITS_SIZES_ML = (
    50, 100, 200, 250, 331, 350, 355, 375, 475, 500, 570, 700, 710, 720,
    750, 900, 945, 1000, 1500, 1750, 1800, 2000, 3000,
)


def _volume_units() -> DecisionTable:
    """The shipped table, not a copy, so a unit missing from it fails here."""
    raw = yaml.safe_load(_TABLE_PATH.read_text())
    return DecisionTable(interpolation=raw["interpolation"], entries=tuple(raw["entries"]))


def _shipped_tolerance() -> dict:
    """The tolerance the three beverage packs ship on their net-contents rule.

    Read out of the packs rather than written here, so a pack that loses the
    block, or that disagrees with the other two, fails these tests instead of
    quietly falling back to an exact comparison.
    """
    found = {}
    for pack in _PACKS:
        rules = yaml.safe_load((_RULES_ROOT / pack).read_text())["rules"]
        for rule in rules:
            if rule["rule_id"].endswith(".net_contents.matches_application"):
                found[pack] = rule.get("tolerance")
    assert set(found) == set(_PACKS), f"a pack has no net-contents rule: {sorted(found)}"
    assert len(set(map(repr, found.values()))) == 1, f"the packs disagree: {found}"
    tolerance = found[_PACKS[0]]
    assert tolerance is not None, "the net-contents rules ship no tolerance block"
    return tolerance


def _check(
    label_number: str,
    label_unit: str,
    declared_ml: str,
    tolerance: dict | None = None,
) -> Outcome:
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
        tolerance=_shipped_tolerance() if tolerance is None else tolerance,
        parameters={
            "amount_field": "container_volume_ml",
            "needs_review_reason_code": "NET_CONTENTS.MATCH.NEEDS_REVIEW",
            "disagreement_reason_code": "NET_CONTENTS.MATCH.APPLICATION_LABEL_DISAGREE",
        },
    )
    ctx = make_context(decision_tables={"volume_units": _volume_units()})
    return quantity_match(obs, exp, rule, ctx).outcome


# ---- the conversions a compliant label makes --------------------------------

def test_a_tenth_of_an_ounce_agrees_with_the_rounded_metric_size() -> None:
    """375 mL is 12.6803 fluid ounces and the label prints 12.7, which converts
    back to 375.58. Compared exactly, that rejected a compliant label."""
    assert _check("12.7", "FL. OZ.", "375") is Outcome.PASS


def test_whole_ounces_agree_with_the_rounded_metric_size() -> None:
    assert _check("16", "FL OZ", "473") is Outcome.PASS


def test_a_customary_figure_rounded_down_agrees_too() -> None:
    """A customary statement may not overstate the contents, so a 250 mL can
    prints 8.4 FL OZ rather than the 8.4535 it actually holds. That is the
    widest gap any authorized size opens — 0.633% — and it is the case a rule
    comparing at the label's printed precision got wrong in the other
    direction, computing 8.5 and rejecting the can."""
    assert _check("8.4", "FL OZ", "250") is Outcome.PASS


def test_the_table_lists_the_words_a_label_prints() -> None:
    """A label reading 11.2 FL. OUNCES converts like any other fluid ounce.
    While the table lacked the spelled-out form the check could not be settled
    and went to a reviewer."""
    assert _check("11.2", "FL. OUNCES", "331") is Outcome.PASS


# ---- what must still fail ---------------------------------------------------

def test_a_genuinely_different_size_still_fails() -> None:
    """12 fluid ounces is 354.88 mL, which is not a rounding of 375."""
    assert _check("12", "FL OZ", "375") is Outcome.FAIL


def test_a_coarse_unit_does_not_forgive_a_different_size() -> None:
    """The hole in comparing at the label's printed precision. A label printing
    `1 PINT` has a last printed digit of one whole pint, so that rule admitted
    anything within half a pint and passed a 700 mL application against a pint
    label. A pint is 473 mL and 700 is not."""
    assert _check("1", "PINT", "700") is Outcome.FAIL
    assert _check("1", "LITER", "1400") is Outcome.FAIL


def test_the_closest_pair_of_authorized_sizes_cannot_pass_as_each_other() -> None:
    """720 mL prints 24.3 FL OZ, which converts to 718.64 — 1.216% from the
    710 mL size next to it in the spirits list. That is the narrowest such gap
    in either list, and the tolerance is below it, so the two stay distinct."""
    assert _check("24.3", "FL OZ", "710") is Outcome.FAIL


def test_same_unit_on_both_sides_is_still_compared_exactly() -> None:
    """No conversion means nothing was rounded away, so nothing is forgiven.
    Half a unit must not be rounded into agreement."""
    assert _check("12", "mL", "12.5") is Outcome.FAIL
    assert _check("375", "mL", "375") is Outcome.PASS


def test_a_rule_carrying_no_tolerance_compares_exactly() -> None:
    """The tolerance is the pack's, not the validator's. A rule that does not
    ship one gets the strict comparison, which is what every other rule using
    this validator — alcohol content — wants."""
    assert _check("12.7", "FL. OZ.", "375", tolerance={}) is Outcome.FAIL


def test_an_unconvertible_unit_goes_to_a_reviewer_not_to_a_failure() -> None:
    """Reporting a failure would tell the reviewer the label is wrong on
    evidence that says nothing either way."""
    assert _check("1", "HOGSHEAD", "750") is Outcome.INSUFFICIENT_EVIDENCE


# ---- the number itself ------------------------------------------------------

def _printed_fl_oz(millilitres: float) -> float:
    """The customary figure a label prints for a metric size: converted, and
    rounded to a tenth of a fluid ounce, which is the precision every customary
    figure in the fixture corpus is printed to — 50 mL as 1.7 FL OZ, 375 mL as
    12.7 FL OZ. Observed from those labels, not read out of the regulation; see
    docs/decisions/0014."""
    return round(millilitres / _FL_OZ_ML, 1)


def test_the_shipped_tolerance_sits_between_its_two_derived_bounds() -> None:
    """The tolerance must absorb the rounding in a printed customary figure and
    must not let one authorized size pass as another. Both bounds are computed
    here from the authorized size lists, so loosening the number fails with the
    reason attached instead of passing quietly.

    The floor is the widest gap a printed customary figure opens on a size it
    describes. Two conventions are in use and both count: the nearest tenth,
    which is what the printed figures in the fixture corpus show, and the tenth
    below it, which a label uses so its customary statement does not overstate
    the contents.

    The ceiling is the distance from an authorized size to the customary figure
    printed for the nearest size that prints a different one. At or above that,
    a label stating one size would pass against an application declaring the
    other.
    """
    sizes = sorted(set(_WINE_SIZES_ML) | set(_SPIRITS_SIZES_ML))
    floor = max(abs(_printed_fl_oz(s) * _FL_OZ_ML - s) / s for s in sizes)
    # The one size in these lists a real label states below its nearest tenth:
    # a 250 mL can prints 8.4 FL OZ, not the 8.5 the nearest tenth gives, so
    # the customary figure does not overstate the contents. Named rather than
    # derived, because rounding down is not a general convention and cannot be
    # treated as one: a 50 mL bottle states the published 1.7 FL OZ, and the
    # 1.6 a truncation would give is 5.4% low, wider than any tolerance that
    # still tells two authorized sizes apart.
    floor = max(floor, abs(8.4 * _FL_OZ_ML - 250) / 250)

    ceiling = min(
        abs(_printed_fl_oz(other) * _FL_OZ_ML - size) / size
        for authorized in (_WINE_SIZES_ML, _SPIRITS_SIZES_ML)
        for size in authorized
        for other in authorized
        if other != size and _printed_fl_oz(other) != _printed_fl_oz(size)
    )

    shipped = float(_shipped_tolerance()["cross_unit_relative"])
    assert floor <= shipped < ceiling, (
        f"the shipped tolerance {shipped:.4%} must absorb the {floor:.4%} that "
        f"rounding a printed customary figure needs, and must stay under the "
        f"{ceiling:.4%} that separates two authorized sizes. "
        f"docs/decisions/0014 carries the working."
    )
    # The bounds themselves, so a change in the size lists is visible here too.
    assert round(floor, 5) == 0.00633, f"floor moved to {floor:.5%}"
    assert round(ceiling, 5) == 0.01216, f"ceiling moved to {ceiling:.5%}"
