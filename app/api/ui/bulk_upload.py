"""``POST /batches/upload`` — start a real batch from N uploaded images.

The JSON ``POST /batches`` endpoint takes references to labels the caller
already has on the server, which is no use to a reviewer who wants to drop their
own files in a browser. This route reads the files, hands the worker the exact
bytes that were uploaded, and redirects into the batch shell that streams the
results back.

A bulk upload carries images and no applications, so there is nothing to
compare each label against. The one thing the form can ask for is which
beverage the set is, because it decides which rules apply at all. A reviewer who
skips it gets each label read and nothing checked, and each reply says so
(`docs/decisions.md#0010`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.api import _background, limits
from app.api.ui._page import _get_settings, templates
from app.api.ui._submission import (
    _build_application,
    _detect_image_mime,
    _get_upload_evaluator,
)
from app.config import Settings
from app.schemas.label import ImageMediaType

router = APIRouter()

# Registered in `rules/reason_codes.yaml`. The file reached the server and was
# read; it is simply not an image, which is a different fact from
# ENGINE.INPUT.LABEL_IMAGE_MISSING, where nothing arrived at all.
UNSUPPORTED_IMAGE = "ENGINE.INPUT.LABEL_IMAGE_UNSUPPORTED"


@router.post("/batches/upload")
async def batches_upload_submit(
    request: Request,
    labels: list[UploadFile] = File(...),
    beverage_type: str = Form(default=""),
    settings: Settings = Depends(_get_settings),
    evaluator=Depends(_get_upload_evaluator),
):
    """Build a real in-flight batch from the uploaded images and redirect to it."""
    from app.api._sse_bus import SSEBus
    from app.batch.anomaly import AnomalyDetector
    from app.batch.state import InFlightBatch
    from app.batch.worker import BatchWorker
    from app.schemas.application import Application
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

    # The file count is checked before a single file is read, because reading
    # them is the cost the cap exists to bound.
    if len(labels) > limits.MAX_BATCH_FILES:
        return templates.TemplateResponse(
            request=request,
            name="batches_upload.html",
            context={
                "dev_mode": settings.dev_mode,
                "upload_error": limits.too_many_files_message(len(labels), limits.MAX_BATCH_FILES),
            },
            status_code=413,
        )

    # Read every file up front. A file that is not a PNG or JPEG does not end
    # the submission: it is queued like the rest and refused by name as its own
    # result, so the reviewer is told which file was not read and every other
    # file still has an answer (requirement R13; `docs/decisions.md#0020`).
    #
    # An oversized file does end it, and deliberately: an unreadable file is a
    # fact about that one file, but a file over the cap is a request this
    # service declined to hold in memory, and queueing the rest would mean
    # holding them anyway.
    #
    # It ends the submission, but it does not end the scan. Every file is
    # checked so that every offender is named in one reply. Returning on the
    # first one meant a set with four bad files took four uploads to discover,
    # each refusal hiding the next.
    raw: list[tuple[str, bytes, ImageMediaType | None]] = []
    too_large: list[str] = []
    for index, upload in enumerate(labels):
        body = await upload.read()
        filename = upload.filename or f"label-{index}"
        refusal: str | None = None
        if len(body) > limits.MAX_UPLOAD_BYTES:
            refusal = limits.upload_too_large_message(
                filename, len(body), limits.MAX_UPLOAD_BYTES
            )
        else:
            bomb = limits.bomb_refusal(filename, body)
            if bomb is not None:
                refusal = bomb[0]
        if refusal is not None:
            too_large.append(refusal)
            # The whole upload is going back, so nothing read so far is worth
            # keeping. Dropping it here is what lets the scan run to the end
            # without holding a batch it has already decided to refuse.
            raw.clear()
            continue
        if too_large:
            continue
        raw.append((filename, body, _detect_image_mime(body)))

    if too_large:
        return templates.TemplateResponse(
            request=request,
            name="batches_upload.html",
            context={
                "dev_mode": settings.dev_mode,
                "upload_error": limits.oversized_batch_message(len(too_large), len(labels)),
                "upload_error_items": too_large,
            },
            status_code=413,
        )

    if all(mime is None for _, _, mime in raw):
        # Nothing to check and so no batch to show a refusal in. This is the
        # empty-submission case wearing different clothes, and it is answered
        # the same way.
        return templates.TemplateResponse(
            request=request,
            name="batches_upload.html",
            context={
                "dev_mode": settings.dev_mode,
                "upload_error": (
                    "None of those files is a PNG or JPEG image, so there was nothing "
                    "to check. Save them as PNG or JPEG and upload them again."
                ),
            },
            status_code=400,
        )

    batch_id = f"B-{uuid.uuid4().hex[:10]}"
    now = datetime.now(UTC)
    items: list[BatchItem] = []
    label_lookup: dict[str, LabelModel] = {}
    app_lookup: dict[str, Application] = {}
    refusals: dict[str, tuple[str, str]] = {}
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
        if mime is None:
            refusals[label_id] = (
                UNSUPPORTED_IMAGE,
                f"{filename} is not a PNG or JPEG image, so it was not read. Save it "
                "as a PNG or JPEG and upload it again \u2014 every other file in this "
                "batch was checked.",
            )
        else:
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
                # Minted, not borrowed from `label_id`: `label_id` carries the
                # uploader's own filename so the reviewer can tell which file a
                # row is, and the evaluation id is a telemetry key that reaches
                # the logs. The two must not be the same string.
                evaluation_id=f"ev-{uuid.uuid4().hex[:12]}",
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
    worker._refusals = refusals
    _background.spawn(request.app, worker.run(), name=f"batch-worker:{batch_id}")

    return RedirectResponse(url=f"/batch/{batch_id}", status_code=303)
