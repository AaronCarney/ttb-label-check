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


# Two paths, one handler. Cloud Run's front end answers /healthz itself with
# its own 404 page and never forwards the request to the container, so the
# deployed service needs a path the platform does not claim. Google's known
# issues page states the rule and offers no way to turn it off: "You can't use
# the following URL paths: Paths starting with /_ah/; Some paths ending with z.
# To prevent conflicts with reserved paths, we recommend avoiding all paths
# that end in z" (cloud.google.com/run/docs/known-issues, read 2026-09-16).
# /api/health therefore ends in no z at all. /healthz stays because every local
# caller and test uses it, and locally nothing intercepts it.
@router.get("/healthz")
@router.get("/api/health")
async def healthz(settings: Settings = Depends(_get_settings)) -> JSONResponse:
    """Report whether the app is ready to evaluate a label.

    The first call proves readiness the only way that settles it: it builds the
    same evaluator a submission builds, which loads the rule pack and the
    reader's models, and reports what happened. A failure answers HTTP 503 with
    ``status: not_ready`` — that is what lets an orchestrator hold traffic back
    — and the next call tries again. Later calls answer from what the first one
    found, so a health check stays fast.

    It also warms the serving path, which it did not always do. The local
    reader is one object for the whole process (``app/deps.py``), so the models
    this call loads are the ones the next submission reads with, and that
    submission does not pay the load again. It goes as far as running one read,
    because loading a model and running it cost separately and only the second
    of those was ever paid by the first label — see ``LocalVisionExtractor.warm``.
    The hosted reader loads nothing, so there is nothing to warm.

    No submitted label is read here: the warm read runs on an image the reader
    draws for itself, which is never parsed, scored or reported.
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
            # `warm`, not `ensure_loaded`: loading the models leaves the first
            # inference still to pay, and this endpoint is what the deployed
            # startup probe calls, so paying it here is what keeps it off the
            # first label. `warm` awaits `ensure_loaded` itself, so a reader
            # that cannot load still fails here and still answers 503.
            await evaluator._vision.warm()
        except Exception as exc:
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
