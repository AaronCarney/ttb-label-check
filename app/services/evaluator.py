"""Application Service chokepoint.

Composes the reader, the rule engine and the orchestrator into one end-to-end
evaluation behind ``POST /labels``.

Thin — all logic lives in helpers under ``app/services/`` (disposition,
aggregation, patcher, triggers, envelope_builder, audit, metrics_builder,
cache, engine_meta). The Evaluator's job is composition, and routing every
downstream exception to needs_review rather than to a 500.
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.config import Settings
from app.orchestrator.base import Orchestrator
from app.rules.engine import RuleEngine
from app.schemas.application import Application
from app.schemas.label import Label
from app.schemas.rejection import Outcome, Severity
from app.schemas.wire.disposition import DispositionEnvelope
from app.services.cache import SessionCache
from app.vision.base import VisionExtractor
from app.vision.quality import assess as assess_quality

_logger = logging.getLogger("app.services.evaluator")


class Evaluator:
    _DEFAULT_SLA_SECONDS = 5.0

    def __init__(
        self,
        *,
        vision: VisionExtractor,
        rules: RuleEngine,
        orchestrator: Orchestrator,
        settings: Settings,
        cache: SessionCache | None = None,
    ) -> None:
        self._vision = vision
        self._rules = rules
        self._orchestrator = orchestrator
        self._settings = settings
        self._cache = cache

    async def evaluate(self, application: Application, label: Label) -> DispositionEnvelope:
        import hashlib

        from app.services.audit import _canonical_json

        # Cache check — key over canonicalized inputs MINUS the
        # per-call evaluation_id (so two calls with the same app + label hit).
        cache_key = None
        if self._cache is not None:
            app_for_key = application.model_dump(mode="json")
            app_for_key.pop("evaluation_id", None)
            cache_key = hashlib.sha256(
                _canonical_json(app_for_key) + label.image_bytes
            ).hexdigest()
            cached = self._cache.get(cache_key)
            if cached is not None:
                # Keeping evaluation_id consistent means patching the nested
                # audit_trail too — a top-level model_copy alone leaves
                # audit_trail.evaluation_id pointing at the cold-path UUID.
                new_audit = cached.audit_trail.model_copy(
                    update={"evaluation_id": application.evaluation_id}
                )
                return cached.model_copy(update={
                    "evaluation_id": application.evaluation_id,
                    "audit_trail": new_audit,
                })

        sla = getattr(self, "_sla_seconds", self._DEFAULT_SLA_SECONDS)
        try:
            envelope = await asyncio.wait_for(
                self._evaluate_inner(application, label), timeout=sla
            )
            # Cache-write: success branch only (NEVER on TimeoutError).
            if self._cache is not None and cache_key is not None:
                self._cache.put(cache_key, envelope)
        except asyncio.TimeoutError:
            envelope = self._timeout_envelope(application, label)
        return envelope

    async def _evaluate_inner(self, application: Application, label: Label) -> DispositionEnvelope:
        from app.services.audit import AuditRecorder
        from app.services.engine_meta import EvaluationTimeline
        from app.services.envelope_builder import build_field_findings, build_success_envelope
        from app.services.metrics_builder import MetricsBuilder

        t_total = time.monotonic()
        timeline = EvaluationTimeline(evaluation_id=application.evaluation_id)
        # Stash for partial-state surfacing in timeout fallback.
        self._last_timeline = timeline
        self._last_t_total = t_total

        # Step 1: vision
        t0 = time.monotonic()
        try:
            observations = await self._vision.extract(label)
        except Exception as e:  # noqa: BLE001
            timeline.record_failure(
                reason_code="ENGINE.EXTRACTION.UNAVAILABLE",
                message=str(e), exception_class=type(e).__name__,
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

        # The application declares which beverage the label is for, and the
        # reader cannot: nothing on a bottle reliably distinguishes a wine
        # from a spirit. Re-tagging here, rather than telling the reader what
        # to expect, keeps the reader reporting only what it saw and still
        # sends every reading to the rule pack the application selected.
        if application.beverage_class is not None:
            observations = [
                obs.model_copy(update={"beverage_class": application.beverage_class})
                for obs in observations
            ]

        # Step 2: image-quality short-circuit. Name the image problem rather
        # than guess at an unreadable label (docs/PRD.md FR-10).
        quality = assess_quality(label)
        if quality.disposition == "needs_better_photo":
            timeline.record_failure(
                reason_code=quality.reason_code,
                message=f"image quality insufficient: {quality.reason_code}",
                exception_class="N/A",
            )
            _logger.info(
                "engine_failure_routed",
                extra={
                    "reason_code": quality.reason_code,
                    "evaluation_id": application.evaluation_id,
                    "error_class": "N/A",
                },
            )
            return self._short_circuit(application, label, timeline, quality.reason_code, t_total)

        # Step 3-4: rules
        try:
            started_at_ms = int(time.monotonic() * 1000)
            ctx = self._rules.build_validator_context(started_at_ms=started_at_ms)
            expected = tuple(application.expected_values)
            results = await self._rules.evaluate(observations, expected, ctx)
        except Exception as e:  # noqa: BLE001
            timeline.record_failure(
                reason_code="ENGINE.RULES.UNAVAILABLE",
                message=str(e), exception_class=type(e).__name__,
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

        # Step 5-6: orchestrator (conditional), then patching its notes in.
        # Master switch: settings.orchestrator_enabled gates the entire
        # AI-on-the-hot-path layer. Default OFF — the brief required AI but
        # every check on the requirements list is deterministic, and Marcus
        # flagged outbound-LLM traffic as firewall-hostile. The patcher already
        # bars the model from touching outcome/severity/reason_code; the
        # switch is the additional defense-in-depth that keeps the demo
        # zero-LLM-call by default.
        from app.services.patcher import patch_validation_results
        from app.services.triggers import should_invoke_orchestrator
        if self._settings.orchestrator_enabled and should_invoke_orchestrator(results):
            t_orch = time.monotonic()
            try:
                refined = await self._orchestrator.refine(application, list(observations), list(results))
                results = patch_validation_results(results, refined)
            except Exception as e:  # noqa: BLE001
                timeline.record_failure(
                    reason_code="ENGINE.MODEL.UNAVAILABLE",
                    message=str(e), exception_class=type(e).__name__,
                )
                _logger.info(
                    "engine_failure_routed",
                    extra={
                        "reason_code": "ENGINE.MODEL.UNAVAILABLE",
                        "evaluation_id": application.evaluation_id,
                        "error_class": type(e).__name__,
                    },
                )
            finally:
                timeline.record_orchestrator_done(int((time.monotonic() - t_orch) * 1000))

        # Surface failures into per_rule_trace so AuditRecorder picks them up.
        for failure in timeline.failures:
            timeline.record_rule_done(rule_id=failure.reason_code, duration_ms=0,
                                      disposition="needs_review",
                                      evidence_ref=f"engine_failure/{failure.exception_class}")

        # Step 7-8: disposition + per-rule timeline updates
        from app.services.disposition import compute_disposition
        for vr in results:
            # A warn-severity failure is a reviewer's call, not a rejection,
            # and the audit has to say so or it contradicts the disposition
            # the same results produced.
            disposition_label = (
                "pass" if vr.outcome == Outcome.PASS else
                "not_applicable" if vr.outcome == Outcome.NOT_APPLICABLE else
                "fail" if vr.outcome == Outcome.FAIL and vr.severity != Severity.WARN else
                "needs_review"
            )
            timeline.record_rule_done(rule_id=vr.rule_id, duration_ms=vr.engine_meta.elapsed_ms,
                                      disposition=disposition_label, evidence_ref=f"vr/{vr.rule_id}")
            # Surface YAML-registry reason_code as a separate trace entry so
            # the chokepoint contract (FR-90X surfacing) holds: any non-PASS
            # outcome carrying a reason_code lands in per_rule_trace verbatim.
            if vr.reason_code and vr.outcome != Outcome.PASS:
                timeline.record_rule_done(
                    rule_id=vr.reason_code, duration_ms=0,
                    disposition=disposition_label,
                    evidence_ref=f"reason_code/{vr.rule_id}",
                )
        disposition = compute_disposition(results)

        # Step 9-10: assembly
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
        audit = AuditRecorder().assemble(timeline=timeline, application=application, label=label,
                                         envelope_for_hash=envelope_for_hash)
        metrics = MetricsBuilder().build(timeline)
        envelope = build_success_envelope(
            application=application, label=label, timeline=timeline,
            disposition=disposition, fields=field_findings, audit=audit, metrics=metrics,
        )
        return envelope

    def _short_circuit(self, application, label, timeline, reason_code: str, t_total: float):
        from app.services.audit import AuditRecorder
        from app.services.envelope_builder import build_short_circuit_envelope
        from app.services.metrics_builder import MetricsBuilder

        # Surface every prior failure (e.g. an upstream vision exception
        # before the legibility gate fired) into per_rule_trace so the audit
        # is complete. Mirrors _timeout_envelope's surfacing loop.
        for failure in timeline.failures:
            timeline.record_rule_done(rule_id=failure.reason_code, duration_ms=0,
                                      disposition="needs_review",
                                      evidence_ref=f"engine_failure/{failure.exception_class}")
        timeline.finish(total_duration_ms=int((time.monotonic() - t_total) * 1000))
        envelope_for_hash = {"evaluation_id": application.evaluation_id, "disposition": "needs_review",
                             "reason_code": reason_code}
        audit = AuditRecorder().assemble(timeline=timeline, application=application, label=label,
                                         envelope_for_hash=envelope_for_hash)
        metrics = MetricsBuilder().build(timeline)
        return build_short_circuit_envelope(
            application=application, label=label, timeline=timeline,
            reason_code=reason_code, audit=audit, metrics=metrics,
        )

    def _timeout_envelope(self, application: Application, label: Label) -> DispositionEnvelope:
        from app.services.audit import AuditRecorder
        from app.services.engine_meta import EvaluationTimeline
        from app.services.envelope_builder import build_short_circuit_envelope
        from app.services.metrics_builder import MetricsBuilder

        timeline = getattr(self, "_last_timeline", None) or EvaluationTimeline(
            evaluation_id=application.evaluation_id
        )
        timeline.record_failure(
            reason_code="ENGINE.SLA.TIMEOUT",
            message="whole-eval timeout exceeded",
            exception_class="TimeoutError",
        )
        # Surface failure into per_rule_trace.
        for failure in timeline.failures:
            timeline.record_rule_done(rule_id=failure.reason_code, duration_ms=0,
                                      disposition="needs_review",
                                      evidence_ref=f"engine_failure/{failure.exception_class}")
        timeline.finish(total_duration_ms=timeline.total_duration_ms or 0)
        _logger.info(
            "engine_failure_routed",
            extra={
                "reason_code": "ENGINE.SLA.TIMEOUT",
                "evaluation_id": application.evaluation_id,
                "error_class": "TimeoutError",
            },
        )
        envelope_for_hash = {"evaluation_id": application.evaluation_id, "disposition": "needs_review",
                             "reason_code": "ENGINE.SLA.TIMEOUT"}
        audit = AuditRecorder().assemble(timeline=timeline, application=application, label=label,
                                         envelope_for_hash=envelope_for_hash)
        metrics = MetricsBuilder().build(timeline)
        return build_short_circuit_envelope(
            application=application, label=label, timeline=timeline,
            reason_code="ENGINE.SLA.TIMEOUT", audit=audit, metrics=metrics,
        )
