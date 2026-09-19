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
  Score        — Jaro-Winkler similarity. At or above `pass_threshold` the two
                 spellings are the same name; between that and
                 `needs_review_threshold` they are too close to call and a
                 reviewer decides; below it they are different names.
  First letter — the score the two reach with a disagreeing first character
                 removed from both. This route can only ever reach a
                 reviewer, never a match, because a rescue that could pass
                 would make "Gin" against "Din" a perfect score.

Thresholds come from the rule pack. What a score above one *means* is decided
here; the numbers are not.
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
from app.rules.brand_match import (
    stage_a_normalized,
    stage_a_word_run,
    stage_b_first_letter_variant,
    stage_b_fuzzy,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
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

    # The rule needs something to compare against. Without an expected brand
    # the application never declared one — surface as NOT_APPLICABLE rather
    # than silently failing every cold-loaded label.
    if not declared.strip():
        return result(Outcome.NOT_APPLICABLE, rule.severity, None)

    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`.
    if unlocated(obs, observed) and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx, element="a brand mark")

    admissible = _admissible_values(declared, exp)
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

    return result(Outcome.FAIL, rule.severity, rule.reason_code)
