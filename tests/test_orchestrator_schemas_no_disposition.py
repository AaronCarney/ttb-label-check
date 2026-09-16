"""The orchestrator never decides pass or fail.

Structural test: no orchestrator-touched schema may carry a disposition, pass
or fail field, so a misbehaving orchestrator cannot return a disposition —
there is no field on the schema to put one in. This is the canary for a future
schema change that adds one by accident.
"""
import json

import pytest

from app.orchestrator.tasks.brand_disambig import BrandDisambigResult
from app.orchestrator.tasks.reasoning_enrich import EnrichedReasoning
from app.orchestrator.tasks.ocr_reconcile import OcrReconcileResult
from app.schemas.refined import Refined, TaskSlice


def _flatten_literal_values(field_info) -> set[str]:
    """Pull all Literal arg strings out of a Pydantic FieldInfo annotation."""
    annot = field_info.annotation
    values: set[str] = set()
    # Recurse on Union/Optional/Literal generics.
    args = getattr(annot, "__args__", ())
    for a in args:
        values |= _flatten_literal_values_from_type(a)
    values |= _flatten_literal_values_from_type(annot)
    return values


def _flatten_literal_values_from_type(t) -> set[str]:
    import typing
    out: set[str] = set()
    origin = typing.get_origin(t)
    if origin is typing.Literal:
        for v in typing.get_args(t):
            if isinstance(v, str):
                out.add(v)
    args = getattr(t, "__args__", ())
    for a in args:
        out |= _flatten_literal_values_from_type(a)
    return out


@pytest.mark.parametrize("schema_cls", [Refined, TaskSlice, BrandDisambigResult, EnrichedReasoning, OcrReconcileResult])
def test_no_disposition_field(schema_cls):
    field_names = set(schema_cls.model_fields.keys())
    forbidden = {n for n in field_names if "disposition" in n.lower()}
    assert forbidden == set(), f"{schema_cls.__name__}: disposition-style field leaked: {forbidden}"


@pytest.mark.parametrize("schema_cls", [Refined, TaskSlice, BrandDisambigResult, EnrichedReasoning, OcrReconcileResult])
def test_no_pass_or_fail_field(schema_cls):
    field_names = set(schema_cls.model_fields.keys())
    assert "pass" not in field_names, f"{schema_cls.__name__}: 'pass' field leaked"
    assert "fail" not in field_names, f"{schema_cls.__name__}: 'fail' field leaked"


@pytest.mark.parametrize("schema_cls", [BrandDisambigResult, EnrichedReasoning, OcrReconcileResult])
def test_no_fail_in_literal_values(schema_cls):
    """No task-output schema may carry a Literal value 'fail' anywhere."""
    leaks: list[str] = []
    for fname, finfo in schema_cls.model_fields.items():
        values = _flatten_literal_values(finfo)
        if "fail" in values:
            leaks.append(f"{fname}: {values}")
    assert leaks == [], f"{schema_cls.__name__}: 'fail' Literal value leaked: {leaks}"


@pytest.mark.parametrize(
    "schema_cls",
    [Refined, TaskSlice, BrandDisambigResult, EnrichedReasoning, OcrReconcileResult],
)
def test_no_fail_or_disposition_substring_in_json_schema(schema_cls):
    """Defense-in-depth: serialize the JSON Schema and grep for forbidden tokens.

    `_flatten_literal_values` only walks direct field annotations; if a future
    schema embeds a sub-model whose own field carries 'fail'/'disposition' as a
    Literal, the recursion misses it. Serializing the JSON Schema closes that
    gap cheaply: the rendered schema includes nested `$defs` for any embedded
    BaseModel, so substring presence is a hard signal of a leak.
    """
    rendered = json.dumps(schema_cls.model_json_schema(), sort_keys=True)
    # `pass` is excluded from this substring grep — it appears commonly in
    # schema metadata strings ("passes", "passenger", etc.) and the structural
    # field-name/Literal-value tests above already cover it precisely.
    for forbidden in ("\"fail\"", "disposition"):
        assert forbidden not in rendered, (
            f"{schema_cls.__name__}: forbidden substring {forbidden!r} surfaced in JSON Schema"
        )
