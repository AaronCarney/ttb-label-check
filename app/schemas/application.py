"""Application input identity, as the orchestrator and the services see it.

The full Application contract — applicant, formula, type_of_application, labels,
etc. — lives in `app/schemas/wire/application.py::ApplicationEnvelope`. This
module exposes only the identity surface (`application_id`, `evaluation_id`) the
orchestrator and downstream services key off. Keep it minimal, so no
orchestrator test comes to depend on a field that is not part of that identity.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.expected import BeverageClass, ExpectedValue


class Application(BaseModel):
    """Identity surface for an in-flight evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    application_id: str
    evaluation_id: str
    expected_values: tuple[ExpectedValue, ...] = ()
    # Which rule pack the label is checked against. The application declares
    # the product type, so nothing downstream has to guess it from the image.
    # Empty where no application was supplied, and then each reading keeps
    # whatever class the reader gave it.
    beverage_class: BeverageClass | None = None
