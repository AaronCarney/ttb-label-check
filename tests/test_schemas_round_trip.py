"""Internal & wire schemas round-trip a representative payload byte-identically."""

from __future__ import annotations

import json
from datetime import UTC

import pytest


def test_extracted_field_observation_round_trip() -> None:
    from app.schemas.expected import BeverageClass
    from app.schemas.extracted import (
        Evidence,
        EvidenceSource,
        FieldObservation,
        MatchKind,
    )

    obs = FieldObservation(
        field_id="brand",
        beverage_class=BeverageClass.SPIRITS,
        observed_value="Stone's Throw",
        evidence=(
            Evidence(
                field_id="brand",
                source=EvidenceSource.OCR,
                page_id=None,
                panel="front",
                image_uri=None,
                bbox=(120, 240, 800, 120),
                extracted_text="Stone's Throw",
                normalized_text="stones throw",
                matched_against_value="Stone's Throw",
                match_kind=MatchKind.NORMALIZED,
                match_score=None,
                confidence=0.96,
                notes=None,
            ),
        ),
        timestamp_ms=1714579200000,
        upstream_meta={"engine": "paddleocr-3.0", "snapshot": "v1"},
    )
    obs2 = FieldObservation.model_validate_json(obs.model_dump_json())
    assert obs2 == obs


def test_extracted_models_are_frozen() -> None:
    from app.schemas.extracted import Evidence, EvidenceSource, MatchKind

    ev = Evidence(
        field_id="brand",
        source=EvidenceSource.OCR,
        page_id=None,
        panel=None,
        image_uri=None,
        bbox=(0, 0, 1, 1),
        extracted_text=None,
        normalized_text=None,
        matched_against_value=None,
        match_kind=MatchKind.NONE,
        match_score=None,
        confidence=0.5,
        notes=None,
    )
    with pytest.raises(Exception):  # ValidationError or FrozenInstanceError-like
        ev.confidence = 0.9  # type: ignore[misc]


def test_extracted_models_forbid_extra_fields() -> None:
    from pydantic import ValidationError

    from app.schemas.extracted import Evidence, EvidenceSource, MatchKind

    with pytest.raises(ValidationError):
        Evidence(
            field_id="brand",
            source=EvidenceSource.OCR,
            page_id=None,
            panel=None,
            image_uri=None,
            bbox=None,
            extracted_text=None,
            normalized_text=None,
            matched_against_value=None,
            match_kind=MatchKind.NONE,
            match_score=None,
            confidence=0.5,
            notes=None,
            unexpected_extra="bad",  # type: ignore[call-arg]
        )


def test_reason_code_grammar() -> None:
    from app.schemas.rejection import ReasonCode

    assert ReasonCode.validate_grammar("BRAND.NAME.MATCH") == "BRAND.NAME.MATCH"
    assert (
        ReasonCode.validate_grammar("ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND")
        == "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND"
    )
    assert (
        ReasonCode.validate_grammar("ENGINE.MODEL.UNAVAILABLE.LLM_OUTPUT_INVALID")
        == "ENGINE.MODEL.UNAVAILABLE.LLM_OUTPUT_INVALID"
    )
    import pytest

    for bad in ["lower.case.code", "TOO.SHORT", "FIVE.PARTS.IS.TOO.MANY.NOPE", ""]:
        with pytest.raises(ValueError):
            ReasonCode.validate_grammar(bad)


def test_validation_result_round_trip() -> None:
    from app.schemas.expected import BeverageClass
    from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult

    vr = ValidationResult(
        rule_id="common.brand.exact_or_normalized",
        cfr_citation="27 CFR §4.33(a)",
        beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.PASS,
        severity=Severity.INFO,
        reason_code="BRAND.NAME.MATCH",
        aggregated_confidence=0.94,
        evidence=(),
        expected=None,
        observed=None,
        message="Brand name matches.",
        engine_meta=EngineMeta(
            engine_version="0.1.0",
            rule_pack_version="0.1.0",
            rule_pack="common",
            started_at_ms=1714579200000,
            elapsed_ms=8,
        ),
    )
    vr2 = ValidationResult.model_validate_json(vr.model_dump_json())
    assert vr2 == vr


