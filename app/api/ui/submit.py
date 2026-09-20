"""``POST /`` — check the labels a reviewer uploaded against the applications
filed for them.

One route, whether the reviewer dropped one image or three hundred. The engine
has always worked that way: the same evaluator is called on the same
``(application, label)`` pair either way, and the batch worker broadcasts each
label's result the moment it lands rather than holding the first one back. What
was split was the interface — a single-label form on ``/`` and a bulk form on
``/batches`` — so a reviewer had to decide which of two systems they were in
before they had checked anything. There is one system, and this is the way in
(`docs/decisions.md#0045`).

**How the files become labels.** Names ending ``-front`` and ``-back`` on the
same stem are two faces of one label; every other filename is a label on its
own (`app/api/ui/_faces.py`). A reviewer holding two photographs of one label
that are not named that way ticks *These images are all faces of one label*
instead of renaming them.

**How the applications arrive.** Either typed into the form, which applies when
the submission is one label, or as a CSV with one row per label, which is what
a reviewer holding three hundred of them has (`app/api/ui/_application_csv.py`).
Where both are present the row wins, because it names the label it belongs to.
The typed beverage type is the fallback for a label no row covers, because it
decides which rule pack runs at all: a wine checked against the spirits rules
fires none of the wine rules.

A label with no application at all is not an error. It is read and checked for
what every label must carry, with nothing to compare against, and its result
says so (`docs/decisions.md#0010`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api import limits
from app.api.ui._application_csv import ApplicationCsvError
from app.api.ui._application_csv import key_for as application_key_for
from app.api.ui._application_csv import parse as parse_applications
from app.api.ui._faces import PlannedFace, PlannedLabel, plan_labels
from app.api.ui._page import _get_settings, templates
from app.api.ui._submission import (
    _build_application,
    _detect_image_mime,
    _get_upload_evaluator,
)
from app.api.ui.images import UploadImageStore, _get_image_store
from app.api.ui.results import SingleResultStore, _get_result_store
from app.batch import admission
from app.config import Settings
from app.schemas.label import FaceTag, ImageMediaType

router = APIRouter()

# Registered in `rules/reason_codes.yaml`. The file reached the server and was
# read; it is simply not an image, which is a different fact from
# ENGINE.INPUT.LABEL_IMAGE_MISSING, where nothing arrived at all.
UNSUPPORTED_IMAGE = "ENGINE.INPUT.LABEL_IMAGE_UNSUPPORTED"

# The ten application fields the form posts, in the order the page shows them.
APPLICATION_FIELDS = (
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

# Which face each image of a one-label submission is placed on, in the order
# they were picked. Beyond the fourth there is no tag left to give, so the
# extras stay labels of their own rather than being dropped.
_ONE_LABEL_FACE_ORDER: tuple[FaceTag, ...] = ("front", "back", "neck", "side")


def refuse(
    *,
    request: Request,
    settings: Settings,
    message: str,
    posted: dict[str, str],
    items: list[str] | None = None,
    status_code: int = 400,
) -> HTMLResponse:
    """The entry page again, with an inline banner and nothing checked.

    What the reviewer typed goes back with it, so a mis-typed field is one
    correction away rather than ten fields away.
    """
    return templates.TemplateResponse(
        request=request,
        name="check.html",
        context={
            "dev_mode": settings.dev_mode,
            "upload_error": message,
            "upload_error_items": items,
            "application_form": posted,
        },
        status_code=status_code,
    )


def _as_one_label(
    raw: list[tuple[str, bytes, ImageMediaType | None]],
) -> list[PlannedLabel]:
    """Every uploaded image placed on one label, in the order it was picked.

    What *These images are all faces of one label* means. It exists because the
    filename convention cannot be read off two photographs a reviewer took on
    their phone, and renaming files is not a thing to ask of someone checking
    one label.

    A file that is not an image is still its own row, refused by name, exactly
    as `plan_labels` makes it: a submission does not lose its other results
    because one file was a PDF.
    """
    faces: list[PlannedFace] = []
    refused: list[PlannedLabel] = []
    spare: list[tuple[str, bytes, ImageMediaType | None]] = []
    for filename, body, media_type in raw:
        if media_type is None:
            refused.append(PlannedLabel(name=filename, faces=(), refused_filename=filename))
        elif len(faces) < len(_ONE_LABEL_FACE_ORDER):
            faces.append(
                PlannedFace(
                    face_tag=_ONE_LABEL_FACE_ORDER[len(faces)],
                    filename=filename,
                    body=body,
                    content_type=media_type,
                )
            )
        else:
            spare.append((filename, body, media_type))

    planned: list[PlannedLabel] = []
    if faces:
        planned.append(PlannedLabel(name=faces[0].filename, faces=tuple(faces)))
    planned.extend(plan_labels(spare))
    planned.extend(refused)
    return planned


class LaunchRefusal(Exception):
    """A submission that cannot be started, carrying the sentence to show."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def launch_batch(
    *,
    request: Request,
    settings: Settings,
    evaluator,
    images: UploadImageStore,
    results: SingleResultStore,
    labels: list[tuple[str, tuple, dict[str, str]]],
    refused: list[tuple[str, str]],
) -> str:
    """Queue a submission and start its worker; returns the batch id.

    `labels` is one `(name, faces, declared application fields)` per checkable
    label, in the order they were submitted. `refused` is one
    `(name, sentence the reviewer reads)` per file that was not an image; those
    are queued too, so a reviewer is told which file was not read and every
    other file still has an answer (`docs/decisions.md#0020`).

    One label and three hundred take this same path. That is the whole point of
    it: the reviewer's own upload and a shipped sample cannot demonstrate
    different behaviour if there is only one way to start a check.

    Raises `LaunchRefusal` when an application cannot be read or a batch is
    already running, and `admission.BatchInProgress` is translated into one.
    """
    from app.api._sse_bus import SSEBus
    from app.batch.anomaly import AnomalyDetector
    from app.batch.state import InFlightBatch
    from app.batch.worker import BatchWorker
    from app.schemas.application import Application
    from app.schemas.batch import BatchItem, ItemState
    from app.schemas.label import Label as LabelModel
    from app.services.application_form import ApplicationFormError

    batch_id = f"B-{uuid.uuid4().hex[:10]}"
    now = datetime.now(UTC)
    items: list[BatchItem] = []
    label_lookup: dict[str, LabelModel] = {}
    app_lookup: dict[str, Application] = {}
    refusals: dict[str, tuple[str, str]] = {}
    named = [(name, faces, declared) for name, faces, declared in labels]
    named += [(name, (), None) for name, _message in refused]

    for idx, (name, faces, declared) in enumerate(named):
        label_id = f"{batch_id}-{idx:03d}-{name}"
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
        if declared is None:
            message = next(sentence for refused_name, sentence in refused if refused_name == name)
            refusals[label_id] = (UNSUPPORTED_IMAGE, message)
            declared = {}
        else:
            label_lookup[label_id] = LabelModel(label_id=label_id, batch_id=batch_id, faces=faces)
        try:
            app_lookup[application_ref] = _build_application(
                declared,
                settings,
                application_id=application_ref,
                # Minted, not borrowed from `label_id`: `label_id` carries the
                # uploader's own filename so the reviewer can tell which row is
                # which, and the evaluation id is a telemetry key that reaches
                # the logs. The two must not be the same string.
                evaluation_id=f"ev-{uuid.uuid4().hex[:12]}",
            )
        except ApplicationFormError as error:
            # Named by label, because with a CSV in play the reviewer has to
            # know which row to fix, and "pick the beverage type" said about
            # three hundred labels at once names none of them.
            where = (
                f"The application for {name!r} cannot be read: {error}"
                if len(named) > 1
                else str(error)
            )
            raise LaunchRefusal(where) from error

    in_flight = InFlightBatch(
        batch_id=batch_id,
        agent_id="ui-upload",
        items=tuple(items),
        lookahead_k=max(1, settings.lookahead_k),
    )
    bus = SSEBus()
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=evaluator,
        anomaly=AnomalyDetector(),
        bus=bus,
        app_lookup=app_lookup,
        label_lookup=label_lookup,
        refusals=refusals,
        # The results page shows each label's photographs beside its findings,
        # and keeps the result so a reviewer's override has something to amend.
        # Both stores are handed over rather than written to here, because the
        # id they are keyed under is the one the finished envelope carries.
        images=images,
        results=results,
    )
    try:
        admission.start(request.app, in_flight, bus, worker)
    except admission.BatchInProgress as busy:
        raise LaunchRefusal(str(busy), status_code=409) from busy
    return batch_id


