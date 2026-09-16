"""type_size_check: read the type size in points from the observation payload
and compare it against the §16.22(b) minimum (2 pt by default; a rule may
override via parameters).

The health-warning type-size rule is switched off: the regulation sets the
minimum in millimetres and keys it to container size, and a photograph does not
carry the physical scale needed to turn pixels into millimetres
(docs/decisions/0006). The shape here matches `contrast_ratio_check`: numeric
threshold from rule parameters, numeric reading from the observation payload,
one comparison.
"""
from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.rules import RuleDefinition


@register("type_size_check")
def type_size_check(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    threshold_pt = float(rule.parameters.get("min_type_size_pt", 2.0))
    payload = obs.observed_value or {}
    size_pt = payload.get("type_size_pt")
    ok = size_pt is not None and float(size_pt) >= threshold_pt
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
