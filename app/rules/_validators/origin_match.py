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

A label that names a different country than the application is a real
disagreement and is reported as one. An import whose label carries no origin
statement at all fails the rule's own reason code.

Known gap: customs marking rules also accept an abbreviation that
unmistakably indicates the country, a variant spelling of its English name,
and the adjectival form. The reference gives those by example rather than as a
list, so this check does not implement them, and an import whose label writes
its country one of those ways is reported as a disagreement for a reviewer to
overturn.
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

    country = "" if exp.value is None else str(exp.value).strip()
    if not country:
        return result(
            Outcome.FAIL,
            Severity.WARN,
            rule.parameters.get("needs_review_reason_code", rule.reason_code),
        )

    observed = project_reading(obs).strip()
    if not observed:
        return result(Outcome.FAIL, rule.severity, rule.reason_code)

    if word_run_present(normalize_words(observed), normalize_words(country)):
        return result(Outcome.PASS, rule.severity, None)

    return result(
        Outcome.FAIL,
        Severity.REJECT,
        rule.parameters.get("disagreement_reason_code", rule.reason_code),
    )
