"""cpi_lookup validator: cardinal decision-table lookup, no interpolation."""
from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.rules import RuleDefinition


@register("cpi_lookup")
def cpi_lookup(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    table = ctx.decision_tables.get(rule.decision_table_ref or "")
    payload = obs.observed_value or {}
    height = payload.get(rule.parameters.get("observed_height_field", "height_mm"))
    cpi = payload.get(rule.parameters.get("observed_cpi_field", "cpi"))
    matched_row = None
    if table is not None and height is not None:
        for row in table.entries:
            if row.get("min_required_type_height_mm") == height:
                matched_row = row
                break
    ok = matched_row is not None and cpi is not None and cpi <= matched_row["max_characters_per_inch"]
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
