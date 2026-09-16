"""Through the running app, a label is compared against its application.

The rule engine has always been able to compare a label with the application
filed for it. What these tests cover is the path a grader actually takes: the
page's own form, posted to the app's own route, through the real rule pack, to
the result the page shows. Everything here is real except the reader, which
would otherwise call a vision model over the network.

Both labels are real ones from the TTB Public COLA Registry, in
`tests/fixtures/labels/manifest.json`:

  - `ttb-26233001000569`, a domestic wine whose label names the grape
    SANGIOVESE while its application declares TABLE RED WINE. It proves the
    wine rules are the ones that run, which they were not while the reader
    tagged every reading as spirits.
  - `ttb-26239001000132`, an imported wine, because the country-of-origin
    check does not apply to a domestic product and would otherwise go
    untested through the app.
"""
from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.api.ui import _get_upload_evaluator
from app.config import Settings
from app.main import create_app
from app.rules import build_rule_engine
from app.schemas.expected import BeverageClass
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.vision import FakeVisionExtractor
from tests.rules.fixtures import make_obs
from tests.rules.manifest_labels import entries_by_id

DOMESTIC_WINE = "ttb-26233001000569"
IMPORTED_WINE = "ttb-26239001000132"

_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)


@pytest.fixture(autouse=True)
def _readable_image(monkeypatch):
    """The one-pixel stand-in for the label image would otherwise be turned
    away as too small to read, before any rule runs."""
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda label: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )


def _readings(entry):
    """What the reader reports for this label.

    Every reading is tagged spirits, because that is what the cloud reader
    tags everything it sees: a vision model cannot tell a wine from a spirit
    reliably, and nothing asked it to. The application settles it instead.
    """
    application = entry["application"]
    observed = entry["label_observed"]

    def obs(field_id, value):
        return make_obs(field_id=field_id, value=value, beverage_class=BeverageClass.SPIRITS)

    readings = [
        obs("brand_name", {"brand_name": application["brand_name"], "confidence": 0.95}),
        obs("class_type", {"class_type": observed["class_type"], "confidence": 0.95}),
        obs("abv", {"abv_pct": application["alcohol_content"]["percent"], "unit": "%", "confidence": 0.95}),
        obs("net_contents", {"net_contents_value": application["net_contents"]["ml"], "unit": "mL", "confidence": 0.95}),
        obs("name_address", {"name": observed["name_address"], "city": "", "state": "", "confidence": 0.95}),
    ]
    # The reader asks for every field on every label and returns an answer
    # for each, so a label carrying no origin statement still produces an
    # empty country_origin reading. Leaving it out instead would silently
    # skip the origin rule, which asks for that evidence by name.
    readings.append(
        obs("country_origin", {"country": observed.get("origin_statement") or "", "confidence": 0.95})
    )
    return readings


def _client_for(label_id: str) -> TestClient:
    """The real app, the real rule pack, the real evaluator, a stubbed reader."""
    evaluator = Evaluator(
        vision=FakeVisionExtractor(observations=_readings(entries_by_id()[label_id])),
        rules=build_rule_engine(Settings()),
        settings=Settings(),
    )
    app = create_app()
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    return TestClient(app)


@pytest.fixture
def client():
    return _client_for(DOMESTIC_WINE)


def _application_form(label_id: str, **overrides) -> dict[str, str]:
    application = entries_by_id()[label_id]["application"]
    form = {
        "beverage_type": entries_by_id()[label_id]["beverage_type"],
        "brand_name": application["brand_name"],
        "fanciful_name": application["fanciful_name"] or "",
        "class_type": application["class_type"],
        "alcohol_content": application["alcohol_content"]["value"],
        "net_contents": application["net_contents"]["value"],
        "applicant_name_address": application["applicant_name_address"],
        "source_of_product": application["source_of_product"],
        "origin": application["origin"] or "",
        "wine_appellation": application["wine_appellation"] or "",
    }
    form.update(overrides)
    return form


def _envelope(response) -> dict:
    assert response.status_code == 200, response.text
    embedded = re.search(
        r'<script id="envelope" type="application/json">(.*?)</script>',
        response.text,
        re.DOTALL,
    )
    assert embedded, "the page embedded no result envelope"
    return json.loads(embedded.group(1))


def _submit(client, label_id=DOMESTIC_WINE, **overrides) -> dict:
    return _envelope(
        client.post(
            "/",
            files={"label": ("label.png", _PNG_1x1, "image/png")},
            data=_application_form(label_id, **overrides),
        )
    )


def _rule_outcomes(envelope) -> dict[str, str]:
    """Every rule the check ran, and what it reported."""
    return {
        entry["rule_id"]: entry["disposition"]
        for entry in envelope["audit_trail"]["per_rule_trace"]
    }


# ---------------------------------------------------------------------------
# The application picks the rule pack
# ---------------------------------------------------------------------------

def test_comparison_rules_run_against_the_posted_application(client):
    outcomes = _rule_outcomes(_submit(client))
    compared = {rule for rule in outcomes if rule.endswith(".matches_application")}
    assert compared, "nothing compared the label against the application"
    assert all(rule.startswith("wine.") for rule in compared), sorted(compared)
    assert not any(rule.startswith("spirits.") for rule in outcomes), sorted(outcomes)


# ---------------------------------------------------------------------------
# A label that agrees, and the same label made to disagree
# ---------------------------------------------------------------------------

