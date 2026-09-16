import json
from collections import deque
from pathlib import Path

import httpx
import pytest
import respx
from httpx import Response

from app.config import Settings
from app.orchestrator.anthropic_strict import AnthropicStrictOrchestrator
from app.schemas.application import Application

REC_DIR = Path("tests/recordings/anthropic/claude-3-5-sonnet-20241022/v1/orchestrator")


def _stub_app():
    return Application(application_id="A-001", evaluation_id="EV-001")


def _mount_anthropic(router) -> None:
    payloads = {}
    for task in ("brand_disambig", "reasoning_enrich", "ocr_reconcile"):
        path = REC_DIR / task / "01-spirits-clean.json"
        payloads[task] = json.loads(path.read_text())

    def _handler(request):
        body = json.loads(request.content)
        name = body.get("tool_choice", {}).get("name")
        if name in payloads:
            return Response(200, json=payloads[name])
        return Response(400, json={"error": f"unknown task {name!r}"})

    router.post("/v1/messages").mock(side_effect=_handler)


@pytest.mark.asyncio
async def test_anthropic_skeleton_returns_refined():
    settings = Settings()
    ring: deque = deque(maxlen=200)
    orch = AnthropicStrictOrchestrator(
        settings=settings, ring_buffer=ring, api_key="sk-ant-test",
        model_snapshot="claude-3-5-sonnet-20241022",
    )
    with respx.mock(base_url="https://api.anthropic.com") as router:
        _mount_anthropic(router)
        refined = await orch.refine(_stub_app(), [], [])
    task_names = {t.task for t in refined.tasks}
    assert task_names == {"brand_disambig", "reasoning_enrich", "ocr_reconcile"}
    assert len(ring) == 3
    assert all(r.provider == "anthropic" for r in ring)


@pytest.mark.asyncio
async def test_anthropic_ensure_client_raises_without_extra(monkeypatch):
    """When the anthropic SDK is genuinely missing, ensure_client raises a clear error.
    We simulate by monkeypatching sys.modules to inject ImportError on the lazy import."""
    import sys
    monkeypatch.setitem(sys.modules, "anthropic", None)
    settings = Settings()
    orch = AnthropicStrictOrchestrator(
        settings=settings, ring_buffer=deque(maxlen=200), api_key="sk-test",
        model_snapshot="claude-3-5-sonnet-20241022",
    )
    with pytest.raises(RuntimeError, match=r"anthropic.*\[anthropic\].*extra"):
        await orch.ensure_client()
