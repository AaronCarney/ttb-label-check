"""The brief's sample label, checked for its proof statement.

The brief's example spirits label reads "45% Alc./Vol. (90 Proof)". 27 CFR §5.1
defines proof as twice the percentage of alcohol by volume, so 90 agrees with
45 and 80 does not. PRD FR-7: a stated proof must equal twice the alcohol by
volume.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.rules import build_rule_engine
from app.schemas.rejection import Outcome
from app.services.disposition import compute_disposition
from tests.rules.fixtures import make_expected, make_obs

WARNING_TEXT = Path("assets/warnings/govt_warning_16_21.txt").read_text(encoding="utf-8").strip()


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setenv("RULES_ROOT", str(Path("rules").resolve()))
    return build_rule_engine(Settings())


def _abv_payload(statement: str, proof: str, *, shape: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "abv_pct": 45.0,
        "unit": "%",
        "alc_text": statement,
        "confidence": 0.97,
    }
    if shape == "local":
        payload["proof"] = [
            {"value": proof, "text": f"({proof} Proof)", "confidence": 0.97, "beside_abv": True}
        ]
    return payload


def _old_tom(proof: str, *, shape: str):
    statement = f"45% Alc./Vol. ({proof} Proof)"
    return (
        make_obs(
            field_id="brand_name", value={"brand_name": "OLD TOM DISTILLERY", "confidence": 0.97}
        ),
        make_obs(
            field_id="class_type",
            value={"class_type": "Kentucky Straight Bourbon Whiskey", "confidence": 0.96},
        ),
        make_obs(field_id="abv", value=_abv_payload(statement, proof, shape=shape)),
        make_obs(
            field_id="net_contents",
            value={"net_contents_value": 750.0, "unit": "mL", "confidence": 0.98},
        ),
        make_obs(
            field_id="gov_warning",
            value={
                "text": WARNING_TEXT,
                "heading_text": "GOVERNMENT WARNING:",
                "heading_all_caps": True,
                "heading_bold": True,
                "type_size_pt": 3.0,
                "confidence": 0.97,
            },
        ),
        make_obs(
            field_id="name_address",
            value={
                "name": "Old Tom Distillery",
                "city": "Louisville",
                "state": "KY",
                "confidence": 0.95,
            },
        ),
    )


def _application():
    return (
        make_expected(field_id="brand_name", value="OLD TOM DISTILLERY"),
        make_expected(field_id="class_type", value="Kentucky Straight Bourbon Whiskey"),
        make_expected(field_id="alcohol_content", value="45", abv_labeled_pct=Decimal("45")),
        make_expected(field_id="net_contents", value="750 mL", container_volume_ml=Decimal("750")),
        make_expected(field_id="government_warning", value=WARNING_TEXT),
    )


async def _results(engine, proof: str, shape: str):
    ctx = engine.build_validator_context(started_at_ms=0)
    return await engine.evaluate(_old_tom(proof, shape=shape), _application(), ctx)


@pytest.mark.parametrize("shape", ["local", "statement_only"])
async def test_ninety_proof_at_forty_five_percent_passes(engine, shape):
    results = await _results(engine, "90", shape)
    (proof,) = [r for r in results if r.rule_id == "spirits.alcohol.proof_agrees"]
    assert proof.outcome is Outcome.PASS


@pytest.mark.parametrize("shape", ["local", "statement_only"])
async def test_eighty_proof_at_forty_five_percent_is_a_mismatch_overall(engine, shape):
    results = await _results(engine, "80", shape)
    (proof,) = [r for r in results if r.rule_id == "spirits.alcohol.proof_agrees"]
    assert proof.outcome is Outcome.FAIL
    assert proof.message == "The label states 80 proof beside 45%; twice 45 is 90."
    assert compute_disposition(results) == "fail"
