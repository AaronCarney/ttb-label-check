"""POST /labels — single-label evaluation endpoint."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import Settings
from app.deps import build_evaluator
from app.schemas.application import Application
from app.schemas.label import Label
from app.schemas.wire.disposition import DispositionEnvelope


router = APIRouter(tags=["evaluation"])

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def _detect_content_type(data: bytes) -> str | None:
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    return None


def _get_settings() -> Settings:
    return Settings()


@router.post("/labels", response_model=DispositionEnvelope)
async def post_labels(
    application: UploadFile = File(...),
    label: UploadFile = File(...),
    settings: Settings = Depends(_get_settings),
) -> DispositionEnvelope:
    try:
        app_bytes = await application.read()
        app_obj = Application(**json.loads(app_bytes))
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"rejected_input: {e}")

    label_bytes = await label.read()
    content_type = _detect_content_type(label_bytes)
    if content_type is None:
        raise HTTPException(status_code=400, detail="rejected_input: unsupported MIME (only PNG/JPEG)")

    label_obj = Label(
        label_id=label.filename or "label",
        batch_id=app_obj.application_id,
        image_bytes=label_bytes,
        content_type=content_type,
        face_tag="front",
        dimensions=None,
    )
    evaluator = build_evaluator(settings)
    return await evaluator.evaluate(application=app_obj, label=label_obj)
