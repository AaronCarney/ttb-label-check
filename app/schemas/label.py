"""Label envelope — what the Vision Extractor consumes.

A label is a document and its faces are its pages. A COLA is filed with every
face of the label — front, back, neck, side — and the reviewer's question is
about the label, not about one photograph of it: a brand printed on the front
and a government warning printed on the back are facts about the same product.
So the image bytes, the content-type discriminator, the face_tag and the
optional dimensions live on `Face`, and a `Label` carries one or more of them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The two media types this service reads. Named rather than written inline on
# `Face.content_type` so the sniffers that produce one can say so in their own
# signature, instead of handing a bare `str` to a field that accepts two values.
ImageMediaType = Literal["image/jpeg", "image/png"]

# Which panel of the label a face is a photograph of. The same four values the
# application envelope's `LabelRef.face_tag` uses.
FaceTag = Literal["front", "back", "neck", "side"]


class Dimensions(BaseModel):
    """Physical dimensions of a label image."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    width_px: int = Field(ge=1)
    height_px: int = Field(ge=1)
    dpi: int | None = Field(default=None, ge=1)


class Face(BaseModel):
    """One photograph of one panel of a label."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    image_bytes: bytes
    content_type: ImageMediaType
    face_tag: FaceTag
    dimensions: Dimensions | None = None


class Label(BaseModel):
    """Label envelope consumed by VisionExtractor.extract().

    `faces` is ordered, and that order is the order the hashes and the cache key
    concatenate in, so a label is compared against the faces it was sent with.
    At least one face: a label with no image is nothing to read.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    label_id: str
    batch_id: str
    faces: tuple[Face, ...] = Field(min_length=1)