def test_audit_record_round_trip() -> None:
    from datetime import datetime

    from app.schemas.audit import AuditRecord, PerRuleTraceEntry

    rec = AuditRecord(
        evaluation_id="00000000-0000-4000-8000-000000000001",
        rule_set_version="0.1.0",
        model_version="gpt-4o-2024-08-06",
        prompt_version="v1",
        input_hash="0" * 64,
        output_hash="1" * 64,
        started_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 1, 12, 0, 1, 230000, tzinfo=UTC),
        per_rule_trace=(
            PerRuleTraceEntry(
                rule_id="common.brand.exact_or_normalized",
                disposition="pass",
                evidence_ref="crop-001",
            ),
        ),
        overrides=(),
    )
    rec2 = AuditRecord.model_validate_json(rec.model_dump_json())
    assert rec2 == rec


def test_per_rule_trace_entry_has_no_duration_ms() -> None:
    """Per-rule durations live in the metrics block, not in the audit trail."""
    from app.schemas.audit import PerRuleTraceEntry

    fields = PerRuleTraceEntry.model_fields
    assert "duration_ms" not in fields, (
        "per-rule duration belongs in app.schemas.metrics, not in audit_trail.per_rule_trace[]."
    )
    assert set(fields.keys()) == {"rule_id", "disposition", "evidence_ref"}


def test_metrics_round_trip() -> None:
    from app.schemas.metrics import Metrics, PerRuleDurationEntry

    m = Metrics(
        total_duration_ms=1230,
        per_rule_durations_ms=(
            PerRuleDurationEntry(rule_id="common.brand.exact_or_normalized", duration_ms=8),
        ),
        vision_duration_ms=720,
    )
    m2 = Metrics.model_validate_json(m.model_dump_json())
    assert m2 == m


def test_rule_set_round_trip() -> None:
    from app.schemas.expected import BeverageClass
    from app.schemas.rejection import Severity
    from app.schemas.rules import (
        AssetRef,
        DecisionTable,
        MatchPolicy,
        ReasonCodeEntry,
        RuleDefinition,
        RuleSet,
    )

    rule = RuleDefinition(
        rule_id="spirits.alcohol.matches_application",
        cfr_citation="27 CFR §5.65",
        applies_to_classes=(BeverageClass.SPIRITS,),
        reason_code="ALCOHOL_CONTENT.MATCH.APPLICATION_LABEL_DISAGREE",
        severity=Severity.REJECT,
        match_policy=MatchPolicy.EXACT,
        validator="quantity_match",
        evidence_required=("abv",),
        confidence_floor=0.5,
        parameters={
            "amount_field": "abv_labeled_pct",
            "needs_review_reason_code": "ALCOHOL_CONTENT.MATCH.NEEDS_REVIEW",
            "disagreement_reason_code": "ALCOHOL_CONTENT.MATCH.APPLICATION_LABEL_DISAGREE",
        },
        tolerance=None,
        decision_table=None,
        decision_table_ref=None,
        asset=None,
        effective_date="2022-02-09",
        supersedes=(),
        rule_pack_version="0.1.0",
        rule_pack="spirits",
        test_fixtures=("F-SPIRITS-ALC-APP-MATCH-01",),
        disabled=False,
        notes=None,
    )

    rs = RuleSet(
        version="0.1.0",
        effective_date="2026-09-15",
        rules=(rule,),
        reason_codes={
            "ALCOHOL_CONTENT.MATCH.APPLICATION_LABEL_DISAGREE": ReasonCodeEntry(
                description=(
                    "Label alcohol content is not the alcohol content the application declared."
                ),
                cfr_anchors=(),
                severity=Severity.REJECT,
            ),
        },
        assets={
            "warning_16_21": AssetRef(
                path="assets/warnings/govt_warning_16_21.txt",
                sha256="0" * 64,
            ),
        },
        decision_tables={
            "cpi_16_22_a_4": DecisionTable(
                interpolation="none",
                entries=({"min_ml": 50, "max_ml": 100, "cpi": 0.4},),
            ),
        },
    )
    rs2 = RuleSet.model_validate_json(rs.model_dump_json())
    assert rs2 == rs


def test_match_policy_enum_values() -> None:
    from app.schemas.rules import MatchPolicy

    assert MatchPolicy("tolerance") is MatchPolicy.TOLERANCE
    assert MatchPolicy("verbatim_hash") is MatchPolicy.VERBATIM_HASH
    assert MatchPolicy("fuzzy") is MatchPolicy.FUZZY


