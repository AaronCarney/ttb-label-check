"""regex_match validator: is the label's alcohol statement in a form the rule's pattern lists?

A statement the pattern matches passes. One it does not match goes to a
reviewer rather than being rejected, because a pattern can list the forms a
regulation gives but not every phrasing it permits, and a label the pattern
does not recognise is not thereby shown to be wrong (docs/decisions.md#0011).
"""

from __future__ import annotations

import logging
import re

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    _conf,
    not_read_result,
    unlocated,
    unlocated_is_absent,
    verdict_result,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition

_logger = logging.getLogger("app.rules._validators.format_check")


def _project_alc_text(value: object) -> str:
    """The alcohol statement as the label prints it, for the pattern to judge.

    Both readers return it as `alc_text` alongside the number
    (`docs/decisions.md#0011`). A reading that is already a string is the
    wording itself.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("alc_text")
        if isinstance(text, str):
            return text
    return ""


@register("regex_match")
def regex_match(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`.
    pattern = rule.parameters.get("pattern", "")
    ignore_case = bool(rule.parameters.get("ignore_case", False))
    flags = re.IGNORECASE if ignore_case else 0
    observed = _project_alc_text(obs.observed_value)
    if unlocated(obs, observed) and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx, element="the statement this rule checks")

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
    if re.match(pattern, observed, flags=flags):
        return verdict_result(obs, exp, rule, ctx, ok=True)
    return ValidationResult(
        rule_id=rule.rule_id,
        cfr_citation=rule.cfr_citation,
        beverage_class=obs.beverage_class,
        outcome=Outcome.INSUFFICIENT_EVIDENCE,
        severity=Severity.WARN,
        reason_code=rule.reason_code,
        aggregated_confidence=_conf(obs),
        evidence=obs.evidence,
        expected=exp,
        observed=obs,
        engine_meta=_build_meta(rule, ctx),
    )
