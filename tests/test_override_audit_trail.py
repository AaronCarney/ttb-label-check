"""Every field of an override lands on the persisted audit_trail."""
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import create_app


def test_override_lands_on_in_flight_results_audit_trail_overrides_tuple():
    from app.api._sse_bus import SSEBus
    from app.batch.state import InFlightBatch
    from app.schemas.batch import BatchItem, ItemState
    from tests.conftest import _stub_disposition_envelope

    app = create_app()
    app.state.batches = {}
    item = BatchItem(
        label_id="lbl-0",
        application_ref="app-0000",
        state=ItemState.QUEUED,
        result=None,
        enqueued_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
    )
    env = _stub_disposition_envelope(0, disposition="needs_review")
    in_flight = InFlightBatch(batch_id="B-OV2", agent_id="a", items=(item,), lookahead_k=3)
    in_flight.results["lbl-0"] = env
    app.state.batches["B-OV2"] = in_flight
    if not hasattr(app.state, "buses"):
        app.state.buses = {}
    app.state.buses["B-OV2"] = SSEBus()

    client = TestClient(app)
    payload = {
        "reason_code": "BRAND.NAME.NEEDS_REVIEW",
        "applied_disposition": "pass",
        "justification_text": "Manual review approved.",
    }
    resp = client.post(f"/labels/{env.evaluation_id}/overrides", json=payload)
    assert resp.status_code == 200

    # In-flight result must now carry the override
    persisted = in_flight.results["lbl-0"]
    overrides = persisted.audit_trail.overrides
    assert len(overrides) == 1
    o = overrides[0]
    assert o.field_name is None  # whole-envelope override
    assert o.original_disposition == "needs_review"
    assert o.applied_disposition == "pass"
    assert o.reason_code == "BRAND.NAME.NEEDS_REVIEW"
    assert o.justification_text == "Manual review approved."
    assert o.reviewer_id.startswith("session-")
    assert isinstance(o.timestamp, datetime)
