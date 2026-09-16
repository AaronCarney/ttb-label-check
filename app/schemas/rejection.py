"""Rule Engine outcome models."""
from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.expected import BeverageClass, ExpectedValue
from app.schemas.extracted import Evidence, FieldObservation


REASON_CODE_GRAMMAR = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*){2,3}$")


class Outcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"
    TIMEOUT = "timeout"
    ERROR = "error"


class Severity(str, Enum):
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
    engine_meta: EngineMeta
