"""``POST /`` — check one uploaded label against the application filed for it.

Reads the upload, refuses it if it is not an image, and hands the bytes and
the typed application to the shared result path in ``_result_page``. That path
is shared with ``POST /samples/{sample_id}`` so a shipped sample and a reviewer's
own upload cannot demonstrate different behaviour.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.api.ui._page import _get_settings
from app.api.ui._result_page import refuse, render_single_result
from app.api.ui._submission import _detect_image_mime, _get_upload_evaluator
from app.api.ui.images import UploadImageStore, _get_image_store
from app.api.ui.results import SingleResultStore, _get_result_store
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
    results: SingleResultStore = Depends(_get_result_store),
) -> HTMLResponse:
    """Check one uploaded label against the application filed for it.

    The page posts the application's own fields beside the image, because a
    comparison needs both sides. Every application field is optional except the
    beverage type: an empty one means the application declared nothing for that
    element, so the check against it reports that it does not apply. The
    beverage type is the exception because it decides which rules apply at all
    — a reviewer who skips it gets the reading and no checks, and the reply says
    so (`docs/decisions.md#0010`).

    Returns the same template as `/` so the React island mounts identically;
    a bad upload or an unreadable application renders an inline banner with
    HTTP 400 and checks nothing.
    """
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

    image_bytes = await label.read()
    mime = _detect_image_mime(image_bytes)
    if mime is None:
        return refuse(
            request=request,
            settings=settings,
            message="Unsupported file type — upload a PNG or JPEG.",
            posted=posted,
        )

    return await render_single_result(
        request=request,
        settings=settings,
        evaluator=evaluator,
        images=images,
        results=results,
        posted=posted,
        image_bytes=image_bytes,
        mime=mime,
        label_id=label.filename or "uploaded-label",
    )
