import pytest
from pydantic import ValidationError

from app.orchestrator.tasks.brand_disambig import (
    BrandDisambigInput,
    BrandDisambigResult,
    apply_to_refined,
    to_input,
)
from app.schemas.refined import Refined


def test_input_dataclass_frozen():
    inp = BrandDisambigInput(
        rule_id="R-BRAND-001",
        applicant_brand="STONE'S THROW BOURBON",
        candidate_matches=("STONES THROW BOURBON", "STONE THROW BOURBON"),
    )
    with pytest.raises((AttributeError, Exception)):
        inp.applicant_brand = "X"  # frozen


def test_result_schema_strict_shape():
    schema = BrandDisambigResult.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"decision", "justification"}
    # No pass/fail in the field names: the orchestrator decides no outcome.
    assert "pass" not in schema["properties"]
    assert "fail" not in schema["properties"]


def test_result_decision_literal_enforced():
    with pytest.raises(ValidationError):
        BrandDisambigResult(decision="fail", justification="...")  # type: ignore[arg-type]


def test_apply_to_refined_slices_correctly():
    refined = Refined(evaluation_id="EV-001")
    result = BrandDisambigResult(decision="match", justification="phonetic equivalence")
    out = apply_to_refined(refined, rule_id="R-BRAND-001", result=result)
    assert len(out.tasks) == 1
    assert out.tasks[0].task == "brand_disambig"
    assert out.tasks[0].rule_id == "R-BRAND-001"
    assert out.tasks[0].payload == {"decision": "match", "justification": "phonetic equivalence"}
