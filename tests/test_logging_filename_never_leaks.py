"""A filename an uploader chose must not reach the logs.

`label_id` is built from the name of the file the reviewer dropped in, so a
file named after a person names that person. The allow-list and the redaction
filter are not enough on their own: the message string is outside both, and
`evaluation_id` is inside the allow-list, so an id derived from the filename
is emitted by design. This runs the real worker through both the refusal path
and the ordinary path and reads everything the real handler emits.
"""

from __future__ import annotations

import asyncio
import io
import logging
from datetime import UTC, datetime

import pytest

from app.api._sse_bus import SSEBus
from app.batch.anomaly import AnomalyDetector
from app.batch.state import InFlightBatch
from app.batch.worker import BatchWorker
from app.logging.otel_genai import OtelGenAIFormatter
from app.logging.redaction import RedactionFilter
from app.schemas.batch import BatchItem, ItemState
from app.schemas.label import Face, Label
from tests.conftest import _fake_evaluator

# The name a person would be identified by, as a filename an uploader picked.
_PERSON = "Jane-Doe-Medical-Release"

_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)


class _Captured:
    """The real formatter and filter, writing where the test can read them."""

    def __init__(self) -> None:
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(OtelGenAIFormatter())
        self.handler.addFilter(RedactionFilter())
        self.handler.setLevel(logging.DEBUG)

    def __enter__(self) -> _Captured:
        self.root = logging.getLogger()
        self.prior_level = self.root.level
        self.root.addHandler(self.handler)
        self.root.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc) -> None:
        self.root.removeHandler(self.handler)
        self.root.setLevel(self.prior_level)

    @property
    def text(self) -> str:
        self.handler.flush()
        return self.stream.getvalue()


def _items(batch_id: str) -> tuple[BatchItem, ...]:
    """Two items whose label_ids carry the uploader's filename, as
    `app/api/ui/bulk_upload.py` builds them: one refused, one checked."""
    return tuple(
        BatchItem(
            label_id=f"{batch_id}-{idx:03d}-{_PERSON}.{ext}",
            application_ref=f"{batch_id}-app-{idx:03d}",
            state=ItemState.QUEUED,
            result=None,
            enqueued_at=datetime(2026, 9, 16, 12, 0, idx, tzinfo=UTC),
        )
        for idx, ext in enumerate(("txt", "png"))
    )


@pytest.mark.asyncio
async def test_no_log_line_carries_the_uploaders_filename() -> None:
    batch_id = "B-abc123"
    items = _items(batch_id)
    refused, checked = items
    in_flight = InFlightBatch(batch_id=batch_id, agent_id="a", items=items, lookahead_k=3)
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=_fake_evaluator(n_items=1, latency_s=0.0),
        anomaly=AnomalyDetector(),
        bus=SSEBus(),
        label_lookup={
            checked.label_id: Label(
                label_id=checked.label_id,
                batch_id=batch_id,
                faces=(
                    Face(
                        image_bytes=_PNG_1x1,
                        content_type="image/png",
                        face_tag="front",
                    ),
                ),
            )
        },
        # What the upload route declares for a file that is not an image. The
        # sentence names the file on purpose: the reviewer needs to know which
        # one. It must still not be logged.
        refusals={
            refused.label_id: (
                "ENGINE.INPUT.UNSUPPORTED_IMAGE",
                f"{_PERSON}.txt is not a PNG or JPEG image, so it was not read.",
            )
        },
    )

    with _Captured() as cap:
        await asyncio.wait_for(worker.run(), timeout=5.0)
        emitted = cap.text

    assert emitted.strip(), "the worker emitted no log lines, so this proves nothing"
    assert _PERSON not in emitted, "the uploader's filename reached the logs:\n" + "\n".join(
        line for line in emitted.splitlines() if _PERSON in line
    )
    # The reviewer is still told which file it was — that path is untouched.
    assert _PERSON in in_flight.failures[refused.label_id]