def test_batch_state_round_trip() -> None:
    from datetime import datetime

    from app.schemas.batch import BatchInFlightState, BatchItem, ItemState

    item = BatchItem(
        label_id="label-001",
        application_ref="app-001",
        state=ItemState.QUEUED,
        result=None,
        enqueued_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC),
    )
    state = BatchInFlightState(
        batch_id="00000000-0000-4000-8000-00000000b001",
        agent_id="session-abc",
        items=(item,),
        current_index=0,
        lookahead_k=3,
    )
    s2 = BatchInFlightState.model_validate_json(state.model_dump_json())
    assert s2 == state


def test_item_state_transitions_documented() -> None:
    from app.schemas.batch import ItemState

    expected = {
        ItemState.QUEUED,
        ItemState.PROCESSING,
        ItemState.READY,
        ItemState.PRESENTED,
        ItemState.REVIEWED,
        ItemState.DISPOSED,
        ItemState.FAILED,
    }
    assert set(ItemState) == expected


def test_call_record_round_trip() -> None:
    from datetime import datetime

    from app.schemas.calls import CallRecord

    rec = CallRecord(
        ts=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC),
        batch_id="b1",
        label_id="l1",
        stage="vision.cloud_read",
        request={"prompt_hash": "abc", "params": {"temperature": 0}},
        response={"text": "match"},
        latency_ms=420,
        model="gpt-4o-2024-08-06",
        provider="openai",
        prompt_version="v1",
        output_hash="0" * 64,
    )
    rec2 = CallRecord.model_validate_json(rec.model_dump_json())
    assert rec2 == rec


def test_application_envelope_round_trip(wire_fixtures_dir) -> None:

    from app.schemas.wire.application import ApplicationEnvelope

    raw = json.loads((wire_fixtures_dir / "application.json").read_text())
    env = ApplicationEnvelope.model_validate(raw)
    rt = json.loads(env.model_dump_json(exclude_none=False))
    # Compare on the keys present in the input — model_dump emits canonical order;
    # round-trip means input keys/values survive a parse + dump cycle.
    assert rt["permit_number"] == raw["permit_number"]
    assert rt["brand_name"] == raw["brand_name"]
    assert rt["labels"][0]["face_tag"] == raw["labels"][0]["face_tag"]


def test_application_envelope_rejects_extra_keys() -> None:
    import pytest
    from pydantic import ValidationError

    from app.schemas.wire.application import ApplicationEnvelope

    with pytest.raises(ValidationError):
        ApplicationEnvelope.model_validate({"permit_number": "x", "rogue_key": 1})


def test_disposition_envelope_round_trip(wire_fixtures_dir) -> None:

    from app.schemas.wire.disposition import DispositionEnvelope

    raw = json.loads((wire_fixtures_dir / "disposition.json").read_text())
    env = DispositionEnvelope.model_validate(raw)
    dumped = json.loads(env.model_dump_json())
    assert dumped["disposition"] == raw["disposition"]
    assert dumped["audit_trail"]["evaluation_id"] == raw["audit_trail"]["evaluation_id"]
    # audit_trail.per_rule_trace[] entries must NOT carry duration_ms.
    for entry in dumped["audit_trail"]["per_rule_trace"]:
        assert "duration_ms" not in entry
    # Durations live in the metrics block.
    assert "metrics" in dumped
    assert dumped["metrics"]["per_rule_durations_ms"][0]["duration_ms"] == 8


def test_batch_envelope_round_trip(wire_fixtures_dir) -> None:

    from app.schemas.wire.batch import BatchEnvelope

    raw = json.loads((wire_fixtures_dir / "batch.json").read_text())
    env = BatchEnvelope.model_validate(raw)
    dumped = json.loads(env.model_dump_json())
    assert dumped["batch_id"] == raw["batch_id"]
    assert len(dumped["items"]) == len(raw["items"])


def test_error_envelope_round_trip(wire_fixtures_dir) -> None:

    from app.schemas.wire.error import ErrorEnvelope

    raw = json.loads((wire_fixtures_dir / "error.json").read_text())
    env = ErrorEnvelope.model_validate(raw)
    dumped = json.loads(env.model_dump_json())
    assert dumped["error_kind"] == raw["error_kind"]
    assert dumped["reason_code"] == raw["reason_code"]
    assert dumped["details"]["expected_inputs"] == ["brand_name"]
