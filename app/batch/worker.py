"""Batch worker — pull-based, reactive-streams-style consumer.

Two coroutines collaborate via the per-batch ``BoundedQueue``:

1. ``_producer`` — iterates ``in_flight.items`` in submission order and awaits
   ``queue.put(item)`` for each. Saturates at ``maxsize=k+1`` and blocks until
   the consumer drains. **The first label is not held back**: the producer starts
   concurrently with the consumer; item 0's put returns immediately and the
   consumer's first get returns it without waiting for the lookahead window.
2. ``_consume`` — ``await queue.get()`` → ``evaluator.evaluate(app, label)`` →
   ``in_flight.record_result(label_id, envelope)`` → broadcast ``label-result``
   SSE event → ``anomaly.observe(headline_reason_code)`` → broadcast
   ``anomaly-advisory`` if one fires. Emits ``stream-end`` after the last item.

A mid-batch override is handled outside this module: the override endpoint
mutates ``in_flight.results[label_id]`` directly. The worker never inspects
``overrides`` as a stop condition.
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.api._sse_bus import SSEBus
from app.batch.anomaly import AnomalyDetector
from app.batch.state import InFlightBatch
from app.schemas.application import Application
from app.schemas.batch import BatchItem
from app.schemas.label import Label
from app.schemas.wire.disposition import DispositionEnvelope

_logger = logging.getLogger("app.batch.worker")


def _headline_reason_code(envelope: DispositionEnvelope) -> str | None:
    """Pick one canonical reason-code string for anomaly observation.

    PerRuleTraceEntry carries no `reason_code` field; reason codes live on
    RuleFindingWire inside envelope.fields, with a short-circuit fallback to
    per_rule_trace[0].rule_id for envelopes that carry no per-field findings
    at all."""
    if envelope.disposition == "pass":
        return None
    for field in envelope.fields:
        for finding in field.rule_findings:
            if finding.disposition in ("fail", "needs_review"):
                return finding.reason_code
    if envelope.audit_trail.per_rule_trace:
        return envelope.audit_trail.per_rule_trace[0].rule_id
    return None


class BatchWorker:
    """Pull-based batch consumer."""

    def __init__(
        self,
        *,
        in_flight: InFlightBatch,
        evaluator,
        anomaly: AnomalyDetector,
        bus: SSEBus,
    ) -> None:
        self._in_flight = in_flight
        self._evaluator = evaluator
        self._anomaly = anomaly
        self._bus = bus
        # Lookup registries. The bulk-upload route and tests populate these;
        # anything missing is synthesized by the _resolve_* helpers below.
        self._app_lookup: dict[str, Application] = {}
        self._label_lookup: dict[str, Label] = {}

    def _resolve_application(self, item: BatchItem) -> Application:
        """Resolve the Application for a queued BatchItem.

        Uses `self._app_lookup` when the caller has populated it; otherwise
        synthesizes a minimal `Application` from the `application_ref`, since a
        batch submitted as refs alone carries no application data."""
        if item.application_ref in self._app_lookup:
            return self._app_lookup[item.application_ref]
        return Application(
            application_id=item.application_ref,
            evaluation_id=item.label_id,
        )

    def _resolve_label(self, item: BatchItem) -> Label:
        """Resolve the Label payload for a queued BatchItem.

        Uses `self._label_lookup` when the caller has populated it — the bulk
        upload route does, so each item carries the exact bytes uploaded.
        Otherwise synthesizes a minimal schema-valid `Label` from the
        `label_id`."""
        if item.label_id in self._label_lookup:
            return self._label_lookup[item.label_id]
        return Label(
            label_id=item.label_id,
            batch_id=self._in_flight.batch_id,
            image_bytes=b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
            face_tag="front",
        )

    async def _producer(self) -> None:
        for item in self._in_flight.items:
            await self._in_flight.queue.put(item)

    async def _consume(self) -> None:
        total = len(self._in_flight.items)
        batch_id = self._in_flight.batch_id
        t_batch = time.monotonic()
        _logger.info(
            f"batch_consume_started batch_id={batch_id} items={total} lookahead_k={self._in_flight.lookahead_k}",
            extra={"batch_id": batch_id, "reason_code": "ENGINE.OK.NONE"},
        )
        for queue_position in range(total):
            item: BatchItem = await self._in_flight.queue.get()
            application = self._resolve_application(item)
            label = self._resolve_label(item)
            t_label = time.monotonic()
            try:
                envelope = await self._evaluator.evaluate(application, label)
            except Exception:
                _logger.exception(
                    f"label_evaluation_failed batch_id={batch_id} label_id={item.label_id} pos={queue_position}",
                    extra={
                        "batch_id": batch_id,
                        "label_id": item.label_id,
                        "evaluation_id": application.evaluation_id,
                        "reason_code": "ENGINE.WORKER.UNHANDLED",
                    },
                )
                raise
            duration_ms = int((time.monotonic() - t_label) * 1000)
            self._in_flight.record_result(item.label_id, envelope)

            headline_code = _headline_reason_code(envelope)
            _logger.info(
                f"label_result batch_id={batch_id} pos={queue_position} disposition={envelope.disposition} duration_ms={duration_ms}",
                extra={
                    "batch_id": batch_id,
                    "label_id": item.label_id,
                    "evaluation_id": envelope.evaluation_id,
                    "duration_ms": duration_ms,
                    "reason_code": headline_code or "ENGINE.OK.NONE",
                },
            )

            # Per-label SSE event with queue_position
            self._bus.broadcast({
                "event": "label-result",
                "data": {
                    "batch_id": batch_id,
                    "queue_position": queue_position,
                    "envelope": envelope.model_dump(mode="json"),
                },
            })

            # Anomaly observation. Bind once: the helper is pure today, but
            # binding here pins the contract that ``recent_dispositions`` and
            # ``observe`` see the same code, even if the helper later acquires
            # side effects.
            self._in_flight.recent_dispositions.append(headline_code)
            advisory = self._anomaly.observe(headline_code)
            if advisory is not None:
                _logger.info(
                    f"anomaly_advisory batch_id={batch_id} advisory_id={advisory.advisory_id} count={advisory.count} window={advisory.window}",
                    extra={"batch_id": batch_id, "reason_code": advisory.reason_code},
                )
                self._bus.broadcast({
                    "event": "anomaly-advisory",
                    "data": {
                        "batch_id": batch_id,
                        "advisory_id": advisory.advisory_id,
                        "reason_code": advisory.reason_code,
                        "count": advisory.count,
                        "window": advisory.window,
                    },
                })

        batch_duration_ms = int((time.monotonic() - t_batch) * 1000)
        _logger.info(
            f"batch_consume_finished batch_id={batch_id} items={total} duration_ms={batch_duration_ms}",
            extra={
                "batch_id": batch_id,
                "duration_ms": batch_duration_ms,
                "reason_code": "ENGINE.OK.NONE",
            },
        )
        self._bus.broadcast({
            "event": "stream-end",
            "data": {
                "batch_id": batch_id,
                "total_count": total,
            },
        })

    async def run(self) -> None:
        producer_task = asyncio.create_task(self._producer())
        consume_error: BaseException | None = None
        try:
            await self._consume()
        except BaseException as e:
            consume_error = e
            raise
        finally:
            # Cancel the producer (which may be parked on a saturated
            # ``queue.put``) and drain any pending exception. Without the
            # cancel, a ``_consume`` error would leave the producer parked
            # forever and ``await producer_task`` would deadlock.
            producer_task.cancel()
            results = await asyncio.gather(producer_task, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                    _logger.error(
                        f"batch_producer_failed batch_id={self._in_flight.batch_id}",
                        exc_info=(type(result), result, result.__traceback__),
                        extra={
                            "batch_id": self._in_flight.batch_id,
                            "reason_code": "ENGINE.WORKER.UNHANDLED",
                            "error_class": type(result).__name__,
                        },
                    )
            # If _consume raised, it never broadcast stream-end — the SSE
            # client would hang on `terminator_event="stream-end"`. Send a
            # terminator carrying the error so the demo recovers.
            if consume_error is not None:
                self._bus.broadcast({
                    "event": "stream-end",
                    "data": {
                        "batch_id": self._in_flight.batch_id,
                        "total_count": len(self._in_flight.items),
                        "error": "ENGINE.WORKER.UNHANDLED",
                        "error_class": type(consume_error).__name__,
                    },
                })