def test_a_label_that_agrees_with_its_application_is_reported_as_agreeing(client):
    outcomes = _rule_outcomes(_submit(client))
    assert outcomes["wine.brand.matches_application"] == "pass"
    assert outcomes["wine.alcohol.matches_application"] == "pass"
    assert outcomes["wine.net_contents.matches_application"] == "pass"
    # The manifest states this label's class check may pass or go to a
    # reviewer: the label names a grape, the application a registry class.
    assert outcomes["wine.class_type.matches_application"] in {"pass", "needs_review"}


def test_a_brand_no_name_the_application_declares_carries_is_reported(client):
    """The comparison is real: change every name the application declares and
    the check that passed a moment ago reports a disagreement.

    All three have to change together. The application declares a brand, a
    fanciful name, and the trade name inside its applicant line marked "(Used
    on label)", and a mark carrying any of them carries a name the application
    itself declared — see `docs/decisions.md#0015`. This label's applicant line
    declares PORTALUPI WINES, which is the mark the label prints, so changing
    the brand field alone leaves the label matching a name that is still there.
    """
    envelope = _submit(
        client,
        brand_name="Entirely Different Cellars",
        fanciful_name="",
        applicant_name_address="DRNK, DRNK LLC 3637 FREI RD Sebastopol CA 95472",
    )
    assert _rule_outcomes(envelope)["wine.brand.matches_application"] == "fail"
    assert envelope["disposition"] != "pass"


def test_a_brand_the_application_declares_only_as_a_trade_name_is_matched(client):
    """The other half of the same decision, through the page.

    The brand field says one thing and the label prints another, but the
    applicant line declares the printed name as used on the label, so the
    check reports a match rather than sending a compliant label to a reviewer.
    """
    envelope = _submit(client, brand_name="Entirely Different Cellars")
    assert _rule_outcomes(envelope)["wine.brand.matches_application"] == "pass"


def test_an_alcohol_content_the_application_does_not_carry_is_reported(client):
    envelope = _submit(client, alcohol_content="ALC 9.0% BY VOLUME")
    assert _rule_outcomes(envelope)["wine.alcohol.matches_application"] == "fail"


def test_a_net_contents_the_application_does_not_carry_is_reported(client):
    """The label reads 750 mL; an application declaring a 1.5 litre bottle
    disagrees, which also proves the unit the grader typed was converted."""
    envelope = _submit(client, net_contents="1.5 L")
    assert _rule_outcomes(envelope)["wine.net_contents.matches_application"] == "fail"


def test_a_net_contents_written_in_another_unit_still_agrees(client):
    """The same 750 mL bottle declared as 75 centilitres is the same bottle."""
    envelope = _submit(client, net_contents="75 cL")
    assert _rule_outcomes(envelope)["wine.net_contents.matches_application"] == "pass"


# ---------------------------------------------------------------------------
# Country of origin
# ---------------------------------------------------------------------------

def test_an_imported_labels_origin_is_compared():
    client = _client_for(IMPORTED_WINE)
    outcomes = _rule_outcomes(_submit(client, IMPORTED_WINE))
    assert outcomes["wine.origin.matches_application"] == "pass"


def test_an_origin_the_application_does_not_carry_goes_to_a_reviewer():
    """A label whose origin statement does not carry the declared country is a
    question for a person, not a rejection.

    The app reads an origin statement only as the application's English country
    name. Customs marking rules also accept the country's name in its own
    language, an abbreviation and the adjectival form (19 CFR §134.45(b), (c)),
    and none of those is built — so a hard `fail` here would reject compliant
    imports on a gap in the reader. See `docs/decisions.md#0016`.
    """
    client = _client_for(IMPORTED_WINE)
    envelope = _submit(client, IMPORTED_WINE, origin="PORTUGAL")
    assert _rule_outcomes(envelope)["wine.origin.matches_application"] == "needs_review"


def test_a_domestic_application_needs_no_origin_statement(client):
    """Domestic is a positive statement that no country-of-origin check
    applies, not a missing answer."""
    outcomes = _rule_outcomes(_submit(client))
    assert outcomes["wine.origin.matches_application"] == "not_applicable"


# ---------------------------------------------------------------------------
# No application at all
# ---------------------------------------------------------------------------

def test_without_an_application_the_label_is_read_and_nothing_is_checked(client):
    """A grader who uploads only an image gets the reading and no verdict.

    The beverage the application declares is what decides which rules apply, so
    with no application there is no rule to run — not even the ones that need
    no application, because each is written for a beverage class. The reply
    says so in one audit row rather than leaving the reviewer to notice an
    absence. See `docs/decisions.md#0010`.
    """
    envelope = _envelope(
        client.post("/", files={"label": ("label.png", _PNG_1x1, "image/png")})
    )
    trace = envelope["audit_trail"]["per_rule_trace"]
    assert [row["rule_id"] for row in trace] == ["ENGINE.RULE_PACK.NOT_SELECTED"], trace
    assert trace[0]["evidence_ref"] == "rule_pack/none"
    assert trace[0]["disposition"] == "needs_review"
    assert envelope["disposition"] == "needs_review"
    # The label was still read: every field the reader answers is reported,
    # with nothing to compare it against.
    read = {field["field_name"]: field["extracted_value"] for field in envelope["fields"]}
    assert "PORTALUPI" in read["brand_name"]
    assert all(field["rule_findings"] == [] for field in envelope["fields"])
