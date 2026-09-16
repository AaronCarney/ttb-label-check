"""The error contract returned at the API boundary."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ErrorEnvelope(BaseModel):
    """Boundary error envelope.

    Reason codes follow the ``BIN.SUB.SPECIFIC[.QUALIFIER]`` grammar.
    """

    model_config = ConfigDict(extra="forbid")

    error_kind: Literal["rejected_input", "engine_failure", "partial_completion"]
    reason_code: str
    message: str
    details: dict[str, Any]
