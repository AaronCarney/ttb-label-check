"""RuleEngine ABC: one async method, ``evaluate``.

Return type is `tuple[ValidationResult, ...]` rather than a list, so results are
immutable end to end, matching the frozen RuleSet the loader builds. Do NOT
relax this signature back to a list without checking every caller that relies on
not being able to mutate what it is handed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.rules._validators import ValidatorContext
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import ValidationResult


class RuleEngine(ABC):
    @property
    @abstractmethod
    def rule_set_version(self) -> str:
        """What this engine would check a label against, as one string.

        Two things read it, and both break when it is approximate:

        * the audit trail names it, so a reviewer can say which rules produced
          a verdict — the one fact about an evaluation that cannot be
          reconstructed afterwards from the answer;
        * the result cache keys on it, so an answer produced under one set of
          rules is never handed back after the rules have changed.

        It must therefore change whenever the answer this engine would give
        could change. A hand-maintained version number alone does not satisfy
        that — nobody bumps it for a threshold edit — so an implementation is
        expected to bind the declared version to the content it actually
        loaded.
        """
        ...

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
