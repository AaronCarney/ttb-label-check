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

A State written out and the same State as its two-letter postal code are the
same State, and the label and the registry routinely differ on which they
write — "Healdsburg, California" against "HEALDSBURG CA 95448". Both sides are
folded to the postal code before they are compared, so the State can do the
corroborating in step 3 instead of the city having to carry it alone.

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

# A State name and its postal code are the same State. The fold is applied
# here rather than in shared normalisation because the equivalence belongs to
# this element and to the clauses that permit it (27 CFR 4.35(c), 5.66(d)(1),
# 7.66(c)): "California" is also a wine appellation and a country-of-origin
# answer, and folding it to "CA" there would corrupt comparisons that turn on
# the word itself. Both sides are folded, so an over-fold is symmetric — a
# city named Washington becomes "wa" on the label and "wa" in the application.
_STATE_POSTAL_CODES: dict[tuple[str, ...], str] = {
    ("alabama",): "al",
    ("alaska",): "ak",
    ("arizona",): "az",
    ("arkansas",): "ar",
    ("california",): "ca",
    ("colorado",): "co",
    ("connecticut",): "ct",
    ("delaware",): "de",
    ("florida",): "fl",
    ("georgia",): "ga",
    ("hawaii",): "hi",
    ("idaho",): "id",
    ("illinois",): "il",
    ("indiana",): "in",
    ("iowa",): "ia",
    ("kansas",): "ks",
    ("kentucky",): "ky",
    ("louisiana",): "la",
    ("maine",): "me",
    ("maryland",): "md",
    ("massachusetts",): "ma",
    ("michigan",): "mi",
    ("minnesota",): "mn",
    ("mississippi",): "ms",
    ("missouri",): "mo",
    ("montana",): "mt",
    ("nebraska",): "ne",
    ("nevada",): "nv",
    ("new", "hampshire"): "nh",
    ("new", "jersey"): "nj",
    ("new", "mexico"): "nm",
    ("new", "york"): "ny",
    ("north", "carolina"): "nc",
    ("north", "dakota"): "nd",
    ("ohio",): "oh",
    ("oklahoma",): "ok",
    ("oregon",): "or",
    ("pennsylvania",): "pa",
    ("rhode", "island"): "ri",
    ("south", "carolina"): "sc",
    ("south", "dakota"): "sd",
    ("tennessee",): "tn",
    ("texas",): "tx",
    ("utah",): "ut",
    ("vermont",): "vt",
    ("virginia",): "va",
    ("washington",): "wa",
    ("west", "virginia"): "wv",
    ("wisconsin",): "wi",
    ("wyoming",): "wy",
    # The District and the territories that appear on TTB basic permits.
    ("district", "of", "columbia"): "dc",
    ("d", "c"): "dc",
    ("puerto", "rico"): "pr",
    ("virgin", "islands"): "vi",
    ("guam",): "gu",
    ("american", "samoa"): "as",
    ("northern", "mariana", "islands"): "mp",
}
_LONGEST_STATE_NAME = max(len(name) for name in _STATE_POSTAL_CODES)


def _fold_state_names(words: tuple[str, ...]) -> tuple[str, ...]:
    """The same words with every State name written as its postal code.

    The longest run wins, so "west virginia" folds to "wv" before "west" and
    "virginia" can be read as two separate words, and "district of columbia"
    to "dc" rather than leaving "columbia" behind.
    """
    folded: list[str] = []
    i = 0
    while i < len(words):
        for length in range(min(_LONGEST_STATE_NAME, len(words) - i), 0, -1):
            code = _STATE_POSTAL_CODES.get(words[i : i + length])
            if code is not None:
                folded.append(code)
                i += length
                break
        else:
            folded.append(words[i])
            i += 1
    return tuple(folded)


def _after_lead_in(words: tuple[str, ...], lead_in_word: str, window: int) -> tuple[str, ...]:
    """The reading with its required lead-in phrase removed.

    The phrase always ends in the same word and always sits at the start, so
    the split is the last occurrence of that word inside the opening `window`
    words. A reading that has no lead-in is returned whole.
    """
    head = words[:window]
    for i in range(len(head) - 1, -1, -1):
        if head[i] == lead_in_word:
            return words[i + 1 :]
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

    label_words = _fold_state_names(_after_lead_in(normalize_words(observed), lead_in_word, window))
    application_words = _fold_state_names(normalize_words(declared))

    anchor = label_words[:anchor_length]
    if not anchor or not word_run_present(application_words, anchor):
        return cannot_check()

    corroborating = set(label_words[anchor_length:]) & set(application_words)
    if not corroborating:
        return cannot_check()

    return result(Outcome.PASS, rule.severity, None)
