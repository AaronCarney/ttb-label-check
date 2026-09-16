"""Builders for per-rule unit tests. They produce frozen, extra='forbid'
Pydantic instances so tests can construct typed payloads without verbosity.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import EngineMeta
from tests.rules.fixtures import (
    make_context,
    make_engine_meta,
    make_evidence,
    make_expected,
    make_obs,
    make_rule,
)


def test_make_obs_returns_field_observation() -> None:
    obs = make_obs(field_id="brand", value="STONE'S THROW")
    assert isinstance(obs, FieldObservation)
    assert obs.field_id == "brand"
    assert obs.observed_value == "STONE'S THROW"
    with pytest.raises(Exception):
        obs.field_id = "x"  # type: ignore[misc]


def test_make_expected_returns_expected_value() -> None:
    exp = make_expected(field_id="brand", value="Stone's Throw")
    assert exp.field_id == "brand"
    assert exp.value == "Stone's Throw"


def test_make_evidence_default_kind_normalized() -> None:
    ev = make_evidence(text="STONE'S THROW")
    assert isinstance(ev, Evidence)
    assert ev.match_kind == MatchKind.NORMALIZED
    assert ev.source == EvidenceSource.OCR


def test_make_rule_minimum_required_fields() -> None:
    rule = make_rule(
        rule_id="x.y.z",
        cfr_citation="27 CFR §0.0",
        validator="presence_check",
        reason_code="WARNING.PRESENCE.MISSING",
    )
    assert rule.validator == "presence_check"


def test_make_engine_meta_defaults() -> None:
    em = make_engine_meta()
    assert isinstance(em, EngineMeta)
    assert em.engine_version
    assert em.rule_pack


def test_make_context_passes_through_assets() -> None:
    ctx = make_context()
    assert ctx.engine_version
