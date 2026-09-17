"""VisionExtractor Protocol + sub-runner shape declarations.

The Protocol is runtime_checkable so substitutability
tests can assert isinstance() without instantiating the heavy sub-runners.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.extracted import FieldObservation
from app.schemas.label import Label


@runtime_checkable
class VisionExtractor(Protocol):
    """The reader seam. Two concrete impls: cloud + local (docs/decisions.md#0005)."""

    async def extract(self, label: Label) -> list[FieldObservation]: ...

    async def ensure_loaded(self) -> None:
        """Warm-up hook. Cloud impl: no-op. Local impl: load model weights."""
        ...

    async def warm(self) -> None:
        """Pay everything a first read would, before a first read arrives.

        Loading is not the whole of it. The local reader's models are built by
        ``ensure_loaded``, but onnxruntime optimizes each graph and allocates
        its arenas on the first *inference*, so a reader whose models are
        loaded still makes the first label wait. Whoever submits first pays it,
        and on a service that scales to zero that is a reviewer's first click.

        Separate from ``ensure_loaded`` because the two answer different
        questions. ``ensure_loaded`` is readiness: it either works or the
        process cannot read labels at all. ``warm`` is cost: it either happens
        early or it happens to somebody. A caller that must know the reader
        works awaits ``ensure_loaded``; a caller with time to spare before
        traffic arrives awaits this.
        """
        ...
