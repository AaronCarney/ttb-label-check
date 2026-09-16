"""Page-shell GET routes for the React island.

This module is template-rendering only. It does NOT import from
``app.services``, ``app.vision``, or ``app.rules``.
Engine logic lives in the JSON API routes (``app.api.labels``,
``app.api.batches``, ``app.api.overrides``).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from collections import OrderedDict

_logger = logging.getLogger("app.api.ui")

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.config import Settings


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "ui" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

# Per-process cache of upload bytes keyed by synthesized evaluation_id. Bounded
# so a long-running Space doesn't grow without limit. The value is (mime, bytes);
# bytes are GC'd when the entry is evicted.
_UPLOAD_IMAGE_CACHE_MAX = 64
_LATEST_UPLOAD_IMAGES: OrderedDict[str, tuple[str, bytes]] = OrderedDict()


def _stash_upload_image(eval_id: str, mime: str, body: bytes) -> None:
    _LATEST_UPLOAD_IMAGES[eval_id] = (mime, body)
    while len(_LATEST_UPLOAD_IMAGES) > _UPLOAD_IMAGE_CACHE_MAX:
        evicted_id, _ = _LATEST_UPLOAD_IMAGES.popitem(last=False)
        _logger.debug(
            "upload_image_evicted",
            extra={"evaluation_id": evicted_id, "cache_max": _UPLOAD_IMAGE_CACHE_MAX},
        )


router = APIRouter(tags=["ui"])


def _get_settings() -> Settings:
    return Settings()


@router.get("/", response_class=HTMLResponse)
async def single_page_shell(
    request: Request,
    settings: Settings = Depends(_get_settings),
) -> HTMLResponse:
    """Render the empty-inbox single-label landing. No pre-loaded fixtures;
    the grader sees a drop-zone CTA and either uploads their own labels or
    pulls a starter pack from `/batches/sample.zip`. The React island mounts
    on `<div id="root" data-mode="single">` and renders an envelope only
    after a real upload returns one."""
    return templates.TemplateResponse(
        request=request,
        name="single.html",
        context={
            "envelope_json": None,
            "dev_mode": settings.dev_mode,
        },
    )


# The application fields the single-label and bulk forms post, in the order
# they are asked for on the page. Named exactly as `ApplicationRecord` names
# them, so nothing has to translate between the form and the record.
_APPLICATION_FIELDS = (
    "beverage_type",
    "brand_name",
    "fanciful_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "applicant_name_address",
    "source_of_product",
    "origin",
    "wine_appellation",
)


def _application_record(posted: dict[str, str], settings: Settings):
    """The application one submitted form declares, or nothing if it declares
    none. Raises `ApplicationFormError` when the grader typed something the
    form cannot read; the caller shows the message and checks nothing."""
    from app.services.application_form import record_from_form

    return record_from_form(rules_root=settings.rules_root, **posted)


def _build_application(
    posted: dict[str, str], settings: Settings, *, application_id: str, evaluation_id: str
):
    """One `Application`, carrying whatever the grader declared.

    Without this the running app builds an application with no reference
    values, and every comparison rule reports that it has nothing to compare
    no matter what the rule pack says.
    """
    from app.schemas.application import Application
    from app.services.application_mapper import expected_values_from

    record = _application_record(posted, settings)
    if record is None:
        return Application(application_id=application_id, evaluation_id=evaluation_id)
    return Application(
        application_id=application_id,
        evaluation_id=evaluation_id,
        expected_values=expected_values_from(record),
        beverage_class=record.beverage_class,
    )


def _get_upload_evaluator():
    """Indirection for tests: builds an evaluator against process settings.
    Tests override this dependency to inject a fake so the upload endpoint
    never reaches OpenAI.

    Nothing here is shared between requests: `app/deps.py` builds a fresh
    evaluator, and a fresh reader, on every call.
    """
    from app.deps import build_evaluator
    return build_evaluator(Settings())


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def _detect_image_mime(data: bytes) -> str | None:
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    return None


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
) -> HTMLResponse:
    """Check one uploaded label against the application filed for it.

    The page posts the application's own fields beside the image, because a
    comparison needs both sides. Every application field is optional: an empty
    one means the application declared nothing for that element, so the check
    against it reports that it does not apply, and a grader who picks only an
    image still gets the presence and health-warning checks.

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
    # Stash under the canonical id the envelope carries so the image route
    # and template URL agree even when the evaluator synthesises its own id.
    _stash_upload_image(envelope.evaluation_id, mime, image_bytes)
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


