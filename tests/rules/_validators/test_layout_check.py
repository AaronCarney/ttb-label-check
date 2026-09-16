"""layout_check covers two layout invariants:

  layout_isolation_check       — the warning is `separate and apart` from
                                  other label information (min_isolation_px).
  same_field_of_vision_check   — the required spirits fields sit within one
                                  field of vision, meaning a single panel.
"""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.layout_check import (  # noqa: F401
    layout_isolation_check,
    same_field_of_vision_check,
)
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _isolation_rule():
    return make_rule(
        rule_id="common.warning.separate_apart",
        cfr_citation="27 CFR §16.21",
        validator="layout_isolation_check",
        reason_code="WARNING.PLACEMENT.NOT_SEPARATE",
        match_policy=MatchPolicy.LAYOUT,
        parameters={"min_isolation_px": 4},
    )


def _sov_rule():
    return make_rule(
        rule_id="spirits.same_field_of_vision",
        cfr_citation="27 CFR §5.63(a)",
        validator="same_field_of_vision_check",
        reason_code="LEGIBILITY.FIELD_OF_VISION.SPLIT",
        match_policy=MatchPolicy.LAYOUT,
        parameters={"required_fields": ["brand", "class_type", "abv", "net_contents"]},
    )


def test_isolation_pass_when_distance_ok() -> None:
    obs = make_obs(field_id="warning_block", value={"min_neighbor_distance_px": 10})
    assert layout_isolation_check(obs, make_expected(field_id="warning_block"), _isolation_rule(), make_context()).outcome is Outcome.PASS


def test_isolation_fail_when_too_close() -> None:
    obs = make_obs(field_id="warning_block", value={"min_neighbor_distance_px": 1})
    assert layout_isolation_check(obs, make_expected(field_id="warning_block"), _isolation_rule(), make_context()).outcome is Outcome.FAIL


def test_sov_pass_when_all_on_one_panel() -> None:
    obs = make_obs(field_id="layout", value={"panels": {"front": ["brand", "class_type", "abv", "net_contents"]}})
    assert same_field_of_vision_check(obs, make_expected(field_id="layout"), _sov_rule(), make_context()).outcome is Outcome.PASS


def test_sov_fail_when_split_across_panels() -> None:
    obs = make_obs(field_id="layout", value={"panels": {"front": ["brand", "class_type"], "back": ["abv", "net_contents"]}})
    assert same_field_of_vision_check(obs, make_expected(field_id="layout"), _sov_rule(), make_context()).outcome is Outcome.FAIL


def test_validators_registered() -> None:
    assert "layout_isolation_check" in VALIDATOR_REGISTRY
    assert "same_field_of_vision_check" in VALIDATOR_REGISTRY
