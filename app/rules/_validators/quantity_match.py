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
  - Both sides give a number, and they must be equal.

The two numbers are compared for equality, not against a tolerance. A
tolerance covers the difference between what a label claims and what is in the
bottle, which is a laboratory result nobody here has. Two declarations of the
same value on two documents either agree or they do not.

Unit conversions come from the rule pack's decision table, so adding a unit is
an edit to the rule pack and not to this file.
"""
from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    _conf,
    first_number,
    normalize_words,
    project_reading,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition

# Two declared numbers agree when they are the same number. The margin exists
# only because a reading that travelled through a float cannot be trusted to
# compare exactly against the same value written as a decimal.
_EQUALITY_MARGIN = 1e-9


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

    A unit's words are run together before they are compared, because a reader
    may or may not keep the space inside one. The local reader strips it, so
    "FL. OZ." arrives as "FLOZ" and would never match the table's "fl oz" if
    the two were compared word for word.
    """
    ref = rule.decision_table_ref
    table = ctx.decision_tables.get(ref) if ref else None
    if table is None or not unit:
        return 1.0
    wanted = "".join(normalize_words(unit))
    for entry in table.entries:
        if "".join(normalize_words(str(entry.get("unit", "")))) == wanted:
            factor = entry.get("factor")
            return None if factor is None else float(factor)
    return None


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

    if abs(observed_amount * factor - float(declared_amount)) <= _EQUALITY_MARGIN:
        return result(Outcome.PASS, rule.severity, None)
    return result(
        Outcome.FAIL,
        Severity.REJECT,
        rule.parameters.get("disagreement_reason_code", rule.reason_code),
    )
