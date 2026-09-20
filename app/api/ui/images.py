"""The label image a result page shows: where it is kept, and the route that
serves it.

A result page renders ``<img src="/labels/{evaluation_id}/image">``, so the
bytes the reviewer uploaded have to still be somewhere when the browser asks for
them a moment later — and when the reviewer opens that page again tomorrow, or
refreshes it after the service restarts, or lands on a different worker.

They are kept as files, one per face of the evaluated label, under the machine's
temporary directory. See `docs/decisions.md#0018` for what that choice buys and
what it does not. Every face is kept, not just the front: a finding read off the
back is shown against the back, and a reviewer who cannot see the photograph a
rejection came from cannot check it.
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

# Which face of the label a file holds. The four the `Label` schema allows, and
# nothing else reaches a filename. The separator is a dot because `_EVALUATION_ID`
# forbids one, so no evaluation id can be mistaken for an id plus a face.
_FACE_TAGS = ("front", "back", "neck", "side")
DEFAULT_FACE = "front"

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

    def put(self, evaluation_id: str, mime: str, body: bytes, face: str = DEFAULT_FACE) -> None:
        """Keep one face of one evaluation's label, under the id its result
        page will ask for.

        An unsupported media type is not written: the upload routes refuse
        anything that is not PNG or JPEG before they get here, so reaching
        this with a third type is a programming error, not a user's. The same
        goes for a face the `Label` schema does not allow.
        """
        suffix = _SUFFIX_FOR_MIME.get(mime)
        if suffix is None:
            raise ValueError(f"cannot store an image of type {mime!r}")
        if not _EVALUATION_ID.match(evaluation_id):
            raise ValueError(f"refusing to store under evaluation id {evaluation_id!r}")
        if face not in _FACE_TAGS:
            raise ValueError(f"refusing to store under face {face!r}")

        self._root.mkdir(parents=True, exist_ok=True)
        final = self._root / f"{evaluation_id}.{face}{suffix}"
        # Written beside the final name and then moved onto it, so a second
        # worker reading the directory never sees a half-written image.
        staging = self._root / f".{evaluation_id}.{uuid.uuid4().hex}.part"
        staging.write_bytes(body)
        os.replace(staging, final)
        self._forget_what_has_expired()

    def get(self, evaluation_id: str, face: str = DEFAULT_FACE) -> tuple[str, bytes] | None:
        """One face of one evaluation's label, with its media type, or nothing.

        Nothing is the honest answer for an id that was never stored, for one
        that is not an id at all, for a face that is not a face, and for one
        whose file the sweep has already dropped; the route turns each into a
        404. An expired image still reads until that sweep runs, because the
        sweep runs on a write: the retention window bounds what the directory
        holds, not what a reader may see. A file that exists but cannot be read
        is answered the same way.
        """
        if not _EVALUATION_ID.match(evaluation_id) or face not in _FACE_TAGS:
            return None
        for suffix, mime in _MIME_FOR_SUFFIX.items():
            path = self._root / f"{evaluation_id}.{face}{suffix}"
            try:
                return mime, path.read_bytes()
            except OSError:
                continue
        return None

    def faces(self, evaluation_id: str) -> tuple[str, ...]:
        """Which faces of this evaluation's label are on disk, in face order.

        What the result page asks before it offers a reviewer a second picture
        to look at.
        """
        if not _EVALUATION_ID.match(evaluation_id):
            return ()
        return tuple(tag for tag in _FACE_TAGS if self.get(evaluation_id, tag) is not None)

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


# What each face is called on the page. The tag is the engine's word; this is
# the reviewer's.
FACE_CAPTIONS = {
    "front": "Front",
    "back": "Back",
    "neck": "Neck",
    "side": "Side",
}


@router.get("/labels/{eval_id}/faces")
async def upload_label_faces(
    eval_id: str,
    store: UploadImageStore = Depends(_get_image_store),
) -> dict:
    """Which photographs of this evaluation's label the store holds, front first.

    The results page asks before it renders any, because the only other way to
    find out is to request an image and see whether it 404s, which puts a
    broken picture on the page of a product whose job is to be trusted. A label
    whose images have passed their retention window answers with an empty list
    rather than 404: the evaluation is real, and it is its photographs that are
    gone.
    """
    return {
        "faces": [
            {
                "tag": tag,
                "caption": FACE_CAPTIONS.get(tag, tag.title()),
                "url": f"/labels/{eval_id}/image?face={tag}",
            }
            for tag in store.faces(eval_id)
        ]
    }


@router.get("/labels/{eval_id}/image")
async def upload_label_image(
    eval_id: str,
    face: str = DEFAULT_FACE,
    store: UploadImageStore = Depends(_get_image_store),
) -> Response:
    """Serve the PNG or JPEG bytes of one face of one evaluation's label.

    `?face=` selects which. It defaults to the front, so every link written
    before a label could have more than one face still resolves.
    """
    entry = store.get(eval_id, face)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no {face} image for evaluation {eval_id!r}")
    mime, body = entry
    return Response(content=body, media_type=mime)
