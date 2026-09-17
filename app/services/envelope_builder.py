"""Pure envelope assembly — success path + short-circuit path + per-field
FieldFindingWire projection.

No I/O, no clock; takes a pre-built AuditRecord + Metrics so audit/metrics
ownership stays clean.
"""
from __future__ import annotations

from collections.abc import Iterable

from app.schemas.application import Application
from app.schemas.audit import AuditRecord, PerRuleTraceEntry
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.label import Label
from app.schemas.metrics import Metrics
from app.schemas.rejection import ValidationResult
from app.schemas.wire.disposition import (
    AISuggestionWire,
    ConfidenceBand,
    DispositionEnvelope,
    FieldEvidenceWire,
    FieldFindingWire,
    RuleFindingWire,
)
from app.services.aggregation import min_aggregate_confidence
from app.services.confidence import to_band
from app.services.disposition import rule_disposition
from app.services.engine_meta import EvaluationTimeline
from app.vision.cloud import OBSERVED_VALUE_AUDIT_KEYS

# Canonical field id → wire field_name enum. Two input forms route to the
# same wire slot: the long canonical form (`alcohol_content`, …) used by
# Application input + hand-built fixtures, and the short extractor form
# (`abv`, `gov_warning`, …) emitted by CloudVisionExtractor.
# Both forms map onto the seven wire slots in `FieldFindingWire`.
_FIELD_CANONICAL_TO_WIRE = {
    # Long canonical form
    "brand_name": "brand_name",
    "class_type": "class_type",
    "alcohol_content": "alcohol_content",
    "net_contents": "net_contents",
    "government_warning": "warning",
    "name_and_address": "name_address",
    "country_of_origin": "country_of_origin",
    # Short extractor form
    "abv": "alcohol_content",
    "gov_warning": "warning",
    "name_address": "name_address",
    "country_origin": "country_of_origin",
}

# One wire slot → every field id that routes to it, in the order above (long
# canonical form first). The reader and the application name three of the same
# elements differently — `abv`/`alcohol_content`, `name_address`/
# `name_and_address`, `country_origin`/`country_of_origin` — so an observation
# and the expected value it must be shown beside arrive under different ids.
# Joining them on the id leaves those three slots with an empty application
# value on the result page; the join is on the slot.
_WIRE_TO_FIELD_IDS: dict[str, tuple[str, ...]] = {}
for _field_id, _wire_slot in _FIELD_CANONICAL_TO_WIRE.items():
    _WIRE_TO_FIELD_IDS[_wire_slot] = _WIRE_TO_FIELD_IDS.get(_wire_slot, ()) + (_field_id,)


def _coerce_str(value) -> str:
    if value is None:
        return ""
    return str(value)


def _strip_audit_keys(value):
    """If `value` is a dict, drop keys we never want on the wire surface.

    The canonical key set is owned by the producer (`app.vision.cloud`) — see
    `OBSERVED_VALUE_AUDIT_KEYS` for the list and the rationale.
    """
    if not isinstance(value, dict):
        return value
    return {k: v for k, v in value.items() if k not in OBSERVED_VALUE_AUDIT_KEYS}


