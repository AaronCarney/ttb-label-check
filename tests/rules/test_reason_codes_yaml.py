"""reason_codes.yaml is the reason-code registry. Shape:
  version: <semver>
  bins: { BIN: <description>, ... }
  codes: { BIN.SUB.SPECIFIC[.QUALIFIER]: { description, cfr_anchors, severity } }

Every code referenced by any rule pack must appear here, otherwise the loader
fail-closes. This test enforces the file's structural
contract independently of the loader.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REGISTRY = Path("rules/reason_codes.yaml")
GRAMMAR = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*){2,3}$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
BINS_REQUIRED = {"BRAND", "CLASS_TYPE", "ALCOHOL_CONTENT", "NAME_ADDRESS",
                 "NET_CONTENTS", "WARNING", "LEGIBILITY", "ENGINE", "AGE_STATEMENT"}


def test_registry_parses() -> None:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert SEMVER.match(data["version"])
    assert BINS_REQUIRED.issubset(set(data["bins"]))


def test_every_code_obeys_grammar() -> None:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    bad = [c for c in data["codes"] if not GRAMMAR.match(c)]
    assert bad == [], f"reason codes failing grammar: {bad}"


def test_every_code_has_required_fields() -> None:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    for code, entry in data["codes"].items():
        assert "description" in entry, code
        assert "cfr_anchors" in entry, code
        assert "severity" in entry, code
        assert entry["severity"] in {"reject", "warn", "info"}, code


def test_brand_needs_review_code_present() -> None:
    """BRAND.NAME.NEEDS_REVIEW must be in the registry: it is the code a
    borderline brand match reports, which sends the label to a reviewer."""
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    assert "BRAND.NAME.NEEDS_REVIEW" in data["codes"]


EXPECTED_LEGIBILITY_WARN_CODES = {
    "WARNING.LEGIBILITY.GLARE",
    "WARNING.LEGIBILITY.MOTION_BLUR",
}


def test_legibility_warn_codes_present() -> None:
    """The GLARE and MOTION_BLUR warn codes the reader emits must be in the registry."""
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    missing = EXPECTED_LEGIBILITY_WARN_CODES - set(data["codes"])
    assert missing == set(), f"missing legibility warn codes: {missing}"
