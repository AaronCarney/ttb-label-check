"""Layout validators: text isolated from other text, and same field of vision."""
from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.rules import RuleDefinition


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


@register("layout_isolation_check")
def layout_isolation_check(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    payload = obs.observed_value or {}
    min_required = int(rule.parameters.get("min_isolation_px", 4))
    distance = payload.get("min_neighbor_distance_px")
    return _result(rule, ctx, obs, exp, ok=(distance is not None and distance >= min_required))


@register("same_field_of_vision_check")
def same_field_of_vision_check(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    required: list[str] = rule.parameters.get("required_fields", [])
    panels: dict[str, list[str]] = (obs.observed_value or {}).get("panels", {})
    on_one_panel = any(set(required).issubset(set(fields)) for fields in panels.values())
    return _result(rule, ctx, obs, exp, ok=on_one_panel)
