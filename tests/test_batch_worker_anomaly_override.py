"""BatchWorker — anomaly broadcast, staying alive through an override, and
completion semantics: stream-end fires once, after the last per-label event."""
import asyncio
from datetime import UTC, datetime

import pytest

from app.api._sse_bus import SSEBus
from app.batch.anomaly import AnomalyDetector
from app.batch.state import InFlightBatch
from app.batch.worker import BatchWorker
from app.schemas.audit import AuditRecord, OverrideEntry, PerRuleTraceEntry
from app.schemas.batch import BatchItem, ItemState
from app.schemas.label import Label
from app.schemas.metrics import Metrics
from app.schemas.wire.disposition import ConfidenceBand, DispositionEnvelope
from tests.conftest import _fake_evaluator

# A tiny valid PNG. The fake evaluators here never read the bytes, but the
# worker refuses any item it has no image for (`docs/decisions.md#0020`), and a
# refused item never reaches the evaluator — so without this the planned
# reason codes below would never be observed at all.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)


def _stub_item(idx: int) -> BatchItem:
    return BatchItem(
        label_id=f"lbl-{idx}",
        application_ref=f"app-{idx:04d}",
        state=ItemState.QUEUED,
        result=None,
        enqueued_at=datetime(2026, 5, 4, 12, 0, idx, tzinfo=UTC),
    )


def _label_lookup_for(items, batch_id: str) -> dict[str, Label]:
    """An image for every queued item, as the bulk-upload route supplies."""
    return {
        item.label_id: Label(
            label_id=item.label_id,
            batch_id=batch_id,
            image_bytes=_PNG_1x1,
            content_type="image/png",
            face_tag="front",
        )
        for item in items
    }


async def _drain_until_stream_end(sub: asyncio.Queue, *, timeout: float = 5.0) -> list[dict]:
    """Read events as they are broadcast, stopping at `stream-end`.

    Reading concurrently with the worker is required, not tidier: the consumer
    holds the next evaluation while the slowest attached subscriber is more
    than `lookahead_k` events behind (`docs/decisions.md#0021`), so a test that
    subscribes and then waits for `run()` to finish deadlocks by design."""
    events: list[dict] = []
    while True:
        evt = await asyncio.wait_for(sub.get(), timeout=timeout)
        events.append(evt)
        if evt["event"] == "stream-end":
            return events


def _envelope_with_reason_code(idx: int, code: str) -> DispositionEnvelope:
    """DispositionEnvelope whose first FieldFindingWire's first RuleFindingWire
    carries the given reason_code, so `_headline_reason_code` returns it via
    the per-field path (the primary, non-short-circuit case)."""
    from app.schemas.wire.disposition import (
        AISuggestionWire,
        FieldEvidenceWire,
        FieldFindingWire,
        RuleFindingWire,
    )

    now = datetime.now(UTC)
    finding = RuleFindingWire(
        rule_id="R-001",
        cfr_citation="27 CFR §4.33",
        disposition="needs_review",
        reason_code=code,
        plain_language_explanation="Synthetic for batch test.",
    )
    field = FieldFindingWire(
        field_name="brand_name",
        extracted_value="x",
        expected_value="x",
        evidence=FieldEvidenceWire(
            bbox=(0, 0, 1, 1),
            crop_ref="ev/R-001",
            extraction_confidence=0.9,
        ),
        rule_findings=(finding,),
        ai_suggestion=AISuggestionWire(present=False),
        field_confidence=ConfidenceBand(band="medium", numeric=0.7),
    )
    return DispositionEnvelope(
        evaluation_id=f"EV-{idx:04d}",
        label_ref=f"lbl-{idx:04d}",
        disposition="needs_review",
        disposition_confidence=ConfidenceBand(band="medium", numeric=0.7),
        fields=(field,),
        audit_trail=AuditRecord(
            evaluation_id=f"EV-{idx:04d}",
            rule_set_version="t",
            input_hash="0" * 64,
            output_hash="0" * 64,
            started_at=now,
            completed_at=now,
            per_rule_trace=(
                PerRuleTraceEntry(
                    rule_id="R-001",
                    disposition="needs_review",
                    evidence_ref="ev/R-001",
                ),
            ),
        ),
        metrics=Metrics(
            total_duration_ms=10,
            per_rule_durations_ms=(),
            vision_duration_ms=5,
        ),
    )


def _short_circuit_envelope_with_reason_code(idx: int, code: str) -> DispositionEnvelope:
    """Short-circuit envelope (no fields) — `_headline_reason_code` falls back
    to `per_rule_trace[0].rule_id`, which carries the reason code on the
    envelopes the evaluator short-circuits."""
    now = datetime.now(UTC)
    return DispositionEnvelope(
        evaluation_id=f"EV-{idx:04d}",
        label_ref=f"lbl-{idx:04d}",
        disposition="needs_review",
        disposition_confidence=ConfidenceBand(band="low", numeric=0.0),
        fields=(),
        audit_trail=AuditRecord(
            evaluation_id=f"EV-{idx:04d}",
            rule_set_version="t",
            input_hash="0" * 64,
            output_hash="0" * 64,
            started_at=now,
            completed_at=now,
            per_rule_trace=(
                PerRuleTraceEntry(
                    rule_id=code,  # short-circuit convention: rule_id IS the reason code
                    disposition="needs_review",
                    evidence_ref="",
                ),
            ),
        ),
        metrics=Metrics(
            total_duration_ms=10,
            per_rule_durations_ms=(),
            vision_duration_ms=5,
        ),
    )


