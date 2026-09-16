from __future__ import annotations

from typing import Sequence

from app.rules._validators import ValidatorContext
from app.rules.engine import RuleEngine
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import ValidationResult


class FakeRuleEngine(RuleEngine):
    def __init__(self, *, results: tuple[ValidationResult, ...] = ()) -> None:
        self._results = results

    async def evaluate(
        self,
        observations: Sequence[FieldObservation],
        expected: Sequence[ExpectedValue],
        context,  # type: ignore[no-untyped-def]
    ) -> tuple[ValidationResult, ...]:
        return self._results

    def build_validator_context(self, *, started_at_ms: int) -> ValidatorContext:
        # Stub: empty assets/tables + placeholder engine_version. Sufficient
        # for any test that doesn't exercise asset-driven validators.
        return ValidatorContext(
            assets={},
            decision_tables={},
            started_at_ms=started_at_ms,
            engine_version="fake",
        )
