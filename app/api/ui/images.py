"""The label image a result page shows: where it is kept, and the route that
serves it.

A result page renders ``<img src="/labels/{evaluation_id}/image">``, so the
bytes the grader uploaded have to still be somewhere when the browser asks for
them a moment later — and when the grader opens that page again tomorrow, or
refreshes it after the service restarts, or lands on a different worker.

They are kept as files, one per evaluation, under the machine's temporary
directory. See `docs/decisions.md#0018` for what that choice buys and what it
does not.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

_logger = logging.getLogger("app.api.ui.images")

router = APIRouter()

# An evaluation id reaches the store from a URL path, so it is checked against
# this before it is ever joined to a directory. Letters, digits, hyphen and
# underscore only: no separator and no dot, so no id can name a path outside
# the store no matter what a caller sends.
_EVALUATION_ID = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")

# The image's own media type is carried by the file's suffix, so reading it
# back needs nothing but the directory.
_SUFFIX_FOR_MIME = {"image/png": ".png", "image/jpeg": ".jpg"}
_MIME_FOR_SUFFIX = {suffix: mime for mime, suffix in _SUFFIX_FOR_MIME.items()}

# How long an uploaded image stays readable. Long enough that a page opened
# now is still whole when it is looked at again, short enough that a
# long-running deployment does not accumulate uploads for ever.
_RETENTION_SECONDS = 7 * 24 * 60 * 60


class UploadImageStore:
    """The uploaded label images, as files in one directory.

    One file per evaluation, named for the evaluation and suffixed with the
    image's type. Nothing about it is held in memory, so every process reading
    the directory sees every other process's uploads, and a restart loses
    nothing.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def put(self, evaluation_id: str, mime: str, body: bytes) -> None:
        """Keep one image under the id its result page will ask for.

        An unsupported media type is not written: the upload routes refuse
        anything that is not PNG or JPEG before they get here, so reaching
        this with a third type is a programming error, not a user's.
        """
        suffix = _SUFFIX_FOR_MIME.get(mime)
        if suffix is None:
            raise ValueError(f"cannot store an image of type {mime!r}")
        if not _EVALUATION_ID.match(evaluation_id):
            raise ValueError(f"refusing to store under evaluation id {evaluation_id!r}")

        self._root.mkdir(parents=True, exist_ok=True)
        final = self._root / f"{evaluation_id}{suffix}"
        # Written beside the final name and then moved onto it, so a second
        # worker reading the directory never sees a half-written image.
        staging = self._root / f".{evaluation_id}.{uuid.uuid4().hex}.part"
        staging.write_bytes(body)
        os.replace(staging, final)
        self._forget_what_has_expired()

    def get(self, evaluation_id: str) -> tuple[str, bytes] | None:
        """The image kept for one evaluation, with its media type, or nothing.

        Nothing is the honest answer for an id that was never stored and for
        one whose image has expired; the route turns both into a 404.
        """
        if not _EVALUATION_ID.match(evaluation_id):
            return None
        for suffix, mime in _MIME_FOR_SUFFIX.items():
            path = self._root / f"{evaluation_id}{suffix}"
            try:
                return mime, path.read_bytes()
            except OSError:
                continue
        return None

    def _forget_what_has_expired(self) -> None:
        """Drop images older than the retention window.

        Run after a write rather than on a timer: the directory only grows when
        something is written to it, so that is the only moment a sweep can be
        owed. A failure here must not fail the upload that triggered it — the
        image is already stored and the page will render.
        """
        cutoff = time.time() - _RETENTION_SECONDS
        try:
            entries = list(self._root.iterdir())
        except OSError:  # pragma: no cover — the directory was just written to
            return
        for path in entries:
            try:
                if path.stat().st_mtime >= cutoff:
                    continue
                path.unlink()
            except OSError:
                continue
            _logger.debug("upload_image_expired", extra={"image_file": path.name})


def _default_store_root() -> Path:
    """Where images live when nothing overrides it.

    The machine's temporary directory, which is writable both in a clone on a
    developer's laptop and in the container this deploys as
    (`docs/decisions.md#0004` requires both), and which every worker on the
    host shares.
    """
    return Path(tempfile.gettempdir()) / "ttb-label-check" / "label-images"


_store = UploadImageStore(_default_store_root())


def _get_image_store() -> UploadImageStore:
    """The store this request reads or writes, as a dependency so a test can
    point the app at a directory of its own."""
    return _store


@router.get("/labels/{eval_id}/image")
async def upload_label_image(
    eval_id: str,
    store: UploadImageStore = Depends(_get_image_store),
) -> Response:
    """Serve the PNG or JPEG bytes uploaded for one evaluation."""
    entry = store.get(eval_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no image for evaluation {eval_id!r}")
    mime, body = entry
    return Response(content=body, media_type=mime)
