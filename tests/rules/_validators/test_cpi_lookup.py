"""cpi_lookup resolves the row whose min_required_type_height_mm matches the
observation's text height, then compares observed cpi to max_characters_per_inch.
The regulation's table is read as written, with no interpolation between rows.
"""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.cpi_lookup import cpi_lookup  # noqa: F401
from app.schemas.rejection import Outcome
from app.schemas.rules import DecisionTable, MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

CPI_TABLE = DecisionTable(
    interpolation="none",
    entries=(
        {"min_required_type_height_mm": 1, "max_characters_per_inch": 40},
        {"min_required_type_height_mm": 2, "max_characters_per_inch": 25},
        {"min_required_type_height_mm": 3, "max_characters_per_inch": 12},
    ),
)


def _rule():
    return make_rule(
        rule_id="common.warning.cpi_max",
        cfr_citation="27 CFR §16.22(a)(4)",
        validator="cpi_lookup",
        reason_code="WARNING.TYPE_SIZE.CPI_EXCEEDED",
        match_policy=MatchPolicy.LOOKUP,
        decision_table_ref="cpi_16_22_a_4",
        parameters={"observed_cpi_field": "cpi", "observed_height_field": "height_mm"},
    )


def _ctx():
    return make_context(decision_tables={"cpi_16_22_a_4": CPI_TABLE})


def test_cpi_lookup_pass_when_under_max() -> None:
    obs = make_obs(field_id="warning_block", value={"cpi": 30, "height_mm": 1})
    res = cpi_lookup(obs, make_expected(field_id="warning_block"), _rule(), _ctx())
    assert res.outcome is Outcome.PASS


def test_cpi_lookup_fail_when_over_max() -> None:
    obs = make_obs(field_id="warning_block", value={"cpi": 50, "height_mm": 1})
    res = cpi_lookup(obs, make_expected(field_id="warning_block"), _rule(), _ctx())
    assert res.outcome is Outcome.FAIL


def test_cpi_lookup_fail_when_height_not_in_table() -> None:
    obs = make_obs(field_id="warning_block", value={"cpi": 10, "height_mm": 99})
    res = cpi_lookup(obs, make_expected(field_id="warning_block"), _rule(), _ctx())
    assert res.outcome is Outcome.FAIL


def test_cpi_lookup_registered() -> None:
    assert "cpi_lookup" in VALIDATOR_REGISTRY
