"""Logging package entry point."""
from __future__ import annotations

import logging
import sys
from typing import Any

from app.logging.otel_genai import OtelGenAIFormatter
from app.logging.redaction import RedactionFilter

__all__ = ["configure_logging"]


def configure_logging(settings: Any) -> None:
    """Wire Python ``logging`` to JSON-line stdout with redaction.

    Idempotent: re-invoking replaces the root handler set so test runs do not
    accumulate duplicate emissions.
    """

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(OtelGenAIFormatter())
    handler.addFilter(RedactionFilter())
    level_name = getattr(settings, "log_level", "INFO")
    handler.setLevel(level_name)
    root.addHandler(handler)
    root.setLevel(level_name)
