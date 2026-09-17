"""JSON-line log formatter using OpenTelemetry GenAI semantic-convention
attribute names.

Future ``OTEL_EXPORTER_OTLP_ENDPOINT`` env var flips emission to a real OTel
collector without code changes.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


# Fields carried on every log line, whatever the event.
#
# `label_id` is deliberately absent. It is a display reference and carries the
# uploader's own filename, so it is submission content and belongs with the
# fields the redaction filter drops, not with the telemetry keys. A log line
# locates a label by `evaluation_id`, or by `batch_id` and the queue position
# in the message.
CROSS_CUTTING_FIELDS = (
    "evaluation_id",
    "batch_id",
    "reason_code",
    "duration_ms",
    "rule_set_version",
    "model_version",
    "prompt_version",
    "error_class",
)

# OpenTelemetry GenAI semantic-convention attribute names. Records may carry
# any subset of these via ``LogRecord`` attributes; the formatter passes them
# through verbatim so attribute names follow the OTel spec.
OTEL_GENAI_ATTRIBUTES = (
    "gen_ai.request.model",
    "gen_ai.response.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.system",
    "gen_ai.operation.name",
)


class OtelGenAIFormatter(logging.Formatter):
    """Emit one JSON line per log record, with OTel GenAI attribute names."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        for attr in CROSS_CUTTING_FIELDS:
            value = getattr(record, attr, None)
            if value is not None:
                payload[attr] = value
        for attr in OTEL_GENAI_ATTRIBUTES:
            value = getattr(record, attr, None)
            if value is not None:
                payload[attr] = value
        if record.exc_info:
            payload["exc_class"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, separators=(",", ":"), default=str)
