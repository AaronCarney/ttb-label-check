"""A validator raising ZeroDivisionError is caught and emits
ENGINE.VALIDATOR.EXCEPTION; other rules continue.
"""

from __future__ import annotations

import pytest

from app.rules._validators import VALIDATOR_REGISTRY, register
from app.rules.yaml_engine import YamlRuleEngine
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome
from app.schemas.rules import RuleSet
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


@register("__crash_validator__")
def _crash(*args, **kwargs):
    return 1 / 0


@pytest.mark.asyncio
async def test_validator_exception_caught_into_error_result() -> None:
    rule = make_rule(
        rule_id="x.crash",
        cfr_citation="27 CFR §0.0",
        validator="__crash_validator__",
        reason_code="WARNING.PRESENCE.MISSING",
    )
    rs = RuleSet(
        version="0.1.0",
        effective_date="2026-09-09",
        rules=(rule,),
        reason_codes={},
        assets={},
        decision_tables={},
    )
    engine = YamlRuleEngine(rs)
    obs = [make_obs(field_id="warning_block", value="x", beverage_class=BeverageClass.SPIRITS)]
    exp = [make_expected(field_id="warning_block")]
    results = await engine.evaluate(obs, exp, make_context())
    assert results
    assert results[0].outcome is Outcome.ERROR
    assert results[0].reason_code == "ENGINE.VALIDATOR.EXCEPTION"
    del VALIDATOR_REGISTRY["__crash_validator__"]
