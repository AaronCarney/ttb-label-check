"""Backward-compatible shim over ``RuleEngine.build_validator_context``.

The abstract method on ``RuleEngine`` (``app/rules/engine.py``) is the source
of truth for per-evaluation ``ValidatorContext`` construction. This module
preserves a free-function name for any caller that prefers it; everything
delegates to the engine method.
"""
from __future__ import annotations

from app.rules._validators import ValidatorContext
from app.rules.engine import RuleEngine


def build_validator_context(
    engine: RuleEngine, *, started_at_ms: int
) -> ValidatorContext:
    return engine.build_validator_context(started_at_ms=started_at_ms)
