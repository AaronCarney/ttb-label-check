"""FakeEvaluator — minimal protocol-compatible double for ``Evaluator``.

Carries a sequence of ``(latency_seconds, envelope)`` tuples consumed in
submission order. Used by every batch-worker test that needs deterministic
per-call latency and canned envelopes."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable

from app.schemas.application import Application
from app.schemas.label import Label
from app.schemas.wire.disposition import DispositionEnvelope


class FakeEvaluator:
    """Test double for ``app.services.evaluator.Evaluator``."""

    def __init__(self, plan: Iterable[tuple[float, DispositionEnvelope]]) -> None:
        self._plan = list(plan)
        self._calls = 0

    async def evaluate(self, application: Application, label: Label) -> DispositionEnvelope:
        if self._calls >= len(self._plan):
            raise AssertionError(
                f"FakeEvaluator depleted after {self._calls} calls "
                f"(plan length {len(self._plan)})"
            )
        latency_s, envelope = self._plan[self._calls]
        self._calls += 1
        if latency_s > 0:
            await asyncio.sleep(latency_s)
        return envelope

    @property
    def call_count(self) -> int:
        return self._calls
