"""layout_check covers one layout invariant:

  same_field_of_vision_check   — the required spirits fields sit within one
                                  field of vision, meaning a single panel.

`layout_isolation_check` was the other, and it is gone: no reader emits the
neighbour distance it compared, so `common.warning.separate_apart` now answers
`unmeasurable` instead (docs/decisions/0013).
"""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.layout_check import same_field_of_vision_check  # noqa: F401
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _sov_rule():
    return make_rule(
        rule_id="spirits.same_field_of_vision",
        cfr_citation="27 CFR §5.63(a)",
        validator="same_field_of_vision_check",
        reason_code="LEGIBILITY.FIELD_OF_VISION.SPLIT",
        match_policy=MatchPolicy.LAYOUT,
        parameters={"required_fields": ["brand", "class_type", "abv", "net_contents"]},
    )


def test_sov_pass_when_all_on_one_panel() -> None:
    obs = make_obs(field_id="layout", value={"panels": {"front": ["brand", "class_type", "abv", "net_contents"]}})
    assert same_field_of_vision_check(obs, make_expected(field_id="layout"), _sov_rule(), make_context()).outcome is Outcome.PASS


def test_sov_fail_when_split_across_panels() -> None:
    obs = make_obs(field_id="layout", value={"panels": {"front": ["brand", "class_type"], "back": ["abv", "net_contents"]}})
    assert same_field_of_vision_check(obs, make_expected(field_id="layout"), _sov_rule(), make_context()).outcome is Outcome.FAIL


def test_validators_registered() -> None:
    assert "same_field_of_vision_check" in VALIDATOR_REGISTRY
    assert "layout_isolation_check" not in VALIDATOR_REGISTRY
