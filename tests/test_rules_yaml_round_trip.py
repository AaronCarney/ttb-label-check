"""Every YAML file under rules/ must load to a valid RuleSet and survive a
model_dump → model_validate round-trip without information loss for shapes the
loader cares about (rule_id, validator, reason_code, match_policy, parameters,
tolerance, decision_table_ref, asset).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.rules.loader import YamlRuleLoader
from app.schemas.rules import RuleSet
from tests.rules.fixtures import load_all_validators

# The loader refuses a pack naming a validator the registry has not got, and a
# validator registers on import. Register them all here, as the running app
# does, so this file loads the real pack whether it runs alone or in a suite.
load_all_validators()


def test_real_rule_tree_loads() -> None:
    rs = YamlRuleLoader().load(Path("rules"))
    assert isinstance(rs, RuleSet)
    assert len(rs.rules) >= 33  # the pack never shrinks below its current size


def test_real_rule_tree_round_trips() -> None:
    rs = YamlRuleLoader().load(Path("rules"))
    dumped = json.loads(rs.model_dump_json())
    rs2 = RuleSet.model_validate(dumped)
    assert rs == rs2


def test_no_orphan_validators_in_registry() -> None:
    """Bidirectional orphan check (registry→YAML direction).

    Every registered validator name MUST be referenced by ≥1 rule in the loaded
    RuleSet. The companion check (file→registry: every validator file registers
    ≥1 name) lives in tests/test_validator_registry.py. Together they keep dead
    validator code from shipping unnoticed. Test-only stubs registered under
    __dunder__ names are excluded, so per-test fixtures do not pollute the
    production surface.
    """
    from app.rules._validators import VALIDATOR_REGISTRY
    rs = YamlRuleLoader().load(Path("rules"))
    referenced = {r.validator for r in rs.rules}
    production_names = {n for n in VALIDATOR_REGISTRY if not n.startswith("__")}
    orphans = production_names - referenced
    assert not orphans, f"validators registered but never referenced: {sorted(orphans)}"
