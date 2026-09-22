"""Does the label's brand mark agree with the application?

The application does not declare one name. It declares a brand, sometimes a
fanciful name beside it, and sometimes a trade name it told TTB it prints on
the label — and a label carrying any of those carries a name its own
application declared. So the comparison is against a set of admissible
values, not against one string, and each route below is run against all of
them before the next route starts:

  Exact        — the two values are the same once normalised. A match against
                 the declared brand is the ordinary case and says nothing more;
                 a match against any other admissible value is reported, so the
                 reviewer sees which name the label used.
  Whole words  — one value's words sit inside the other's as a consecutive run.
                 A mark that drops or adds a word is the same brand written
                 shorter or longer ("THE UGLY" against "UGLY SWEATER").
  Punctuation  — the two are the same once punctuation and spacing are taken
                 out ("O'S" against "Os", "FIRESTONE" against "Fire Stone"). A
                 match at any length, and the finding says what differs. Form
                 TTB F 5100.31, allowable revisions item 3.b, lets an approved
                 label change the punctuation of its words without a new
                 approval (`docs/decisions.md#0017`).
  Score        — Jaro-Winkler similarity. At or above `pass_threshold` the two
                 spellings are the same name; between that and
                 `needs_review_threshold` they are too close to call and a
                 reviewer decides; below it they are different names.
  Search       — the label's other lines, searched for the declared brand
                 and the trade names (`search_route` in
                 `app/rules/brand_match.py`). The reader picks the text set
                 in the largest type, and on many labels that is a statutory
                 line or a class designation while the brand sits in a
                 stylised mark or the bottler's line. The application states
                 the brand, so the question is whether the label shows it.
                 The fanciful name is not searched for: it describes the
                 product, and "BARREL PROOF" is on labels of many brands.
  First letter — the score the two reach with a disagreeing first character
                 removed from both. This route can only ever reach a
                 reviewer, never a match, because a rescue that could pass
                 would make "Gin" against "Din" a perfect score.

A name found nowhere goes to a reviewer, under the rule's own code, and never
to a mismatch: the picked text is a guess at which line is the brand, and a
wrong guess is not evidence that the label names a different brand
(`docs/decisions.md#0052`).

Thresholds come from the rule pack. What a score above one *means* is decided
here; the numbers are not.
"""

