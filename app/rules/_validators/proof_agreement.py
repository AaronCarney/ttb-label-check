"""Does the proof a label states equal twice the ABV the same label states?

This compares the label with itself, not with the application. A proof is a
second way of writing the alcohol content, so a label stating "45% ALC/VOL (80
PROOF)" contradicts itself whatever the application declared. The application's
figure is quoted to a reviewer where the label's own ABV could not be read, and
never decides the outcome.

The reading carries a `proof` list: every proof figure the reader found on the
label, each with its own OCR confidence and whether it sat on the ABV
statement's line or the line next to it (`beside_abv`). A reading with no such
list — a recorded reading, or one built by hand — has its proof read out of
`alc_text` by the same finder the readers use, and anything found there is
inside the ABV statement by construction.

Each figure is compared in `Decimal`, built from the printed string:

  - equal to twice the ABV: agrees;
  - off by less than one unit of the precision it is printed at ("86" against
    twice 42.8, which is 85.6): a reviewer decides whether the label rounded;
  - otherwise, beside the ABV: the label contradicts itself, and it is rejected;
  - otherwise, elsewhere on the label: a reviewer decides, because a number
    away from the statement may be something the reader could not tell apart
    from a proof;
  - above 200, which no proof can be: unreadable, and a reviewer decides;
  - twice the ABV but for one "1" dropped or added ("17" against 117): the
    reader drops and adds that thin figure as it does thin letters inside a
    word, so a reviewer decides. docs/decisions.md#0063.

The worst figure decides. `docs/decisions.md#0050` records why only a proof
beside the ABV may reject.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf
from app.rules.proof import PROOF_CEILING, proofs_in_statement
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition

_AGREES, _REVIEW, _DISAGREES = 0, 1, 2


def _text(value: Decimal) -> str:
    """A figure as a person writes it: 45, not 45.0; 85.6, not 85.60."""
    return format(value.normalize(), "f")


def _entries(payload: Mapping[str, Any], confidence: float) -> list[dict[str, Any]]:
    """The proof figures this reading carries, whichever reader produced it."""
    listed = payload.get("proof")
    if isinstance(listed, list):
        return [dict(e) for e in listed if isinstance(e, Mapping) and e.get("value")]
    statement = payload.get("alc_text")
    if not isinstance(statement, str):
        return []
    return proofs_in_statement(statement, confidence)


def _thin_one_apart(proof: Decimal, twice: Decimal) -> bool:
    """Is one figure the other with a single "1" dropped or added?"""
    shorter, longer = sorted((_text(proof), _text(twice)), key=len)
    if len(longer) != len(shorter) + 1:
        return False
    return any(
        longer[i] == "1" and longer[:i] + longer[i + 1 :] == shorter for i in range(len(longer))
    )


def _judge(proof: Decimal | None, twice: Decimal, beside: bool) -> int:
    if proof is None or proof > PROOF_CEILING:
        return _REVIEW
    if proof == twice:
        return _AGREES
    if _thin_one_apart(proof, twice):
        return _REVIEW
    unit = Decimal(1).scaleb(proof.as_tuple().exponent)  # type: ignore[arg-type]
    if abs(proof - twice) < unit:
        return _REVIEW
    return _DISAGREES if beside else _REVIEW


def _decimal(value: Any) -> Decimal | None:
    try:
        figure = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return figure if figure.is_finite() else None


@register("proof_agreement")
def proof_agreement(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    meta = _build_meta(rule, ctx)
    payload = obs.observed_value if isinstance(obs.observed_value, Mapping) else {}
    entries = _entries(payload, _conf(obs))

    def result(
        outcome: Outcome,
        severity: Severity,
        reason_code: str | None,
        message: str | None = None,
        lean: Literal["pass", "fail"] | None = None,
    ) -> ValidationResult:
        confidences = [_conf(obs), *(float(e.get("confidence", 0.0)) for e in entries)]
        return ValidationResult(
            rule_id=rule.rule_id,
            cfr_citation=rule.cfr_citation,
            beverage_class=obs.beverage_class,
            outcome=outcome,
            severity=severity,
            reason_code=reason_code,
            aggregated_confidence=min(confidences),
            evidence=obs.evidence,
            expected=exp,
            observed=obs,
            engine_meta=meta,
            message=message,
            lean=lean,
        )

    review_code = rule.parameters.get("needs_review_reason_code", rule.reason_code)
    stated = ", ".join(f"{e['value']} proof" for e in entries)

    # A label need not state proof at all.
    if not entries:
        return result(Outcome.NOT_APPLICABLE, rule.severity, None)

    abv = _decimal(payload.get("abv_pct")) if payload.get("abv_pct") is not None else None
    if abv is None:
        declared = exp.abv_labeled_pct
        also = (
            f" The application declares {_text(Decimal(declared))}%, but the proof is "
            f"checked against the label's own figure."
            if declared is not None
            else ""
        )
        return result(
            Outcome.INSUFFICIENT_EVIDENCE,
            Severity.WARN,
            review_code,
            f"The label states {stated}, but its alcohol by volume could not be read to "
            f"compare it with.{also}",
        )

    twice = abv * 2
    worst, worst_entry = _AGREES, entries[0]
    for entry in entries:
        verdict = _judge(_decimal(entry["value"]), twice, bool(entry.get("beside_abv")))
        if verdict > worst:
            worst, worst_entry = verdict, entry

    if worst == _AGREES:
        return result(
            Outcome.PASS,
            rule.severity,
            None,
            f"The label states {stated} and {_text(abv)}%; twice {_text(abv)} is {_text(twice)}.",
        )
    where = "beside" if worst_entry.get("beside_abv") else "elsewhere on the label from"
    message = (
        f"The label states {worst_entry['value']} proof {where} {_text(abv)}%; "
        f"twice {_text(abv)} is {_text(twice)}."
    )
    figure = _decimal(worst_entry["value"])
    if figure is None or figure > PROOF_CEILING:
        message = (
            f"The label reads as {worst_entry['value']} proof, which no proof can be: "
            f"{PROOF_CEILING} is pure alcohol. The figure was probably misread."
        )
    elif _thin_one_apart(figure, twice):
        message += ' The two differ by one "1", which the reader may have misread.'

    if worst == _DISAGREES:
        return result(
            Outcome.FAIL,
            Severity.REJECT,
            rule.parameters.get("disagreement_reason_code", rule.reason_code),
            message,
        )
    # A figure no proof can be, one "1" from twice the ABV, or within its last
    # printed digit is most likely a misread of an agreeing proof. A clear
    # difference printed away from the ABV is still a difference.
    misread = _judge(figure, twice, beside=True) != _DISAGREES
    return result(
        Outcome.INSUFFICIENT_EVIDENCE,
        Severity.WARN,
        review_code,
        message,
        lean="pass" if misread else "fail",
    )
