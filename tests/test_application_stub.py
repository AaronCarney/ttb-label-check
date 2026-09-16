"""Application — the fields every other layer relies on being there.

The richer behaviour is covered with the evaluator and the batch worker; this
file only pins the constructor surface the orchestrator seam imports.
"""
from app.schemas.application import Application


def test_application_constructs_with_required_fields():
    a = Application(application_id="A-001", evaluation_id="EV-001")
    assert a.application_id == "A-001"
    assert a.evaluation_id == "EV-001"


def test_application_is_frozen_extra_forbid():
    a = Application(application_id="A-001", evaluation_id="EV-001")
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Application(application_id="A-001", evaluation_id="EV-001", unknown_field="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        a.application_id = "A-002"  # type: ignore[misc]
