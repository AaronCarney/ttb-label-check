"""Redaction filter: nothing a submission contains reaches the logs.

Drops at emission time:
- Submitted application content (the JSON body in toto).
- Label artwork bytes.
- Extracted field values verbatim.

Preserves: evaluation_id, batch_id, label_id, reason_code, duration_ms,
rule_set_version, model_version, prompt_version, error_class.
"""
from __future__ import annotations

import logging


REDACTED_FIELDS = (
    "application_content",
    "application_body",
    "label_bytes",
    "image_bytes",
    "extracted_text",
    "extracted_value",
    "verbatim_text",
)


class RedactionFilter(logging.Filter):
    """Strip configured fields from every emitted record before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        for attr in REDACTED_FIELDS:
            if hasattr(record, attr):
                setattr(record, attr, None)
        return True
