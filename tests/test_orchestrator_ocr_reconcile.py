import pytest
from pydantic import ValidationError

from app.orchestrator.tasks.ocr_reconcile import (
    OcrReconcileInput,
    OcrReconcileResult,
    apply_to_refined,
)
from app.schemas.refined import Refined


def test_input_frozen():
    inp = OcrReconcileInput(
        rule_id="R-OCR-001",
        field_id="brand_name",
        candidate_reads=("ACME BOURBON", "ACAE BOURBON"),
    )
    with pytest.raises((AttributeError, Exception)):
        inp.field_id = "X"


def test_schema_strict_shape():
    schema = OcrReconcileResult.model_json_schema()
    assert schema["additionalProperties"] is False
    # `winner` is optional (None ⇒ orchestrator abstains), so only `reasoning` required.
    assert "reasoning" in schema["required"]
    assert "pass" not in schema["properties"]
    assert "fail" not in schema["properties"]


def test_winner_can_be_none():
    """winner=None means the task abstains, and the check routes to needs_review."""
    result = OcrReconcileResult(winner=None, reasoning="ambiguous; defer to needs_review")
    assert result.winner is None


def test_apply_to_refined_slices_correctly():
    refined = Refined(evaluation_id="EV-001")
    result = OcrReconcileResult(winner="ACME BOURBON", reasoning="majority of OCR votes")
    out = apply_to_refined(refined, rule_id="R-OCR-001", result=result)
    assert out.tasks[0].task == "ocr_reconcile"
    assert out.tasks[0].payload["winner"] == "ACME BOURBON"
