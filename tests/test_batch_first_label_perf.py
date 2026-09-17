"""Perf canary for the first label of a batch: P50 ≤ 2.7 s, P99 ≤ 5.0 s, so a
batch's first result lands inside the single-check budget (docs/PRD.md NFR-1).

Method: 12 trials (2 warm-up + 10 measured) × 20 items × 0.1 s of evaluator
latency, about 30 s in total, which is cheap enough to run in CI.

The event count is exact because SSEBus replays on subscribe: a subscriber that
attaches after the worker has already emitted item 0 still sees it, so the
assertion ``lr == n_items`` holds rather than coming up one short.
"""

import statistics
import time
from datetime import UTC

import httpx
import pytest


@pytest.mark.slow
@pytest.mark.asyncio
async def test_first_label_p50_under_2_7s_and_p99_under_5_0s_for_50_item_batch(monkeypatch):
    """First-label latency and event count, measured at the HTTP boundary."""
    from datetime import datetime

    from app.main import create_app
    from app.schemas.wire.batch import BatchEnvelope, BatchItemRef
    from tests.conftest import _fake_evaluator

    N_ITEMS = 20
    LATENCY_S = 0.1
    N_TRIALS = 12  # 2 warmup + 10 measure

    monkeypatch.setattr(
        "app.deps.build_evaluator",
        lambda settings: _fake_evaluator(n_items=N_ITEMS, latency_s=LATENCY_S),
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        samples_s: list[float] = []
        event_counts: list[tuple[int, int]] = []
        for trial in range(N_TRIALS):
            bid = f"B-perf-{trial:03d}"
            envelope = BatchEnvelope(
                batch_id=bid,
                agent_id="a",
                submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
                items=tuple(
                    BatchItemRef(label_ref=f"lbl-{i}", application_ref=f"app-{i:04d}")
                    for i in range(N_ITEMS)
                ),
            ).model_dump(mode="json")
            t0 = time.perf_counter()
            post_resp = await client.post("/batches", json=envelope)
            assert post_resp.status_code == 202, post_resp.text

            first_event_t = None
            lr = se = 0
            async with client.stream("GET", f"/batches/{bid}/stream") as resp:
                assert resp.status_code == 200
                async for line in resp.aiter_lines():
                    if line.startswith("event: label-result"):
                        if first_event_t is None:
                            first_event_t = time.perf_counter() - t0
                        lr += 1
                    elif line.startswith("event: stream-end"):
                        se += 1
                        break
            assert first_event_t is not None
            if trial >= 2:  # drop warmup
                samples_s.append(first_event_t)
            event_counts.append((lr, se))

    # Event count: every trial saw N label-result events and one stream-end.
    for trial_idx, (lr, se) in enumerate(event_counts):
        assert lr == N_ITEMS, f"trial {trial_idx}: expected {N_ITEMS} label-result events, got {lr}"
        assert se == 1, f"trial {trial_idx}: expected exactly 1 stream-end, got {se}"

    p50 = statistics.median(samples_s)
    p99 = max(samples_s)  # 10-sample window — max() is the conservative P99 proxy
    assert p50 <= 2.7, f"P50 {p50:.3f}s exceeds 2.7s budget"
    assert p99 <= 5.0, f"P99 {p99:.3f}s exceeds 5.0s budget"
