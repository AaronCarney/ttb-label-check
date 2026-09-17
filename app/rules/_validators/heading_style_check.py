"""heading_style_check: the GOVERNMENT WARNING heading's words, capitals and
bold weight, under §16.22(a)(2).

The rule asks three questions of one heading, and this product can answer two
of them from any readable image and the third only sometimes:

  * the words — read from `heading_text`;
  * the capitals — read from `heading_all_caps`, which the reader computes
    from the heading's own characters;
  * the bold weight — `heading_bold`, which is a stroke-width measurement
    taken on the heading's own region of the image. Where the reader could
    not take it, the payload says so in `heading_bold_measured_confident`.

Words or capitals wrong is a rejection: the label is not compliant and the
image was good enough to show it. Boldness that was never measured is not.
Reporting it as *not bold* against a reject-severity rule turns the product's
own blindness into a rejection of a label that may well be in bold, so that
branch returns insufficient evidence at warn severity under the code the rule
declares in `unmeasured_weight_reason_code`, and the label goes to a reviewer
on that point alone.

Spacing inside the heading is not a difference: §16.21 fixes the words, and a
label printing "GOVERNMENT  WARNING" or "GOVERNMENT WARNING   :" prints the
mandated heading. Trailing punctuation goes the same way — the regulation
sets the statement out as "GOVERNMENT WARNING: (1) …", so a compliant label
carries a colon that the rule's own target phrase does not.

Backwards-compatible with the legacy `heading_styles` sub-object used by
hand-built fixtures, which carries a weight it states rather than one it
measured, and is therefore read as measured.
"""
from __future__ import annotations

import re

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    _conf,
    not_read_result,
    unlocated,
    unlocated_is_absent,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition

_WHITESPACE = re.compile(r"\s+")


def _heading_phrase(text: str) -> str:
    """The heading's words, with spacing and the punctuation that separates
    the heading from the statement taken out."""
    collapsed = _WHITESPACE.sub(" ", text).strip()
    return collapsed.rstrip(":;.,-–—").strip().upper()


def _weight_was_measured(payload: dict) -> bool:
    """False only when the reader explicitly reports that its stroke-width
    measurement was not confident. A payload that says nothing about the
    measurement — every hand-built fixture — is taken at its word."""
    return bool(payload.get("heading_bold_measured_confident", True))


def _phrase_and_case_ok(payload: dict, target: str, case: str) -> bool:
    text = payload.get("heading_text", "")
    if _heading_phrase(text) != _heading_phrase(target):
        return False
    if "heading_all_caps" in payload or "heading_bold" in payload:
        all_caps = bool(payload.get("heading_all_caps", False))
        return (case == "upper" and all_caps) or (case == "lower" and not all_caps)
    return payload.get("heading_styles", {}).get("case") == case


def _weight_ok(payload: dict, weight: str) -> bool:
    if "heading_all_caps" in payload or "heading_bold" in payload:
        is_bold = bool(payload.get("heading_bold", False))
        return (weight == "bold" and is_bold) or (weight == "regular" and not is_bold)
    return payload.get("heading_styles", {}).get("weight") == weight


def _heading_reading(payload: dict) -> str:
    """What this check needs to have been read: the heading, or a style report
    about it. Either one means the reader found the heading."""
    parts = [str(payload.get("heading_text") or "")]
    if payload.get("heading_styles") or "heading_all_caps" in payload:
        parts.append("styled")
    return " ".join(p for p in parts if p)


@register("heading_style_check")
def heading_style_check(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`.
    payload = obs.observed_value if isinstance(obs.observed_value, dict) else {}
    if unlocated(obs, _heading_reading(payload)) and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx, element="the warning heading")

    target = rule.parameters.get("target_phrase", "GOVERNMENT WARNING")
    required_case = rule.parameters.get("required_case", "upper")
    required_weight = rule.parameters.get("required_weight", "bold")

    def result(outcome: Outcome, severity: Severity, reason_code: str | None) -> ValidationResult:
        return ValidationResult(
            rule_id=rule.rule_id,
            cfr_citation=rule.cfr_citation,
            beverage_class=obs.beverage_class,
            outcome=outcome,
            severity=severity,
            reason_code=reason_code,
            aggregated_confidence=_conf(obs),
            evidence=obs.evidence,
            expected=exp,
            observed=obs,
            engine_meta=_build_meta(rule, ctx),
        )

    # The words and the capitals first: both are read from the heading's own
    # text, so a failure here is the label's, not the reader's.
    if not _phrase_and_case_ok(payload, target, required_case):
        return result(Outcome.FAIL, rule.severity, rule.reason_code)

    # The rule pack names the code this branch reports. Without one there is
    # no sentence to hand a reviewer, so the check falls through to the weight
    # the payload carries rather than reporting a needs-review with no reason.
    if not _weight_was_measured(payload):
        unmeasured_code = rule.parameters.get("unmeasured_weight_reason_code")
        if unmeasured_code:
            return result(Outcome.INSUFFICIENT_EVIDENCE, Severity.WARN, unmeasured_code)

    if not _weight_ok(payload, required_weight):
        return result(Outcome.FAIL, rule.severity, rule.reason_code)

    return result(Outcome.PASS, rule.severity, None)
