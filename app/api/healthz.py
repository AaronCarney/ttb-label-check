"""GET /healthz — readiness, including whether the reader has warmed up."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from app.config import Settings


router = APIRouter(tags=["health"])
_logger = logging.getLogger("app.healthz")
_warmed: dict[str, bool] = {"done": False}


def _get_settings() -> Settings:
    return Settings()


@router.get("/healthz")
async def healthz(settings: Settings = Depends(_get_settings)) -> dict[str, object]:
    body: dict[str, object] = {
        "status": "ok",
        "version": settings.app_version,
        "mode": {"vision": settings.vision_mode},
    }
    if not _warmed["done"]:
        try:
            from app.deps import build_evaluator
            from app.schemas.application import Application
            from app.schemas.label import Label

            evaluator = build_evaluator(settings)
            await evaluator._vision.ensure_loaded()
            fixture_path = Path("fixtures/01-spirits-clean/label.png")
            if fixture_path.exists():
                label = Label(
                    label_id="01-spirits-clean",
                    batch_id="warmup",
                    image_bytes=fixture_path.read_bytes(),
                    content_type="image/png",
                    face_tag="front",
                    dimensions=None,
                )
                application = Application(application_id="warmup", evaluation_id="warmup-EV")
                envelope = await evaluator.evaluate(application=application, label=label)
                body["sentinel_disposition"] = envelope.disposition
            body["warmup_ran"] = True
            _warmed["done"] = True
        except Exception as e:
            body["warmup_error"] = str(e)
            body["warmup_ran"] = False
    _logger.info("healthz_invoked", extra={"reason_code": "ENGINE.OK.NONE"})
    return body
