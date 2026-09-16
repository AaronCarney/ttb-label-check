"""The application-input envelope: what an agent submits for one label.

``extra='forbid'`` — unknown keys are rejected at the boundary.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Address(BaseModel):
    model_config = ConfigDict(extra="forbid")

    street: str
    city: str
    state: str
    zip: str
    country: str


class Applicant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    address: Address
    mailing_address: Address | None = None


class Formula(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ttb_formula_id: str
    approval_date: date


class TypeOfApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cola: bool
    exemption: bool
    exemption_state: str | None = None
    distinctive_bottle: bool
    bottle_capacity: str | None = None
    resubmission: bool
    prior_ttb_id: str | None = None


class LabelDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width_px: int
    height_px: int
    dpi: int


class LabelRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_ref: str
    face_tag: Literal["front", "back", "neck", "side"]
    dimensions: LabelDimensions


class ApplicationEnvelope(BaseModel):
    """The application-input contract.

    Source: TTB Form 5100.31 rev. 04/2023 items 1–18 + ``labels[]``.
    """

    model_config = ConfigDict(extra="forbid")

    rep_id: str | None = None
    permit_number: str
    source_of_product: Literal["domestic", "imported"]
    serial_number: str = Field(max_length=6)
    type_of_product: Literal["wine", "distilled_spirits", "malt_beverages"]
    brand_name: str
    fanciful_name: str | None = None
    applicant: Applicant
    formula: Formula | None = None
    grape_varietals: tuple[str, ...] | None = None
    wine_appellation: str | None = None
    phone: str
    email: str | None = None
    type_of_application: TypeOfApplication
    blown_branded_embossed_text: str | None = None
    date_of_application: date
    applicant_signature: str | None = None
    applicant_print_name: str
    perjury_attested: Literal[True]
    labels: tuple[LabelRef, ...]
