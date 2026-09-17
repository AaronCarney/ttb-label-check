"""Envelope confidence aggregates as the minimum across its fields, so the
weakest reading sets the overall band."""

from app.schemas.wire.disposition import (
    AISuggestionWire,
    ConfidenceBand,
    FieldEvidenceWire,
    FieldFindingWire,
    RuleFindingWire,
)
from app.services.aggregation import min_aggregate_confidence


def _field(name, numeric, band):
    return FieldFindingWire(
        field_name=name,
        extracted_value="x",
        expected_value="x",
        evidence=FieldEvidenceWire(
            bbox=(0, 0, 10, 10), crop_ref="c", extraction_confidence=numeric
        ),
        rule_findings=(
            RuleFindingWire(
                rule_id="R",
                cfr_citation="27 CFR §x",
                disposition="pass",
                reason_code="OK",
                plain_language_explanation="ok",
            ),
        ),
        ai_suggestion=AISuggestionWire(present=False),
        field_confidence=ConfidenceBand(band=band, numeric=numeric),
    )


def test_min_aggregation_across_fields():
    fields = (
        _field("brand_name", 0.95, "high"),
        _field("class_type", 0.6, "medium"),
        _field("alcohol_content", 0.4, "low"),
    )
    band, numeric = min_aggregate_confidence(fields)
    assert numeric == 0.4
    assert band == "low"


def test_empty_fields_returns_low_zero():
    band, numeric = min_aggregate_confidence(())
    assert band == "low" and numeric == 0.0