def build_field_findings(
    *,
    results: Iterable[ValidationResult],
    observations: Iterable[FieldObservation],
    expected_values: Iterable[ExpectedValue],
) -> tuple[FieldFindingWire, ...]:
    """Project (ValidationResult, FieldObservation, ExpectedValue) tuples
    into the wire-side `FieldFindingWire` list.

    One entry per wire slot for which there is either an observation OR an
    expected value. Observation, expected value and rule results are joined on
    the wire slot rather than on the field id, because the reader and the
    application name three of the same elements differently
    (`_WIRE_TO_FIELD_IDS`). A slot with no observation AND no expected value is
    omitted; it stays visible to the reviewer through the synthetic
    `per_rule_trace` entries the audit record carries for engine_failure rows.
    The seven slots and the ids that route to them are in
    `_FIELD_CANONICAL_TO_WIRE`; `country_of_origin` is included only when an
    observation surfaces it.
    """
    obs_by_field: dict[str, FieldObservation] = {o.field_id: o for o in observations}
    exp_by_field: dict[str, ExpectedValue] = {e.field_id: e for e in expected_values}
    # Group ValidationResults by the canonical field they touch (sourced from
    # the first evidence's `field_id`). Validators that emit no evidence
    # cannot be associated with a field — they surface in audit only.
    results_by_field: dict[str, list[ValidationResult]] = {}
    for vr in results:
        if not vr.evidence:
            continue
        fid = vr.evidence[0].field_id
        results_by_field.setdefault(fid, []).append(vr)

    out: list[FieldFindingWire] = []
    for wire_slot, slot_ids in _WIRE_TO_FIELD_IDS.items():
        obs = next((obs_by_field[i] for i in slot_ids if i in obs_by_field), None)
        exp = next((exp_by_field[i] for i in slot_ids if i in exp_by_field), None)
        if obs is None and exp is None:
            continue
        if obs is None or not obs.evidence:
            # Per the contract: needs_review trace entry handled in audit;
            # skip the wire entry to keep the wire surface tight.
            continue
        ev = obs.evidence[0]
        evidence_wire = FieldEvidenceWire(
            bbox=ev.bbox if ev.bbox is not None else (0, 0, 0, 0),
            crop_ref=ev.image_uri or "",
            extraction_confidence=ev.confidence,
        )
        # What the card says a rule found comes from `rule_disposition`, the
        # one mapping the audit trail and the overall result also use. Reading
        # the outcome here instead is how a field came to say *fail* beside an
        # audit trail saying *needs_review* for the same rule.
        #
        # NOT_APPLICABLE rules are filtered out: the wire enum only models
        # {pass, fail, needs_review}, so bucketing not_applicable as
        # needs_review would mislead the reviewer into looking at a rule that
        # explicitly opted out (e.g. fuzzy_brand with no expected value).
        # The audit trail still carries them.
        #
        # Confidence is the minimum over the rules that did evaluate; a rule
        # that opted out carries the observation's confidence by default but
        # measured nothing, so excluding it keeps the aggregate honest.
        rule_findings: list[RuleFindingWire] = []
        confidences: list[float] = []
        slot_results = [vr for i in slot_ids for vr in results_by_field.get(i, [])]
        for vr in slot_results:
            verdict = rule_disposition(vr)
            if verdict == "not_applicable":
                continue
            rule_findings.append(RuleFindingWire(
                rule_id=vr.rule_id,
                cfr_citation=vr.cfr_citation,
                disposition=verdict,
                reason_code=vr.reason_code or "",
                plain_language_explanation=vr.message or "",
            ))
            confidences.append(vr.aggregated_confidence)
        rule_findings_for_field = tuple(rule_findings)
        # Fall back to the observation's own evidence confidence when no rule
        # fired on this field.
        numeric = min(confidences) if confidences else ev.confidence
        out.append(FieldFindingWire(
            field_name=wire_slot,  # type: ignore[arg-type]
            extracted_value=_coerce_str(_strip_audit_keys(obs.observed_value)),
            expected_value=_coerce_str(exp.value if exp else None),
            evidence=evidence_wire,
            rule_findings=rule_findings_for_field,
            ai_suggestion=AISuggestionWire(present=False),
            field_confidence=ConfidenceBand(band=to_band(numeric), numeric=numeric),
        ))
    return tuple(out)


def build_success_envelope(
    *,
    application: Application,
    label: Label,
    timeline: EvaluationTimeline,
    disposition: str,
    fields: Iterable[FieldFindingWire],
    audit: AuditRecord,
    metrics: Metrics,
) -> DispositionEnvelope:
    fields_t = tuple(fields)
    band, numeric = min_aggregate_confidence(fields_t)
    return DispositionEnvelope(
        evaluation_id=application.evaluation_id,
        label_ref=label.label_id,  # wire-side name <- internal name (Conventions §)
        disposition=disposition,  # type: ignore[arg-type]
        disposition_confidence=ConfidenceBand(band=band, numeric=numeric),
        fields=fields_t,
        audit_trail=audit,
        metrics=metrics,
    )


def build_short_circuit_envelope(
    *,
    application: Application,
    label: Label,
    timeline: EvaluationTimeline,
    reason_code: str,
    audit: AuditRecord,
    metrics: Metrics,
) -> DispositionEnvelope:
    """Assemble a needs_review envelope when an upstream short-circuit fired
    (legibility, whole-eval timeout, total engine failure). Surfaces the
    reason code as a synthetic per_rule_trace entry so reviewers see why."""
    # Augment audit trail with the short-circuit reason if not already present.
    existing_ids = {e.rule_id for e in audit.per_rule_trace}
    if reason_code not in existing_ids:
        synthetic = PerRuleTraceEntry(
            rule_id=reason_code, disposition="needs_review",
            evidence_ref=f"engine_failure/{reason_code}",
        )
        augmented = audit.model_copy(update={"per_rule_trace": audit.per_rule_trace + (synthetic,)})
    else:
        augmented = audit
    return DispositionEnvelope(
        evaluation_id=application.evaluation_id,
        label_ref=label.label_id,  # wire-side name <- internal name (Conventions §)
        disposition="needs_review",
        disposition_confidence=ConfidenceBand(band="low", numeric=0.0),
        fields=(),
        audit_trail=augmented,
        metrics=metrics,
    )
