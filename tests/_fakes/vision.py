from __future__ import annotations

from typing import Sequence

from app.schemas.extracted import FieldObservation
from app.schemas.label import Label


class FakeVisionExtractor:
    """Protocol-compatible VisionExtractor stub. The legibility short-circuit
    is plumbed through ``app.vision.quality.assess`` (monkeypatched in tests),
    NOT through any fake-only attribute."""

    def __init__(self, *, observations: Sequence[FieldObservation] = ()) -> None:
        self._obs = list(observations)

    async def extract(self, label: Label) -> list[FieldObservation]:
        return list(self._obs)

    async def ensure_loaded(self) -> None:
        return None

    async def warm(self) -> None:
        """No models, so nothing to load and nothing to run before a read.

        It is here because ``VisionExtractor`` is runtime-checkable and every
        seam member has to be present for ``isinstance`` to hold; a fake
        missing one stops being a stand-in for the thing it stands in for.
        """
        return None
