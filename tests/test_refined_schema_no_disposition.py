"""``Refined`` carries no disposition-style field.

The schema-side half of the rule that the orchestrator never decides pass or
fail. ``tests/test_orchestrator_schemas_no_disposition.py`` extends the same
check to the task output schemas."""
from app.schemas.refined import Refined


def test_refined_has_no_disposition_field():
    field_names = set(Refined.model_fields.keys())
    forbidden = {n for n in field_names if "disposition" in n.lower()}
    assert forbidden == set(), f"disposition-style fields leaked: {forbidden}"


def test_refined_has_no_pass_or_fail_field():
    field_names = set(Refined.model_fields.keys())
    assert "pass" not in field_names
    assert "fail" not in field_names


def test_refined_carries_evaluation_id():
    """Refined still keys back to the evaluation it came from."""
    assert "evaluation_id" in Refined.model_fields
