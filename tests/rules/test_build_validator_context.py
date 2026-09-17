"""RuleEngine.build_validator_context — abstract-method seam.

Validates the abstract method on the concrete YamlRuleEngine the
build_rule_engine factory returns: assets, decision tables and engine version
come off the engine's own rule set, and the per-evaluation clock comes from the
caller. The fake rule engine is exercised elsewhere, so this file stays on the
production path.
"""

from app.config import Settings
from app.rules import build_rule_engine
from app.rules._validators import ValidatorContext
from app.rules.context import build_validator_context  # thin shim → engine method


def test_yaml_engine_build_validator_context_returns_validator_context():
    engine = build_rule_engine(Settings())
    ctx = engine.build_validator_context(started_at_ms=12345)
    assert isinstance(ctx, ValidatorContext)


def test_yaml_engine_build_validator_context_sources_from_ruleset():
    engine = build_rule_engine(Settings())
    ctx = engine.build_validator_context(started_at_ms=99)
    assert ctx.assets == engine._ruleset.assets
    assert ctx.decision_tables == engine._ruleset.decision_tables
    assert ctx.started_at_ms == 99
    assert ctx.engine_version  # non-empty (sourced from RuleSet.version)


def test_shim_delegates_to_engine_method():
    """The free-function shim is a one-line forwarder so existing recipes that
    prefer the free-function name still work — but the contract lives on the
    abstraction."""
    engine = build_rule_engine(Settings())
    via_method = engine.build_validator_context(started_at_ms=7)
    via_shim = build_validator_context(engine, started_at_ms=7)
    assert via_method == via_shim
