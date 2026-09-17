"""Label envelope — what the Vision Extractor consumes.

Carries image bytes, the content-type discriminator, optional dimensions
(applicant-supplied or extracted from EXIF), and the face_tag that distinguishes
front/back/neck/side panels.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The two media types this service reads. Named rather than written inline on
# `Label.content_type` so the sniffers that produce one can say so in their own
# signature, instead of handing a bare `str` to a field that accepts two values.
ImageMediaType = Literal["image/jpeg", "image/png"]


class Dimensions(BaseModel):
    """Physical dimensions of the label image."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    width_px: int = Field(ge=1)
    height_px: int = Field(ge=1)
    dpi: int | None = Field(default=None, ge=1)


class Label(BaseModel):
    """Label envelope consumed by VisionExtractor.extract()."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label_id: str
    batch_id: str
    image_bytes: bytes
    content_type: ImageMediaType
    face_tag: Literal["front", "back", "neck", "side"]
    dimensions: Dimensions | None = None
