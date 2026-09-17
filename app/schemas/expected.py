"""Application-derived reference values."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BeverageClass(StrEnum):
    WINE = "wine"
    SPIRITS = "spirits"
    MALT = "malt"


class ExpectedValue(BaseModel):
    """What the application JSON says should be on the label.

    Constructed by the Application Service from the inbound application envelope
    on each evaluation; held only for the call frame.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    value: Any | None = None
    aliases: tuple[str, ...] = ()
    abv_labeled_pct: Decimal | None = None
    container_volume_ml: Decimal | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    source_cola: str | None = None
