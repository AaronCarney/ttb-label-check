import inspect
import json
from collections import deque
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.config import Settings
from app.orchestrator.base import Orchestrator
from app.orchestrator.openai_strict import OpenAIStrictOrchestrator
from app.orchestrator.anthropic_strict import AnthropicStrictOrchestrator
from app.schemas.application import Application


OPENAI_REC = Path("tests/recordings/openai/gpt-4o-2024-08-06/v1/orchestrator")
ANTHROPIC_REC = Path("tests/recordings/anthropic/claude-3-5-sonnet-20241022/v1/orchestrator")
TASKS = ("brand_disambig", "reasoning_enrich", "ocr_reconcile")


def _stub_app():
    return Application(application_id="A-001", evaluation_id="EV-001")


def test_both_subclass_orchestrator():
    assert issubclass(OpenAIStrictOrchestrator, Orchestrator)
    assert issubclass(AnthropicStrictOrchestrator, Orchestrator)


def test_both_refine_are_coroutines():
    assert inspect.iscoroutinefunction(OpenAIStrictOrchestrator.refine)
    assert inspect.iscoroutinefunction(AnthropicStrictOrchestrator.refine)


@pytest.mark.asyncio
async def test_both_produce_same_task_keys():
    settings = Settings()

    # OpenAI under recordings — single dispatcher keyed on json_schema.name
    openai_ring: deque = deque(maxlen=200)
    openai_orch = OpenAIStrictOrchestrator(settings=settings, ring_buffer=openai_ring, api_key="sk-test")
    openai_payloads = {
        task: json.loads((OPENAI_REC / task / "01-spirits-clean.json").read_text())
        for task in TASKS
    }
    with respx.mock(base_url="https://api.openai.com") as router:
        def _dispatch_openai(request):
            body = json.loads(request.content)
            name = body.get("response_format", {}).get("json_schema", {}).get("name")
            return Response(200, json=openai_payloads[name])
        router.post("/v1/chat/completions").mock(side_effect=_dispatch_openai)
        openai_refined = await openai_orch.refine(_stub_app(), [], [])

    # Anthropic under recordings — single dispatcher keyed on tool_choice.name
    anth_ring: deque = deque(maxlen=200)
    anth_orch = AnthropicStrictOrchestrator(
        settings=settings, ring_buffer=anth_ring, api_key="sk-ant-test",
        model_snapshot="claude-3-5-sonnet-20241022",
    )
    anth_payloads = {
        task: json.loads((ANTHROPIC_REC / task / "01-spirits-clean.json").read_text())
        for task in TASKS
    }
    with respx.mock(base_url="https://api.anthropic.com") as router:
        def _dispatch_anthropic(request):
            body = json.loads(request.content)
            name = body.get("tool_choice", {}).get("name")
            return Response(200, json=anth_payloads[name])
        router.post("/v1/messages").mock(side_effect=_dispatch_anthropic)
        anth_refined = await anth_orch.refine(_stub_app(), [], [])

    openai_keys = {t.task for t in openai_refined.tasks}
    anth_keys = {t.task for t in anth_refined.tasks}
    assert openai_keys == anth_keys == {"brand_disambig", "reasoning_enrich", "ocr_reconcile"}
