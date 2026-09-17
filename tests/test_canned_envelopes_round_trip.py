"""Every canned envelope JSON deserializes to the schema it is pinned to.

The UI tests are built on these fixtures. If the engine starts producing
envelopes whose shape diverges from them, that is a wire-contract break to be
settled deliberately — not something to paper over by reworking the fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.wire.batch import BatchEnvelope
from app.schemas.wire.disposition import DispositionEnvelope

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "envelopes"
SINGLE_DIR = FIXTURE_ROOT / "single"
BATCH_DIR = FIXTURE_ROOT / "batch"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "01-spirits-clean.json",
        "02-bourbon-stones-throw.json",
        "03-warning-title-case.json",
        "04-low-res-blurry.json",
        "06-abv-application-disagreement.json",
        "07-borderline-confidence.json",
    ],
)
def test_single_envelope_round_trip(fixture_name: str) -> None:
    payload = json.loads((SINGLE_DIR / fixture_name).read_text())
    envelope = DispositionEnvelope.model_validate(payload)
    # Round-trip: serialize back to dict and assert no drift on a sentinel field.
    assert envelope.evaluation_id == payload["evaluation_id"]
    assert envelope.disposition == payload["disposition"]


def test_batch_envelope_round_trip() -> None:
    payload = json.loads((BATCH_DIR / "05-batch-of-50-envelope.json").read_text())
    envelope = BatchEnvelope.model_validate(payload)
    assert envelope.batch_id == payload["batch_id"]
    assert len(envelope.items) == len(payload["items"])


def test_sse_events_each_round_trip() -> None:
    """Each line of the SSE event sequence is a valid §6.2 envelope augmented
    with batch_id + queue_position. We strip those two fields and assert the
    remainder satisfies DispositionEnvelope (extra='forbid' would block the
    naive shape; we therefore validate via model_construct_then_assert)."""
    lines = (BATCH_DIR / "05-batch-of-50-events.jsonl").read_text().splitlines()
    assert len(lines) == 5
    for line in lines:
        payload = json.loads(line)
        # SSE-augmented fields — strip before round-trip.
        assert isinstance(payload.pop("batch_id"), str)
        assert isinstance(payload.pop("queue_position"), int)
        envelope = DispositionEnvelope.model_validate(payload)
        assert envelope.disposition in {"pass", "fail", "needs_review"}
