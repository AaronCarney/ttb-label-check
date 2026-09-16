"""Wire fixtures must exist, parse as JSON, and carry the canonical top-level keys."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

EXPECTED_TOP_LEVEL_KEYS: dict[str, set[str]] = {
    "application.json": {
        "permit_number", "source_of_product", "serial_number",
        "type_of_product", "brand_name", "applicant", "phone",
        "type_of_application", "date_of_application", "applicant_print_name",
        "perjury_attested", "labels",
    },
    "disposition.json": {
        "evaluation_id", "label_ref", "disposition", "disposition_confidence",
        "fields", "audit_trail", "metrics",
    },
    "batch.json": {"batch_id", "agent_id", "submitted_at", "items"},
    "error.json": {"error_kind", "reason_code", "message", "details"},
}


@pytest.mark.parametrize("name,keys", list(EXPECTED_TOP_LEVEL_KEYS.items()))
def test_fixture_exists_parses_and_has_required_keys(
    wire_fixtures_dir: Path, name: str, keys: set[str]
) -> None:
    path = wire_fixtures_dir / name
    assert path.exists(), f"missing fixture: {name}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert keys.issubset(data.keys()), f"{name} missing keys: {keys - data.keys()}"
