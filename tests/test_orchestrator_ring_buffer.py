import json
from collections import deque
from pathlib import Path

import httpx
import pytest
import respx
from httpx import Response

from app.config import Settings
from app.orchestrator.openai_strict import OpenAIStrictOrchestrator
from app.schemas.application import Application

REC_DIR = Path("tests/recordings/openai/gpt-4o-2024-08-06/v1/orchestrator")


def _stub_app():
    return Application(application_id="A-001", evaluation_id="EV-001")


@pytest.mark.asyncio
async def test_successful_refine_writes_3_call_records():
    settings = Settings()
    ring: deque = deque(maxlen=200)
    orch = OpenAIStrictOrchestrator(settings=settings, ring_buffer=ring, api_key="sk-test")
    with respx.mock(base_url="https://api.openai.com") as router:
        payloads_by_task = {
            task: json.loads((REC_DIR / task / "01-spirits-clean.json").read_text())
            for task in ("brand_disambig", "reasoning_enrich", "ocr_reconcile")
        }

        def _dispatch(request):
            body = json.loads(request.content)
            name = body.get("response_format", {}).get("json_schema", {}).get("name")
            return Response(200, json=payloads_by_task[name])

        router.post("/v1/chat/completions").mock(side_effect=_dispatch)
        await orch.refine(_stub_app(), [], [])
    assert len(ring) == 3
    assert {r.stage for r in ring} == {"orch.brand_disambig", "orch.reasoning_enrich", "orch.ocr_reconcile"}
    assert all(r.provider == "openai" for r in ring)
    assert all(r.model == "gpt-4o-2024-08-06" for r in ring)
    assert all(r.prompt_version == "v1" for r in ring)
    assert all(len(r.output_hash) == 16 for r in ring)


@pytest.mark.asyncio
async def test_failed_refine_writes_1_call_record_per_failed_task():
    settings = Settings()
    ring: deque = deque(maxlen=200)
    orch = OpenAIStrictOrchestrator(settings=settings, ring_buffer=ring, api_key="sk-test")
    with respx.mock(base_url="https://api.openai.com") as router:
        router.post("/v1/chat/completions").mock(side_effect=httpx.ConnectError("boom"))
        await orch.refine(_stub_app(), [], [])
    assert len(ring) == 3  # one per failed task
    assert all(r.response.get("error") == "ENGINE.MODEL.UNAVAILABLE" for r in ring)


def test_ring_buffer_maxlen_honored():
    ring: deque = deque(maxlen=200)
    for i in range(250):
        ring.append(i)
    assert len(ring) == 200
    assert ring[0] == 50
