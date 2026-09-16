"""GET /healthz — readiness, including whether the reader has warmed up."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.config import Settings


router = APIRouter(tags=["health"])
_logger = logging.getLogger("app.healthz")
_warmed: dict[str, bool] = {"done": False}


def _get_settings() -> Settings:
    return Settings()


@router.get("/healthz")
async def healthz(settings: Settings = Depends(_get_settings)) -> JSONResponse:
    """Report whether the app is ready to evaluate a label.

    The first call also warms the app up: it builds the evaluator and loads the
    reader's models, so that cost falls on the container's start-up probe
    rather than on the first real submission. A warm-up that raises answers
    HTTP 503 with ``status: not_ready``, which is what lets an orchestrator
    hold traffic back; the next call retries the warm-up.

    No label is read here. The probe loads the reader; it never runs one.
    """
    body: dict[str, object] = {
        "status": "ok",
        "version": settings.app_version,
        "mode": {"vision": settings.vision_mode},
        "reader_loaded": _warmed["done"],
        "warmup_ran": False,
    }
    if not _warmed["done"]:
        try:
            from app.deps import build_evaluator

            evaluator = build_evaluator(settings)
            await evaluator._vision.ensure_loaded()
        except Exception as exc:  # noqa: BLE001 — any failure to warm up means not ready
            body["status"] = "not_ready"
            body["warmup_error"] = str(exc)
            _logger.warning(
                "healthz_warmup_failed",
                extra={"reason_code": "ENGINE.EXTRACTION.UNAVAILABLE"},
            )
            return JSONResponse(status_code=503, content=body)
        _warmed["done"] = True
        body["reader_loaded"] = True
        body["warmup_ran"] = True
    _logger.info("healthz_invoked", extra={"reason_code": "ENGINE.OK.NONE"})
    return JSONResponse(status_code=200, content=body)
