"""heading_style_check: the GOVERNMENT WARNING heading's words, capitals and
bold weight, under §16.22(a)(2).

The rule asks three questions of one heading, and this product can answer two
of them from any readable image and the third not at all:

  * the words — read from `heading_text`;
  * the capitals — read from `heading_all_caps`, which the reader computes
    from the heading's own characters;
  * the bold weight — `heading_bold`, a stroke-width measurement taken on the
    heading's own region of the image.

Words or capitals wrong is a rejection: the label is not compliant and the
image was good enough to show it.

**A measured weight never rejects a label.** It used to, when the measurement
was confident. A sweep of the 38-label corpus
(`eval/heading_bold_ratios.py`) showed it cannot carry that: the stroke-width
ratio ran from 0.111 to 0.508 across labels that are all TTB-approved and
therefore all required to be bold, and one label measured 0.111 from a clean
photograph and 0.261 from a blurred copy of the same printing. The number moves
with the photograph, not with the typeface, and at the 0.25 cut it called 18 of
28 approved labels not bold. So a measured weight that does not satisfy the
rule — whether the measurement failed, was never taken, or came back low —
returns insufficient evidence at warn severity under the code the rule declares
in `unmeasured_weight_reason_code`, and the label goes to a reviewer on that
point alone. `docs/decisions.md#0037` carries the argument.

A weight the payload *states* rather than measures is different, and still
rejects: the legacy `heading_styles` sub-object used by hand-built fixtures
asserts a weight as a fact about the label, and a fixture that says its heading
is regular is describing a non-compliant label.

Spacing inside the heading is not a difference: §16.21 fixes the words, and a
label printing "GOVERNMENT  WARNING" or "GOVERNMENT WARNING   :" prints the
mandated heading. A missing space counts too: the reader returns a correctly
printed heading as "GOVERNMENTWARNING" where the gap between the words is
narrow, so the words are compared without their spaces. Trailing punctuation
goes the same way — the regulation sets the statement out as
"GOVERNMENT WARNING: (1) …", so a compliant label carries a colon that the
rule's own target phrase does not.

Both payload shapes are read in one place, into `_HeadingReading`. They used
to be told apart three separate times — once to decide whether the reader had
found the heading at all, once for the capitals and once for the weight — by
three conditions that did not agree with each other, each turning an absent
key into a stated `False` through its own `dict.get` default. That is what let
silence about the weight read as a measured *not bold*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    _conf,
    heading_not_read_result,
    not_read_result,
    unlocated,
    unlocated_is_absent,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition

_WHITESPACE = re.compile(r"\s+")

# The keys the reader writes. Either one present means the payload is the
# reader's own shape and the legacy sub-object is not consulted.
_READER_KEYS = ("heading_all_caps", "heading_bold")


def _heading_phrase(text: str) -> str:
    """The heading's words, with spacing and the punctuation that separates
    the heading from the statement taken out."""
    collapsed = _WHITESPACE.sub(" ", text).strip()
    return collapsed.rstrip(":;.,-–—").strip().upper()


def _case_word(all_caps: bool) -> str:
    """The reader's boolean said as the word a rule pack names."""
    return "upper" if all_caps else "lower"


def _weight_word(bold: bool) -> str:
    """The reader's boolean said as the word a rule pack names."""
    return "bold" if bold else "regular"


@dataclass(frozen=True)
class _HeadingReading:
    """What one payload says about the heading, whichever shape it arrived in.

    `case` and `weight` are the words a rule pack compares against — `upper`,
    `bold` — and are **`None` when the payload does not report them at all**.
    That distinction is why this exists: "the reader says the heading is not
    bold" and "nobody reported a weight" are different answers, and the code
    that read them through three separate `dict.get` defaults could not tell
    them apart.

    `weight_from_measurement` says where the weight came from, which decides
    what it is allowed to do. A stroke-width measurement may send a label to a
    reviewer and may never reject it; a weight a fixture states may reject.

    `weight_confident` is the reader's own report on whether it managed to take
    the measurement at all.

    `styled` says the payload carries a style report of some kind, which means
    the reader found the heading even where it read no characters from it.
    """

    text: str
    case: str | None
    weight: str | None
    weight_from_measurement: bool
    weight_confident: bool
    styled: bool


def _read_payload(payload: dict) -> _HeadingReading:
    """Both payload shapes, read once.

    The reader's shape wins outright where either of its keys is present: a
    payload carrying both shapes is a reader payload that happens to sit
    beside a legacy sub-object, and the measured signal is the better one.
    """
    text = str(payload.get("heading_text") or "")
    styles = payload.get("heading_styles")
    styles = styles if isinstance(styles, dict) else {}

    from_reader = any(key in payload for key in _READER_KEYS)
    if from_reader:
        case = (
            _case_word(bool(payload["heading_all_caps"])) if "heading_all_caps" in payload else None
        )
        weight = _weight_word(bool(payload["heading_bold"])) if "heading_bold" in payload else None
    else:
        case = styles.get("case")
        weight = styles.get("weight")

    return _HeadingReading(
        text=text,
        case=case,
        weight=weight,
        weight_from_measurement=from_reader,
        # A payload that says nothing about the measurement — every hand-built
        # fixture — is taken at its word.
        weight_confident=bool(payload.get("heading_bold_measured_confident", True)),
        styled=bool(styles) or from_reader,
    )


@register("heading_style_check")
def heading_style_check(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    payload = obs.observed_value if isinstance(obs.observed_value, dict) else {}
    reading = _read_payload(payload)

    # The warning's words were read and its heading was not.
    heading_not_read = heading_not_read_result(obs, exp, rule, ctx)
    if heading_not_read is not None:
        return heading_not_read

    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`. A style
    # report with no characters in it still means the heading was found.
    if not reading.styled and unlocated(obs, reading.text) and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx, element="the warning heading")

    target = rule.parameters.get("target_phrase", "GOVERNMENT WARNING")
    required_case = rule.parameters.get("required_case", "upper")
    required_weight = rule.parameters.get("required_weight", "bold")

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
            engine_meta=_build_meta(rule, ctx),
        )

    # The words and the capitals first: both are read from the heading's own
    # text, so a failure here is the label's, not the reader's. The words are
    # compared without their spaces, as `common.warning.verbatim` compares the
    # statement: the engine returns a correctly printed heading as
    # "GOVERNMENTWARNING" where the gap between the words is narrow.
    if _heading_phrase(reading.text).replace(" ", "") != _heading_phrase(target).replace(" ", ""):
        return result(Outcome.FAIL, rule.severity, rule.reason_code)
    if reading.case != required_case:
        return result(Outcome.FAIL, rule.severity, rule.reason_code)

    # A measured weight satisfies the rule only where the reader says it took
    # the measurement. An unconfident measurement reports `is_bold=False`
    # meaning "not measured", and reading that as a compliant bold would be
    # the same mistake in the other direction.
    if reading.weight == required_weight and (
        reading.weight_confident or not reading.weight_from_measurement
    ):
        return result(Outcome.PASS, rule.severity, None)

    # Nothing here may reject the label unless the payload *stated* a weight.
    # The rule pack names the code this branch reports; without one there is no
    # sentence to hand a reviewer, so the check falls through to the weight the
    # payload carries rather than reporting a needs-review with no reason.
    if reading.weight is None or reading.weight_from_measurement:
        unmeasured_code = rule.parameters.get("unmeasured_weight_reason_code")
        if unmeasured_code:
            return result(Outcome.INSUFFICIENT_EVIDENCE, Severity.WARN, unmeasured_code)

    return result(Outcome.FAIL, rule.severity, rule.reason_code)
