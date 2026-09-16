"""fuzzy_brand validator. Two-stage policy:

  Stage A — normalized exact. Pass immediately if equal; record kind=normalized.
  Stage B — Jaro-Winkler fuzzy.
    score >= pass_threshold       → PASS  (kind=fuzzy, score recorded)
    needs_review_threshold <= s < pass_threshold → FAIL with severity=warn,
                                  reason_code=BRAND.NAME.NEEDS_REVIEW
                                  (what triggers an orchestrator call)
    score < needs_review_threshold → FAIL with reason_code=BRAND.NAME.MISMATCH
"""
from __future__ import annotations

import logging

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf
from app.rules.brand_match import stage_a_normalized, stage_b_fuzzy
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition

_logger = logging.getLogger("app.rules._validators.fuzzy_brand")


def _project_brand(value: object) -> str:
    """The cloud extractor produces {brand_name, confidence}; legacy fixtures
    pass a bare string. Return the brand string in either shape."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # `brand_name` is the canonical cloud key; `value` is the legacy fixture key.
        for key in ("brand_name", "value"):
            v = value.get(key)
            if isinstance(v, str) and v:
                return v
    return ""


@register("fuzzy_brand")
def fuzzy_brand(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    observed = _project_brand(obs.observed_value)
    expected = "" if exp.value is None else str(exp.value)
    meta = _build_meta(rule, ctx)

    # The rule needs something to compare against. Without an expected brand
    # the application never declared one — surface as NOT_APPLICABLE rather
    # than silently failing every cold-loaded label.
    if not expected:
        return ValidationResult(
            rule_id=rule.rule_id, cfr_citation=rule.cfr_citation,
            beverage_class=obs.beverage_class, outcome=Outcome.NOT_APPLICABLE,
            severity=rule.severity, reason_code=None,
            aggregated_confidence=_conf(obs), evidence=obs.evidence,
            expected=exp, observed=obs, engine_meta=meta,
        )

    if stage_a_normalized(observed, expected):
        return ValidationResult(
            rule_id=rule.rule_id,
            cfr_citation=rule.cfr_citation,
            beverage_class=obs.beverage_class,
            outcome=Outcome.PASS,
            severity=rule.severity,
            reason_code=None,
            aggregated_confidence=_conf(obs),
            evidence=obs.evidence,
            expected=exp,
            observed=obs,
            engine_meta=meta,
        )

    score = stage_b_fuzzy(observed, expected)
    pass_th = float(rule.parameters.get("pass_threshold", 0.92))
    nr_th = float(rule.parameters.get("needs_review_threshold", 0.85))
    nr_code = rule.parameters.get("needs_review_reason_code", "BRAND.NAME.NEEDS_REVIEW")

    if score >= pass_th:
        return ValidationResult(
            rule_id=rule.rule_id, cfr_citation=rule.cfr_citation,
            beverage_class=obs.beverage_class, outcome=Outcome.PASS,
            severity=rule.severity, reason_code=None,
            aggregated_confidence=_conf(obs), evidence=obs.evidence,
            expected=exp, observed=obs, engine_meta=meta,
        )
    if score >= nr_th:
        return ValidationResult(
            rule_id=rule.rule_id, cfr_citation=rule.cfr_citation,
            beverage_class=obs.beverage_class, outcome=Outcome.FAIL,
            severity=Severity.WARN, reason_code=nr_code,
            aggregated_confidence=_conf(obs), evidence=obs.evidence,
            expected=exp, observed=obs, engine_meta=meta,
        )
    return ValidationResult(
        rule_id=rule.rule_id, cfr_citation=rule.cfr_citation,
        beverage_class=obs.beverage_class, outcome=Outcome.FAIL,
        severity=rule.severity, reason_code=rule.reason_code,
        aggregated_confidence=_conf(obs), evidence=obs.evidence,
        expected=exp, observed=obs, engine_meta=meta,
    )
