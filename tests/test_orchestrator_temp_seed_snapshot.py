"""Determinism canary: every recorded request body must carry temperature=0, a
fixed seed, and a pinned model snapshot. Drift on any of the three means the
same submission can come back with a different answer."""
import json
from collections import deque
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.config import Settings
from app.orchestrator.openai_strict import OpenAIStrictOrchestrator, _DETERMINISTIC_SEED
from app.schemas.application import Application

REC_DIR = Path("tests/recordings/openai/gpt-4o-2024-08-06/v1/orchestrator")


def _stub_app():
    return Application(application_id="A-001", evaluation_id="EV-001")


@pytest.mark.asyncio
async def test_request_body_has_temperature_zero_and_seed():
    settings = Settings()
    captured_bodies: list[dict] = []
    ring: deque = deque(maxlen=200)
    orch = OpenAIStrictOrchestrator(settings=settings, ring_buffer=ring, api_key="sk-test")

    with respx.mock(base_url="https://api.openai.com") as router:
        payloads_by_task = {
            task: json.loads((REC_DIR / task / "01-spirits-clean.json").read_text())
            for task in ("brand_disambig", "reasoning_enrich", "ocr_reconcile")
        }

        def _dispatch(request):
            body = json.loads(request.content)
            captured_bodies.append(body)
            name = body.get("response_format", {}).get("json_schema", {}).get("name")
            return Response(200, json=payloads_by_task[name])

        router.post("/v1/chat/completions").mock(side_effect=_dispatch)
        await orch.refine(_stub_app(), [], [])

    assert len(captured_bodies) >= 3
    successful = [
        b for b in captured_bodies
        if b.get("response_format", {}).get("json_schema", {}).get("name")
        in {"brand_disambig", "reasoning_enrich", "ocr_reconcile"}
    ]

    for body in successful:
        assert body.get("temperature") == 0, f"determinism drift: temperature={body.get('temperature')!r}"
        assert body.get("seed") == _DETERMINISTIC_SEED, (
            f"determinism drift: seed={body.get('seed')!r} (expected {_DETERMINISTIC_SEED})"
        )
        assert body.get("model") == "gpt-4o-2024-08-06", f"snapshot drift: model={body.get('model')!r}"
