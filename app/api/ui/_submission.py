"""What a posted upload becomes before the engine sees it.

Both upload routes — one label on ``POST /``, a folder of them on
``POST /batches/upload`` — need the same three things: the uploaded bytes
identified as an image the reader can open, the application the form declares,
and the evaluator that checks one against the other. They are here so the two
routes cannot drift apart on any of the three.

This module reaches into ``app.services`` and ``app.deps``, which is why the
page shells do not: rendering a page needs none of it.
"""
from __future__ import annotations

from app.config import Settings

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def _detect_image_mime(data: bytes) -> str | None:
    """The media type of an upload, read from its own first bytes.

    The browser's declared content type is not consulted: it is whatever the
    client chose to send, and an unreadable upload has to be turned away before
    it reaches the reader rather than after.
    """
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    return None


def _application_record(posted: dict[str, str], settings: Settings):
    """The application one submitted form declares, or nothing if it declares
    none. Raises `ApplicationFormError` when the reviewer typed something the
    form cannot read; the caller shows the message and checks nothing."""
    from app.services.application_form import record_from_form

    return record_from_form(rules_root=settings.rules_root, **posted)


def _build_application(
    posted: dict[str, str], settings: Settings, *, application_id: str, evaluation_id: str
):
    """One `Application`, carrying whatever the reviewer declared.

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
    """The evaluator this submission is checked by, as a dependency.

    A test overrides it to inject a fake, so an upload test never reaches a
    vision model. In the running app `app/deps.py` builds a fresh evaluator
    each call but hands it the reader the process already has: the local
    reader is a process-wide singleton, so its models load once rather than
    once per upload.
    """
    from app.deps import build_evaluator

    return build_evaluator(Settings())
