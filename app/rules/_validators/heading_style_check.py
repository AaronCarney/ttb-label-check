"""heading_style_check: §16.22(a)(2) caps + bold heading enforcement.

Reads the consolidated gov_warning observation produced by
`app/vision/cloud.py`. Keys: `heading_text`, `heading_all_caps`,
`heading_bold`. The `heading_bold` value is the SWT-measured signal whenever
the local stroke-width measurement was confident; otherwise it falls back to
the reader's own classification.

Backwards-compatible with the legacy `heading_styles` sub-object used by
hand-built fixtures so existing fixture tests don't have to be rewritten.
"""
from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.rules import RuleDefinition


def _heading_phrase(text: str) -> str:
    """The heading's words, with the punctuation that separates the heading
    from the statement removed.

    §16.21 sets the mandated statement out as "GOVERNMENT WARNING: (1) …", so
    a compliant label reads the heading with a trailing colon, while the rule
    names the phrase the words themselves must spell. Comparing the two
    literally fails every compliant label.
    """
    return text.strip().rstrip(":;.,-\u2013\u2014").strip().upper()


def _read_heading_signal(payload: dict, target: str, weight: str, case: str) -> bool:
    """Resolve (text, case, weight) match from either the consolidated cloud
    shape or the legacy `heading_styles` sub-object."""
    text = payload.get("heading_text", "")
    if "heading_all_caps" in payload or "heading_bold" in payload:
        all_caps = bool(payload.get("heading_all_caps", False))
        is_bold = bool(payload.get("heading_bold", False))
        case_ok = (case == "upper" and all_caps) or (case == "lower" and not all_caps)
        weight_ok = (weight == "bold" and is_bold) or (weight == "regular" and not is_bold)
    else:
        styles = payload.get("heading_styles", {})
        case_ok = styles.get("case") == case
        weight_ok = styles.get("weight") == weight
    return (_heading_phrase(text) == _heading_phrase(target)) and case_ok and weight_ok


@register("heading_style_check")
def heading_style_check(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    payload = obs.observed_value or {}
    target = rule.parameters.get("target_phrase", "GOVERNMENT WARNING")
    required_case = rule.parameters.get("required_case", "upper")
    required_weight = rule.parameters.get("required_weight", "bold")
    ok = _read_heading_signal(payload, target, required_weight, required_case)
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