@pytest.mark.asyncio
async def test_worker_emits_anomaly_advisory_on_5_of_10_same_reason_code():
    """Five of the last ten observations sharing a reason code fire an advisory."""
    # 10 items, all returning needs_review with same reason_code
    items = tuple(_stub_item(i) for i in range(10))
    in_flight = InFlightBatch(
        batch_id="B-AN1", agent_id="a", items=items, lookahead_k=3,
    )
    plan = [(0.0, _envelope_with_reason_code(i, "BRAND.NAME.MISMATCH")) for i in range(10)]
    fake_eval = _fake_evaluator(plan=plan)
    bus = SSEBus()
    sub = bus.subscribe()
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=fake_eval,
        anomaly=AnomalyDetector(window_n=10, threshold_m=5),
        bus=bus,
        label_lookup=_label_lookup_for(items, "B-AN1"),
    )

    # Read while the worker runs. Ten items and k=3 means an attached
    # subscriber that does not read stops the batch at the fourth event, which
    # is the demand gate doing its job rather than a fault.
    run_task = asyncio.create_task(worker.run())
    events = await _drain_until_stream_end(sub)
    await asyncio.wait_for(run_task, timeout=1.0)

    # Expected event types: 10 label-result + 1 anomaly-advisory + 1 stream-end
    types = [e["event"] for e in events]
    assert types.count("label-result") == 10
    assert types.count("anomaly-advisory") == 1
    assert types.count("stream-end") == 1
    # The advisory must come BEFORE stream-end (in order)
    advisory_idx = types.index("anomaly-advisory")
    stream_end_idx = types.index("stream-end")
    assert advisory_idx < stream_end_idx


@pytest.mark.asyncio
async def test_worker_does_not_inspect_audit_trail_overrides():
    """Negative control: the worker never reads overrides off the audit trail.
    Matches the `audit_trail.overrides` member chain rather than the bare word
    `overrides`, which appears in docstrings and in the conftest helper."""
    import re
    from pathlib import Path
    src = Path("app/batch/worker.py").read_text()
    hits = re.findall(r"\.audit_trail\s*\.\s*overrides", src)
    assert hits == [], (
        f"BatchWorker must not access audit_trail.overrides "
        f"(found {len(hits)} occurrences)."
    )


@pytest.mark.asyncio
async def test_worker_continues_after_in_flight_results_mutation_simulating_override():
    """When the override endpoint mutates
    `in_flight.results[label_id]` mid-batch, the worker keeps going."""
    items = tuple(_stub_item(i) for i in range(3))
    in_flight = InFlightBatch(
        batch_id="B-OV1", agent_id="a", items=items, lookahead_k=3,
    )
    fake_eval = _fake_evaluator(n_items=3, latency_s=0.05)
    bus = SSEBus()
    sub = bus.subscribe()
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=fake_eval,
        anomaly=AnomalyDetector(),
        bus=bus,
        label_lookup=_label_lookup_for(items, "B-OV1"),
    )

    run_task = asyncio.create_task(worker.run())

    # After item 0 lands, simulate an override mutation
    e0 = await asyncio.wait_for(sub.get(), timeout=1.0)
    assert e0["data"]["queue_position"] == 0

    # Mutate in_flight.results[lbl-0] — simulating the override endpoint
    from datetime import datetime

    original = in_flight.results["lbl-0"]
    new_audit = original.audit_trail.model_copy(update={
        "overrides": (
            OverrideEntry(
                field_name=None,
                original_disposition=original.disposition,
                applied_disposition="pass",
                reason_code="BRAND.NAME.NEEDS_REVIEW",
                justification_text="Test override",
                reviewer_id="session-test1234",
                timestamp=datetime.now(UTC),
            ),
        ),
    })
    in_flight.results["lbl-0"] = original.model_copy(update={"audit_trail": new_audit})

    # Worker must continue and emit events 1, 2, then stream-end
    e1 = await asyncio.wait_for(sub.get(), timeout=1.0)
    e2 = await asyncio.wait_for(sub.get(), timeout=1.0)
    end_evt = await asyncio.wait_for(sub.get(), timeout=1.0)

    assert e1["data"]["queue_position"] == 1
    assert e2["data"]["queue_position"] == 2
    assert end_evt["event"] == "stream-end"
    await run_task


@pytest.mark.asyncio
async def test_worker_emits_stream_end_exactly_once_after_last_label_result():
    items = tuple(_stub_item(i) for i in range(3))
    in_flight = InFlightBatch(
        batch_id="B-CC1", agent_id="a", items=items, lookahead_k=3,
    )
    fake_eval = _fake_evaluator(n_items=3, latency_s=0.0)
    bus = SSEBus()
    sub = bus.subscribe()
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=fake_eval,
        anomaly=AnomalyDetector(),
        bus=bus,
        label_lookup=_label_lookup_for(items, "B-CC1"),
    )

    # Three items and k=3 sits exactly on the demand gate's boundary, so this
    # would pass without draining concurrently — until someone adds a fourth
    # item and the test hangs instead of failing. Read as it runs.
    run_task = asyncio.create_task(worker.run())
    events = await _drain_until_stream_end(sub)
    await asyncio.wait_for(run_task, timeout=1.0)

    types = [e["event"] for e in events]
    assert types == ["label-result", "label-result", "label-result", "stream-end"]
