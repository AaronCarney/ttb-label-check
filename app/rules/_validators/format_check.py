"""regex_match validator: tests observed string against rule.parameters['pattern']."""
from __future__ import annotations

import logging
import re

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.rules import RuleDefinition

_logger = logging.getLogger("app.rules._validators.format_check")


def _project_alc_text(value: object, field_id: str) -> str:
    """Build the canonical 'alcohol N% by volume' string from the cloud
    extractor's abv dict. Legacy string observations pass through unchanged."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if field_id in ("abv", "alcohol_content"):
            pct = value.get("abv_pct")
            unit = value.get("unit", "%")
            if pct is None:
                return ""
            return f"alcohol {pct}{unit} by volume"
        # Generic projection: pick the first scalar value with a stable order.
        for key in ("text", "value", "name"):
            v = value.get(key)
            if isinstance(v, str) and v:
                return v
    return ""


@register("regex_match")
def regex_match(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    pattern = rule.parameters.get("pattern", "")
    ignore_case = bool(rule.parameters.get("ignore_case", False))
    flags = re.IGNORECASE if ignore_case else 0
    observed = _project_alc_text(obs.observed_value, obs.field_id)
    if not observed and isinstance(obs.observed_value, dict):
        # Diagnostic for "why did this rule fail" — distinguishes projection
        # failure (no recognized key) from regex mismatch on a real string.
        _logger.debug(
            "regex_match_empty_projection",
            extra={
                "rule_id": rule.rule_id,
                "field_id": obs.field_id,
                "observed_keys": sorted(obs.observed_value.keys()),
            },
        )
    ok = bool(re.match(pattern, observed, flags=flags)) if observed else False
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
