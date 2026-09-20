"""End-to-end canary: a 5-item batch with a fake evaluator over a real SSE
response. Drains the events and asserts five per-label events, a stream-end,
no advisories, and that the connection closes.

The batch is started through `POST /`, the form, not the JSON `POST /batches`.
That is the whole point of the canary: the form is the route that carries the
label images, and since `docs/decisions.md#0020` an item with no image is
refused by name without ever reaching the evaluator. Run over the JSON route
these tests would still be green and would be checking nothing — five refusals
in place of five evaluations. The JSON route's own behaviour is covered in
`tests/test_batch_endpoint_post.py`.
"""

import asyncio

import httpx
import pytest

# A tiny valid PNG. The upload route reads an upload's own first bytes to
# decide its media type, so the file has to really be a PNG; the evaluator is
# a fake and never looks at it.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)


def _five_png_files() -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("labels", (f"label-{i}.png", _PNG_1x1, "image/png")) for i in range(5)]


@pytest.mark.asyncio
async def test_5_item_batch_end_to_end_via_real_sse_response():
    from app.api.ui import _get_upload_evaluator
    from app.main import create_app
    from tests.conftest import _fake_evaluator

    app = create_app()
    app.dependency_overrides[_get_upload_evaluator] = lambda: _fake_evaluator(
        n_items=5, latency_s=0.3
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        upload_resp = await client.post("/", files=_five_png_files())
        assert upload_resp.status_code == 303, upload_resp.text
        batch_id = upload_resp.headers["location"].removeprefix("/batch/")

        events: list[str] = []
        async with client.stream("GET", f"/batches/{batch_id}/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
                if "stream-end" in line:
                    break

        assert events.count("label-result") == 5
        assert events.count("anomaly-advisory") == 0  # no anomaly with 5 distinct
        assert events.count("stream-end") == 1
        assert events[-1] == "stream-end"

    # The evaluator really ran: nothing was refused for want of an image.
    in_flight = app.state.batches[batch_id]
    assert in_flight.failures == {}
    assert len(in_flight.results) == 5


@pytest.mark.asyncio
async def test_5_item_batch_with_mid_batch_override_continues_to_completion():
    """An override applied mid-batch does not stop the worker."""
    from app.api.ui import _get_upload_evaluator
    from app.main import create_app
    from tests.conftest import _fake_evaluator, _stub_disposition_envelope

    plan = [(0.1, _stub_disposition_envelope(i, disposition="needs_review")) for i in range(5)]
    app = create_app()
    app.dependency_overrides[_get_upload_evaluator] = lambda: _fake_evaluator(plan=plan)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        upload_resp = await client.post("/", files=_five_png_files())
        assert upload_resp.status_code == 303, upload_resp.text
        batch_id = upload_resp.headers["location"].removeprefix("/batch/")

        events: list[dict] = []

        async def _drain():
            async with client.stream("GET", f"/batches/{batch_id}/stream") as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        events.append({"event": line.split(":", 1)[1].strip()})
                    if "stream-end" in line:
                        break

        # Run draining + override concurrently
        drain_task = asyncio.create_task(_drain())
        await asyncio.sleep(0.15)  # let item 0 land

        override_resp = await client.post(
            "/labels/EV-0000/overrides",
            json={
                "reason_code": "BRAND.NAME.NEEDS_REVIEW",
                "applied_disposition": "pass",
                "justification_text": "Mid-batch override",
            },
        )
        assert override_resp.status_code == 200, override_resp.text

        await asyncio.wait_for(drain_task, timeout=5.0)

    label_count = sum(1 for e in events if e["event"] == "label-result")
    end_count = sum(1 for e in events if e["event"] == "stream-end")
    override_count = sum(1 for e in events if e["event"] == "override-applied")
    assert label_count == 5  # all items processed despite mid-batch override
    assert end_count == 1
    assert override_count == 1
