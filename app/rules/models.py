"""Namespace re-export of the canonical rule-pack types declared in
``app.schemas.rules``.

This module MUST use ``from app.schemas.rules import X as X`` style (rebinding
the class object) — NOT a redeclaration — so the ``is``-identity assertion
holds. Any future refactor that redeclares these names here is a regression.
"""
from __future__ import annotations

from app.schemas.rules import (
    AssetRef as AssetRef,
    DecisionTable as DecisionTable,
    MatchPolicy as MatchPolicy,
    ReasonCodeEntry as ReasonCodeEntry,
    RuleDefinition as RuleDefinition,
    RuleSet as RuleSet,
)

__all__ = [
    "AssetRef",
    "DecisionTable",
    "MatchPolicy",
    "ReasonCodeEntry",
    "RuleDefinition",
    "RuleSet",
]
