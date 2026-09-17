"""Turning one label's faces plus one application into the page the reviewer reads.

Two routes arrive here: the reviewer's own upload on ``POST /`` and a shipped
sample on ``POST /samples/{sample_id}``. They differ only in where the images
and the application values come from; everything after that — build the
application, run the evaluator, keep every face where the result page can fetch
it, render the shell — has to be identical, or a sample would demonstrate a
path the reviewer's own upload does not take.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.api.ui._page import templates
from app.api.ui._submission import _build_application
from app.api.ui.images import UploadImageStore
from app.api.ui.results import SingleResultStore
from app.config import Settings
from app.schemas.label import Face


def refuse(
    *,
    request: Request,
    settings: Settings,
    message: str,
    posted: dict[str, str],
    status_code: int = 400,
) -> HTMLResponse:
    """The landing page again, with an inline banner and nothing checked.

    The samples go back with it: a reviewer who mis-typed something should still
    have the one-click way out in front of them.
    """
    from app.api.ui.samples import offered_samples

    return templates.TemplateResponse(
        request=request,
        name="single.html",
        context={
            "envelope_json": None,
            "dev_mode": settings.dev_mode,
            "upload_error": message,
            "application_form": posted,
            "samples": offered_samples(),
        },
        status_code=status_code,
    )


async def render_single_result(
    *,
    request: Request,
    settings: Settings,
    evaluator,
    images: UploadImageStore,
    results: SingleResultStore,
    posted: dict[str, str],
    faces: tuple[Face, ...],
    label_id: str,
) -> HTMLResponse:
    """Check one label against one application and render the result shell.

    `faces` is every photograph of the label, in the order it was submitted, the
    front first. All of them are checked and all of them are kept, because a
    label's mandatory elements are spread across its panels — the government
    warning is most often on the back — and a finding a reviewer cannot see the
    photograph for is a finding they cannot check.

    `posted` is the ten application fields in the form's own key names, whether
    a reviewer typed them or a sample supplied them. An application the form
    cannot read renders the banner and checks nothing.
    """
    from app.schemas.label import Label as LabelModel
    from app.services.application_form import ApplicationFormError

    application_id = f"app-{uuid.uuid4().hex[:12]}"
    evaluation_id = f"ev-{uuid.uuid4().hex[:12]}"
    try:
        app_obj = _build_application(
            posted, settings, application_id=application_id, evaluation_id=evaluation_id
        )
    except ApplicationFormError as error:
        return refuse(request=request, settings=settings, message=str(error), posted=posted)

    label_obj = LabelModel(label_id=label_id, batch_id=application_id, faces=faces)
    envelope = await evaluator.evaluate(application=app_obj, label=label_obj)
    # Kept under the id the returned envelope carries rather than the one
    # generated above, so the image route and the URL this template renders
    # agree even where the two differ.
    for face in faces:
        images.put(envelope.evaluation_id, face.content_type, face.image_bytes, face.face_tag)
    # The result is kept too, and under the same id. Without it a reviewer's
    # override of a single label has nothing to amend, because only a batch
    # holds its results (`docs/decisions.md#0033`).
    results.put(envelope)
    return templates.TemplateResponse(
        request=request,
        name="single.html",
        context={
            "envelope_json": envelope.model_dump_json(),
            "dev_mode": settings.dev_mode,
            # Every face that reached the store, not just the front. A finding
            # read off the back shown against the front photograph is a page
            # that reads as broken to the reviewer it is meant to convince,
            # and the store has held every face since `2853765` without
            # anything ever asking it which it had.
            "label_faces": _faces_on_show(images, envelope.evaluation_id),
            "application_form": posted,
        },
    )


# What each face is called on the page. The tag is the engine's word; this is
# the reviewer's.
_FACE_CAPTIONS = {
    "front": "Front",
    "back": "Back",
    "neck": "Neck",
    "side": "Side",
}


def _faces_on_show(images: UploadImageStore, evaluation_id: str) -> list[dict[str, str]]:
    """The photographs this result page can show, front first.

    Read back from the store rather than from what was submitted, because the
    store is what the browser will be fetching from: a face that failed to
    write is one the page must not offer a broken image for.
    """
    return [
        {
            "tag": tag,
            "caption": _FACE_CAPTIONS.get(tag, tag.title()),
            "url": f"/labels/{evaluation_id}/image?face={tag}",
        }
        for tag in images.faces(evaluation_id)
    ]
