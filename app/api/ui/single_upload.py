"""``POST /`` — check one uploaded label against the application filed for it.

The whole single-label path in one place: read the upload, refuse it if it is
not an image, build the application from what the grader typed, run the
evaluator, keep the image where the result page can fetch it, and render the
result into the same shell the landing page uses.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.api.ui._page import _get_settings, templates
from app.api.ui._submission import (
    _build_application,
    _detect_image_mime,
    _get_upload_evaluator,
)
from app.api.ui.images import UploadImageStore, _get_image_store
from app.config import Settings

router = APIRouter()


@router.post("/", response_class=HTMLResponse)
async def single_label_upload(
    request: Request,
    label: UploadFile = File(...),
    beverage_type: str = Form(default=""),
    brand_name: str = Form(default=""),
    fanciful_name: str = Form(default=""),
    class_type: str = Form(default=""),
    alcohol_content: str = Form(default=""),
    net_contents: str = Form(default=""),
    applicant_name_address: str = Form(default=""),
    source_of_product: str = Form(default=""),
    origin: str = Form(default=""),
    wine_appellation: str = Form(default=""),
    settings: Settings = Depends(_get_settings),
    evaluator=Depends(_get_upload_evaluator),
    images: UploadImageStore = Depends(_get_image_store),
) -> HTMLResponse:
    """Check one uploaded label against the application filed for it.

    The page posts the application's own fields beside the image, because a
    comparison needs both sides. Every application field is optional except the
    beverage type: an empty one means the application declared nothing for that
    element, so the check against it reports that it does not apply. The
    beverage type is the exception because it decides which rules apply at all
    — a grader who skips it gets the reading and no checks, and the reply says
    so (`docs/decisions.md#0010`).

    Returns the same template as `/` so the React island mounts identically;
    a bad upload or an unreadable application renders an inline banner with
    HTTP 400 and checks nothing.
    """
    from app.schemas.label import Label as LabelModel
    from app.services.application_form import ApplicationFormError

    posted = {
        "beverage_type": beverage_type,
        "brand_name": brand_name,
        "fanciful_name": fanciful_name,
        "class_type": class_type,
        "alcohol_content": alcohol_content,
        "net_contents": net_contents,
        "applicant_name_address": applicant_name_address,
        "source_of_product": source_of_product,
        "origin": origin,
        "wine_appellation": wine_appellation,
    }

    def refuse(message: str) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="single.html",
            context={
                "envelope_json": None,
                "dev_mode": settings.dev_mode,
                "upload_error": message,
                "application_form": posted,
            },
            status_code=400,
        )

    image_bytes = await label.read()
    mime = _detect_image_mime(image_bytes)
    if mime is None:
        return refuse("Unsupported file type — upload a PNG or JPEG.")

    application_id = f"app-{uuid.uuid4().hex[:12]}"
    evaluation_id = f"ev-{uuid.uuid4().hex[:12]}"
    try:
        app_obj = _build_application(
            posted, settings, application_id=application_id, evaluation_id=evaluation_id
        )
    except ApplicationFormError as error:
        return refuse(str(error))
    label_obj = LabelModel(
        label_id=label.filename or "uploaded-label",
        batch_id=application_id,
        image_bytes=image_bytes,
        content_type=mime,
        face_tag="front",
        dimensions=None,
    )
    envelope = await evaluator.evaluate(application=app_obj, label=label_obj)
    # Kept under the id the returned envelope carries rather than the one
    # generated above, so the image route and the URL this template renders
    # agree even where the two differ.
    images.put(envelope.evaluation_id, mime, image_bytes)
    return templates.TemplateResponse(
        request=request,
        name="single.html",
        context={
            "envelope_json": envelope.model_dump_json(),
            "dev_mode": settings.dev_mode,
            "image_url": f"/labels/{envelope.evaluation_id}/image",
            "application_form": posted,
        },
    )
