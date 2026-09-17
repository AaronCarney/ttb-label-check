"""How a set of uploaded files says which of them are one label.

A browser's file picker returns a flat list of names and nothing else: no
folders, no grouping, no way for a reviewer to say "these two are the same
product". The only thing they control is what the files are called, so that is
what this reads.

**The convention is the one the product already emits.** `/batches/sample.zip`
has always named its entries `{ttbid}-front.jpg`. It simply never shipped a
`-back` to go with it and never read the suffix back. A stem ending `-front` or
`-back`, in any case, is half of a label; the two halves of one stem are one
label. Every other filename is a label on its own, exactly as before, so a
reviewer who names their files anything else sees no change at all.

Two mistakes a reviewer can make, and what happens:

- **Two files claiming the same face of one stem.** The extra one becomes a
  label of its own. Dropping it silently would mean an uploaded file with no
  result, which is the worse answer.
- **A back with no front.** It is one label carrying a back. Calling it a front
  instead would have the reader report that a back label has no brand on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

from app.schemas.label import FaceTag, ImageMediaType

_FACE_TAGS: tuple[FaceTag, ...] = ("front", "back")
# The order a label's faces are held in, which is not the order they were
# picked in: the quality gate stops at the first unusable face and names it, so
# the front has to be looked at first whatever the filesystem handed over.
_FACE_ORDER = {tag: index for index, tag in enumerate(_FACE_TAGS)}

assert set(_FACE_TAGS) <= set(get_args(FaceTag))


@dataclass(frozen=True)
class PlannedFace:
    """One uploaded file, placed on one face of one label."""

    face_tag: FaceTag
    filename: str
    body: bytes
    content_type: ImageMediaType


@dataclass(frozen=True)
class PlannedLabel:
    """What one row of the batch is about.

    `faces` is empty for a file that is not a PNG or JPEG: it is still a row,
    refused by name, so a reviewer is told which file was not read and every
    other file still has an answer (R13, `docs/decisions.md#0020`).
    """

    name: str
    faces: tuple[PlannedFace, ...]
    refused_filename: str | None = None


def split_face_suffix(filename: str) -> tuple[str, FaceTag] | None:
    """`("lucy", "front")` for `lucy-front.jpg`, or None for a plain name.

    The extension is kept out of the stem so `lucy-front.jpg` and
    `lucy-back.png` still pair: a reviewer photographing two panels may well
    save them differently.
    """
    stem, _, _extension = filename.rpartition(".")
    if not stem:
        stem = filename
    head, separator, tail = stem.rpartition("-")
    if not separator or not head:
        return None
    tag = tail.strip().lower()
    if tag not in _FACE_TAGS:
        return None
    return head, tag  # type: ignore[return-value]


def plan_labels(
    uploads: list[tuple[str, bytes, ImageMediaType | None]],
) -> list[PlannedLabel]:
    """The labels one batch upload is about, in the order the files arrived.

    `uploads` is `(filename, body, media_type)` per file, with a media type of
    None for a file that is not an image.
    """
    planned: list[PlannedLabel] = []
    # Where each stem's label sits in `planned`, so a back arriving after its
    # front joins the label the front already opened rather than starting one.
    # Keyed on the folded stem, because a reviewer who types `LUCY-FRONT.PNG`
    # and `lucy-back.png` means one label.
    opened: dict[str, int] = {}

    for filename, body, media_type in uploads:
        if media_type is None:
            planned.append(PlannedLabel(name=filename, faces=(), refused_filename=filename))
            continue

        split = split_face_suffix(filename)
        if split is None:
            planned.append(
                PlannedLabel(
                    name=filename,
                    faces=(
                        PlannedFace(
                            face_tag="front",
                            filename=filename,
                            body=body,
                            content_type=media_type,
                        ),
                    ),
                )
            )
            continue

        stem, face_tag = split
        face = PlannedFace(face_tag=face_tag, filename=filename, body=body, content_type=media_type)
        index = opened.get(stem.casefold())
        if index is None:
            opened[stem.casefold()] = len(planned)
            planned.append(PlannedLabel(name=stem, faces=(face,)))
            continue

        held = planned[index]
        if any(existing.face_tag == face_tag for existing in held.faces):
            # A second file claiming a face this label already has. It is its
            # own label rather than a discard, and it does not open a stem:
            # a third file of the same face would otherwise join *it*.
            planned.append(PlannedLabel(name=stem, faces=(face,)))
            continue

        planned[index] = PlannedLabel(
            name=held.name,
            faces=tuple(sorted((*held.faces, face), key=lambda f: _FACE_ORDER[f.face_tag])),
        )

    return planned
