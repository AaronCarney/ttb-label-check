"""abv_band is registered under three names:

  abv_band                 — class-aware alcohol tolerance band.
  abv_class_boundary_check — §4.36(c) anti-overlap for wine.
  abv_hard_floor           — §7.65(c) malt 0.5% hard floor.

All alcohol arithmetic uses Decimal, so the band edges compare exactly.
"""
from __future__ import annotations

from decimal import Decimal

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.abv_band import (  # noqa: F401
    abv_band,
    abv_class_boundary_check,
    abv_hard_floor,
)
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _rule(validator: str, reason: str, tolerance: dict | None = None, params: dict | None = None):
    return make_rule(
        rule_id=f"x.{validator}",
        cfr_citation="27 CFR §0.0",
        validator=validator,
        reason_code=reason,
        match_policy=MatchPolicy.TOLERANCE,
        tolerance=tolerance,
        parameters=params or {},
    )


# --- spirits ±0.3 pp ---

def test_spirits_at_tolerance_passes() -> None:
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.SPIRITS)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("40.0"), abv_actual_pct=Decimal("40.3"))
    rule = _rule("abv_band", "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND", tolerance={"plus_pp": 0.3, "minus_pp": 0.3})
    assert abv_band(obs, exp, rule, make_context()).outcome is Outcome.PASS


def test_spirits_just_outside_tolerance_fails() -> None:
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.SPIRITS)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("40.0"), abv_actual_pct=Decimal("40.4"))
    rule = _rule("abv_band", "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND", tolerance={"plus_pp": 0.3, "minus_pp": 0.3})
    assert abv_band(obs, exp, rule, make_context()).outcome is Outcome.FAIL


# --- wine class-aware tolerance (±1.0 pp above 14%, ±1.5 pp at or below) ---

_WINE_CLASS_AWARE_PARAMS = {
    "class_boundary_pct": 14.0,
    "tolerance_by_class_boundary": {
        "<=": {"plus_pp": 1.5, "minus_pp": 1.5},
        ">":  {"plus_pp": 1.0, "minus_pp": 1.0},
    },
}


def test_wine_under_14_uses_wide_band_pass() -> None:
    """12% labeled, 13.5% actual → inside ≤14% bucket's ±1.5 pp."""
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("12.0"), abv_actual_pct=Decimal("13.5"))
    rule = _rule("abv_band", "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND", params=_WINE_CLASS_AWARE_PARAMS)
    assert abv_band(obs, exp, rule, make_context()).outcome is Outcome.PASS


def test_wine_over_14_uses_tight_band_fail() -> None:
    """16% labeled, 17.2% actual → outside >14% bucket's ±1.0 pp."""
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("16.0"), abv_actual_pct=Decimal("17.2"))
    rule = _rule("abv_band", "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND", params=_WINE_CLASS_AWARE_PARAMS)
    assert abv_band(obs, exp, rule, make_context()).outcome is Outcome.FAIL


def test_wine_over_14_within_tight_band_pass() -> None:
    """16% labeled, 16.8% actual → inside >14% bucket's ±1.0 pp."""
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("16.0"), abv_actual_pct=Decimal("16.8"))
    rule = _rule("abv_band", "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND", params=_WINE_CLASS_AWARE_PARAMS)
    assert abv_band(obs, exp, rule, make_context()).outcome is Outcome.PASS


# --- wine §4.36(c) class-boundary anti-overlap ---

def test_wine_no_class_boundary_cross_fail() -> None:
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("13.5"), abv_actual_pct=Decimal("14.5"))
    rule = _rule(
        "abv_class_boundary_check",
        "ALCOHOL_CONTENT.TOLERANCE.CROSSES_CLASS_BOUNDARY",
        params={"class_boundary_pct": 14.0},
    )
    assert abv_class_boundary_check(obs, exp, rule, make_context()).outcome is Outcome.FAIL


def test_wine_no_cross_when_both_below_pass() -> None:
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.WINE)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("12.0"), abv_actual_pct=Decimal("12.5"))
    rule = _rule(
        "abv_class_boundary_check",
        "ALCOHOL_CONTENT.TOLERANCE.CROSSES_CLASS_BOUNDARY",
        params={"class_boundary_pct": 14.0},
    )
    assert abv_class_boundary_check(obs, exp, rule, make_context()).outcome is Outcome.PASS


# --- malt §7.65(c) 0.5% hard floor ---

def test_malt_below_hard_floor_fail() -> None:
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("0.4"), abv_actual_pct=Decimal("0.4"))
    rule = _rule(
        "abv_hard_floor",
        "ALCOHOL_CONTENT.TOLERANCE.BELOW_HARD_FLOOR",
        params={"floor_pct": 0.5},
    )
    assert abv_hard_floor(obs, exp, rule, make_context()).outcome is Outcome.FAIL


def test_malt_at_or_above_hard_floor_pass() -> None:
    obs = make_obs(field_id="abv", value=None, beverage_class=BeverageClass.MALT)
    exp = make_expected(field_id="abv", abv_labeled_pct=Decimal("0.5"), abv_actual_pct=Decimal("0.5"))
    rule = _rule(
        "abv_hard_floor",
        "ALCOHOL_CONTENT.TOLERANCE.BELOW_HARD_FLOOR",
        params={"floor_pct": 0.5},
    )
    assert abv_hard_floor(obs, exp, rule, make_context()).outcome is Outcome.PASS


def test_validators_registered() -> None:
    assert "abv_band" in VALIDATOR_REGISTRY
    assert "abv_class_boundary_check" in VALIDATOR_REGISTRY
    assert "abv_hard_floor" in VALIDATOR_REGISTRY
