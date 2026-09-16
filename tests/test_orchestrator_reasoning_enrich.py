import pytest
from pydantic import ValidationError

from app.orchestrator.tasks.reasoning_enrich import (
    EnrichedReasoning,
    ReasoningEnrichInput,
    apply_to_refined,
)
from app.schemas.refined import Refined


def test_input_frozen():
    inp = ReasoningEnrichInput(
        rule_id="R-WARN-001",
        template_text="Government warning text shall appear ...",
    )
    with pytest.raises((AttributeError, Exception)):
        inp.template_text = "X"


def test_schema_strict_shape():
    schema = EnrichedReasoning.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"plain_language", "citation_anchor"}
    assert "pass" not in schema["properties"]
    assert "fail" not in schema["properties"]


def test_apply_to_refined_slices_correctly():
    refined = Refined(evaluation_id="EV-001")
    result = EnrichedReasoning(plain_language="Be sure the warning is visible.", citation_anchor="27 CFR §16.21")
    out = apply_to_refined(refined, rule_id="R-WARN-001", result=result)
    assert out.tasks[0].task == "reasoning_enrich"
    assert out.tasks[0].rule_id == "R-WARN-001"
    assert out.tasks[0].payload["citation_anchor"] == "27 CFR §16.21"
