from __future__ import annotations

from typing import Sequence

from app.orchestrator.base import Orchestrator
from app.schemas.application import Application
from app.schemas.extracted import FieldObservation
from app.schemas.refined import Refined
from app.schemas.rejection import ValidationResult


class FakeOrchestrator(Orchestrator):
    def __init__(self, *, refined_outputs: Sequence[Refined] = (), raise_on_call: int | None = None) -> None:
        self._outputs = list(refined_outputs)
        self._raise_on = raise_on_call
        self.call_count = 0

    async def ensure_client(self) -> None:
        return None

    async def refine(
        self,
        application: Application,
        observations: list[FieldObservation],
        validation_results: list[ValidationResult],
    ) -> Refined:
        self.call_count += 1
        if self._raise_on is not None and self.call_count == self._raise_on:
            raise RuntimeError("fake orchestrator scheduled failure")
        if not self._outputs:
            return Refined(evaluation_id=getattr(application, "evaluation_id", "EV-fake"))
        return self._outputs.pop(0)
