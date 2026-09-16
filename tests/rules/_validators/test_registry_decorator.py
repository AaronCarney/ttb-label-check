"""Validator-registry contract: @register binds a name; duplicates raise; lookup works."""
from __future__ import annotations

import pytest

from app.rules._validators import (
    VALIDATOR_REGISTRY,
    ValidatorContext,
    register,
)


def test_register_decorator_binds_name() -> None:
    @register("__test_demo__")
    def demo(*args, **kwargs):
        return "demo"

    assert VALIDATOR_REGISTRY["__test_demo__"] is demo
    del VALIDATOR_REGISTRY["__test_demo__"]


def test_register_rejects_duplicate_name() -> None:
    @register("__test_dup__")
    def first(*args, **kwargs):
        return 1

    with pytest.raises(ValueError, match="already registered"):
        @register("__test_dup__")
        def second(*args, **kwargs):
            return 2

    del VALIDATOR_REGISTRY["__test_dup__"]


def test_validator_context_is_frozen_dataclass() -> None:
    ctx = ValidatorContext(
        assets={},
        decision_tables={},
        started_at_ms=0,
        engine_version="0.0.0",
    )
    with pytest.raises(Exception):
        ctx.engine_version = "mutated"  # type: ignore[misc]
