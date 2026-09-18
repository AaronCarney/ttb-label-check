"""regex_match validator: tests observed string against rule.parameters['pattern']."""

from __future__ import annotations

import logging
import re

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    not_read_result,
    unlocated,
    unlocated_is_absent,
    verdict_result,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import ValidationResult
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
    ok = bool(re.match(pattern, observed, flags=flags)) if observed else False
    return verdict_result(obs, exp, rule, ctx, ok=ok)
