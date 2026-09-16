"""Does the quantity on the label equal the one the application declared?

Alcohol content and net contents are numbers written as words. A label says
"40% ALC./VOL. 80 PROOF" or "12.7 FL. OZ."; the application declares 40 and
375 millilitres. Comparing the words matches nothing, so this validator pulls
the number out of each side and compares those, converting the label's unit
into the application's first.

Four outcomes:

  - The application declared no value for the element: there is nothing to
    compare, so the check does not apply.
  - The application declared words that name no single quantity — a keg collar
    listing three sizes with one struck through — and a reviewer decides.
  - The label states no number a reader could pull out, and a reviewer decides.
    A label carrying no statement at all is the presence rule's business, not
    this one's.
  - Both sides give a number, and they must agree.

**Two figures in the same unit must be equal.** Nothing was rounded away
between them, so nothing is forgiven: a label reading 12 against a declared
12.5 disagrees. The margin there exists only because a number that travelled
through a float cannot be trusted to compare exactly against the same value
written as a decimal.

**Two figures in different units agree within the rule's own tolerance.** The
container sizes the regulations authorize are rounded metric equivalents of
customary ones, so a label stating the customary size and an application
stating the metric one can never convert into each other exactly: 375 mL is
12.68 fluid ounces, which a label prints as 12.7, and demanding that 12.7
convert back to exactly 375 rejects a compliant label by construction. The
tolerance that closes that gap is data in the rule pack — the `tolerance`
block of the rule — not a constant in this file, so a reviewer can read the
number that decided a verdict, and the same input always gives the same
answer. `docs/decisions/0014` records where the number comes from. A rule that
carries no tolerance compares exactly, in either case.

Unit conversions come from the rule pack's decision table, read through
`app.rules.units`, which is also what the application form and the
reading-accuracy harness read it with. Adding a unit is an edit to the rule
pack and not to this file.
"""
from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    _conf,
    first_number,
    project_reading,
)
from app.rules.units import table_from_entries
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition

# Two declared numbers in the same unit agree when they are the same number.
# The margin exists only because a reading that travelled through a float
# cannot be trusted to compare exactly against the same value written as a
# decimal.
_EQUALITY_MARGIN = 1e-9

# The rule's own name for the tolerance a converted comparison allows, as a
# fraction of the figure the application declared.
_CROSS_UNIT_TOLERANCE = "cross_unit_relative"


def _observed_unit(obs: FieldObservation) -> str:
    value = obs.observed_value
    if isinstance(value, dict):
        unit = value.get("unit")
        if isinstance(unit, str):
            return unit
    return ""


def _conversion_factor(unit: str, rule: RuleDefinition, ctx: ValidatorContext) -> float | None:
    """How many of the application's units one of `unit` makes, or None when
    the label's unit cannot be converted into the application's.

    A reading with no unit, and a rule with no conversion table, convert by 1:
    the reader reports the same unit the application declares unless it says
    otherwise.

    A unit the table does not list cannot be converted, and neither can one it
    lists with no factor. Both report that the check could not be settled.
    Treating an unlisted unit as the application's own is how a label reading
    "1 PT" came to be compared with 750 millilitres and rejected: the two
    numbers are not the same measurement, and the product must not say a label
    is wrong on that basis.
    """
    ref = rule.decision_table_ref
    table = ctx.decision_tables.get(ref) if ref else None
    if table is None or not unit:
        return 1.0
    return table_from_entries(table.entries).factor(unit)


def _margin(declared_amount: float, factor: float, rule: RuleDefinition) -> float:
    """How far apart the two figures may be and still agree.

    Nothing, beyond float noise, where no conversion happened. Where one
    happened, the rule pack's own tolerance, because the two figures are a
    customary size and its rounded metric equivalent and cannot be expected to
    convert into each other exactly.
    """
    noise = abs(declared_amount) * _EQUALITY_MARGIN
    if factor == 1.0:
        return max(noise, _EQUALITY_MARGIN)
    ratio = (rule.tolerance or {}).get(_CROSS_UNIT_TOLERANCE)
    if ratio is None:
        return max(noise, _EQUALITY_MARGIN)
    return max(abs(declared_amount) * float(ratio), _EQUALITY_MARGIN)


@register("quantity_match")
def quantity_match(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    meta = _build_meta(rule, ctx)

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
            engine_meta=meta,
        )

    def cannot_check() -> ValidationResult:
        """No number to compare, so the check reports that it could not be
        settled. Reporting a failure would tell the reviewer the label is
        wrong on evidence that says nothing either way."""
        return result(
            Outcome.INSUFFICIENT_EVIDENCE,
            Severity.WARN,
            rule.parameters.get("needs_review_reason_code", rule.reason_code),
        )

    amount_field = rule.parameters.get("amount_field", "")
    declared_amount = getattr(exp, amount_field, None) if amount_field else None
    declared_text = "" if exp.value is None else str(exp.value).strip()

    # The application said nothing about this element.
    if declared_amount is None and not declared_text:
        return result(Outcome.NOT_APPLICABLE, rule.severity, None)

    # It said something, but no one number: a reviewer reads the words.
    if declared_amount is None:
        return cannot_check()

    observed_amount = first_number(project_reading(obs))
    if observed_amount is None:
        return cannot_check()

    factor = _conversion_factor(_observed_unit(obs), rule, ctx)
    if factor is None:
        return cannot_check()

    declared = float(declared_amount)
    difference = abs(observed_amount * factor - declared)
    if difference <= _margin(declared, factor, rule):
        return result(Outcome.PASS, rule.severity, None)
    return result(
        Outcome.FAIL,
        Severity.REJECT,
        rule.parameters.get("disagreement_reason_code", rule.reason_code),
    )
