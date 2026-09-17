"""build_rule_engine(settings) — constructs YamlRuleEngine after forcing
validator-decorator imports (per loader.py:24-29 forward note)."""

from pathlib import Path

import pytest

from app.config import Settings
from app.rules import build_rule_engine
from app.rules._validators import VALIDATOR_REGISTRY
from app.rules.yaml_engine import YamlRuleEngine


@pytest.fixture
def rules_root_env(monkeypatch):
    """Pin RULES_ROOT to an absolute path so neither test depends on the
    interpreter's import-time CWD (Settings.rules_root default resolves
    `Path('rules')` at module load)."""
    monkeypatch.setenv("RULES_ROOT", str(Path("rules").resolve()))


def test_build_rule_engine_returns_yaml_engine(rules_root_env):
    engine = build_rule_engine(Settings())
    assert isinstance(engine, YamlRuleEngine)


def test_build_rule_engine_populates_validator_registry(rules_root_env):
    engine = build_rule_engine(Settings())
    # Force-import side effect must register at least one validator.
    assert len(VALIDATOR_REGISTRY) >= 1
    # Engine carries a non-empty ruleset against the real fixtures.
    assert len(engine._ruleset.rules) >= 1
