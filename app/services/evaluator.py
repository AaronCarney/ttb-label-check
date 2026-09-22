"""Application Service chokepoint.

Composes the reader and the rule engine into one end-to-end evaluation behind
``POST /labels``.

Thin — all logic lives in helpers under ``app/services/`` (disposition,
aggregation, envelope_builder, audit, metrics_builder, cache, engine_meta).
The Evaluator's job is composition, and routing every downstream exception to
needs_review rather than to a 500.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.config import Settings
from app.rules.engine import RuleEngine
from app.schemas.application import Application
from app.schemas.extracted import FieldObservation
from app.schemas.label import Label
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.wire.disposition import DispositionEnvelope
from app.services.audit import _output_hash, faces_fingerprint
from app.services.cache import SessionCache
from app.services.headline import headline_reason_code
from app.vision.base import VisionExtractor
from app.vision.quality import assess as assess_quality

if TYPE_CHECKING:
    # Imported for the annotation only. `app.services.engine_meta` is imported
    # inside the methods that build a timeline rather than at module load, and
    # naming its type here would otherwise undo that.
    from app.services.engine_meta import EvaluationTimeline

_logger = logging.getLogger("app.services.evaluator")


@dataclass
class _PartialEvaluation:
    """What one evaluation had finished at the moment it was cut off.

    ``asyncio.wait_for`` cancels ``_evaluate_inner``, and every local the
    cancelled frame held goes with it — including a read that had already
    completed. This is the handle the timeout branch keeps on that work: each
    step fills it in as it finishes, so the envelope built after the
    cancellation can carry what was done instead of nothing.

    It is created per call and passed down, rather than stashed on the
    Evaluator. A batch reuses one Evaluator across every item in the batch
    (``app/api/batches.py``), so instance state is the wrong place for
    per-evaluation work: the failure mode is an item reporting the readings of
    a different label, which is worse than reporting none.
    """

    timeline: EvaluationTimeline | None = None
    t_total: float | None = None
    observations: tuple[FieldObservation, ...] = ()
    results: tuple[ValidationResult, ...] = field(default_factory=tuple)


class Evaluator:
    """Runs one evaluation end to end, and stops one that has gone wrong.

    The stop is a runaway guard, not a latency target — see
    `Settings.evaluation_guard_seconds` for the number and why it is not the
    five seconds R15/NFR-1 measures. When it fires, the evaluation returns what
    it had finished rather than nothing (`_timeout_envelope`).
    """

    def __init__(
        self,
        *,
        vision: VisionExtractor,
        rules: RuleEngine,
        settings: Settings,
        cache: SessionCache | None = None,
    ) -> None:
        self._vision = vision
        self._rules = rules
        self._settings = settings
        self._cache = cache

    async def evaluate(self, application: Application, label: Label) -> DispositionEnvelope:
        """Check one label, and leave one log line saying how it came out.

        The line carries the outcome, the reason code behind it and what the
        check cost, under the evaluation's id. Nothing from the application or
        the label reaches it (`docs/PRD.md` C-2): the message holds only the
        disposition, and every other value is on the logging allow-list.
        """
        t_start = time.monotonic()
        envelope = await self._evaluate_once(application, label)
        duration_ms = int((time.monotonic() - t_start) * 1000)
        _logger.info(
            f"evaluation_finished disposition={envelope.disposition}",
            extra={
                "evaluation_id": application.evaluation_id,
                "reason_code": headline_reason_code(envelope) or "ENGINE.OK.NONE",
                "duration_ms": duration_ms,
            },
        )
        return envelope

    async def _evaluate_once(self, application: Application, label: Label) -> DispositionEnvelope:
        import hashlib

        from app.services.audit import _canonical_json

        # Cache check — key over canonicalized inputs MINUS the
        # per-call evaluation_id (so two calls with the same app + label hit),
        # PLUS the rules that would answer it. A cached answer is only still
        # the right answer while the rules that produced it are the rules that
        # apply; without this, editing a rule left every label already in the
        # cache being answered under the rules it replaced, for the life of
        # the process.
        cache_key = None
        if self._cache is not None:
            t_hit = time.monotonic()
            started_at = datetime.now(UTC)
            app_for_key = application.model_dump(mode="json")
            app_for_key.pop("evaluation_id", None)
            cache_key = hashlib.sha256(
                _canonical_json(app_for_key)
                + self._rules.rule_set_version.encode("utf-8")
                + faces_fingerprint(label)
            ).hexdigest()
            cached = self._cache.get(cache_key)
            if cached is not None:
                return self._replay(cached, application, label, started_at, t_hit)

        # `_sla_seconds` is the per-instance override tests set to make the
        # guard fire in milliseconds; the setting is what ships.
        guard = getattr(self, "_sla_seconds", self._settings.evaluation_guard_seconds)
        partial = _PartialEvaluation()
        try:
            envelope = await asyncio.wait_for(
                self._evaluate_inner(application, label, partial), timeout=guard
            )
            # Cache-write: success branch only (NEVER on TimeoutError).
            if self._cache is not None and cache_key is not None:
                self._cache.put(cache_key, envelope)
        except TimeoutError:
            envelope = self._timeout_envelope(application, label, partial)
        return envelope

    def _replay(
        self,
        cached: DispositionEnvelope,
        application: Application,
        label: Label,
        started_at: datetime,
        t_hit: float,
    ) -> DispositionEnvelope:
        """Hand back a stored answer as this request's answer, honestly.

        The verdict and the findings are the stored ones — the inputs and the
        rules are identical, which is what the cache key means. Everything
        that describes *when* and *how long* is this request's, because that
        is the request being answered: the durations are what serving it cost,
        and the audit window is when it was served. `metrics.cache_hit` is
        what says the verdict behind them was worked out earlier.

        Before this, a hit patched only `evaluation_id` and returned the first
        call's `total_duration_ms` and `vision_duration_ms` beside the new id —
        so a repeat submission reported time it never spent, and four
        byte-identical latencies measured against production
        were four copies of one measurement.

        `label_ref` is this request's label for the same reason. The cache key
        is a fingerprint of the application and the image bytes and carries no
        filename, which is right — renaming a file does not change what is
        printed on the label — but a batch may legitimately carry one image
        under two names, and a results page headed with the other one is a
        wrong answer whatever the verdict beneath it says.

        `output_hash` is recomputed because it covers `evaluation_id` and
        `label_ref`, both of which this method rewrites. Carried over
        unchanged it is the first call's hash, so the one check a third party
        can run against a warm-path envelope fails on an envelope nobody
        tampered with. `input_hash` is NOT recomputed and must not be: it
        fingerprints the application minus `evaluation_id` plus the image
        bytes, which is what the cache key matched on, so the stored one is
        already this request's.
        """
        elapsed_ms = int((time.monotonic() - t_hit) * 1000)
        # Keeping evaluation_id consistent means patching the nested
        # audit_trail too — a top-level model_copy alone leaves
        # audit_trail.evaluation_id pointing at the cold-path UUID.
        # The same shape `_evaluate_inner` hashes on the cold path. `fields` are
        # the envelope's own — `build_success_envelope` passes the field
        # findings straight through — so this reproduces the cold-path hash
        # exactly rather than approximating it.
        envelope_for_hash = {
            "evaluation_id": application.evaluation_id,
            "label_ref": label.label_id,
            "disposition": cached.disposition,
            "fields": [f.model_dump() for f in cached.fields],
        }
        new_audit = cached.audit_trail.model_copy(
            update={
                "evaluation_id": application.evaluation_id,
                "started_at": started_at,
                "completed_at": datetime.now(UTC),
                "output_hash": _output_hash(envelope_for_hash),
            }
        )
        new_metrics = cached.metrics.model_copy(
            update={
                "cache_hit": True,
                "total_duration_ms": elapsed_ms,
                "vision_duration_ms": 0,
                # No rule ran on this request. The rules that produced the verdict
                # are still named in audit_trail.per_rule_trace.
                "per_rule_durations_ms": (),
            }
        )
        return cached.model_copy(
            update={
                "evaluation_id": application.evaluation_id,
                "label_ref": label.label_id,
                "audit_trail": new_audit,
                "metrics": new_metrics,
            }
        )

    async def _evaluate_inner(
        self, application: Application, label: Label, partial: _PartialEvaluation
    ) -> DispositionEnvelope:
        from app.services.audit import AuditRecorder
        from app.services.envelope_builder import build_field_findings, build_success_envelope
        from app.services.metrics_builder import MetricsBuilder

        t_total = time.monotonic()
        timeline = self._new_timeline(application)
        # From here on every step hands its finished work to `partial`, so a
        # cancellation after it still has something to return.
        partial.timeline = timeline
        partial.t_total = t_total

        # Which set of rules a label was checked against is the first thing a
        # reviewer needs and the last thing they can reconstruct, so it is
        # recorded before anything can go wrong. Every envelope this call can
        # produce — success, image-quality short circuit, timeout — is built
        # from this timeline, so every one of them carries the row.
        self._record_rule_pack(timeline, application.beverage_class)

        # Step 1: vision
        t0 = time.monotonic()
        try:
            observations = await self._vision.extract(label)
        except Exception as e:
            timeline.record_failure(
                reason_code="ENGINE.EXTRACTION.UNAVAILABLE",
                message=str(e),
                exception_class=type(e).__name__,
            )
            _logger.info(
                "engine_failure_routed",
                extra={
                    "reason_code": "ENGINE.EXTRACTION.UNAVAILABLE",
                    "evaluation_id": application.evaluation_id,
                    "error_class": type(e).__name__,
                },
            )
            observations = []
        timeline.record_vision_done(int((time.monotonic() - t0) * 1000))
        partial.observations = tuple(observations)

        # The application declares which beverage the label is for, and the
        # reader cannot: nothing on a bottle reliably distinguishes a wine
        # from a spirit. Re-tagging here, rather than telling the reader what
        # to expect, keeps the reader reporting only what it saw and still
        # sends every reading to the rule pack the application selected.
        #
        # When the application names no class, no pack can be selected and
        # nothing is checked — docs/decisions.md#0010. The reader's own tag is
        # not a fallback: both readers label everything they see `spirits`,
        # so inheriting it would score a wine against the spirits pack.
        # `FieldObservation.beverage_class` has no value for "unknown", so the
        # unknown case is expressed by handing the rules no readings at all:
        # `yaml_engine` selects a rule only where a reading's class is one the
        # rule applies to, so an empty sequence produces exactly what an
        # unknown class should produce — no rule evaluated. The readings still
        # reach the envelope below, so the reviewer sees what the label says.
        if application.beverage_class is not None:
            observations = [
                obs.model_copy(update={"beverage_class": application.beverage_class})
                for obs in observations
            ]
            readings_for_rules = observations
            partial.observations = tuple(observations)
        else:
            readings_for_rules = []

        # Step 2: image-quality short-circuit. Name the image problem rather
        # than guess at an unreadable label (docs/PRD.md FR-10).
        #
        # Every face, and the first unusable one stops the label: on a two-face
        # label the blurred photograph is as likely to be the one carrying the
        # government warning as the one carrying the brand, so there is nothing
        # to be gained by judging the label on the faces that did come out. The
        # message names the face so the applicant knows which one to retake.
        for face in label.faces:
            quality = assess_quality(face)
            if quality.disposition != "needs_better_photo":
                continue
            timeline.record_failure(
                reason_code=quality.reason_code,
                message=(
                    f"image quality insufficient on the {face.face_tag} face: {quality.reason_code}"
                ),
                exception_class="N/A",
            )
            _logger.info(
                "engine_failure_routed",
                extra={
                    "reason_code": quality.reason_code,
                    "evaluation_id": application.evaluation_id,
                    "face_tag": face.face_tag,
                    "error_class": "N/A",
                },
            )
            return self._short_circuit(
                application, label, timeline, quality.failure_reason_code(), t_total
            )

        # Step 3-4: rules
        try:
            started_at_ms = int(time.monotonic() * 1000)
            ctx = self._rules.build_validator_context(started_at_ms=started_at_ms)
            expected = tuple(application.expected_values)
            results = await self._rules.evaluate(readings_for_rules, expected, ctx)
        except Exception as e:
            timeline.record_failure(
                reason_code="ENGINE.RULES.UNAVAILABLE",
                message=str(e),
                exception_class=type(e).__name__,
            )
            _logger.info(
                "engine_failure_routed",
                extra={
                    "reason_code": "ENGINE.RULES.UNAVAILABLE",
                    "evaluation_id": application.evaluation_id,
                    "error_class": type(e).__name__,
                },
            )
            results = ()
        partial.results = tuple(results)

        # Surface failures into per_rule_trace so AuditRecorder picks them up.
        for failure in timeline.failures:
            timeline.record_rule_done(
                rule_id=failure.reason_code,
                duration_ms=0,
                disposition="needs_review",
                evidence_ref=f"engine_failure/{failure.exception_class}",
            )

        # Step 5-6: disposition + per-rule timeline updates
        from app.services.disposition import compute_disposition

        self._record_rule_results(timeline, results)
        disposition = compute_disposition(results)

        # Step 7-8: assembly
        timeline.finish(total_duration_ms=int((time.monotonic() - t_total) * 1000))
        field_findings = build_field_findings(
            results=results,
            observations=observations,
            expected_values=tuple(application.expected_values),
        )
        envelope_for_hash = {
            "evaluation_id": application.evaluation_id,
            "label_ref": label.label_id,
            "disposition": disposition,
            "fields": [f.model_dump() for f in field_findings],
        }
        audit = AuditRecorder().assemble(
            timeline=timeline,
            application=application,
            label=label,
            envelope_for_hash=envelope_for_hash,
        )
        metrics = MetricsBuilder().build(timeline)
        return build_success_envelope(
            application=application,
            label=label,
            timeline=timeline,
            disposition=disposition,
            fields=field_findings,
            audit=audit,
            metrics=metrics,
        )

    @staticmethod
    def _record_rule_results(timeline, results) -> None:
        """Write every finished rule onto the timeline.

        Called from the success path and again from the timeout path, because
        a cut-off evaluation may still have rules that finished, and the
        reviewer's audit trail should name them. Recording the same rule twice
        rewrites its row rather than duplicating it.
        """
        from app.services.disposition import rule_disposition

        for vr in results:
            # One mapping, shared with the reviewer's field card and with the
            # overall result, so the audit trail cannot contradict either.
            disposition_label = rule_disposition(vr)
            timeline.record_rule_done(
                rule_id=vr.rule_id,
                duration_ms=vr.engine_meta.elapsed_ms,
                disposition=disposition_label,
                evidence_ref=f"vr/{vr.rule_id}",
            )
            # Surface YAML-registry reason_code as a separate trace entry so
            # the chokepoint contract (FR-90X surfacing) holds: any non-PASS
            # outcome carrying a reason_code lands in per_rule_trace verbatim.
            if vr.reason_code and vr.outcome != Outcome.PASS:
                timeline.record_rule_done(
                    rule_id=vr.reason_code,
                    duration_ms=0,
                    disposition=disposition_label,
                    evidence_ref=f"reason_code/{vr.rule_id}",
                    row_key=f"reason_code/{vr.rule_id}",
                )

    def _new_timeline(self, application: Application):
        """A timeline that already knows which rules are answering.

        `EvaluationTimeline.rule_set_version` defaults to "unknown" and, until
        this, nothing in `app/` ever set it — so `audit_trail.rule_set_version`
        read "unknown" on every envelope the service has served. That field is
        the compliance record of which rules produced a verdict, and it is the
        one fact about an evaluation nobody can reconstruct from the answer
        afterwards.

        `model_version` was the other half of the same gap and was fixed the
        same way: it defaulted to `None`, nothing assigned it,
        and so no record said what read the label. Between the two, a record
        now names both the rules that judged a label and the reader that gave
        them the text to judge. `tests/test_audit_names_the_reader.py` holds it.
        """
        from app.services.engine_meta import EvaluationTimeline

        return EvaluationTimeline(
            evaluation_id=application.evaluation_id,
            rule_set_version=self._rules.rule_set_version,
            model_version=self._vision.reader_version,
        )

    # The two audit-trail rows that name the rules a label was checked
    # against. Both are engine facts rather than rule outcomes, which is the
    # same footing as ENGINE.EXTRACTION.UNAVAILABLE and ENGINE.SLA.TIMEOUT
    # already surfaced in this trace.
    _PACK_SELECTED = "ENGINE.RULE_PACK.SELECTED"
    _PACK_NOT_SELECTED = "ENGINE.RULE_PACK.NOT_SELECTED"

    @classmethod
    def _record_rule_pack(cls, timeline, beverage_class) -> None:
        """Name the rules this evaluation ran, in the audit trail.

        `rule_pack/wine` means the wine rules plus the ones that apply to
        every class; `rule_pack/none` means the application named no beverage,
        so no rule could be selected and nothing was checked.
        """
        if beverage_class is None:
            timeline.record_rule_done(
                rule_id=cls._PACK_NOT_SELECTED,
                duration_ms=0,
                disposition="needs_review",
                evidence_ref="rule_pack/none",
            )
            return
        timeline.record_rule_done(
            rule_id=cls._PACK_SELECTED,
            duration_ms=0,
            disposition="not_applicable",
            evidence_ref=f"rule_pack/{beverage_class.value}",
        )

    def _short_circuit(self, application, label, timeline, reason_code: str, t_total: float):
        from app.services.audit import AuditRecorder
        from app.services.envelope_builder import build_short_circuit_envelope
        from app.services.metrics_builder import MetricsBuilder

        # Surface every prior failure (e.g. an upstream vision exception
        # before the legibility gate fired) into per_rule_trace so the audit
        # is complete. Mirrors _timeout_envelope's surfacing loop.
        for failure in timeline.failures:
            timeline.record_rule_done(
                rule_id=failure.reason_code,
                duration_ms=0,
                disposition="needs_review",
                evidence_ref=f"engine_failure/{failure.exception_class}",
            )
        timeline.finish(total_duration_ms=int((time.monotonic() - t_total) * 1000))
        envelope_for_hash = {
            "evaluation_id": application.evaluation_id,
            "disposition": "needs_review",
            "reason_code": reason_code,
        }
        audit = AuditRecorder().assemble(
            timeline=timeline,
            application=application,
            label=label,
            envelope_for_hash=envelope_for_hash,
        )
        metrics = MetricsBuilder().build(timeline)
        return build_short_circuit_envelope(
            application=application,
            label=label,
            timeline=timeline,
            reason_code=reason_code,
            audit=audit,
            metrics=metrics,
        )

    def _timeout_envelope(
        self, application: Application, label: Label, partial: _PartialEvaluation
    ) -> DispositionEnvelope:
        """The envelope for an evaluation the cutoff stopped.

        It carries what the evaluation finished before it was stopped — the
        readings the reader produced, the rules that completed, and the time
        actually spent — with ``ENGINE.SLA.TIMEOUT`` in the audit trail saying
        why the rest is missing. This is what row 10 of the failure taxonomy in
        ``docs/research/2026-09-15-rule-engine-architecture.md`` specified from
        the start: "needs_review whole-evaluation; partial results returned".

        It used to return no fields and ``total_duration_ms: 0``. On
        the live service that made the same label answer completely or not at
        all on a difference of about fifty milliseconds, and turned a check
        that was merely slow into one that reported nothing — failing the
        requirements for showing a result (FR-1, FR-8) in order to serve a
        latency requirement that a blank page does not satisfy either.
        """
        from app.services.audit import AuditRecorder
        from app.services.envelope_builder import build_field_findings, build_short_circuit_envelope
        from app.services.metrics_builder import MetricsBuilder

        timeline = partial.timeline or self._new_timeline(application)
        # A timeout that fired before `_evaluate_inner` recorded anything gets
        # a fresh timeline, and that envelope must still name its rules.
        # Re-recording on an existing timeline rewrites the same row.
        self._record_rule_pack(timeline, application.beverage_class)
        # Rules that finished but were cancelled before the success path could
        # write them down still belong in the audit trail.
        self._record_rule_results(timeline, partial.results)
        timeline.record_failure(
            reason_code="ENGINE.SLA.TIMEOUT",
            message="whole-eval timeout exceeded",
            exception_class="TimeoutError",
        )
        # Surface failure into per_rule_trace.
        for failure in timeline.failures:
            timeline.record_rule_done(
                rule_id=failure.reason_code,
                duration_ms=0,
                disposition="needs_review",
                evidence_ref=f"engine_failure/{failure.exception_class}",
            )
        # What the check cost. `timeline.finish` never ran inside the cancelled
        # frame, so `total_duration_ms` is still 0 here; taking the elapsed time
        # from the start the inner recorded is the only honest number.
        elapsed_ms = (
            int((time.monotonic() - partial.t_total) * 1000) if partial.t_total is not None else 0
        )
        timeline.finish(total_duration_ms=elapsed_ms)
        _logger.info(
            "engine_failure_routed",
            extra={
                "reason_code": "ENGINE.SLA.TIMEOUT",
                "evaluation_id": application.evaluation_id,
                "error_class": "TimeoutError",
            },
        )
        fields = build_field_findings(
            results=partial.results,
            observations=partial.observations,
            expected_values=tuple(application.expected_values),
        )
        envelope_for_hash = {
            "evaluation_id": application.evaluation_id,
            "disposition": "needs_review",
            "reason_code": "ENGINE.SLA.TIMEOUT",
            "fields": [f.model_dump() for f in fields],
        }
        audit = AuditRecorder().assemble(
            timeline=timeline,
            application=application,
            label=label,
            envelope_for_hash=envelope_for_hash,
        )
        metrics = MetricsBuilder().build(timeline)
        return build_short_circuit_envelope(
            application=application,
            label=label,
            timeline=timeline,
            reason_code="ENGINE.SLA.TIMEOUT",
            audit=audit,
            metrics=metrics,
            fields=fields,
        )
