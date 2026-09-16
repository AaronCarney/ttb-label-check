"""GET /healthz — readiness: can this process build a reader and load its rules."""
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

    The first call proves readiness the only way that settles it: it builds the
    same evaluator a submission builds, which loads the rule pack and the
    reader's models, and reports what happened. A failure answers HTTP 503 with
    ``status: not_ready`` — that is what lets an orchestrator hold traffic back
    — and the next call tries again. Later calls answer from what the first one
    found, so a health check stays fast.

    What this does not do is warm the serving path. Every request builds its
    own evaluator (``app/deps.py``), so the models loaded here are discarded
    with the evaluator that loaded them. Sparing a submission the load would
    mean giving the process one shared reader to hand out.

    No label is read here.
    """
    body: dict[str, object] = {
        "status": "ok",
        "version": settings.app_version,
        "mode": {"vision": settings.vision_mode},
        "warmup_ran": False,
    }
    if not _warmed["done"]:
        try:
            from app.deps import build_evaluator

            evaluator = build_evaluator(settings)
            await evaluator._vision.ensure_loaded()
        except Exception as exc:  # noqa: BLE001 — anything that raises here means not ready
            body["status"] = "not_ready"
            body["warmup_error"] = str(exc)
            _logger.warning(
                "healthz_warmup_failed",
                extra={"reason_code": "ENGINE.EXTRACTION.UNAVAILABLE"},
            )
            return JSONResponse(status_code=503, content=body)
        _warmed["done"] = True
        body["warmup_ran"] = True
    _logger.info("healthz_invoked", extra={"reason_code": "ENGINE.OK.NONE"})
    return JSONResponse(status_code=200, content=body)
