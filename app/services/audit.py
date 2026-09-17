"""AuditRecorder — pure assembly + canonical hashing.

input_hash  = sha256(canonical_application_json_minus_evaluation_id ‖ faces_fingerprint)
output_hash = sha256(canonical_envelope_with_hashes_zeroed)

evaluation_id is excluded from input_hash so the hash is a CONTENT fingerprint
(not a call identity). This matches the SessionCache key (which also strips
evaluation_id) and keeps tamper detection working on the warm path:
a verifier recomputing input_hash from a cache-hit envelope's
returned evaluation_id will get the same hash as the cold-path call.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.schemas.application import Application
from app.schemas.audit import AuditRecord, PerRuleTraceEntry
from app.schemas.label import Label
from app.services.engine_meta import EvaluationTimeline


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def faces_fingerprint(label: Label) -> bytes:
    """The label's faces, as the bytes a hash of "what was submitted" is taken over.

    Shared by `input_hash` and the evaluator's cache key, so the audit trail and
    the cache can never disagree about what two submissions have in common.

    Each face contributes a length-framed descriptor and its length-framed image
    bytes, in face order. Three things follow, and all three are the point:

    * Two submissions that sent different faces cannot produce the same
      fingerprint. A plain concatenation cannot promise that — `(b"ab", b"c")`
      and `(b"a", b"bc")` concatenate identically — and an audit hash that two
      different submissions can share is not a fingerprint of either.
    * The same photograph submitted as a front and as a back are different
      submissions, because every observation now carries the face it was read
      from and the two answers differ. The descriptor carries `face_tag`, so
      they key differently.
    * Face order counts, and so do the applicant's declared dimensions, which
      feed the DPI the quality report states.
    """
    parts: list[bytes] = []
    for face in label.faces:
        descriptor = _canonical_json(
            {
                "face_tag": face.face_tag,
                "content_type": face.content_type,
                "dimensions": (
                    None if face.dimensions is None else face.dimensions.model_dump(mode="json")
                ),
            }
        )
        parts.append(len(descriptor).to_bytes(8, "big"))
        parts.append(descriptor)
        parts.append(len(face.image_bytes).to_bytes(8, "big"))
        parts.append(face.image_bytes)
    return b"".join(parts)


def _input_hash(application: Application, label: Label) -> str:
    app_dict = application.model_dump(mode="json")
    # Exclude evaluation_id: input_hash is a content fingerprint, matching
    # the SessionCache key. See the module docstring on the warm path.
    app_dict.pop("evaluation_id", None)
    return hashlib.sha256(_canonical_json(app_dict) + faces_fingerprint(label)).hexdigest()


def _output_hash(envelope_for_hash: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(envelope_for_hash)).hexdigest()


class AuditRecorder:
    def assemble(
        self,
        *,
        timeline: EvaluationTimeline,
        application: Application,
        label: Label,
        envelope_for_hash: dict[str, Any],
    ) -> AuditRecord:
        per_rule = tuple(
            PerRuleTraceEntry(
                rule_id=rid,
                disposition=timeline.per_rule_dispositions.get(rid, "not_applicable"),  # type: ignore[arg-type]
                evidence_ref=timeline.per_rule_evidence_refs.get(rid, ""),
            )
            for rid in timeline.per_rule_durations
        )
        completed = timeline.completed_at or datetime.now(UTC)
        return AuditRecord(
            evaluation_id=timeline.evaluation_id,
            rule_set_version=timeline.rule_set_version,
            model_version=timeline.model_version,
            prompt_version=timeline.prompt_version,
            input_hash=_input_hash(application, label),
            output_hash=_output_hash(envelope_for_hash),
            started_at=timeline.started_at,
            completed_at=completed,
            per_rule_trace=per_rule,
            overrides=(),
        )
