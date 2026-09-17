"""Regression: the batch-worker log call sites do not leak content
through the OtelGenAIFormatter / RedactionFilter contract.

Locks the contract that:

1. Whitelisted structured fields (`batch_id`, `evaluation_id`, `reason_code`,
   `duration_ms`, `error_class`) survive emission, and `label_id` does not:
   it carries the uploader's filename and is submission content.
2. Redaction-stripped fields (`image_bytes`, `extracted_text`, etc.) do
   not appear in the JSON line — even if a future call site accidentally
   sets them via ``extra=``.
3. Arbitrary off-whitelist keys — an ``exception_class`` that the schema does
   not name, say — are dropped silently, so the formatter enforces the schema
   rather than letting drift pass through.
"""
from __future__ import annotations

import json
import logging

from app.logging.otel_genai import OtelGenAIFormatter
from app.logging.redaction import RedactionFilter


def _emit(record: logging.LogRecord) -> dict:
    """Run a record through both filter and formatter, return parsed JSON."""
    filter_ = RedactionFilter()
    formatter = OtelGenAIFormatter()
    assert filter_.filter(record) is True
    return json.loads(formatter.format(record))


def _record(msg: str, **extras) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.batch.worker",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=None,
        exc_info=None,
    )
    for key, value in extras.items():
        setattr(record, key, value)
    return record


def test_label_result_emits_whitelisted_fields() -> None:
    record = _record(
        "label_result batch_id=B-1 pos=0 disposition=pass duration_ms=42",
        batch_id="B-1",
        label_id="L-1",
        evaluation_id="00000000-0000-4000-8000-000000000001",
        duration_ms=42,
        reason_code="ENGINE.OK.NONE",
    )
    parsed = _emit(record)
    assert parsed["msg"].startswith("label_result")
    assert parsed["batch_id"] == "B-1"
    assert "label_id" not in parsed
    assert parsed["evaluation_id"] == "00000000-0000-4000-8000-000000000001"
    assert parsed["duration_ms"] == 42
    assert parsed["reason_code"] == "ENGINE.OK.NONE"


def test_label_evaluation_failed_emits_error_class() -> None:
    record = _record(
        "label_evaluation_failed batch_id=B-2 label_id=L-X pos=3",
        batch_id="B-2",
        label_id="L-X",
        evaluation_id="00000000-0000-4000-8000-000000000002",
        reason_code="ENGINE.WORKER.UNHANDLED",
        error_class="RuntimeError",
    )
    parsed = _emit(record)
    assert parsed["error_class"] == "RuntimeError"
    assert parsed["reason_code"] == "ENGINE.WORKER.UNHANDLED"


def test_redaction_filter_strips_image_bytes_even_via_extra() -> None:
    """If a future call site accidentally passes image_bytes via ``extra=``
    (or sets it on the record), the filter MUST strip it before emit."""
    record = _record(
        "label_result batch_id=B-3",
        batch_id="B-3",
        label_id="L-Y",
        reason_code="ENGINE.OK.NONE",
        image_bytes=b"\x89PNG\r\n\x1a\n" + b"secret-bytes",
        extracted_text="MOUNTAIN BREWERY EST 1924",
        application_content={"brand_name": "MOUNTAIN BREWERY"},
    )
    parsed = _emit(record)
    raw = json.dumps(parsed)
    assert "secret-bytes" not in raw
    assert "MOUNTAIN BREWERY" not in raw
    assert "image_bytes" not in parsed
    assert "extracted_text" not in parsed
    assert "application_content" not in parsed
    assert parsed["batch_id"] == "B-3"


def test_off_whitelist_extras_dropped_silently() -> None:
    """The formatter must NOT pass arbitrary ``extra=`` keys through — that is
    the failure mode that would let an off-schema key drift in unnoticed."""
    record = _record(
        "engine_failure_routed",
        evaluation_id="00000000-0000-4000-8000-000000000003",
        reason_code="ENGINE.RULES.UNAVAILABLE",
        exception_class="ValueError",  # NOT whitelisted — must be dropped
        custom_field="should-not-emit",
    )
    parsed = _emit(record)
    assert "exception_class" not in parsed
    assert "custom_field" not in parsed
    assert parsed["reason_code"] == "ENGINE.RULES.UNAVAILABLE"


def test_override_applied_emits_full_correlation_set() -> None:
    record = _record(
        "override_applied batch_id=B-4 evaluation_id=E-7 field=brand_name pass->fail bus=True",
        batch_id="B-4",
        label_id="L-Z",
        evaluation_id="00000000-0000-4000-8000-000000000004",
        reason_code="REJ.LABEL.GENERIC",
    )
    parsed = _emit(record)
    assert parsed["batch_id"] == "B-4"
    assert "label_id" not in parsed
    assert parsed["evaluation_id"] == "00000000-0000-4000-8000-000000000004"
    assert parsed["reason_code"] == "REJ.LABEL.GENERIC"


def test_batch_stream_closed_carries_terminator_in_msg() -> None:
    """The terminator-vs-disconnect distinction lives in the msg string;
    ``terminated=true|false`` is the greppable token."""
    record = _record(
        "batch_stream_closed batch_id=B-5 events=12 terminated=true",
        batch_id="B-5",
        reason_code="ENGINE.OK.NONE",
    )
    parsed = _emit(record)
    assert "terminated=true" in parsed["msg"]
    assert parsed["batch_id"] == "B-5"


def test_label_id_is_never_emitted_even_when_a_call_site_passes_it() -> None:
    """The filename arrives as `label_id`. A call site that passes it anyway
    must not put it in the log line."""
    record = _record(
        "label_not_checked batch_id=B-6 pos=0",
        batch_id="B-6",
        label_id="B-6-000-Jane-Doe-Medical-Release.png",
        evaluation_id="ev-0123456789ab",
        reason_code="ENGINE.INPUT.UNSUPPORTED_IMAGE",
    )
    parsed = _emit(record)
    assert "label_id" not in parsed
    assert "Jane-Doe" not in json.dumps(parsed)
