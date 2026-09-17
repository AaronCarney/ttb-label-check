"""Logging subsystem: formatter + redaction + configure_logging."""

from __future__ import annotations

import json
import logging


def test_otel_genai_formatter_emits_one_json_line() -> None:
    from app.logging.otel_genai import OtelGenAIFormatter

    formatter = OtelGenAIFormatter()
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="evaluation_complete",
        args=None,
        exc_info=None,
    )
    record.evaluation_id = "00000000-0000-4000-8000-000000000001"
    line = formatter.format(record)
    parsed = json.loads(line)
    assert parsed["msg"] == "evaluation_complete"
    assert parsed["level"] == "INFO"
    assert parsed["evaluation_id"] == "00000000-0000-4000-8000-000000000001"
    assert "ts" in parsed


def test_otel_genai_formatter_uses_gen_ai_attribute_names() -> None:
    """LLM-call log lines use the OpenTelemetry GenAI field names."""
    from app.logging.otel_genai import OtelGenAIFormatter

    formatter = OtelGenAIFormatter()
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="llm_call",
        args=None,
        exc_info=None,
    )
    setattr(record, "gen_ai.request.model", "gpt-4o-2024-08-06")
    setattr(record, "gen_ai.response.model", "gpt-4o-2024-08-06")
    setattr(record, "gen_ai.usage.input_tokens", 1234)
    line = formatter.format(record)
    parsed = json.loads(line)
    assert parsed["gen_ai.request.model"] == "gpt-4o-2024-08-06"
    assert parsed["gen_ai.usage.input_tokens"] == 1234


def test_redaction_filter_strips_application_content_and_label_bytes() -> None:
    from app.logging.redaction import RedactionFilter

    filter_ = RedactionFilter()
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="leakage_attempt",
        args=None,
        exc_info=None,
    )
    record.application_content = {"brand_name": "secret"}
    record.label_bytes = b"\xff\xd8\xff..."
    record.extracted_text = "verbatim contents that should not log"
    record.evaluation_id = "00000000-0000-4000-8000-000000000001"
    record.reason_code = "ENGINE.OK.NONE"
    assert filter_.filter(record) is True  # filter does not drop the record
    assert not hasattr(record, "application_content") or record.application_content is None
    assert not hasattr(record, "label_bytes") or record.label_bytes is None
    assert not hasattr(record, "extracted_text") or record.extracted_text is None
    # Preserved fields
    assert record.evaluation_id == "00000000-0000-4000-8000-000000000001"
    assert record.reason_code == "ENGINE.OK.NONE"


def test_call_record_ring_buffer_default_maxlen_is_200() -> None:
    from app.logging.ring_buffer import new_call_ring_buffer

    rb = new_call_ring_buffer()
    assert rb.maxlen == 200
    assert len(rb) == 0


def test_call_record_ring_buffer_evicts_fifo_at_capacity() -> None:
    from app.logging.ring_buffer import new_call_ring_buffer

    rb = new_call_ring_buffer(maxlen=3)
    rb.append("a")
    rb.append("b")
    rb.append("c")
    rb.append("d")  # evicts "a"
    assert list(rb) == ["b", "c", "d"]


def test_configure_logging_wires_formatter_and_redaction(capsys) -> None:
    import logging as stdlib_logging

    from app.logging import configure_logging

    # A caller-provided settings shim, so this test does not import app.config.
    class _StubSettings:
        log_level: str = "INFO"

    configure_logging(_StubSettings())
    logger = stdlib_logging.getLogger("app.test")
    logger.info("healthz_invoked", extra={"evaluation_id": "evt-001"})
    captured = capsys.readouterr()
    assert captured.out.count("\n") == 1
    import json

    parsed = json.loads(captured.out.strip())
    assert parsed["msg"] == "healthz_invoked"
    assert parsed["evaluation_id"] == "evt-001"
