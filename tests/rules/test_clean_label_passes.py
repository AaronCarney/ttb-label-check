"""A correctly-labelled submission must produce no failing check.

This is the check the product exists to make. Every value below is what a
correct spirits label carries, and every expected value is what its
application declares, keyed the way the application keys them. If the engine
reports a failure here, it is reporting one against a label that complies.

PRD FR-1, FR-7 and FR-11: a result per applicable check, matching rules that
treat equivalent values as equal, and an overall result of match when every
check matches.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.rules import build_rule_engine
from app.config import Settings
from app.schemas.extracted import BeverageClass
from app.schemas.rejection import Outcome

from tests.rules.fixtures import make_expected, make_obs

WARNING_TEXT = (
    Path("assets/warnings/govt_warning_16_21.txt").read_text(encoding="utf-8").strip()
)


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setenv("RULES_ROOT", str(Path("rules").resolve()))
    return build_rule_engine(Settings())


def _clean_observations():
    """What a reader returns for a compliant spirits label.

    The payload shapes are the ones the extractor emits (app/vision/cloud.py
    _SCHEMAS): every field is a dict carrying its value and a confidence, not
    a bare string.
    """
    return (
        make_obs(field_id="brand_name", value={"brand_name": "STONE'S THROW", "confidence": 0.97}),
        make_obs(field_id="class_type", value={"class_type": "KENTUCKY STRAIGHT BOURBON WHISKEY", "confidence": 0.96}),
        make_obs(field_id="abv", value={"abv_pct": 45.0, "unit": "%", "confidence": 0.98}),
        make_obs(field_id="net_contents", value={"net_contents_value": 750.0, "unit": "mL", "confidence": 0.98}),
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
        make_obs(field_id="name_address", value={"name": "Stone's Throw Distillery", "city": "Louisville", "state": "KY", "confidence": 0.95}),
        make_obs(field_id="country_origin", value={"country": "United States", "confidence": 0.95}),
    )


def _matching_application():
    """What the application declares, keyed as the application keys it.

    These are the field names the applicant fills in — `alcohol_content`, not
    `abv`; `government_warning`, not `gov_warning`. The engine is responsible
    for reconciling them with the reader's names.
    """
    return (
        make_expected(field_id="brand_name", value="Stone's Throw"),
        make_expected(field_id="class_type", value="Kentucky Straight Bourbon Whiskey"),
        make_expected(field_id="alcohol_content", value="45.0", abv_labeled_pct=Decimal("45.0"), abv_actual_pct=Decimal("45.0")),
        make_expected(field_id="net_contents", value="750 mL", container_volume_ml=Decimal("750")),
        make_expected(field_id="government_warning", value=WARNING_TEXT),
        make_expected(field_id="name_and_address", value="Stone's Throw Distillery, Louisville, KY"),
        make_expected(field_id="country_of_origin", value="United States"),
    )


async def _run(engine):
    ctx = engine.build_validator_context(started_at_ms=0)
    return await engine.evaluate(_clean_observations(), _matching_application(), ctx)


async def test_no_check_fails_on_a_compliant_label(engine):
    results = await _run(engine)
    failures = [r for r in results if r.outcome is Outcome.FAIL]
    assert not failures, "checks failed on a compliant label: " + ", ".join(
        f"{r.rule_id} ({r.reason_code})" for r in failures
    )


async def test_the_warning_check_passes_on_the_verbatim_text(engine):
    results = await _run(engine)
    verbatim = [r for r in results if r.rule_id == "common.warning.verbatim"]
    assert verbatim, "the verbatim warning rule did not run"
    assert verbatim[0].outcome is Outcome.PASS


async def test_the_application_value_reaches_every_check(engine):
    """Each comparison rule must see the application's value, whatever the
    reader called the field. A rule comparing against an empty expected value
    fails a correct label, which is the defect this guards."""
    results = await _run(engine)
    compared = [r for r in results if r.expected is not None and r.observed is not None]
    unbound = [
        r for r in compared
        if r.observed.field_id in {"abv", "gov_warning", "name_address", "country_origin"}
        and r.expected.value is None
    ]
    assert not unbound, "application values did not bind: " + ", ".join(
        f"{r.rule_id} -> {r.observed.field_id}" for r in unbound
    )


async def test_an_absent_warning_is_reported_as_a_failure(engine):
    """The mirror of the first test. Presence must mean the warning is there,
    not merely that the reader returned a payload shaped like a warning."""
    ctx = engine.build_validator_context(started_at_ms=0)
    observations = tuple(
        make_obs(
            field_id="gov_warning",
            value={
                "text": "",
                "heading_text": "",
                "heading_all_caps": False,
                "heading_bold": False,
                "type_size_pt": 0.0,
                "confidence": 0.9,
            },
        )
        if obs.field_id == "gov_warning" else obs
        for obs in _clean_observations()
    )
    results = await engine.evaluate(observations, _matching_application(), ctx)
    presence = [r for r in results if r.rule_id == "common.warning.present"]
    assert presence, "the warning presence rule did not run"
    assert presence[0].outcome is Outcome.FAIL
