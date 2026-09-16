"""app.rules.models re-exports the canonical rule types verbatim.

Identity (the `is` operator) — not structural equality — so `isinstance` checks
agree across both import paths and downstream code can rely on a single type
object regardless of which module path it imported through.
"""
from __future__ import annotations

import app.rules.models as via_models
import app.schemas.rules as via_schemas


def test_rule_set_identity() -> None:
    assert via_models.RuleSet is via_schemas.RuleSet


def test_rule_definition_identity() -> None:
    assert via_models.RuleDefinition is via_schemas.RuleDefinition


def test_match_policy_identity() -> None:
    assert via_models.MatchPolicy is via_schemas.MatchPolicy


def test_reason_code_entry_identity() -> None:
    assert via_models.ReasonCodeEntry is via_schemas.ReasonCodeEntry


def test_asset_ref_identity() -> None:
    assert via_models.AssetRef is via_schemas.AssetRef


def test_decision_table_identity() -> None:
    assert via_models.DecisionTable is via_schemas.DecisionTable