@router.post("/", response_class=HTMLResponse)
async def submit(
    request: Request,
    labels: list[UploadFile] = File(...),
    applications: UploadFile | None = File(default=None),
    one_label: str = Form(default=""),
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
):
    """Start the check and send the reviewer to where its results arrive."""
    from app.schemas.label import Face

    # Written out rather than gathered from `locals()`: a dict comprehension
    # has a scope of its own, so `locals()` inside one does not see the
    # function's arguments at all.
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
    assert tuple(posted) == APPLICATION_FIELDS

    uploaded = [upload for upload in labels if upload is not None and upload.filename]
    if not uploaded:
        return refuse(
            request=request,
            settings=settings,
            message="Pick at least one PNG or JPEG file.",
            posted=posted,
        )

    # The file count is checked before a single file is read, because reading
    # them is the cost the cap exists to bound.
    if len(uploaded) > limits.MAX_BATCH_FILES:
        return refuse(
            request=request,
            settings=settings,
            message=limits.too_many_files_message(len(uploaded), limits.MAX_BATCH_FILES),
            posted=posted,
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
    # The applications may arrive in their own field or among the images. The
    # sample pack is one zip holding both, and a reviewer who unzips it and
    # selects everything sends the CSV through the image picker; refusing it
    # there as "not a PNG or JPEG" would name the one file carrying the
    # applications as the one file that was not read.
    #
    # A file input the reviewer left alone still posts a part — an empty one,
    # with no filename. Read naively that empty part is an applications file,
    # and it shadows the real CSV sitting in the image picker: every label in
    # the batch then arrives with nothing to compare against, on the path that
    # exists to compare. So an upload is only an applications file if it
    # carries a name and bytes.
    applications_body: bytes | None = None
    if applications is not None and applications.filename:
        applications_body = (await applications.read()) or None
    for index, upload in enumerate(uploaded):
        body = await upload.read()
        filename = upload.filename or f"label-{index}"
        refusal: str | None = None
        if len(body) > limits.MAX_UPLOAD_BYTES:
            refusal = limits.upload_too_large_message(filename, len(body), limits.MAX_UPLOAD_BYTES)
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
        if filename.lower().endswith(".csv"):
            # A second CSV does not replace the first: a reviewer who sent one
            # deliberately in its own field meant that one.
            if applications_body is None:
                applications_body = body
            continue
        raw.append((filename, body, _detect_image_mime(body)))

    if too_large:
        return refuse(
            request=request,
            settings=settings,
            message=limits.oversized_batch_message(len(too_large), len(uploaded)),
            posted=posted,
            items=too_large,
            status_code=413,
        )

    try:
        posted_by_label = parse_applications(applications_body) if applications_body else {}
    except ApplicationCsvError as error:
        return refuse(request=request, settings=settings, message=str(error), posted=posted)

    if not raw:
        # Applications and no labels. The CSV is not a submission on its own.
        return refuse(
            request=request,
            settings=settings,
            message="Pick at least one PNG or JPEG file.",
            posted=posted,
        )

    if all(media_type is None for _, _, media_type in raw):
        # Nothing to check and so no batch to show a refusal in. This is the
        # empty-submission case wearing different clothes, and it is answered
        # the same way.
        return refuse(
            request=request,
            settings=settings,
            message=(
                "None of those files is a PNG or JPEG image, so there was nothing "
                "to check. Save them as PNG or JPEG and upload them again."
            ),
            posted=posted,
        )

    planned = _as_one_label(raw) if one_label else plan_labels(raw)
    checkable = [item for item in planned if item.refused_filename is None]
    # What the reviewer typed is the application for *one* label, so it applies
    # when the submission is one label. Spread across several it would claim
    # that every label declares the same brand, which is a comparison the
    # product must not invent; only the beverage type carries over, because a
    # label with no rule pack is not checked at all.
    typed_applies = len(checkable) == 1 and not posted_by_label

    entries: list[tuple[str, tuple, dict[str, str]]] = []
    refused_files: list[tuple[str, str]] = []
    for item in planned:
        if item.refused_filename is not None:
            refused_files.append(
                (
                    item.name,
                    f"{item.refused_filename} is not a PNG or JPEG image, so it was not "
                    "read. Save it as a PNG or JPEG and upload it again \u2014 every other "
                    "file in this submission was checked.",
                )
            )
            continue
        row = posted_by_label.get(application_key_for(item.name))
        if row is not None:
            declared = row if row.get("beverage_type") else {**row, "beverage_type": beverage_type}
        elif typed_applies:
            declared = posted
        else:
            declared = {"beverage_type": beverage_type}
        entries.append(
            (
                item.name,
                tuple(
                    Face(
                        image_bytes=face.body,
                        content_type=face.content_type,
                        face_tag=face.face_tag,
                        dimensions=None,
                    )
                    for face in item.faces
                ),
                declared,
            )
        )

    try:
        batch_id = launch_batch(
            request=request,
            settings=settings,
            evaluator=evaluator,
            images=images,
            results=results,
            labels=entries,
            refused=refused_files,
        )
    except LaunchRefusal as declined:
        return refuse(
            request=request,
            settings=settings,
            message=declined.message,
            posted=posted,
            status_code=declined.status_code,
        )

    return RedirectResponse(url=f"/batch/{batch_id}", status_code=303)
