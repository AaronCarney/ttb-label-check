"""OpenAI-strict orchestrator: the default backend behind the seam.

HTTP-layer only — does NOT import the openai SDK. Uses httpx so respx
recordings cover the wire. Records 1 CallRecord per task per attempt.
Never returns a disposition; outputs are sliced into Refined.tasks.
Catches httpx.HTTPError (RequestError transport + HTTPStatusError 4xx/5xx) → returns slice with ENGINE.MODEL.UNAVAILABLE; latency_ms reflects actual elapsed time.
Strict-retry: on Pydantic ValidationError of LLM output, retries once;
on second failure, surfaces LLM_OUTPUT_INVALID qualifier.
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

_DETERMINISTIC_SEED = 42


class OpenAIStrictOrchestrator(Orchestrator):
    def __init__(
        self,
        *,
        settings: Settings,
        ring_buffer: deque,
        api_key: str,
    ) -> None:
        self._settings = settings
        self._ring = ring_buffer
        self._api_key = api_key
        self._model = settings.llm_model_snapshot
        self._prompt_version = settings.prompt_version

    async def ensure_client(self) -> None:
        return None

    async def refine(
        self,
        application: Application,
        observations: list[FieldObservation],
        validation_results: list[ValidationResult],
    ) -> Refined:
        evaluation_id = getattr(application, "evaluation_id", "EV-unknown")
        refined = Refined(evaluation_id=evaluation_id)
        # Run all 3 tasks. No per-extractor bulkhead at this layer.
        # asyncio.gather is fine for latency; order doesn't affect output.
        slices = await asyncio.gather(
            self._call_task("brand_disambig", application, observations, validation_results),
            self._call_task("reasoning_enrich", application, observations, validation_results),
            self._call_task("ocr_reconcile", application, observations, validation_results),
        )
        return refined.model_copy(update={"tasks": tuple(slices)})

    async def _call_task(
        self,
        task_name: str,
        application: Application,
        observations: list[FieldObservation],
        validation_results: list[ValidationResult],
    ) -> TaskSlice:
        schema_cls = _TASK_SCHEMAS[task_name]
        body = self._build_body(task_name, schema_cls)
        # First attempt. Catch the broader httpx.HTTPError so 4xx/5xx
        # (HTTPStatusError raised by raise_for_status) also routes through
        # the model-unavailable fallback — RequestError covers transport,
        # HTTPStatusError covers protocol-level failure; the fallback spans both.
        t0 = time.monotonic()
        try:
            content = await self._post_one(task_name, body)
        except httpx.HTTPError as e:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            self._record(task_name, body, {"error": "ENGINE.MODEL.UNAVAILABLE", "exception": str(e)}, latency_ms=elapsed_ms)
            return TaskSlice(task=task_name, qualifier="ENGINE.MODEL.UNAVAILABLE")  # type: ignore[arg-type]
        # Validate; one retry on Pydantic ValidationError.
        try:
            result = schema_cls.model_validate(content)
            return TaskSlice(task=task_name, payload=result.model_dump())  # type: ignore[arg-type]
        except ValidationError:
            # Retry attempt — must produce its own CallRecord regardless of
            # outcome, so both attempts leave a CallRecord entry. On
            # retry-attempt HTTPError, _post_one never reaches its internal
            # _record() call, so we write the failure record explicitly here.
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
            except ValidationError:
                # _post_one already wrote a success-shaped record carrying the bad payload.
                return TaskSlice(task=task_name, qualifier="LLM_OUTPUT_INVALID")  # type: ignore[arg-type]

    def _build_body(self, task_name: str, schema_cls: type) -> dict[str, Any]:
        return {
            "model": self._model,
            "temperature": 0,
            "seed": _DETERMINISTIC_SEED,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": f"Run task: {task_name}"}]}
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": task_name,
                    "strict": True,
                    "schema": schema_cls.model_json_schema(),
                },
            },
        }

    async def _post_one(self, task_name: str, body: dict[str, Any]) -> dict[str, Any]:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
            )
            resp.raise_for_status()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        payload = resp.json()
        content = json.loads(payload["choices"][0]["message"]["content"])
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
                request={"task": task_name, "model": body.get("model"), "temperature": body.get("temperature"), "seed": body.get("seed")},
                response=response,
                latency_ms=latency,
                model=self._model,
                provider="openai",
                prompt_version=self._prompt_version,
                output_hash=hashlib.sha256(json.dumps(response, sort_keys=True, default=str).encode()).hexdigest()[:16],
            )
        )
