"""The §16.21 GOVERNMENT WARNING asset is the single source of truth for the
verbatim text the rule pack pins by hash. Mutating either side of that pin
(asset content or rule-pack pin) must be detectable; this test only verifies
that the asset exists and contains both required sentences. Hash-drift detection
lives in tests/test_rule_loader_failclose.py.
"""

from __future__ import annotations

from pathlib import Path

ASSET = Path("assets/warnings/govt_warning_16_21.txt")


def test_asset_exists_and_nonempty() -> None:
    assert ASSET.exists(), f"missing asset: {ASSET}"
    assert ASSET.stat().st_size > 0


def test_asset_contains_required_sentences() -> None:
    text = ASSET.read_text(encoding="utf-8")
    assert "GOVERNMENT WARNING" in text
    assert "Surgeon General" in text
    assert "pregnancy" in text
    assert "operate machinery" in text
