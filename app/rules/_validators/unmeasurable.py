"""unmeasurable: the answer a rule gives when this product cannot take the
measurement the regulation asks for.

Several requirements in the rule pack are real requirements that this product
has no way to check. Contrast needs the colour of the ink and of the surface
behind it; type height and characters per inch need the physical scale of the
label, which a photograph does not carry; separation from other text needs a
reader that reports the distance to the nearest neighbour, and none does yet.

A check that cannot be made has three possible answers, and only one of them
is honest. Passing claims a requirement was met that nobody looked at.
Failing rejects a compliant label for the product's own blindness — which is
what the deleted implementations did, because every one of them compared
against a reading the payload never carries. This validator gives the third:
insufficient evidence, at warn severity, carrying the rule's own reason code,
which says in words what could not be measured. The label goes to a reviewer
on that point and is never rejected on it.

Each such rule also stays `disabled: true` in the pack, so it does not add a
finding to every label today. The validator is what the rule answers with the
moment anyone switches it on, and it is why switching one on can no longer
produce a wrong verdict.
"""

from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition


@register("unmeasurable")
def unmeasurable(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
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
