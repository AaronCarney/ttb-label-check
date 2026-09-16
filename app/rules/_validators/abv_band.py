"""ABV-content validators. Every comparison is in Decimal, never float.

  abv_band                 — labeled ± tolerance covers actual.
  abv_class_boundary_check — labeled ± tolerance must NOT cross class boundary
                             (wine §4.36(c)).
  abv_hard_floor           — actual must meet/exceed a hard floor that
                             tolerance does not relax (malt §7.65(c)).
"""
from __future__ import annotations

from decimal import Decimal

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.rules import RuleDefinition


def _decimal(v: object | None) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _result(rule, ctx, obs, exp, ok: bool) -> ValidationResult:
    return ValidationResult(
        rule_id=rule.rule_id,
        cfr_citation=rule.cfr_citation,
        beverage_class=obs.beverage_class,
        outcome=Outcome.PASS if ok else Outcome.FAIL,
        severity=rule.severity,
        reason_code=None if ok else rule.reason_code,
        aggregated_confidence=_conf(obs),
        evidence=obs.evidence,
        expected=exp,
        observed=obs,
        engine_meta=_build_meta(rule, ctx),
    )


def _select_tolerance(rule: RuleDefinition, labeled: Decimal) -> tuple[Decimal, Decimal]:
    """Resolve (plus_pp, minus_pp) for this labeled value.

    Class-aware path (wine takes ±1.0 pp above 14% and ±1.5 pp at or below):
    when ``parameters['tolerance_by_class_boundary']`` is present, pick the
    bucket keyed by ``"<="`` or ``">"`` based on
    ``parameters['class_boundary_pct']``. Tolerance values stay in YAML,
    never in Python.

    Flat-band path (spirits, malt): fall back to ``rule.tolerance``.
    """
    by_boundary = rule.parameters.get("tolerance_by_class_boundary")
    if by_boundary:
        boundary = Decimal(str(rule.parameters["class_boundary_pct"]))
        bucket = by_boundary[">"] if labeled > boundary else by_boundary["<="]
        return Decimal(str(bucket["plus_pp"])), Decimal(str(bucket["minus_pp"]))
    plus = Decimal(str((rule.tolerance or {}).get("plus_pp", 0)))
    minus = Decimal(str((rule.tolerance or {}).get("minus_pp", 0)))
    return plus, minus


@register("abv_band")
def abv_band(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    labeled = _decimal(exp.abv_labeled_pct)
    actual = _decimal(exp.abv_actual_pct)
    if labeled is None or actual is None:
        return _result(rule, ctx, obs, exp, ok=False)
    plus, minus = _select_tolerance(rule, labeled)
    ok = (labeled - minus) <= actual <= (labeled + plus)
    return _result(rule, ctx, obs, exp, ok)


@register("abv_class_boundary_check")
def abv_class_boundary_check(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    labeled = _decimal(exp.abv_labeled_pct)
    actual = _decimal(exp.abv_actual_pct)
    boundary = Decimal(str(rule.parameters.get("class_boundary_pct", 14.0)))
    if labeled is None or actual is None:
        return _result(rule, ctx, obs, exp, ok=False)
    crosses = (labeled <= boundary < actual) or (actual <= boundary < labeled)
    return _result(rule, ctx, obs, exp, ok=not crosses)


@register("abv_hard_floor")
def abv_hard_floor(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    actual = _decimal(exp.abv_actual_pct)
    floor = Decimal(str(rule.parameters.get("floor_pct", 0.5)))
    if actual is None:
        return _result(rule, ctx, obs, exp, ok=False)
    return _result(rule, ctx, obs, exp, ok=actual >= floor)
