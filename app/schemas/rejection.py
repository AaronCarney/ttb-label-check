"""Rule Engine outcome models."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.expected import BeverageClass, ExpectedValue
from app.schemas.extracted import Evidence, FieldObservation

# `\Z` rather than `$`: in Python `$` also matches immediately before a trailing
# newline, so `"WARNING.PRESENCE.MISSING\n"` passed this gate. An accepted code is
# used as a key into `rules/reason_codes.yaml` (`app/rules/yaml_engine.py`) and is
# written into the envelope and into the audit hash, so a code carrying a
# character nobody can see is looked up by a name nobody wrote.
REASON_CODE_GRAMMAR = re.compile(r"\A[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*){2,3}\Z")


class Outcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"
    TIMEOUT = "timeout"
    ERROR = "error"


class Severity(StrEnum):
    REJECT = "reject"
    WARN = "warn"
    INFO = "info"


class ReasonCode:
    """Reason-code grammar validator. The runtime type is `str`; we keep the
    validator as a static helper so YAML-loaded codes can be sanity-checked
    by the RuleLoader and at construction sites.

    Grammar: ``BIN.SUB.SPECIFIC[.QUALIFIER]``.
    """

    @staticmethod
    def validate_grammar(value: str) -> str:
        if not isinstance(value, str) or not REASON_CODE_GRAMMAR.match(value):
            raise ValueError(f"reason_code does not match grammar: {value!r}")
        return value


class EngineMeta(BaseModel):
    """Per-rule engine metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engine_version: str
    rule_pack_version: str
    rule_pack: str
    started_at_ms: int
    elapsed_ms: int


class ValidationResult(BaseModel):
    """Single, immutable outcome of evaluating one rule on one application + one label.

    ``aggregated_confidence`` is the **min** over evidence confidences, computed
    at construction by the engine: a result is only as good as its weakest
    piece of evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    cfr_citation: str
    beverage_class: BeverageClass
    outcome: Outcome
    severity: Severity
    reason_code: str | None = None
    aggregated_confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[Evidence, ...] = ()
    expected: ExpectedValue | None = None
    observed: FieldObservation | None = None
    message: str | None = None
    # The admissible value this rule actually matched, when that was not the
    # one `expected.value` holds. An application declares more than one name a
    # label may carry - a brand, a fanciful name, trade names it told TTB it
    # prints - and a rule that passes on one of the others leaves a result page
    # showing a label reading that differs from the expected value beside a
    # pass. Naming it here is what lets the page say which one was matched.
    matched_value: str | None = None
    # Which way a result the rule could not settle leans: the answer a reviewer
    # is shown pre-filled, to confirm or correct. None leaves it to the reason
    # code's registered lean (`rules/reason_codes.yaml`), set by the engine.
    # A validator sets it only where its own evidence points one way while its
    # reason code covers both, such as a proof one "1" from twice the ABV.
    lean: Literal["pass", "fail"] | None = None
    engine_meta: EngineMeta
