"""Layout validation: the required statements share one field of vision.

`layout_isolation_check` was the other name here: it compared a payload's
`min_neighbor_distance_px` against a threshold for `common.warning.separate_apart`.
No reader emits that distance, so the check could never run on a real label, and
docs/decisions.md#0013 moved the rule to the `unmeasurable` validator. The
registration went with it — an unreferenced validator name fails the orphan check
in `tests/test_rules_yaml_round_trip.py::test_no_orphan_validators_in_registry` by
design. When a reader does emit a neighbour distance, the lane that lands it
writes the comparison against that real signal.
"""

from __future__ import annotations

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


@register("same_field_of_vision_check")
def same_field_of_vision_check(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`.
    required: list[str] = rule.parameters.get("required_fields", [])
    panels: dict[str, list[str]] = (obs.observed_value or {}).get("panels", {})
    # No panel map at all means the reader read no layout, not that the label
    # splits its mandatory elements across faces.
    if unlocated(obs, "read" if panels else "") and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx, element="the elements this rule places")

    on_one_panel = any(set(required).issubset(set(fields)) for fields in panels.values())
    return _result(rule, ctx, obs, exp, ok=on_one_panel)