@router.get("/labels/{eval_id}/image")
async def upload_label_image(eval_id: str) -> Response:
    """Serve the PNG/JPEG bytes uploaded for a given evaluation."""
    from fastapi import HTTPException

    entry = _LATEST_UPLOAD_IMAGES.get(eval_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no image for evaluation {eval_id!r}")
    mime, body = entry
    return Response(content=body, media_type=mime)


@router.get("/batch/{batch_id}", response_class=HTMLResponse)
async def batch_page_shell(
    request: Request,
    batch_id: str,
    settings: Settings = Depends(_get_settings),
) -> HTMLResponse:
    """Render the batch review shell for a given batch_id. The React island
    subscribes via SSE to ``/batches/{batch_id}/stream``."""
    return templates.TemplateResponse(
        request=request,
        name="batch.html",
        context={"batch_id": batch_id, "dev_mode": settings.dev_mode},
    )


@router.get("/batches", response_class=HTMLResponse)
async def batches_upload_page(
    request: Request,
    settings: Settings = Depends(_get_settings),
) -> HTMLResponse:
    """Render the bulk-upload form. Submitting it lands at POST /batches/upload
    which spawns a worker and redirects into the existing batch shell."""
    return templates.TemplateResponse(
        request=request,
        name="batches_upload.html",
        context={"dev_mode": settings.dev_mode},
    )


# The sample label images ship inside the application, one directory per TTB
# ID. Serving a sample fetches nothing over the network, so the product works
# with outbound traffic blocked (PRD C-4) and a clone needs no extra download.
_SAMPLE_LABELS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "labels"
)
_SAMPLE_FACE = "front.jpg"


def _load_sample_ttbids() -> list[str]:
    """TTB IDs of the sample labels installed with the app."""
    if not _SAMPLE_LABELS_DIR.is_dir():
        return []
    return sorted(
        d.name for d in _SAMPLE_LABELS_DIR.iterdir() if (d / _SAMPLE_FACE).is_file()
    )


def _read_label_bytes(ttbid: str) -> bytes | None:
    """The front-face JPEG for one TTB ID, or None if it is not installed."""
    local = _SAMPLE_LABELS_DIR / ttbid / _SAMPLE_FACE
    if local.is_file():
        return local.read_bytes()
    return None


@router.get("/batches/sample.zip")
async def batches_sample_zip(n: int = 10) -> Response:
    """Stream a zip of N random sample labels.

    Lets a reviewer try the bulk pipeline against real CC0 TTB Public COLA
    Registry labels without needing their own files: download → drop into
    the upload form on /batches → real worker runs through the same code
    path a production caller would hit.

    Every image is read from the copy installed with the app, so the download
    works with outbound traffic blocked (PRD C-4).
    """
    if n <= 0:
        return Response(
            content=b"n must be a positive integer",
            status_code=400,
            media_type="text/plain",
        )

    available = _load_sample_ttbids()
    if not available:
        return Response(
            content=b"no sample labels are installed with this build",
            status_code=500,
            media_type="text/plain",
        )

    import io
    import random
    import zipfile

    take = min(n, len(available))
    chosen = random.sample(available, take)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ttbid in chosen:
            body = _read_label_bytes(ttbid)
            if body is None:
                continue
            zf.writestr(f"{ttbid}-front.jpg", body)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"content-disposition": 'attachment; filename="sample.zip"'},
    )


