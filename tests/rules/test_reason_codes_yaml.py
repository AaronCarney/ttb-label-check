"""reason_codes.yaml is the reason-code registry. Shape:
  version: <semver>
  bins: { BIN: <description>, ... }
  codes: { BIN.SUB.SPECIFIC[.QUALIFIER]: { description, cfr_anchors, severity } }
  reviewer_vocabulary: { CODE: <why it stays>, ... }

Every code referenced by any rule pack must appear here, otherwise the loader
fail-closes. This test enforces the file's structural contract independently of
the loader: the blocks are present, every code obeys the grammar, sits in a bin
the file declares, and carries the three fields an entry needs.

Whether a registered code is actually used, and whether an unused one is
declared in `reviewer_vocabulary`, is the other half of the contract and lives
in tests/rules/test_reason_code_registry.py.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REGISTRY = Path("rules/reason_codes.yaml")
GRAMMAR = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*){2,3}$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
# ORIGIN was left out of this set when it was written, though the file has
# carried an ORIGIN bin and three ORIGIN codes throughout.
BINS_REQUIRED = {"BRAND", "CLASS_TYPE", "ALCOHOL_CONTENT", "NAME_ADDRESS",
                 "NET_CONTENTS", "ORIGIN", "WARNING", "LEGIBILITY", "ENGINE",
                 "AGE_STATEMENT"}


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


def _bin_of(code: str) -> str:
    return code.split(".")[0]


def test_every_code_sits_in_a_declared_bin() -> None:
    """A code whose first segment is not a key of `bins:` is outside the
    registry's own namespace, and invisible to the source scan in
    tests/rules/test_reason_code_registry.py, which is anchored on the bins."""
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    declared = set(data["bins"])
    stray = sorted({c for c in data["codes"] if _bin_of(c) not in declared})
    assert stray == [], f"reason codes in no declared bin: {stray}"


def test_the_declared_bin_check_catches_a_stray_code() -> None:
    declared = {"BRAND", "ENGINE"}
    codes = ["BRAND.PRESENCE.MISSING", "PACKAGING.SIZE.WRONG"]
    stray = sorted({c for c in codes if _bin_of(c) not in declared})
    assert stray == ["PACKAGING.SIZE.WRONG"]


def test_every_declared_bin_carries_at_least_one_code() -> None:
    """A bin with no codes is a heading for nothing, and it widens the source
    scan's net over a namespace the registry does not use."""
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    used = {_bin_of(c) for c in data["codes"]}
    empty = sorted(set(data["bins"]) - used)
    assert empty == [], f"bins declared but carrying no code: {empty}"


def test_the_empty_bin_check_catches_an_unused_bin() -> None:
    bins = {"BRAND", "PACKAGING"}
    used = {_bin_of(c) for c in ["BRAND.PRESENCE.MISSING"]}
    assert sorted(bins - used) == ["PACKAGING"]
