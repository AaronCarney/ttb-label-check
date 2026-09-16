"""Does the label state the country the application says the product came from?

The application answers one question first — domestic or imported — and only
then names a place. That first answer decides whether there is a check at all:

  - Domestic. The application is stating positively that the product was made
    in the United States, and no country-of-origin statement is required. The
    check does not apply, whatever the label happens to say. The place the
    application names for a domestic product is a State, which is not what a
    country-of-origin statement carries.
  - Imported, with a country named. The label must say so. The country has to
    appear inside the label's origin statement as whole words, because the
    statement wraps it in wording the label chooses: "PRODUCT OF MEXICO",
    "HECHO EN MEXICO", "DISTILLED IN IRELAND".
  - Imported, with no country named. Nothing to compare, and a reviewer reads
    the application.

Where the label's statement does not carry the country as whole words, the
check reports that it could not be settled and a reviewer reads the label. It
does not reject, because it cannot tell the two cases apart: the label may
name a different country, or it may name the right one in a form this product
does not recognise. Customs marking rules accept the country's name in the
language of the country, an abbreviation that unmistakably indicates it, and
the adjectival form — "HECHO EN MEXICO", "U.K.", "Irish". The customs marking
reference gives those by example rather than as a list, so none of them are
built here, and rejecting on their account would reject compliant labels. The
citation for the rule sits in the rule pack, with the decision record at
docs/decisions/0016.

The cost of that is real and is the cost this product chooses: a label that
genuinely names the wrong country reaches a reviewer rather than being
rejected outright. An import whose label carries no origin statement at all is
a different matter — nothing was stated, so there is nothing to interpret, and
that branch does reject under the rule's own reason code.
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


@register("origin_match")
def origin_match(
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

    source = exp.parameters.get(rule.parameters.get("source_field", "source_of_product"))
    imported_value = rule.parameters.get("imported_value", "imported")

    # The application said nothing about where the product came from, or said
    # it was made here. Either way there is no country-of-origin check.
    if source is None or str(source) != imported_value:
        return result(Outcome.NOT_APPLICABLE, rule.severity, None)

    # Imported, but the application names no country. There is nothing to
    # compare the label's statement against, so the check reports that it
    # could not be settled rather than failing a label on a gap in the
    # application.
    country = "" if exp.value is None else str(exp.value).strip()
    if not country:
        return result(
            Outcome.INSUFFICIENT_EVIDENCE,
            Severity.WARN,
            rule.parameters.get("needs_review_reason_code", rule.reason_code),
        )

    observed = project_reading(obs).strip()
    if not observed:
        return result(Outcome.FAIL, rule.severity, rule.reason_code)

    if word_run_present(normalize_words(observed), normalize_words(country)):
        return result(Outcome.PASS, rule.severity, None)

    # The label states an origin and it does not carry the declared country in
    # a form this check reads. That is a question for a person, not a verdict
    # — see the note above.
    return result(
        Outcome.INSUFFICIENT_EVIDENCE,
        Severity.WARN,
        rule.parameters.get("disagreement_reason_code", rule.reason_code),
    )