from __future__ import annotations

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    normalize_words,
    not_read_result,
    project_reading,
    unlocated,
    unlocated_is_absent,
)
from app.rules.brand_match import (
    SEARCH_MISREAD,
    SEARCH_PUNCTUATION,
    SEARCH_ROUTES,
    SEARCH_SHORTENED,
    SEARCH_WITHIN,
    canonicalize,
    search_route,
    shortened,
    stage_a_normalized,
    stage_a_punctuation_only,
    stage_a_word_run,
    stage_b_first_letter_variant,
    stage_b_fuzzy,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition

# How each admissible value is described to a reviewer. The declared brand is
# the ordinary case and carries no explanation; the others are named, because
# "the label shows a different name from the brand field, and here is where
# the application says that name" is the finding.
_DECLARED = "the brand the application declares"
_FANCIFUL = "the fanciful name the application declares"
_TRADE_NAME = "a name the application marks as used on the label"


def _admissible_values(declared: str, exp: ExpectedValue) -> tuple[tuple[str, str], ...]:
    """Every name the application says this label may carry, declared first.

    `application_mapper` supplies the fanciful name as a string and the trade
    names as a tuple of strings. A blank one is dropped: an empty name equals
    the empty reading of a brand box the reader found but could not read, and
    would pass it.

    A trade name that repeats the brand is kept. Every route below stops at
    the first value that answers, and the declared brand comes first, so the
    repeat can never be the one a finding names.
    """
    candidates = [(declared, _DECLARED)]
    fanciful = exp.parameters.get("fanciful_name")
    if fanciful:
        candidates.append((fanciful, _FANCIFUL))
    candidates += [
        (name, _TRADE_NAME) for name in exp.parameters.get("trade_names_used_on_label", ())
    ]
    return tuple((value.strip(), source) for value, source in candidates if value.strip())


def _best(
    observed: str,
    admissible: tuple[tuple[str, str], ...],
    score_of,
) -> tuple[float, str, str]:
    """The highest score the label's mark reaches, and the value it reached it
    against. On a tie the earlier value wins, so the declared brand does."""
    return max(
        ((score_of(observed, value), value, source) for value, source in admissible),
        key=lambda scored: scored[0],
    )


# What each search route found, in the words a reviewer reads after 'The
# label's <face> shows "<line>", which'.
_FOUND_AS = {
    SEARCH_PUNCTUATION: "differs from {source}, \"{value}\", only in punctuation or "
    "spacing, which TTB's allowable revisions let a label change without a new approval",
    SEARCH_WITHIN: "carries {source}, \"{value}\"",
    SEARCH_MISREAD: "is {source}, \"{value}\", with one character read differently",
}


def _trailing_words(rule: RuleDefinition, ctx: ValidatorContext) -> frozenset[str]:
    """The business and class words a declared name may be printed without,
    from the rule pack's table, normalised the way names are compared."""
    table = ctx.decision_tables.get(rule.decision_table_ref) if rule.decision_table_ref else None
    if table is None:
        return frozenset()
    return frozenset(
        word
        for entry in table.entries
        for listed in entry.get("words") or ()
        for word in normalize_words(canonicalize(str(listed)))
    )


def _candidates(obs: FieldObservation) -> list[dict]:
    """The lines the reader lists beside its pick, each with its text."""
    value = obs.observed_value
    listed = value.get("candidates") if isinstance(value, dict) else None
    return [c for c in listed or () if isinstance(c, dict) and str(c.get("text", "")).strip()]


def _search(
    obs: FieldObservation,
    admissible: tuple[tuple[str, str], ...],
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> tuple[str, dict, str, str] | None:
    """The strongest route by which any listed line shows a searched name.

    Routes are tried strongest first, and within a route the names in
    admissible order and the lines in the order the reader listed them, so the
    same reading always reports the same line.
    """
    candidates = _candidates(obs)
    if not candidates:
        return None
    searched = tuple((v, s) for v, s in admissible if s != _FANCIFUL)
    trailing = _trailing_words(rule, ctx)
    lengths = {
        "min_length": int(rule.parameters.get("search_min_length", 3)),
        "within_min_length": int(rule.parameters.get("search_within_min_length", 5)),
        "misread_min_length": int(rule.parameters.get("search_misread_min_length", 8)),
    }
    found: dict[str, tuple[str, dict, str, str]] = {}
    for value, source in searched:
        for candidate in candidates:
            route = search_route(str(candidate["text"]), value, trailing=trailing, **lengths)
            if route is not None:
                found.setdefault(route, (route, candidate, value, source))
    return next((found[route] for route in SEARCH_ROUTES if route in found), None)


def _found_message(
    route: str, candidate: dict, value: str, source: str, trailing: frozenset[str]
) -> str:
    face = candidate.get("face")
    where = f"The label's {face}" if face else "The label"
    line = str(candidate["text"]).strip()
    if route == SEARCH_SHORTENED:
        dropped = value.split()[len(shortened(value, trailing)) :]
        return (
            f'{where} shows "{line}", which is {source}, "{value}", without '
            f'"{" ".join(dropped)}".'
        )
    template = _FOUND_AS.get(route)
    if template is None:
        return f'{where} shows "{line}", which is {source}, "{value}".'
    return f'{where} shows "{line}", which {template.format(source=source, value=value)}.'


def _found_evidence(obs: FieldObservation, route: str, candidate: dict, value: str) -> Evidence:
    """The line the name was found in, as the evidence a reviewer is shown."""
    bbox = candidate.get("bbox")
    return Evidence(
        field_id=obs.evidence[0].field_id if obs.evidence else obs.field_id,
        source=EvidenceSource.OCR,
        panel=candidate.get("face"),
        bbox=tuple(int(v) for v in bbox) if bbox else None,
        extracted_text=str(candidate["text"]).strip(),
        matched_against_value=value,
        match_kind=MatchKind.FUZZY if route == SEARCH_MISREAD else MatchKind.NORMALIZED,
        confidence=max(0.0, min(1.0, float(candidate.get("confidence", 0.0)))),
    )


@register("fuzzy_brand")
def fuzzy_brand(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    observed = project_reading(obs)
    declared = "" if exp.value is None else str(exp.value)
    meta = _build_meta(rule, ctx)

    def result(
        outcome: Outcome,
        severity: Severity,
        reason_code: str | None,
        message: str | None = None,
        matched: str | None = None,
        evidence: tuple[Evidence, ...] | None = None,
    ) -> ValidationResult:
        evidence = obs.evidence if evidence is None else evidence
        return ValidationResult(
            rule_id=rule.rule_id,
            cfr_citation=rule.cfr_citation,
            beverage_class=obs.beverage_class,
            outcome=outcome,
            severity=severity,
            reason_code=reason_code,
            aggregated_confidence=min((e.confidence for e in evidence), default=0.0),
            evidence=evidence,
            expected=exp,
            observed=obs,
            engine_meta=meta,
            message=message,
            matched_value=matched,
        )

    # The rule needs something to compare against. Without an expected brand
    # the application never declared one — surface as NOT_APPLICABLE rather
    # than silently failing every cold-loaded label.
    if not declared.strip():
        return result(Outcome.NOT_APPLICABLE, rule.severity, None)

    admissible = _admissible_values(declared, exp)

    def found_on_label() -> ValidationResult | None:
        """The pass for a searched name some line of the label shows, if any."""
        hit = _search(obs, admissible, rule, ctx)
        if hit is None:
            return None
        route, candidate, value, source = hit
        return result(
            Outcome.PASS,
            rule.severity,
            None,
            _found_message(route, candidate, value, source, _trailing_words(rule, ctx)),
            matched=None if source == _DECLARED else value,
            evidence=(_found_evidence(obs, route, candidate, value),),
        )

    # The reader picked nothing as the brand. The name may still be on a line
    # it read; if not, that is a question for a reviewer, not a rejection -
    # see `unlocated` in `_helpers.py`.
    if unlocated(obs, observed) and not unlocated_is_absent(rule):
        return found_on_label() or not_read_result(obs, exp, rule, ctx, element="a brand mark")

    pass_th = float(rule.parameters.get("pass_threshold", 0.92))
    nr_th = float(rule.parameters.get("needs_review_threshold", 0.85))
    nr_code = rule.parameters.get("needs_review_reason_code", "BRAND.NAME.NEEDS_REVIEW")

    for value, source in admissible:
        if stage_a_normalized(observed, value):
            # A plain match against the declared brand is the expected result
            # and needs no explaining. A match against one of the other names
            # does, because the reviewer is looking at a label whose mark is
            # not the brand field's wording.
            message = (
                None
                if source == _DECLARED
                else f'The label shows "{observed}", which is {source}, "{value}".'
            )
            return result(
                Outcome.PASS,
                rule.severity,
                None,
                message,
                matched=None if source == _DECLARED else value,
            )

    for value, source in admissible:
        if stage_a_word_run(observed, value):
            return result(
                Outcome.PASS,
                rule.severity,
                None,
                f'The label shows "{observed}". Its words and those of {source}, '
                f'"{value}", carry one inside the other in order, so the label '
                "states that name with a word added or left off.",
                matched=None if source == _DECLARED else value,
            )

    for value, source in admissible:
        if stage_a_punctuation_only(observed, value):
            return result(
                Outcome.PASS,
                rule.severity,
                None,
                f'The label shows "{observed}" against {source}, "{value}". They '
                "differ only in punctuation or spacing, which TTB's allowable "
                "revisions let a label change without a new approval.",
                matched=None if source == _DECLARED else value,
            )

    score, value, source = _best(observed, admissible, stage_b_fuzzy)

    if score >= pass_th:
        return result(
            Outcome.PASS,
            rule.severity,
            None,
            f'The label shows "{observed}" against {source}, "{value}" — the two '
            f"spellings score {score:.4f}, at or above the {pass_th:g} this rule "
            "treats as the same name.",
            matched=None if source == _DECLARED else value,
        )

    # The pick is not the name. Before a reviewer is asked, the rest of the
    # label is searched for it.
    found = found_on_label()
    if found is not None:
        return found

    # The borderline band. The two names are close enough that the difference
    # may be how the label was read rather than a different brand, so the
    # check reports that it could not be settled and a reviewer compares them.
    if score >= nr_th:
        return result(
            Outcome.INSUFFICIENT_EVIDENCE,
            Severity.WARN,
            nr_code,
            f'The label shows "{observed}" against {source}, "{value}" — the two '
            f"spellings score {score:.4f}, short of the {pass_th:g} a match needs "
            "and above the point where they stop resembling each other, so a "
            "reviewer decides.",
        )

    # A brand mark set in a display face loses its first character more often
    # than any other, and the score above punishes exactly that hardest. Where
    # the two names agree on everything after it, that is worth a reviewer's
    # eye — but never a match on its own, or a three-letter brand differing in
    # its only distinguishing letter would score perfectly.
    variant, variant_value, variant_source = _best(
        observed, admissible, stage_b_first_letter_variant
    )
    if variant >= nr_th:
        return result(
            Outcome.INSUFFICIENT_EVIDENCE,
            Severity.WARN,
            nr_code,
            f'The label shows "{observed}" against {variant_source}, '
            f'"{variant_value}". The two differ at their first character and '
            f"score {variant:.4f} from the second on. A stylised first letter is "
            "the one a reader most often mistakes, so a reviewer compares the "
            "label against the application rather than the check deciding it.",
        )

    # Not found. The pick is shown so the reviewer sees what the reader took
    # for the brand, and the reviewer decides; a guess at which line is the
    # brand is not evidence the label names another one.
    shown = f'"{observed}"' if observed.strip() else "no text"
    return result(
        Outcome.INSUFFICIENT_EVIDENCE,
        Severity.WARN,
        rule.reason_code,
        f'The application declares the brand "{declared}", and no line read on the '
        f"label shows it. The largest text read as a brand is {shown}. A stylised or "
        "curved mark is often not read, so a reviewer compares the label against "
        "the application.",
    )
