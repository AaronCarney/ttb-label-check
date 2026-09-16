"""YamlRuleEngine.evaluate runs every rule in the RuleSet that applies to the
observation's beverage class, wraps each call in a 250 ms timeout, and isolates
exceptions. Output is a tuple of ValidationResult, sorted by rule_id.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest

# Populate VALIDATOR_REGISTRY by walking the validator subpackage. The loader
# refuses to start unless every RuleDefinition.validator name is registered, so
# the registry must be complete before the engine runs. Listing the validators
# one import at a time works too, but goes stale as new ones land; walking the
# package mirrors what the production CLI does, so this test exercises the same
# import path the runtime takes.
_pkg = importlib.import_module("app.rules._validators")
for _mod in pkgutil.iter_modules(_pkg.__path__):
    importlib.import_module(f"app.rules._validators.{_mod.name}")

from app.rules.engine import RuleEngine  # noqa: E402
from app.rules.loader import YamlRuleLoader  # noqa: E402
from app.rules.yaml_engine import YamlRuleEngine  # noqa: E402
from app.schemas.expected import BeverageClass  # noqa: E402
from app.schemas.rejection import Outcome, ValidationResult  # noqa: E402
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule  # noqa: E402


@pytest.fixture(scope="module")
def ruleset():
    return YamlRuleLoader().load(Path("rules"))


def test_engine_is_abc_with_async_abstract_evaluate() -> None:
    """RuleEngine.evaluate is an async abstract method.

    `hasattr(RuleEngine, "evaluate")` would pass for a non-abstract
    `evaluate = None`, defeating the contract. Assert both:
      - it is a coroutine function (async def)
      - it is marked @abstractmethod (subclasses must override)
    """
    assert inspect.iscoroutinefunction(RuleEngine.evaluate)
    assert getattr(RuleEngine.evaluate, "__isabstractmethod__", False)


@pytest.mark.asyncio
async def test_yaml_engine_evaluates_applicable_rules(ruleset) -> None:
    obs = [
        make_obs(field_id="brand", value="Acme Lager", beverage_class=BeverageClass.MALT),
        make_obs(field_id="net_contents", value="12 fl oz", beverage_class=BeverageClass.MALT),
    ]
    exp = [
        make_expected(field_id="brand", value="Acme Lager"),
        make_expected(field_id="net_contents", value="12 fl oz"),
    ]
    ctx = make_context(assets=ruleset.assets, decision_tables=ruleset.decision_tables)
    engine = YamlRuleEngine(ruleset)
    results = await engine.evaluate(obs, exp, ctx)
    assert isinstance(results, tuple)
    assert len(results) > 0
    assert all(isinstance(r, ValidationResult) for r in results)
    assert [r.rule_id for r in results] == sorted(r.rule_id for r in results)


@pytest.mark.asyncio
async def test_yaml_engine_skips_non_matching_classes(ruleset) -> None:
    """A wine-only rule should not produce a result for a malt observation."""
    obs = [make_obs(field_id="brand", value="Foo", beverage_class=BeverageClass.MALT)]
    exp = [make_expected(field_id="brand", value="Foo")]
    ctx = make_context(assets=ruleset.assets, decision_tables=ruleset.decision_tables)
    engine = YamlRuleEngine(ruleset)
    results = await engine.evaluate(obs, exp, ctx)
    rule_ids = {r.rule_id for r in results}
    assert not any(rid.startswith("wine.") for rid in rule_ids)


@pytest.mark.asyncio
async def test_yaml_engine_records_per_rule_timing(ruleset) -> None:
    """Every result carries engine-measured started_at_ms (monotonic ms) and
    elapsed_ms (the per-rule duration).

    The validator-side `_build_meta` defaults elapsed_ms to 0; the engine
    must overwrite it on the success path so audit consumers see real
    per-rule timing rather than a uniform zero.
    """
    obs = [make_obs(field_id="brand", value="Acme Lager", beverage_class=BeverageClass.MALT)]
    exp = [make_expected(field_id="brand", value="Acme Lager")]
    ctx = make_context(assets=ruleset.assets, decision_tables=ruleset.decision_tables)
    engine = YamlRuleEngine(ruleset)
    results = await engine.evaluate(obs, exp, ctx)
    assert results
    for r in results:
        assert r.engine_meta is not None
        assert r.engine_meta.started_at_ms > 0, f"started_at_ms not set: {r.rule_id}"
        assert r.engine_meta.elapsed_ms >= 0, f"elapsed_ms negative: {r.rule_id}"


@pytest.mark.asyncio
async def test_yaml_engine_unregistered_validator_emits_not_found() -> None:
    """A validator name that is not in the registry is a CONFIGURATION error
    (loader cross-check 6 normally rejects at startup), distinct from a
    validator that exists and crashes at runtime (ENGINE.VALIDATOR.EXCEPTION).

    Constructs a RuleSet manually with a never-registered validator name to
    bypass the loader and exercise the defensive engine branch directly.
    """
    from app.schemas.rules import RuleSet
    rule = make_rule(
        rule_id="x.unregistered",
        cfr_citation="27 CFR §0.0",
        validator="__never_registered__",
        reason_code="WARNING.PRESENCE.MISSING",
    )
    rs = RuleSet(
        version="0.1.0", effective_date="2026-09-09",
        rules=(rule,), reason_codes={}, assets={}, decision_tables={},
    )
    engine = YamlRuleEngine(rs)
    obs = [make_obs(field_id="warning_block", value="x", beverage_class=BeverageClass.SPIRITS)]
    exp = [make_expected(field_id="warning_block")]
    results = await engine.evaluate(obs, exp, make_context())
    assert results
    assert results[0].outcome is Outcome.ERROR
    assert results[0].reason_code == "ENGINE.VALIDATOR.NOT_FOUND"
