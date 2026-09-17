"""The single-label page carries the application, so something gets compared.

The brief's subject is whether a label agrees with the application filed for
it. Through the running app that only happens if the page asks for the
application's fields and passes them on, so these tests check the page offers
them and that what a reviewer types reaches the evaluator as reference values
and as the beverage class the rules are picked by.

A reviewer who fills nothing in still gets a check: the presence rules and the
health-warning rules need no application, and every comparison reports that it
does not apply.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.ui import _get_upload_evaluator
from app.main import create_app
from app.schemas.expected import BeverageClass
from tests.conftest import _stub_disposition_envelope

_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)


class _RecordingEvaluator:
    """An evaluator that keeps every application it was asked to check."""

    def __init__(self) -> None:
        self.applications = []

    async def evaluate(self, application, label):
        self.applications.append(application)
        return _stub_disposition_envelope(len(self.applications), disposition="pass")


@pytest.fixture
def recorder():
    return _RecordingEvaluator()


@pytest.fixture
def client(recorder):
    app = create_app()
    app.dependency_overrides[_get_upload_evaluator] = lambda: recorder
    return TestClient(app)


def _expected(application) -> dict[str, object]:
    return {e.field_id: e for e in application.expected_values}


# ---------------------------------------------------------------------------
# The page asks for the application
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "beverage_type",
        "brand_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "applicant_name_address",
        "source_of_product",
        "origin",
    ],
)
def test_the_form_asks_for_each_application_field(field):
    response = TestClient(create_app()).get("/")
    assert f'name="{field}"' in response.text


def test_the_form_says_a_blank_field_is_not_checked():
    """A reviewer must be able to tell that leaving a field empty skips its
    comparison rather than failing the label."""
    response = TestClient(create_app()).get("/")
    assert "not checked" in response.text.lower()


# ---------------------------------------------------------------------------
# What is typed reaches the rules
# ---------------------------------------------------------------------------


def test_typed_fields_become_reference_values(client, recorder):
    client.post(
        "/",
        files={"label": ("upload.png", _PNG_1x1, "image/png")},
        data={
            "beverage_type": "distilled_spirits",
            "brand_name": "Stone's Throw",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "45% ALC/VOL",
            "net_contents": "750 mL",
            "applicant_name_address": "Stone's Throw Distillery, Bardstown, KY",
            "source_of_product": "domestic",
        },
    )
    expected = _expected(recorder.applications[0])
    assert expected["brand_name"].value == "Stone's Throw"
    assert expected["class_type"].value == "Kentucky Straight Bourbon Whiskey"
    assert float(expected["alcohol_content"].abv_labeled_pct) == 45.0
    assert float(expected["net_contents"].container_volume_ml) == 750.0
    assert expected["name_and_address"].value.startswith("Stone's Throw Distillery")
    assert expected["country_of_origin"].parameters["source_of_product"] == "domestic"


def test_the_declared_beverage_type_picks_the_rule_pack(client, recorder):
    client.post(
        "/",
        files={"label": ("upload.png", _PNG_1x1, "image/png")},
        data={"beverage_type": "wine", "wine_appellation": "Napa Valley"},
    )
    application = recorder.applications[0]
    assert application.beverage_class is BeverageClass.WINE
    assert _expected(application)["wine_appellation"].value == "Napa Valley"


def test_an_image_on_its_own_still_evaluates(client, recorder):
    """Today's behaviour is preserved: no application, no comparisons, and the
    presence and warning checks still run."""
    response = client.post("/", files={"label": ("upload.png", _PNG_1x1, "image/png")})
    assert response.status_code == 200
    application = recorder.applications[0]
    assert application.expected_values == ()
    assert application.beverage_class is None


def test_an_unreadable_application_is_reported_not_ignored(client, recorder):
    """Dropping a field the reviewer filled in would show a checked label that
    was never compared."""
    response = client.post(
        "/",
        files={"label": ("upload.png", _PNG_1x1, "image/png")},
        data={"beverage_type": "cider", "brand_name": "Stone's Throw"},
    )
    assert response.status_code == 400
    assert "cider" in response.text
    assert recorder.applications == []


def test_fields_without_a_beverage_type_are_reported(client, recorder):
    response = client.post(
        "/",
        files={"label": ("upload.png", _PNG_1x1, "image/png")},
        data={"beverage_type": "", "brand_name": "Stone's Throw"},
    )
    assert response.status_code == 400
    assert "beverage type" in response.text.lower()
    assert recorder.applications == []


# ---------------------------------------------------------------------------
# Bulk upload
# ---------------------------------------------------------------------------


def test_the_bulk_page_asks_for_one_beverage_type():
    """A folder of wine labels checked against the spirits pack fires none of
    the wine rules, so the batch form asks which pack applies to the set."""
    response = TestClient(create_app()).get("/batches")
    assert 'name="beverage_type"' in response.text


def test_the_bulk_beverage_type_reaches_every_label(client, recorder):
    response = client.post(
        "/batches/upload",
        files=[
            ("labels", ("a.png", _PNG_1x1, "image/png")),
            ("labels", ("b.png", _PNG_1x1, "image/png")),
        ],
        data={"beverage_type": "malt_beverage"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert len(recorder.applications) == 2
    assert {a.beverage_class for a in recorder.applications} == {BeverageClass.MALT}


def test_a_bulk_upload_without_a_beverage_type_still_runs(client, recorder):
    """The batch form's type is an aid, not a gate: a reviewer who skips it gets
    the same check the app gave before it existed."""
    response = client.post(
        "/batches/upload",
        files=[("labels", ("a.png", _PNG_1x1, "image/png"))],
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert recorder.applications[0].beverage_class is None
