"""Anthropic-strict orchestrator: the alternative backend behind the seam.

HTTP-layer via httpx so respx recordings cover the wire. The `anthropic` SDK is
lazy-imported in ensure_client() — module is importable without the [anthropic]
extra installed. Mirrors OpenAIStrictOrchestrator's task surface but uses the
Anthropic Messages API tool_use shape.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.orchestrator.base import Orchestrator
from app.orchestrator.tasks.brand_disambig import BrandDisambigResult
from app.orchestrator.tasks.reasoning_enrich import EnrichedReasoning
from app.orchestrator.tasks.ocr_reconcile import OcrReconcileResult
from app.schemas.application import Application
from app.schemas.calls import CallRecord
from app.schemas.extracted import FieldObservation
from app.schemas.refined import Refined, TaskSlice
from app.schemas.rejection import ValidationResult

_TASK_SCHEMAS: dict[str, type] = {
    "brand_disambig": BrandDisambigResult,
    "reasoning_enrich": EnrichedReasoning,
    "ocr_reconcile": OcrReconcileResult,
}

_STAGE_BY_TASK: dict[str, str] = {
    "brand_disambig": "orch.brand_disambig",
    "reasoning_enrich": "orch.reasoning_enrich",
    "ocr_reconcile": "orch.ocr_reconcile",
}

_DETERMINISTIC_SEED = 42  # Anthropic ignores seed but we record it for parity.


def _to_anthropic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip OpenAI-specific keys; Anthropic tool_use accepts standard JSON Schema."""
    out = {k: v for k, v in schema.items() if k not in {"$schema", "title"}}
    return out


class AnthropicStrictOrchestrator(Orchestrator):
    def __init__(
        self,
        *,
        settings: Settings,
        ring_buffer: deque,
        api_key: str,
        model_snapshot: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        self._settings = settings
        self._ring = ring_buffer
        self._api_key = api_key
        self._model = model_snapshot
        self._prompt_version = settings.prompt_version

    async def ensure_client(self) -> None:
        try:
            import anthropic  # noqa: F401  # lazy import; presence-check only
        except ImportError as e:
            raise RuntimeError(
                "anthropic SDK not installed. Install the [anthropic] extra: "
                "uv sync --extra anthropic"
            ) from e

    async def refine(
        self,
        application: Application,
        observations: list[FieldObservation],
        validation_results: list[ValidationResult],
    ) -> Refined:
        evaluation_id = getattr(application, "evaluation_id", "EV-unknown")
        refined = Refined(evaluation_id=evaluation_id)
        slices = await asyncio.gather(
            self._call_task("brand_disambig"),
            self._call_task("reasoning_enrich"),
            self._call_task("ocr_reconcile"),
        )
        return refined.model_copy(update={"tasks": tuple(slices)})

    async def _call_task(self, task_name: str) -> TaskSlice:
        # NOTE: signature is intentionally narrower than
        # OpenAIStrictOrchestrator._call_task — this backend does not thread
        # application/observations into the prompt body. Widen to match once
        # the Anthropic path is validated against the demo fixtures.
        # ValueError covers the "tool_use block missing from response" path
        # raised by _post_one — see note on `raise ValueError(...)` below.
        # httpx.HTTPError covers both transport (RequestError) and protocol
        # (HTTPStatusError from raise_for_status) failures; the fallback covers both.
        schema_cls = _TASK_SCHEMAS[task_name]
        body = self._build_body(task_name, schema_cls)
        t0 = time.monotonic()
        try:
            content = await self._post_one(task_name, body)
        except httpx.HTTPError as e:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            self._record(task_name, body, {"error": "ENGINE.MODEL.UNAVAILABLE", "exception": str(e)}, latency_ms=elapsed_ms)
            return TaskSlice(task=task_name, qualifier="ENGINE.MODEL.UNAVAILABLE")  # type: ignore[arg-type]
        try:
            result = schema_cls.model_validate(content)
            return TaskSlice(task=task_name, payload=result.model_dump())  # type: ignore[arg-type]
        except (ValidationError, ValueError):
            # Retry attempt — write its own CallRecord on HTTPError so the
            # failure is visible (parity with OpenAIStrictOrchestrator).
            t0_retry = time.monotonic()
            try:
                content = await self._post_one(task_name, body)
            except httpx.HTTPError as e:
                elapsed_ms = int((time.monotonic() - t0_retry) * 1000)
                self._record(task_name, body, {"error": "ENGINE.MODEL.UNAVAILABLE", "exception": str(e)}, latency_ms=elapsed_ms)
                return TaskSlice(task=task_name, qualifier="LLM_OUTPUT_INVALID")  # type: ignore[arg-type]
            try:
                result = schema_cls.model_validate(content)
                return TaskSlice(task=task_name, payload=result.model_dump())  # type: ignore[arg-type]
            except (ValidationError, ValueError):
                return TaskSlice(task=task_name, qualifier="LLM_OUTPUT_INVALID")  # type: ignore[arg-type]

    def _build_body(self, task_name: str, schema_cls: type) -> dict[str, Any]:
        return {
            "model": self._model,
            "max_tokens": 1024,
            "temperature": 0,
            "messages": [{"role": "user", "content": f"Run task: {task_name}"}],
            "tools": [{
                "name": task_name,
                "description": f"Run the {task_name} task and return a typed result.",
                "input_schema": _to_anthropic_schema(schema_cls.model_json_schema()),
            }],
            "tool_choice": {"type": "tool", "name": task_name},
        }

    async def _post_one(self, task_name: str, body: dict[str, Any]) -> dict[str, Any]:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                },
                json=body,
            )
            resp.raise_for_status()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        payload = resp.json()
        # Find the tool_use block matching this task.
        tool_use = next(
            (b for b in payload.get("content", []) if b.get("type") == "tool_use" and b.get("name") == task_name),
            None,
        )
        if tool_use is None:
            # NB: do NOT use `ValidationError.from_exception_data(line_errors=[])`
            # — pydantic v2 ≥ 2.6 raises `PydanticUserError` on an empty error list.
            # `_call_task` above catches `ValueError` alongside `ValidationError`
            # so the malformed-output retry path still kicks in.
            raise ValueError(f"anthropic response missing tool_use block for task {task_name!r}")
        content = tool_use["input"]
        self._record(task_name, body, content, elapsed_ms=elapsed_ms)
        return content

    def _record(self, task_name: str, body: dict[str, Any], response: dict[str, Any], *, elapsed_ms: int = 0, latency_ms: int = 0) -> None:
        latency = elapsed_ms or latency_ms
        self._ring.append(
            CallRecord(
                ts=datetime.now(timezone.utc),
                batch_id="",
                label_id="",
                stage=_STAGE_BY_TASK[task_name],  # type: ignore[arg-type]
                request={"task": task_name, "model": body.get("model"), "temperature": body.get("temperature")},
                response=response,
                latency_ms=latency,
                model=self._model,
                provider="anthropic",
                prompt_version=self._prompt_version,
                output_hash=hashlib.sha256(json.dumps(response, sort_keys=True, default=str).encode()).hexdigest()[:16],
            )
        )