@router.post("/batches/upload")
async def batches_upload_submit(
    request: Request,
    labels: list[UploadFile] = File(...),
    beverage_type: str = Form(default=""),
    settings: Settings = Depends(_get_settings),
    evaluator=Depends(_get_upload_evaluator),
):
    """Build a real in-flight batch from N uploaded images.

    The existing JSON `POST /batches` endpoint takes only refs and the worker
    stubs out image bytes — that's fine for tests but useless for a grader who
    wants to drop their own files. We pre-populate `BatchWorker._label_lookup`
    here so each item carries the exact bytes the user uploaded.

    A bulk upload carries images and no applications, so there is nothing to
    compare each label against. The one thing the form can ask for is which
    beverage the set is, because a folder of wine labels checked against the
    spirits pack fires none of the wine rules. A grader who skips it gets the
    reader's own class.
    """
    from app.api._sse_bus import SSEBus
    from app.batch.anomaly import AnomalyDetector
    from app.batch.state import InFlightBatch
    from app.batch.worker import BatchWorker
    from app.schemas.batch import BatchItem, ItemState
    from app.schemas.label import Label as LabelModel
    from app.services.application_form import ApplicationFormError

    if not labels:
        return templates.TemplateResponse(
            request=request,
            name="batches_upload.html",
            context={
                "dev_mode": settings.dev_mode,
                "upload_error": "Pick at least one PNG or JPEG file.",
            },
            status_code=400,
        )

    # Read every file up front so we can validate MIME before scheduling work.
    raw: list[tuple[str, bytes, str]] = []
    for upload in labels:
        body = await upload.read()
        mime = _detect_image_mime(body)
        if mime is None:
            return templates.TemplateResponse(
                request=request,
                name="batches_upload.html",
                context={
                    "dev_mode": settings.dev_mode,
                    "upload_error": (
                        f"Unsupported file: {upload.filename or 'upload'} — "
                        "every upload must be PNG or JPEG."
                    ),
                },
                status_code=400,
            )
        raw.append((upload.filename or f"label-{len(raw)}", body, mime))

    batch_id = f"B-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc)
    items: list[BatchItem] = []
    label_lookup: dict[str, LabelModel] = {}
    app_lookup: dict[str, Application] = {}
    for idx, (filename, body, mime) in enumerate(raw):
        label_id = f"{batch_id}-{idx:03d}-{filename}"
        application_ref = f"{batch_id}-app-{idx:03d}"
        items.append(
            BatchItem(
                label_id=label_id,
                application_ref=application_ref,
                state=ItemState.QUEUED,
                result=None,
                enqueued_at=now,
            )
        )
        label_lookup[label_id] = LabelModel(
            label_id=label_id,
            batch_id=batch_id,
            image_bytes=body,
            content_type=mime,
            face_tag="front",
            dimensions=None,
        )
        try:
            app_lookup[application_ref] = _build_application(
                {"beverage_type": beverage_type},
                settings,
                application_id=application_ref,
                evaluation_id=label_id,
            )
        except ApplicationFormError as error:
            return templates.TemplateResponse(
                request=request,
                name="batches_upload.html",
                context={"dev_mode": settings.dev_mode, "upload_error": str(error)},
                status_code=400,
            )

    in_flight = InFlightBatch(
        batch_id=batch_id,
        agent_id="ui-bulk-upload",
        items=tuple(items),
        lookahead_k=max(1, settings.lookahead_k),
    )
    bus = SSEBus()
    request.app.state.batches[batch_id] = in_flight
    if not hasattr(request.app.state, "buses"):
        request.app.state.buses = {}
    request.app.state.buses[batch_id] = bus

    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=evaluator,
        anomaly=AnomalyDetector(),
        bus=bus,
    )
    worker._label_lookup = label_lookup
    worker._app_lookup = app_lookup
    asyncio.create_task(worker.run())

    return RedirectResponse(url=f"/batch/{batch_id}", status_code=303)
