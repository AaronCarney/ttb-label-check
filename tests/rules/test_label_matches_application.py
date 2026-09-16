"""Every label element the application declares is checked against it.

This is the brief's subject: the product compares what a label says with what
the application for that label declared. The cases are the 30 approved labels
and 8 flawed variants in `tests/fixtures/labels/manifest.json`, and the
outcome each check must reach is the manifest's own, not this file's.

Approved labels were approved by TTB, so every field check on them is expected
to match. The variants that alter an application — a changed alcohol content, a
brand whose case and punctuation differ — are what prove the comparison is real
rather than a check that always agrees.

PRD FR-1, FR-7 and FR-11: a result per applicable check, matching rules that
treat equivalent values as equal, and an overall result of match when every
check matches.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.rules import build_rule_engine
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome, Severity
from app.services.application_mapper import expected_values_from

from tests.rules.fixtures import make_obs
from tests.rules.manifest_labels import (
    FIELD_CHECKS,
    accepted_verdicts,
    application_record,
    label_observations,
    manifest,
)

# Rule-id element name -> the manifest's name for the same check.
_CHECK_BY_ELEMENT = {
    "brand": "brand",
    "class_type": "class_type",
    "alcohol": "abv",
    "net_contents": "net_contents",
    "name_address": "name_address",
    "origin": "origin",
}


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setenv("RULES_ROOT", str(Path("rules").resolve()))
    return build_rule_engine(Settings())


def _verdict(result) -> str:
    """The manifest's vocabulary for one rule outcome.

    A failure the engine marks `warn` is one a reviewer should look at rather
    than a rejection, which the manifest calls `needs_review`.
    """
    if result.outcome is Outcome.PASS:
        return "pass"
    if result.outcome is Outcome.NOT_APPLICABLE:
        return "not_applicable"
    if result.outcome is Outcome.FAIL:
        return "needs_review" if result.severity is Severity.WARN else "fail"
    return "needs_review"


async def _verdicts_for(engine, entry) -> dict[str, list[tuple[str, str]]]:
    """Per manifest check, the (rule_id, verdict) pairs the engine produced."""
    record = application_record(entry)
    ctx = engine.build_validator_context(started_at_ms=0)
    results = await engine.evaluate(
        label_observations(entry), expected_values_from(record), ctx
    )
    by_check: dict[str, list[tuple[str, str]]] = {check: [] for check in FIELD_CHECKS}
    for result in results:
        parts = result.rule_id.split(".")
        if len(parts) != 3 or parts[2] != "matches_application":
            continue
        check = _CHECK_BY_ELEMENT.get(parts[1])
        if check:
            by_check[check].append((result.rule_id, _verdict(result)))
    return by_check


def _cases():
    return [pytest.param(entry, id=entry["id"]) for entry in manifest()["labels"]]


@pytest.mark.parametrize("entry", _cases())
@pytest.mark.parametrize("check", FIELD_CHECKS)
async def test_check_reaches_the_outcome_the_manifest_states(engine, entry, check):
    produced = (await _verdicts_for(engine, entry))[check]
    assert produced, (
        f"no rule compared {check} against the application for {entry['id']}; "
        "the element is declared but nothing checks it"
    )
    accepted = accepted_verdicts(entry, check)
    for rule_id, verdict in produced:
        assert verdict in accepted, (
            f"{entry['id']}: {rule_id} reported {verdict!r}; "
            f"the manifest accepts {accepted}"
        )


# ---------------------------------------------------------------------------
# What every comparison reports when there is no application to compare with
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "beverage_class", [pytest.param(cls, id=cls.value) for cls in BeverageClass]
)
async def test_no_application_means_no_comparison_applies(engine, beverage_class):
    """A grader who uploads only an image declares no application. Every
    comparison must report that it does not apply — reporting that the label
    agrees would tell them a check ran that never had two sides.
    """
    readings = (
        make_obs(field_id="brand_name", value={"brand_name": "Stone's Throw"}, beverage_class=beverage_class),
        make_obs(field_id="class_type", value={"class_type": "BOURBON WHISKEY"}, beverage_class=beverage_class),
        make_obs(field_id="abv", value={"abv_pct": 40.0, "unit": "%"}, beverage_class=beverage_class),
        make_obs(field_id="net_contents", value={"net_contents_value": 750, "unit": "mL"}, beverage_class=beverage_class),
        make_obs(field_id="name_address", value={"name": "A Distillery", "city": "", "state": ""}, beverage_class=beverage_class),
        make_obs(field_id="country_origin", value={"country": "PRODUCT OF FRANCE"}, beverage_class=beverage_class),
    )
    ctx = engine.build_validator_context(started_at_ms=0)
    results = await engine.evaluate(readings, (), ctx)
    compared = {
        result.rule_id: result.outcome
        for result in results
        if result.rule_id.endswith(".matches_application")
    }
    assert compared, "no comparison rule ran"
    not_applicable = {
        rule_id: outcome for rule_id, outcome in compared.items()
        if outcome is not Outcome.NOT_APPLICABLE
    }
    assert not not_applicable, not_applicable
