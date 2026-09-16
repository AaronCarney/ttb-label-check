"""Conftest fixtures must be importable and produce the documented helpers."""
from __future__ import annotations


def test_synthetic_image_fixture(synthetic_jpeg_bytes: bytes) -> None:
    assert synthetic_jpeg_bytes[:3] == b"\xff\xd8\xff"  # JPEG SOI marker
    assert len(synthetic_jpeg_bytes) > 100


def test_wire_fixtures_dir_path(wire_fixtures_dir) -> None:
    assert wire_fixtures_dir.is_dir()
    assert wire_fixtures_dir.name == "wire_fixtures"
