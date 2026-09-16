"""Does the label name the business the application named?

This is the loosest of the label-to-application comparisons, and deliberately
so. The application's entry is a free-text block that runs the applicant's
trading name, its legal name, a street address, a city, a state, a ZIP code
and any trade name marked as used on the label all together:

    CHATEAU DIANA, CHATEAU DIANA, LLC 6195 DRY CREEK RD HEALDSBURG CA 95448
    UGLY WINES (Used on label)

The label prints one of those names behind a lead-in phrase the regulations
require — "CELLARED AND BOTTLED BY", "IMPORTED BY" — with a city and a state
and nothing else. So the two sides are compared by asking whether the name the
label prints is one of the names the application block carries:

  1. Drop the lead-in phrase: everything through the last standalone "by" near
     the start of the reading.
  2. Take the first two words after it as the name the label prints.
  3. Require that pair inside the application block as consecutive words, and
     require one more of the label's words in the block as well, so a city or
     a legal suffix corroborates the name rather than a single common word
     carrying the match alone.

Where that does not hold, the result is a reviewer's to settle, never a
rejection. A trade name may be on the label without appearing in the block the
registry happens to expose, and a name that is absent from the block is not
evidence that the label is wrong. Whether the label carries a name and address
at all is a separate rule, and that one does reject.
"""
from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    _conf,
    normalize_words,
    project_reading,
    word_run_present,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition


def _after_lead_in(words: tuple[str, ...], lead_in_word: str, window: int) -> tuple[str, ...]:
    """The reading with its required lead-in phrase removed.

    The phrase always ends in the same word and always sits at the start, so
    the split is the last occurrence of that word inside the opening `window`
    words. A reading that has no lead-in is returned whole.
    """
    head = words[:window]
    for i in range(len(head) - 1, -1, -1):
        if head[i] == lead_in_word:
            return words[i + 1:]
    return words


@register("name_address_match")
def name_address_match(
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
        """The label's name cannot be lined up with the application's block,
        which is not evidence the label is wrong — the block need not carry
        every name the label may print. The check reports that it could not be
        settled and a reviewer reads both."""
        return result(Outcome.INSUFFICIENT_EVIDENCE, Severity.WARN, rule.reason_code)

    declared = "" if exp.value is None else str(exp.value).strip()
    if not declared:
        return result(Outcome.NOT_APPLICABLE, rule.severity, None)

    observed = project_reading(obs).strip()
    if not observed:
        return cannot_check()

    lead_in_word = str(rule.parameters.get("lead_in_ends_with", "by"))
    window = int(rule.parameters.get("lead_in_window_words", 8))
    anchor_length = int(rule.parameters.get("anchor_words", 2))

    label_words = _after_lead_in(normalize_words(observed), lead_in_word, window)
    application_words = normalize_words(declared)

    anchor = label_words[:anchor_length]
    if not anchor or not word_run_present(application_words, anchor):
        return cannot_check()

    corroborating = set(label_words[anchor_length:]) & set(application_words)
    if not corroborating:
        return cannot_check()

    return result(Outcome.PASS, rule.severity, None)
