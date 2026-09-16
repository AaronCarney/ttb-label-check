"""Bootstrap-level smoke tests: dependencies install, app package importable."""
from __future__ import annotations


def test_fastapi_importable() -> None:
    import fastapi  # noqa: F401


def test_pydantic_v2() -> None:
    import pydantic
    assert pydantic.VERSION.startswith("2."), pydantic.VERSION


def test_pydantic_settings_importable() -> None:
    import pydantic_settings  # noqa: F401


def test_app_package_importable() -> None:
    import app  # noqa: F401
