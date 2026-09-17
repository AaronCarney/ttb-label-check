"""Presence-style validators.

  presence_check        — fail when the reading is absent or whitespace-only.
  conditional_presence  — same, but skip when the precondition in
                          rule.parameters['required_when'] (a key into
                          expected.parameters) is falsy.

Presence is judged on the reading itself, not on whether the reader returned a
payload. The reader emits a dict for every field it was asked about, empty
strings included, so a label carrying no government warning still arrives as a
`gov_warning` observation. `project_reading` pulls the reading out of that
payload so an empty one fails, which is what §16.21 requires.
"""

from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    _conf,
    not_read_result,
    project_reading,
    unlocated,
    unlocated_is_absent,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.rules import RuleDefinition


def _is_present(obs: FieldObservation) -> bool:
    return bool(project_reading(obs).strip())


def _result(rule, ctx, obs, exp, present: bool) -> ValidationResult:
    return ValidationResult(
        rule_id=rule.rule_id,
        cfr_citation=rule.cfr_citation,
        beverage_class=obs.beverage_class,
        outcome=Outcome.PASS if present else Outcome.FAIL,
        severity=rule.severity,
        reason_code=None if present else rule.reason_code,
        aggregated_confidence=_conf(obs),
        evidence=obs.evidence,
        expected=exp,
        observed=obs,
        engine_meta=_build_meta(rule, ctx),
    )


@register("presence_check")
def presence_check(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`.
    if unlocated(obs) and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx)

    return _result(rule, ctx, obs, exp, _is_present(obs))


@register("conditional_presence")
def conditional_presence(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    key = rule.parameters.get("required_when")
    required = bool(exp.parameters.get(key, False)) if key else True
    if not required:
        return ValidationResult(
            rule_id=rule.rule_id,
            cfr_citation=rule.cfr_citation,
            beverage_class=obs.beverage_class,
            outcome=Outcome.NOT_APPLICABLE,
            severity=rule.severity,
            reason_code=None,
            aggregated_confidence=_conf(obs),
            evidence=obs.evidence,
            expected=exp,
            observed=obs,
            engine_meta=_build_meta(rule, ctx),
        )
    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`.
    if unlocated(obs) and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx)

    return _result(rule, ctx, obs, exp, _is_present(obs))
