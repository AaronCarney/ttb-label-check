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
   ``anomaly-advisory`` if one fires → hold until the reviewer has caught up to
   within ``lookahead_k`` events. Emits ``stream-end`` after the last item.

**No one label ends the batch.** An item with no image, and an item whose
evaluation raises, each get a refusal result that names the reason code, and the
consumer carries on to the next item (``docs/PRD.md`` FR-13,
``docs/decisions.md#0020``). Nothing is invented for a label that was never
supplied.

**The demand that paces the work is the reviewer's, not the queue's.** The
producer above iterates a tuple already in memory, so the bounded queue throttles
something that costs nothing. The cost is in ``evaluator.evaluate``, and what
holds it back is how far the slowest attached SSE reader has fallen behind
(``docs/decisions.md#0021``). With nobody reading, nothing is held back.

A mid-batch override is handled outside this module: the override endpoint
mutates ``in_flight.results[label_id]`` directly. The worker never inspects
``overrides`` as a stop condition.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import UTC, datetime

from app.api._sse_bus import SSEBus
from app.batch.anomaly import AnomalyDetector
from app.batch.state import InFlightBatch
from app.schemas.application import Application
from app.schemas.audit import AuditRecord, PerRuleTraceEntry
from app.schemas.batch import BatchItem
from app.schemas.label import Label
from app.schemas.metrics import Metrics
from app.schemas.wire.disposition import ConfidenceBand, DispositionEnvelope

# The one canonicalisation every audit hash in the tree is computed over. A
# second copy here would let two audit trails disagree about what the same
# input hashes to.
from app.services.audit import _canonical_json, faces_fingerprint
from app.services.headline import headline_reason_code

_logger = logging.getLogger("app.batch.worker")

# The two ways a batch item can fail to be checked. Both are declared in
# `rules/reason_codes.yaml`; neither is a verdict about the label.
_NO_IMAGE = "ENGINE.INPUT.LABEL_IMAGE_MISSING"
_EVALUATION_RAISED = "ENGINE.WORKER.UNHANDLED"


class BatchWorker:
    """Pull-based batch consumer."""

    # How often `_await_demand` re-reads the reviewer's backlog while holding.
    _DEMAND_POLL_SECONDS = 0.01

    def __init__(
        self,
        *,
        in_flight: InFlightBatch,
        evaluator,
        anomaly: AnomalyDetector,
        bus: SSEBus,
        app_lookup: dict[str, Application] | None = None,
        label_lookup: dict[str, Label] | None = None,
        refusals: dict[str, tuple[str, str]] | None = None,
        images=None,
        results=None,
    ) -> None:
        self._in_flight = in_flight
        self._evaluator = evaluator
        self._anomaly = anomaly
        self._bus = bus
        # What the caller already holds for each queued item, keyed by
        # `application_ref` and `label_id`. A missing application is
        # synthesized — a batch of refs still names an application. A missing
        # label is **not**: there is nothing to stand in for image bytes, and
        # the item is refused by name instead (`docs/decisions.md#0020`). Both
        # stay assignable after construction, which is how
        # `app/api/ui/bulk_upload.py` has always filled them.
        self._app_lookup: dict[str, Application] = app_lookup or {}
        self._label_lookup: dict[str, Label] = label_lookup or {}
        # Items the caller already knows cannot be checked, keyed by `label_id`,
        # each carrying its own reason code and the sentence a reviewer reads.
        # The upload route fills this for a file that is not an image: it knows
        # why, and "no image was supplied" would be a worse answer than the one
        # it can give. Refusing per item rather than rejecting the submission is
        # what lets the rest of the batch run (`docs/decisions.md#0020`).
        self._refusals: dict[str, tuple[str, str]] = refusals or {}
        # Where a finished label's photographs and its result are kept so the
        # results page can show them and a reviewer's override has something to
        # amend. Both are optional because a batch submitted as refs over the
        # JSON API has no uploaded bytes to keep and no page to show them on.
        self._images = images
        self._results = results

    def _resolve_application(self, item: BatchItem) -> Application:
        """Resolve the Application for a queued BatchItem.

        Uses `self._app_lookup` when the caller has populated it; otherwise
        synthesizes a minimal `Application` from the `application_ref`, since a
        batch submitted as refs alone carries no application data."""
        if item.application_ref in self._app_lookup:
            return self._app_lookup[item.application_ref]
        # Minted, not taken from `label_id`. `evaluation_id` is emitted on every
        # log line, and `label_id` is the uploader's own filename — borrowing it
        # here put that filename in the logs by way of the allow-list, which is
        # the one route neither the allow-list nor the redaction filter guards.
        return Application(
            application_id=item.application_ref,
            evaluation_id=f"ev-{uuid.uuid4().hex[:12]}",
        )

    def _resolve_label(self, item: BatchItem) -> Label | None:
        """The Label payload for a queued BatchItem, or None if there is none.

        `self._label_lookup` is populated by the bulk upload route, so each item
        there carries the exact bytes uploaded. A batch submitted as refs alone
        carries no image, and **None is the answer** — an item with no bytes is
        not a label, and a stand-in for one would have the reader, the rules and
        the disposition all run over something that is not a label and report a
        verdict about it. The caller refuses the item by name instead
        (`docs/decisions.md#0020`)."""
        return self._label_lookup.get(item.label_id)

    def _refusal_envelope(
        self,
        application: Application,
        *,
        label: Label | None,
        label_id: str,
        reason_code: str,
        started_at: datetime,
        duration_ms: int,
    ) -> DispositionEnvelope:
        """The result for a label the app could not check.

        `needs_review` with no fields, carrying the reason code as its one
        audit-trail row. This is the shape `app/services/evaluator.py` already
        produces when an image is too poor to read, so a label that cannot be
        checked is answered the same way whichever path it arrived on, and the
        reviewer's table shows the item rather than silently dropping it.

        The sentence a reviewer reads is not here — a no-fields envelope has
        nowhere to carry one — it is on the snapshot item's `failed_reason`,
        recorded by `InFlightBatch.record_failure`.
        """
        app_dict = application.model_dump(mode="json")
        # Excluded for the same reason `app/services/audit.py` excludes it: the
        # input hash is a fingerprint of the content, not of the call.
        app_dict.pop("evaluation_id", None)
        artwork = faces_fingerprint(label) if label is not None else b""
        envelope_for_hash = {
            "evaluation_id": application.evaluation_id,
            "label_ref": label_id,
            "disposition": "needs_review",
            "reason_code": reason_code,
        }
        audit = AuditRecord(
            evaluation_id=application.evaluation_id,
            # No rule pack was selected, because nothing was checked — this
            # path never reached an engine, so there is no version to name.
            # An evaluation that did reach one names it: the Evaluator reads
            # `RuleEngine.rule_set_version` onto the timeline. `model_version`
            # is left unset here for the same reason and is honest that way —
            # no reader ran on this path either, so there is nothing to name.
            rule_set_version="unknown",
            input_hash=hashlib.sha256(_canonical_json(app_dict) + artwork).hexdigest(),
            output_hash=hashlib.sha256(_canonical_json(envelope_for_hash)).hexdigest(),
            started_at=started_at,
            completed_at=datetime.now(UTC),
            per_rule_trace=(
                PerRuleTraceEntry(
                    rule_id=reason_code,
                    disposition="needs_review",
                    evidence_ref=f"engine_failure/{reason_code}",
                ),
            ),
        )
        return DispositionEnvelope(
            evaluation_id=application.evaluation_id,
            label_ref=label_id,
            disposition="needs_review",
            disposition_confidence=ConfidenceBand(band="low", numeric=0.0),
            fields=(),
            audit_trail=audit,
            metrics=Metrics(
                total_duration_ms=duration_ms,
                per_rule_durations_ms=(),
                vision_duration_ms=0,
            ),
        )

    def _keep(self, envelope: DispositionEnvelope, label: Label | None) -> None:
        """Put this label's photographs and its result where the page can read
        them, under the id the finished envelope carries.

        The photographs, because a finding a reviewer cannot see the photograph
        for is a finding they cannot check, and the warning is usually on a face
        the front does not show. The result, because an override amends a
        recorded disposition and the in-flight batch holds one only until the
        next batch starts (`docs/decisions.md#0033`).

        A write that fails is logged and swallowed. Neither store is part of the
        verdict, and a full disk must not turn a checked label into an
        unchecked one.
        """
        if self._images is not None and label is not None:
            for face in label.faces:
                try:
                    self._images.put(
                        envelope.evaluation_id,
                        face.content_type,
                        face.image_bytes,
                        face.face_tag,
                    )
                except Exception:
                    _logger.exception(
                        "label_image_not_kept",
                        extra={
                            "evaluation_id": envelope.evaluation_id,
                            "reason_code": "ENGINE.OK.NONE",
                        },
                    )
        if self._results is not None:
            try:
                self._results.put(envelope)
            except Exception:
                _logger.exception(
                    "label_result_not_kept",
                    extra={
                        "evaluation_id": envelope.evaluation_id,
                        "reason_code": "ENGINE.OK.NONE",
                    },
                )

    def _reviewer_backlog(self) -> int:
        """Events broadcast but not yet taken by the slowest attached reader."""
        return max((q.qsize() for q in self._bus.subscribers), default=0)

    async def _await_demand(self) -> None:
        """Hold the next evaluation until the reviewer has caught up.

        The reviewer's pull is the SSE subscriber queue draining, and the window
        is `lookahead_k`: the consumer may run that many results ahead of the
        slowest attached reader and no further, so a 300-label batch does not
        spend its way to the end for a reviewer who is still on label one.

        With no subscriber attached this is inert, which is what the JSON API
        caller who polls `GET /batches/{batch_id}` gets. There is no timeout: a
        reader that stops reading is meant to hold the batch. It cannot wedge,
        because the stream route unsubscribes in its `finally` when the response
        generator closes, and `sse_starlette`'s ping forces that on a reader
        that has gone away.

        It polls rather than waiting on a signal because a drain signal would
        mean changing `app/api/_sse_bus.py`, which is not worth widening this
        change for on a path that is idle whenever anyone is actually reading.
        """
        while self._bus.subscribers and self._reviewer_backlog() > self._in_flight.lookahead_k:
            await asyncio.sleep(self._DEMAND_POLL_SECONDS)

    async def _producer(self) -> None:
        for item in self._in_flight.items:
            await self._in_flight.queue.put(item)

    async def _consume(self) -> None:
        total = len(self._in_flight.items)
        batch_id = self._in_flight.batch_id
        t_batch = time.monotonic()
        _logger.info(
            f"batch_consume_started batch_id={batch_id} items={total} "
            f"lookahead_k={self._in_flight.lookahead_k}",
            extra={"batch_id": batch_id, "reason_code": "ENGINE.OK.NONE"},
        )
        failed = 0
        for queue_position in range(total):
            item: BatchItem = await self._in_flight.queue.get()
            application = self._resolve_application(item)
            label = self._resolve_label(item)
            t_label = time.monotonic()
            started_at = datetime.now(UTC)
            envelope: DispositionEnvelope | None = None
            refusal: tuple[str, str] | None = None  # (reason_code, plain words)

            declared = self._refusals.get(item.label_id)
            if declared is not None:
                # The caller named the reason when it queued the item.
                refusal = declared
            elif label is None:
                refusal = (
                    _NO_IMAGE,
                    f"No image was supplied for {item.label_id}, so it was not checked. "
                    "Send the label files themselves — the batch upload page carries each "
                    "file with its item.",
                )
            else:
                try:
                    envelope = await self._evaluator.evaluate(application, label)
                except Exception as error:
                    # Caught rather than re-raised: the rest of the batch is
                    # still checked (docs/PRD.md FR-13). `Exception` and not
                    # `BaseException`, so cancelling the worker still cancels it.
                    _logger.exception(
                        f"label_evaluation_failed batch_id={batch_id} pos={queue_position}",
                        extra={
                            "batch_id": batch_id,
                            "evaluation_id": application.evaluation_id,
                            "reason_code": _EVALUATION_RAISED,
                        },
                    )
                    refusal = (
                        _EVALUATION_RAISED,
                        f"{item.label_id} could not be checked: the check stopped with "
                        f"{type(error).__name__}. The rest of the batch was checked. Submit "
                        "this label on its own to see what went wrong with it.",
                    )

            duration_ms = int((time.monotonic() - t_label) * 1000)
            if refusal is not None:
                reason_code, message = refusal
                failed += 1
                envelope = self._refusal_envelope(
                    application,
                    label=label,
                    label_id=item.label_id,
                    reason_code=reason_code,
                    started_at=started_at,
                    duration_ms=duration_ms,
                )
                self._in_flight.record_failure(item.label_id, message)
                # `message` is deliberately not logged: it is the sentence the
                # reviewer reads, and it names the file they uploaded.
                # `reason_code` says the same thing to an operator.
                _logger.warning(
                    f"label_not_checked batch_id={batch_id} pos={queue_position}",
                    extra={
                        "batch_id": batch_id,
                        "evaluation_id": application.evaluation_id,
                        "reason_code": reason_code,
                    },
                )
            assert envelope is not None  # one of the two branches always sets it
            self._in_flight.record_result(item.label_id, envelope)
            self._keep(envelope, label)
            # The bytes go as soon as they have been written somewhere a page
            # can fetch them from. Holding them in the worker instead would mean
            # a batch carrying every upload until its last label is done.
            self._label_lookup.pop(item.label_id, None)
            label = None

            headline_code = headline_reason_code(envelope)
            _logger.info(
                f"label_result batch_id={batch_id} pos={queue_position} "
                f"disposition={envelope.disposition} duration_ms={duration_ms}",
                extra={
                    "batch_id": batch_id,
                    "evaluation_id": envelope.evaluation_id,
                    "duration_ms": duration_ms,
                    "reason_code": headline_code or "ENGINE.OK.NONE",
                },
            )

            # Per-label SSE event with queue_position
            self._bus.broadcast(
                {
                    "event": "label-result",
                    "data": {
                        "batch_id": batch_id,
                        "queue_position": queue_position,
                        "envelope": envelope.model_dump(mode="json"),
                    },
                }
            )

            # Anomaly observation. Bind once: the helper is pure today, but
            # binding here pins the contract that ``recent_dispositions`` and
            # ``observe`` see the same code, even if the helper later acquires
            # side effects.
            self._in_flight.recent_dispositions.append(headline_code)
            advisory = self._anomaly.observe(headline_code)
            if advisory is not None:
                _logger.info(
                    f"anomaly_advisory batch_id={batch_id} advisory_id={advisory.advisory_id} "
                    f"count={advisory.count} window={advisory.window}",
                    extra={"batch_id": batch_id, "reason_code": advisory.reason_code},
                )
                self._bus.broadcast(
                    {
                        "event": "anomaly-advisory",
                        "data": {
                            "batch_id": batch_id,
                            "advisory_id": advisory.advisory_id,
                            "reason_code": advisory.reason_code,
                            "count": advisory.count,
                            "window": advisory.window,
                        },
                    }
                )

            # Pull-based demand, at the seam where the work actually costs
            # something. Held after this item's events are out, so the first
            # verdict is never delayed and the rest of the batch runs behind it.
            await self._await_demand()

        batch_duration_ms = int((time.monotonic() - t_batch) * 1000)
        _logger.info(
            f"batch_consume_finished batch_id={batch_id} items={total} failed={failed} "
            f"duration_ms={batch_duration_ms}",
            extra={
                "batch_id": batch_id,
                "duration_ms": batch_duration_ms,
                "reason_code": "ENGINE.OK.NONE",
            },
        )
        self._bus.broadcast(
            {
                "event": "stream-end",
                "data": {
                    "batch_id": batch_id,
                    "total_count": total,
                    # How many of them the app could not check. Every one of those
                    # is in the stream as a needs_review result naming its reason
                    # code, and on the snapshot with the sentence to show a person.
                    "failed_count": failed,
                },
            }
        )

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
                if isinstance(result, BaseException) and not isinstance(
                    result, asyncio.CancelledError
                ):
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
                self._bus.broadcast(
                    {
                        "event": "stream-end",
                        "data": {
                            "batch_id": self._in_flight.batch_id,
                            "total_count": len(self._in_flight.items),
                            "error": "ENGINE.WORKER.UNHANDLED",
                            "error_class": type(consume_error).__name__,
                        },
                    }
                )
