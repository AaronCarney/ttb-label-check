"""Does the label's class-and-type designation say what the application declared?

The application names a class or type from the registry's own list, which
carries filing shorthand the label never shows: "OTHER GIN FB", "VODKA 80-89
PROOF". The label carries a designation, which is the class or type with the
qualifiers the regulations permit around it: "AMERICAN DRY GIN", "GUAVA FORWARD
GIN / DISTILLED FROM GRAIN". The two agree when they name the same class, not
when they read the same.

Four ways they can agree, in order:

  1. The application's designation is the label's, or appears inside it as a
     run of whole words.
  2. Both name the same recognised class, where a designation names a class if
     it carries every word of that class's name.
  3. The label's designation is one the decision table lists as falling within
     the application's class — a lager is a beer.
  4. Neither: the label names some other recognised class, which is a
     disagreement to report; or it names none the list knows, which is a
     judgement for a reviewer.

The recognised classes and the within-class table are rule-pack data, so
adding a class is an edit to the rule pack and not to this file.
"""

from __future__ import annotations

import re

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    _conf,
    normalize_words,
    not_read_result,
    project_reading,
    unlocated,
    unlocated_is_absent,
    word_run_present,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition

# A class is its words, in order, and that is what every comparison below is
# between. They were joined back into a string first, on both sides, purely so
# two sets could be intersected - a separator written out twice that nothing
# ever read. The words are already the thing being compared, so they are what
# is carried around.
Class = tuple[str, ...]


def _classes_named(words: Class, recognised: list[str]) -> set[Class]:
    """Every recognised class whose words all appear in this designation.

    Word presence rather than a run, because a designation interleaves its
    qualifiers: "TABLE RED WINE" and "RED TABLE WINE" both name table wine.
    """
    present = set(words)
    named = (normalize_words(str(value)) for value in recognised)
    return {c for c in named if c and present.issuperset(c)}


def _within(
    label_classes: set[Class], application_classes: set[Class], table: dict[Class, list]
) -> bool:
    """True when a class the label names falls within one the application did."""
    for declared in application_classes:
        inner = {normalize_words(str(v)) for v in table.get(declared) or []}
        if label_classes & inner:
            return True
    return False


@register("designation_match")
def designation_match(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    observed = project_reading(obs).strip()
    declared = "" if exp.value is None else str(exp.value).strip()
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

    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`.
    if unlocated(obs) and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx, element="a class or type designation")

    # The designation has to be on the label whatever the application says.
    if not observed:
        return result(Outcome.FAIL, rule.severity, rule.reason_code)

    # The application declared no class or type, so there is nothing to
    # compare the label's designation with and the check does not apply.
    # Reporting agreement here would name a check that only ever had one side.
    if not declared:
        return result(Outcome.NOT_APPLICABLE, rule.severity, None)

    label_words = normalize_words(observed)
    declared_words = normalize_words(declared)

    # 1. The application's designation, or any segment of it, inside the label's.
    for segment in _segments(declared):
        if segment and word_run_present(label_words, segment):
            return result(Outcome.PASS, rule.severity, None)

    recognised = list(rule.parameters.get("recognised_classes", []))
    label_classes = _classes_named(label_words, recognised)
    application_classes = _classes_named(declared_words, recognised)

    # 2. Both name the same class.
    if label_classes & application_classes:
        return result(Outcome.PASS, rule.severity, None)

    # 3. The label's class falls within the application's.
    table = _within_table(rule, ctx)
    if _within(label_classes, application_classes, table):
        return result(Outcome.PASS, rule.severity, None)

    # 4a. The label names a different recognised class: a disagreement.
    if label_classes and application_classes:
        return result(
            Outcome.FAIL,
            Severity.REJECT,
            rule.parameters.get("disagreement_reason_code", rule.reason_code),
        )

    # 4b. Neither side lines up with the list, so the check could not be
    # settled and a reviewer decides. This is not a disagreement: a
    # designation the list does not know is no evidence the label is wrong.
    return result(
        Outcome.INSUFFICIENT_EVIDENCE,
        Severity.WARN,
        rule.parameters.get("needs_review_reason_code", rule.reason_code),
    )


def _segments(declared: str) -> list[Class]:
    """The declared class/type split where the registry packs several into one
    string: on slashes and around a parenthesised alternative.

    One split on all three characters, rather than rewriting the brackets into
    slashes first. The rewrite said "a bracket is a slash", which is not what
    is meant and left the slash spelled out in two places.
    """
    return [normalize_words(part) for part in re.split(r"[/()]", declared)]


def _within_table(rule: RuleDefinition, ctx: ValidatorContext) -> dict[Class, list]:
    """The decision table as a map from a class to the designations within it.

    Each table entry names one class and the designations it covers:
    `{class: Beer, designations_within: [Lager, Ale, ...]}`. An entry naming no
    class is dropped rather than stringified: `str(None)` is "None", which
    would enter the map as a class called "none" and pair with any label
    reading that word.
    """
    ref = rule.decision_table_ref
    table = ctx.decision_tables.get(ref) if ref else None
    if table is None:
        return {}
    mapped: dict[Class, list] = {}
    for entry in table.entries:
        declared = entry.get("class")
        name = normalize_words(str(declared)) if declared is not None else ()
        if name:
            mapped[name] = list(entry.get("designations_within") or [])
    return mapped
