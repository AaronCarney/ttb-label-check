"""RuleEngine ABC: one async method, ``evaluate``.

Return type is `tuple[ValidationResult, ...]` rather than a list, so results are
immutable end to end, matching the frozen RuleSet the loader builds. Do NOT
relax this signature back to a list without checking every caller that relies on
not being able to mutate what it is handed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from app.rules._validators import ValidatorContext
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import ValidationResult


class RuleEngine(ABC):
    @abstractmethod
    async def evaluate(
        self,
        observations: Sequence[FieldObservation],
        expected: Sequence[ExpectedValue],
        context: ValidatorContext,
    ) -> tuple[ValidationResult, ...]: ...

    @abstractmethod
    def build_validator_context(self, *, started_at_ms: int) -> ValidatorContext:
        """Construct a per-evaluation ``ValidatorContext`` for this engine.

        Each subclass sources ``assets``, ``decision_tables``, and
        ``engine_version`` from whatever it has on hand; the caller (the
        Evaluator) supplies the per-evaluation wall-clock reference. Pulling
        construction onto the abstraction means tests (FakeRuleEngine) can
        return a stub without reaching into private state.
        """
        ...
