"""Nothing about a submission outlives the process: app.state.batches is
evicted on lifespan teardown."""
from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_lifespan_teardown_clears_app_state_batches():
    from app.main import create_app
    from app.batch.state import InFlightBatch
    from app.api._sse_bus import SSEBus
    from app.schemas.batch import BatchItem, ItemState

    app = create_app()
    # Manually trigger lifespan startup
    async with app.router.lifespan_context(app):
        item = BatchItem(
            label_id="lbl-0",
            application_ref="app-0000",
            state=ItemState.QUEUED,
            result=None,
            enqueued_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
        )
        in_flight = InFlightBatch(batch_id="B-EV", agent_id="a", items=(item,), lookahead_k=3)
        app.state.batches["B-EV"] = in_flight
        app.state.buses["B-EV"] = SSEBus()
        assert app.state.batches  # populated during lifespan-active
        assert app.state.buses

    # Lifespan exited — both registries should be cleared
    assert app.state.batches == {}
    assert app.state.buses == {}
