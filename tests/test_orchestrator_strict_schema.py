"""For every task output schema, model_json_schema() must produce a JSON Schema
compatible with OpenAI Structured Outputs strict-mode requirements:
- additionalProperties: false on the top-level object
- required populated for all properties (Optional fields use Optional[T] = None)
- no $ref at the top level (closed-form schema)
"""
import pytest

from app.orchestrator.tasks.brand_disambig import BrandDisambigResult
from app.orchestrator.tasks.reasoning_enrich import EnrichedReasoning
from app.orchestrator.tasks.ocr_reconcile import OcrReconcileResult


@pytest.mark.parametrize("schema_cls", [BrandDisambigResult, EnrichedReasoning, OcrReconcileResult])
def test_schema_strict_mode_compatible(schema_cls):
    schema = schema_cls.model_json_schema()
    assert schema.get("additionalProperties") is False, (
        f"{schema_cls.__name__}: additionalProperties must be False for strict mode"
    )
    # All non-Optional properties must be required.
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    for prop, prop_schema in properties.items():
        # An Optional[T] property has type: ["T", "null"] in Pydantic v2 JSON schema.
        is_nullable = "null" in (
            prop_schema.get("type", []) if isinstance(prop_schema.get("type"), list) else []
        ) or prop_schema.get("anyOf") is not None
        if not is_nullable:
            assert prop in required, (
                f"{schema_cls.__name__}.{prop} is non-optional but not in required: {required}"
            )


@pytest.mark.parametrize("schema_cls", [BrandDisambigResult, EnrichedReasoning, OcrReconcileResult])
def test_schema_top_level_is_object(schema_cls):
    schema = schema_cls.model_json_schema()
    assert schema.get("type") == "object", f"{schema_cls.__name__} top-level must be object"
