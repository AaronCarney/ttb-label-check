"""The single-label result store keeps what an override needs and nothing else.

`docs/decisions.md#0033` gave a single label's result a home on disk so an
override has something to amend. The whole envelope went into that file, and
the envelope restates what the application declared -- the applicant's name and
address among it -- beside the text read off the label. C-2 asks the product to
keep neither. These drive the real store and the real override route.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.api.ui.results import SingleResultStore
from app.schemas.audit import AuditRecord
from app.schemas.metrics import Metrics
from app.schemas.wire.disposition import (
    AISuggestionWire,
    ConfidenceBand,
    DispositionEnvelope,
    FieldEvidenceWire,
    FieldFindingWire,
    RuleFindingWire,
)

# Strings a real submission would carry. Each is distinctive enough that a
# substring search over the written file cannot match it by accident.
_ON_THE_LABEL = "MARGARET-OKONKWO-DISTILLERY-9F3A"
_ON_THE_APPLICATION = "41 Marchmont Row, Portland OR 97203"
_IN_THE_EXPLANATION = "the label says QUINTESSENCE-7B21 and the application says something else"
_MODEL_PROSE = "these two brand strings differ only in punctuation, ZEPHYR-4C88"
_THE_FILENAME = "margaret-okonkwo-scan.png"


def _envelope_with_applicant_material() -> DispositionEnvelope:
    now = datetime.now(UTC)
    return DispositionEnvelope(
        evaluation_id="ev-abc123def456",
        label_ref=_THE_FILENAME,
        disposition="needs_review",
        disposition_confidence=ConfidenceBand(band="medium", numeric=0.71),
        fields=(
            FieldFindingWire(
                field_name="name_address",
                extracted_value=_ON_THE_LABEL,
                expected_value=_ON_THE_APPLICATION,
                evidence=FieldEvidenceWire(
                    bbox=(12, 34, 56, 78),
                    crop_ref="",
                    extraction_confidence=0.66,
                ),
                rule_findings=(
                    RuleFindingWire(
                        rule_id="NAME.ADDRESS.MATCH",
                        cfr_citation="27 CFR 5.66",
                        disposition="needs_review",
                        reason_code="NAME.ADDRESS.UNCERTAIN",
                        plain_language_explanation=_IN_THE_EXPLANATION,
                    ),
                ),
                ai_suggestion=AISuggestionWire(
                    present=True,
                    task="brand_borderline",
                    text=_MODEL_PROSE,
                    model_disposition="needs_review",
                ),
                field_confidence=ConfidenceBand(band="medium", numeric=0.71),
            ),
        ),
        audit_trail=AuditRecord(
            evaluation_id="ev-abc123def456",
            rule_set_version="unknown",
            input_hash="0" * 64,
            output_hash="0" * 64,
            started_at=now,
            completed_at=now,
            per_rule_trace=(),
        ),
        metrics=Metrics(
            total_duration_ms=10, per_rule_durations_ms=(), vision_duration_ms=5
        ),
    )


def test_the_written_file_quotes_neither_the_label_nor_the_application(
    tmp_path: Path,
) -> None:
    store = SingleResultStore(tmp_path / "results")
    envelope = _envelope_with_applicant_material()

    store.put(envelope)

    written = (tmp_path / "results" / "ev-abc123def456.json").read_text()
    for material in (
        _ON_THE_LABEL,
        _ON_THE_APPLICATION,
        _IN_THE_EXPLANATION,
        _MODEL_PROSE,
        _THE_FILENAME,
    ):
        assert material not in written, f"the store wrote {material!r} to disk"


def test_what_an_override_needs_survives_the_blanking(tmp_path: Path) -> None:
    store = SingleResultStore(tmp_path / "results")

    store.put(_envelope_with_applicant_material())
    kept = store.get("ev-abc123def456")

    assert kept is not None
    # The endpoint reads exactly these three to build and attach an override.
    assert kept.evaluation_id == "ev-abc123def456"
    assert kept.disposition == "needs_review"
    assert kept.audit_trail.evaluation_id == "ev-abc123def456"
    # And the shape a reader needs to make sense of the trail is still there.
    assert kept.fields[0].field_name == "name_address"
    assert kept.fields[0].rule_findings[0].cfr_citation == "27 CFR 5.66"
    assert kept.fields[0].rule_findings[0].reason_code == "NAME.ADDRESS.UNCERTAIN"
    assert kept.fields[0].evidence.bbox == (12, 34, 56, 78)


def test_the_caller_s_own_envelope_still_carries_its_values(tmp_path: Path) -> None:
    """The envelope handed to `put` is the one rendered to the page."""
    store = SingleResultStore(tmp_path / "results")
    envelope = _envelope_with_applicant_material()

    store.put(envelope)

    assert envelope.fields[0].extracted_value == _ON_THE_LABEL
    assert envelope.fields[0].expected_value == _ON_THE_APPLICATION
    assert envelope.label_ref == _THE_FILENAME
