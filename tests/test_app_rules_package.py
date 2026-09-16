"""Smoke: the app.rules package is importable."""
from __future__ import annotations


def test_app_rules_importable() -> None:
    import app.rules  # noqa: F401
