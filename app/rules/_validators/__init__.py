"""Validator registry: string→callable map populated by @register at import time.

Contract:
  - VALIDATOR_REGISTRY is mutable at module-import time only; the loader's
    registry cross-check iterates this dict to validate `RuleDefinition.validator`
    values.
  - @register raises ValueError on duplicate names so accidental shadowing fails
    loud rather than silently replacing a validator.
  - ValidatorContext carries the per-evaluation environment (assets,
    decision tables, engine version, started-at clock) that validators read but
    never mutate. It is a frozen dataclass so validators cannot stash state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.expected import ExpectedValue
    from app.schemas.extracted import FieldObservation
    from app.schemas.rejection import ValidationResult
    from app.schemas.rules import AssetRef, DecisionTable, RuleDefinition


ValidatorFn = Callable[
    ["FieldObservation", "ExpectedValue", "RuleDefinition", "ValidatorContext"],
    "ValidationResult",
]


@dataclass(frozen=True)
class ValidatorContext:
    assets: dict[str, "AssetRef"]
    decision_tables: dict[str, "DecisionTable"]
    started_at_ms: int
    engine_version: str


VALIDATOR_REGISTRY: dict[str, ValidatorFn] = {}


def register(name: str) -> Callable[[ValidatorFn], ValidatorFn]:
    def _decorator(fn: ValidatorFn) -> ValidatorFn:
        if name in VALIDATOR_REGISTRY:
            raise ValueError(f"validator name already registered: {name!r}")
        VALIDATOR_REGISTRY[name] = fn
        return fn

    return _decorator
