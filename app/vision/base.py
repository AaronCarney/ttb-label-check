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

    @property
    def reader_version(self) -> str:
        """What read the label, in a form the audit trail can record.

        `AuditRecord.model_version` is the half of the compliance record that
        names the reader, and originally nothing in `app/` ever set it,
        so every envelope the service served said the reader was unknown. A
        producer contesting a rejection is contesting a reading, and a record
        that cannot name the reader cannot answer them.

        It belongs on the seam rather than on one reader, because the point of
        the seam is that either implementation can be behind it: a version only
        the local reader could report would go quiet the moment the hosted one
        was selected, which is exactly when knowing would matter most.

        The shape is `<seam>:<what>` — `local:rapidocr@3.9.2`,
        `cloud:gpt-4o-2024-08-06` — so a record says which of the two read it
        as well as which version did.
        """
        ...

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
