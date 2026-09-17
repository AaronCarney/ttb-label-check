"""Rule-loader failure modes, ten cross-checks in all. Each malformed YAML triggers
RuleLoaderError with a violation-count message. Tests use a tmp_path-built
rule tree so they do not depend on the real rules/ tree.
"""
from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

import pytest

import app.rules._validators.equality_match
import app.rules._validators.presence_check
import app.rules._validators.verbatim_hash  # noqa: F401
from app.rules._validators import VALIDATOR_REGISTRY  # noqa: F401  (force registry population)
from app.rules.loader import RuleLoaderError, YamlRuleLoader

REGISTRY_YAML = """
version: "0.1.0"
bins:
  WARNING: ""
  BRAND: ""
codes:
  WARNING.PRESENCE.MISSING:
    description: ""
    cfr_anchors: []
    severity: reject
  WARNING.VERBATIM.MISMATCH:
    description: ""
    cfr_anchors: []
    severity: reject
  BRAND.PRESENCE.MISSING:
    description: ""
    cfr_anchors: []
    severity: reject
"""


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text), encoding="utf-8")


def _baseline_rule_yaml(rule_id: str = "test.brand.present", validator: str = "presence_check", reason: str = "BRAND.PRESENCE.MISSING") -> str:
    return f"""
        rule_pack: test
        rule_pack_version: "0.1.0"
        rules:
          - rule_id: {rule_id}
            cfr_citation: "27 CFR §0.0"
            applies_to_classes: [spirits]
            reason_code: {reason}
            severity: reject
            match_policy: exact
            validator: {validator}
            evidence_required: [brand]
            effective_date: "2026-09-09"
            test_fixtures: [F-X-1]
        """


def _setup(tmp_path: Path, rules_text: str = "", extra_files: dict | None = None) -> Path:
    rules = tmp_path / "rules"
    _write(rules / "reason_codes.yaml", REGISTRY_YAML)
    if rules_text:
        _write(rules / "test_pack.yaml", rules_text)
    for rel, body in (extra_files or {}).items():
        _write(rules / rel, body)
    return rules


def test_unknown_validator_fails_closed(tmp_path: Path) -> None:
    rules = _setup(tmp_path, _baseline_rule_yaml(validator="not_real"))
    with pytest.raises(RuleLoaderError, match="unknown validator"):
        YamlRuleLoader().load(rules)


def test_unknown_reason_code_fails_closed(tmp_path: Path) -> None:
    rules = _setup(tmp_path, _baseline_rule_yaml(reason="DOES.NOT.EXIST"))
    with pytest.raises(RuleLoaderError, match="reason_code .* not in registry"):
        YamlRuleLoader().load(rules)


def test_duplicate_rule_id_fails_closed(tmp_path: Path) -> None:
    body = textwrap.dedent("""
        rule_pack: test
        rule_pack_version: "0.1.0"
        rules:
          - rule_id: test.brand.present
            cfr_citation: "27 CFR §0.0"
            applies_to_classes: [spirits]
            reason_code: BRAND.PRESENCE.MISSING
            severity: reject
            match_policy: exact
            validator: presence_check
            evidence_required: [brand]
            effective_date: "2026-09-09"
            test_fixtures: [F-X-1]
          - rule_id: test.brand.present
            cfr_citation: "27 CFR §0.0"
            applies_to_classes: [spirits]
            reason_code: BRAND.PRESENCE.MISSING
            severity: reject
            match_policy: exact
            validator: presence_check
            evidence_required: [brand]
            effective_date: "2026-09-09"
            test_fixtures: [F-X-1]
    """)
    rules = _setup(tmp_path, body)
    with pytest.raises(RuleLoaderError, match="duplicate rule_id"):
        YamlRuleLoader().load(rules)


def test_empty_test_fixtures_fails_closed(tmp_path: Path) -> None:
    body = _baseline_rule_yaml().replace("test_fixtures: [F-X-1]", "test_fixtures: []")
    rules = _setup(tmp_path, body)
    with pytest.raises(RuleLoaderError, match="test_fixtures"):
        YamlRuleLoader().load(rules)


def test_pack_version_outside_range_fails_closed(tmp_path: Path) -> None:
    body = _baseline_rule_yaml().replace("rule_pack_version: \"0.1.0\"", "rule_pack_version: \"9.9.9\"")
    rules = _setup(tmp_path, body)
    with pytest.raises(RuleLoaderError, match="outside engine-supported"):
        YamlRuleLoader().load(rules)


def test_invalid_semver_fails_closed(tmp_path: Path) -> None:
    body = _baseline_rule_yaml().replace("rule_pack_version: \"0.1.0\"", "rule_pack_version: \"banana\"")
    rules = _setup(tmp_path, body)
    with pytest.raises(RuleLoaderError, match="semver"):
        YamlRuleLoader().load(rules)


def test_yaml_parse_error_fails_closed(tmp_path: Path) -> None:
    rules = _setup(tmp_path, "::: not yaml :::")
    with pytest.raises(RuleLoaderError, match="YAML parse"):
        YamlRuleLoader().load(rules)


def test_asset_hash_drift_fails_closed(tmp_path: Path) -> None:
    asset = tmp_path / "assets/warnings/x.txt"
    _write(asset, "different content here")
    real_sha = hashlib.sha256(b"different content here").hexdigest()
    body = _baseline_rule_yaml(validator="verbatim_hash", reason="WARNING.VERBATIM.MISMATCH").rstrip() + """
            asset:
              path: assets/warnings/x.txt
              sha256_pin: deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef
              normalization: []
        """
    body = body.replace("BRAND.PRESENCE.MISSING", "WARNING.VERBATIM.MISMATCH")
    body = body.replace("test.brand.present", "test.warning.verbatim")
    rules = _setup(tmp_path, body)
    with pytest.raises(RuleLoaderError, match="asset hash drift"):
        YamlRuleLoader(rules_root_for_assets=tmp_path).load(rules)


def test_asset_file_missing_fails_closed(tmp_path: Path) -> None:
    body = _baseline_rule_yaml(validator="verbatim_hash", reason="WARNING.VERBATIM.MISMATCH").rstrip() + """
            asset:
              path: assets/warnings/missing.txt
              sha256_pin: deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef
              normalization: []
        """
    rules = _setup(tmp_path, body)
    with pytest.raises(RuleLoaderError, match="asset file not found"):
        YamlRuleLoader(rules_root_for_assets=tmp_path).load(rules)


def test_decision_table_ref_dangling_fails_closed(tmp_path: Path) -> None:
    body = _baseline_rule_yaml(validator="unmeasurable", reason="WARNING.PRESENCE.MISSING")
    body = body.replace("evidence_required: [brand]", "evidence_required: [brand]\n            decision_table_ref: tables/does_not_exist")
    rules = _setup(tmp_path, body)
    # unmeasurable must be importable for the registry check; force-import here:
    import app.rules._validators.unmeasurable  # noqa: F401
    with pytest.raises(RuleLoaderError, match="decision_table_ref"):
        YamlRuleLoader().load(rules)
