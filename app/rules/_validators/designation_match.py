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
     disagreement to report where the line read is nothing but class names
     and a reviewer's question where it carries other words; or it names none
     the list knows, which is a judgement for a reviewer.

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
    text_as_written,
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


def _within_pair(
    label_classes: set[Class], application_classes: set[Class], table: dict[Class, list]
) -> tuple[Class, Class] | None:
    """The class the label names and the one it falls within, or None.

    The pairing rather than a yes: a pass has to tell a reviewer which of the
    label's classes the table placed inside which of the application's, and
    answering that from outside would repeat this walk.
    """
    for declared in sorted(application_classes):
        inner = {normalize_words(str(v)) for v in table.get(declared) or []}
        found = label_classes & inner
        if found:
            return _longest(found), declared
    return None


def _longest(classes: set[Class]) -> Class:
    """The most specific class in a set — the one naming the most words.

    A designation names every class whose words it carries, so "TABLE WINE"
    also names "WINE". Telling a reviewer the label named wine, when the rule
    had table wine to work with, is true and useless. Ties break on the words
    themselves, so the same input always names the same class.
    """
    return max(classes, key=lambda c: (len(c), c))


def _class_as_written(name: Class, recognised: list[str]) -> str:
    """A class as the rule pack spells it, which is what a reviewer can look up.

    The comparison runs on normalised words; the pack writes "Table Wine". A
    class not found in the list — it cannot be, since that list is where it
    came from — falls back to its own words.
    """
    for value in recognised:
        if normalize_words(str(value)) == name:
            return str(value)
    return " ".join(name).upper()


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

    def result(
        outcome: Outcome,
        severity: Severity,
        reason_code: str | None,
        message: str | None = None,
        matched: str | None = None,
    ) -> ValidationResult:
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
            message=message,
            matched_value=matched,
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
    #
    # The card shows "STOUT" beside "BARREL-AGED IMPERIAL STOUT" under one
    # pill, which reads as a contradiction until the pass says where the
    # application's words were found. A segment that is the whole declared
    # designation is already on the card as the expected value, so only a
    # shorter one — the registry packs four classes into
    # "DESSERT /PORT/SHERRY/(COOKING) WINE" — is carried as a value of its own.
    for segment in _segments(declared):
        if segment and word_run_present(label_words, segment):
            written = text_as_written(declared, segment)
            whole = segment == declared_words
            return result(
                Outcome.PASS,
                rule.severity,
                None,
                f'The label designates "{observed}", which carries the '
                + ("application's designation" if whole else "designation the application declares")
                + f', "{written}", inside it as whole words.',
                matched=None if whole else written,
            )

    recognised = list(rule.parameters.get("recognised_classes", []))
    label_classes = _classes_named(label_words, recognised)
    application_classes = _classes_named(declared_words, recognised)

    # 2. Both name the same class.
    #
    # Neither side need read like the class they share: "RED TABLE WINE" and
    # "TABLE RED WINE" both name table wine and neither spells it that way, so
    # the class is the only thing a reviewer can check the verdict against.
    shared = label_classes & application_classes
    if shared:
        named = _longest(shared)
        written = _class_as_written(named, recognised)
        return result(
            Outcome.PASS,
            rule.severity,
            None,
            f'The label designates "{observed}" and the application declares '
            f'"{declared}". Both name the class "{written}".',
            matched=None if named == declared_words else written,
        )

    # 3. The label's class falls within the application's.
    table = _within_table(rule, ctx)
    pairing = _within_pair(label_classes, application_classes, table)
    if pairing is not None:
        inner, outer = pairing
        inner_written = _class_as_written(inner, recognised)
        outer_written = _class_as_written(outer, recognised)
        return result(
            Outcome.PASS,
            rule.severity,
            None,
            f'The label designates "{observed}", which names "{inner_written}". '
            f'The rule pack lists that as falling within "{outer_written}", the '
            f'class the application declares as "{declared}".',
            matched=inner_written,
        )

    # 4a. The label names a different recognised class: a disagreement.
    # The pack's own severity, like every other branch that reports against the
    # label. All three packs set reject, so nothing moves today; hard-coding it
    # here meant a pack could not pilot this rule as a warning and said so
    # nowhere. 4b below is the deliberate exception and carries its reason.
    #
    # Only where the line is nothing but class names. The reader's pick is the
    # largest line naming a class, a guess at which line is the designation, as
    # a brand pick is (decision 0052); a line carrying other words may be one
    # the guess took from running text, and a reviewer decides. Decision 0063.
    class_words = set().union(*label_classes)
    if label_classes and application_classes and not set(label_words) <= class_words:
        on_label = _class_as_written(_longest(label_classes), recognised)
        return result(
            Outcome.INSUFFICIENT_EVIDENCE,
            Severity.WARN,
            rule.parameters.get("needs_review_reason_code", rule.reason_code),
            f'The line read as the designation, "{observed}", names the class "{on_label}" '
            f'and the application declares "{declared}", but the line carries other '
            "words and may not be the label's designation. Check the designation on "
            "the label.",
        )
    if label_classes and application_classes:
        return result(
            Outcome.FAIL,
            rule.severity,
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
