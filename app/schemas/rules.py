"""Canonical declaration of rule-pack types.

These types live here, not in ``app/rules/models.py``, so that everything that
touches the rule-pack data shape can reach them without importing the engine.
``app/rules/models.py`` re-exports them for namespace ergonomics, and
``from app.schemas.rules import RuleSet is from app.rules.models import RuleSet``
holds.

**Re-export contract.** ``app/rules/models.py`` MUST use
``from app.schemas.rules import RuleSet as RuleSet`` style (re-binding the
class object) — NOT a redeclaration — or that ``is``-identity breaks.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.expected import BeverageClass
from app.schemas.rejection import Severity


class MatchPolicy(str, Enum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY = "fuzzy"
    TOLERANCE = "tolerance"
    VERBATIM_HASH = "verbatim_hash"
    LOOKUP = "lookup"
    REGEX = "regex"
    LAYOUT = "layout"


class ReasonCodeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str
    cfr_anchors: tuple[str, ...]
    severity: Severity


class AssetRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str


class DecisionTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    interpolation: Literal["none", "linear"] = "none"
    entries: tuple[dict[str, Any], ...]


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    cfr_citation: str
    applies_to_classes: tuple[BeverageClass, ...]
    reason_code: str
    severity: Severity
    match_policy: MatchPolicy
    validator: str
    evidence_required: tuple[str, ...]
    confidence_floor: float = Field(default=0.5, ge=0.0, le=1.0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    tolerance: dict[str, Any] | None = None
    decision_table: dict[str, Any] | None = None
    decision_table_ref: str | None = None
    asset: dict[str, Any] | None = None
    effective_date: str
    supersedes: tuple[str, ...] = ()
    rule_pack_version: str | None = None
    rule_pack: str | None = None
    test_fixtures: tuple[str, ...]
    disabled: bool = False
    notes: str | None = None


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    effective_date: str
    rules: tuple[RuleDefinition, ...]
    reason_codes: dict[str, ReasonCodeEntry]
    assets: dict[str, AssetRef]
    decision_tables: dict[str, DecisionTable]
