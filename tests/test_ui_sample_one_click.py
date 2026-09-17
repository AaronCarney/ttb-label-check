"""One click from arriving to a checked label.

Everything the product does needs a label and the application filed for it.
Before this route, a reviewer with neither had to download a zip, unzip it,
pick a file and type ten application fields before anything happened at all —
so the most likely outcome of a first visit was that nothing was ever checked.

These tests hold the three things that make the one-click path worth having:
the landing page offers it, clicking it checks a real shipped image against the
application really filed for that label, and it runs the same path a reviewer's
own upload runs rather than a demonstration path of its own.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from app.api.ui import _get_upload_evaluator
from app.api.ui.samples import _manifest_entries, _posted_from, offered_samples
from app.main import create_app
from tests.conftest import _stub_disposition_envelope


class _RecordingEvaluator:
    """An evaluator that keeps every (application, label) pair it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    async def evaluate(self, application, label):
        self.calls.append((application, label))
        return _stub_disposition_envelope(len(self.calls), disposition="pass")


@pytest.fixture
def recorder():
    return _RecordingEvaluator()


@pytest.fixture
def client(recorder):
    app = create_app()
    app.dependency_overrides[_get_upload_evaluator] = lambda: recorder
    return TestClient(app)


# ---------------------------------------------------------------------------
# The landing page offers it
# ---------------------------------------------------------------------------


def test_the_landing_page_offers_at_least_one_sample_to_check():
    response = TestClient(create_app()).get("/")
    assert response.status_code == 200
    samples = offered_samples()
    assert samples, "no sample labels are installed, so the page can offer none"
    for sample in samples:
        assert f'action="/samples/{sample["id"]}"' in response.text


def test_each_offered_sample_says_what_checking_it_will_show():
    """A row of identical buttons is not an offer. Each one names the label and
    what the check demonstrates, or a reviewer has no reason to pick any."""
    response = TestClient(create_app()).get("/")
    for sample in offered_samples():
        # Escaped as Jinja renders it — a brand such as LUCKY LUCY'S reaches
        # the page with its apostrophe as an entity.
        assert str(escape(sample["brand"])) in response.text
        assert str(escape(sample["blurb"])) in response.text


def test_the_offered_samples_are_all_installed():
    entries = _manifest_entries()
    for sample in offered_samples():
        assert sample["id"] in entries


# ---------------------------------------------------------------------------
# Clicking it checks the label against the application really filed for it
# ---------------------------------------------------------------------------


def test_clicking_a_sample_returns_a_result_page(client):
    sample_id = offered_samples()[0]["id"]
    response = client.post(f"/samples/{sample_id}")
    assert response.status_code == 200
    assert 'id="envelope"' in response.text, "the page carries no envelope to render"


def test_clicking_a_sample_sends_the_real_image_to_the_evaluator(client, recorder):
    sample_id = offered_samples()[0]["id"]
    client.post(f"/samples/{sample_id}")
    assert len(recorder.calls) == 1
    _, label = recorder.calls[0]
    assert label.faces[0].content_type in {"image/jpeg", "image/png"}
    assert len(label.faces[0].image_bytes) > 1000, "a real label image, not a placeholder"


def test_clicking_a_sample_sends_the_application_filed_for_that_label(client, recorder):
    """The point of the click is a comparison, so the application values have
    to arrive as reference values — otherwise every rule reports that it has
    nothing to compare and the reviewer learns nothing."""
    sample_id = "ttb-26239001000132"  # imported wine: the widest set of fields
    entry = _manifest_entries()[sample_id]
    client.post(f"/samples/{sample_id}")
    application, _ = recorder.calls[0]

    expected = {e.field_id: e.value for e in application.expected_values}
    assert expected, "the sample arrived with no reference values at all"
    assert expected.get("brand_name") == entry["application"]["brand_name"]
    assert expected.get("country_of_origin") == entry["application"]["origin"]


def test_the_result_page_shows_the_application_it_used(client):
    """A reviewer has to be able to see what the label was checked against,
    or a pass means nothing to them."""
    sample_id = "ttb-26239001000132"
    response = client.post(f"/samples/{sample_id}")
    posted = _posted_from(_manifest_entries()[sample_id])
    assert f'value="{posted["brand_name"]}"' in response.text
    assert f'value="{posted["origin"]}"' in response.text


def test_the_result_page_shows_the_label_image(client):
    sample_id = offered_samples()[0]["id"]
    response = client.post(f"/samples/{sample_id}")
    assert "/image" in response.text, "the result page shows no label image"


# ---------------------------------------------------------------------------
# It is the same path a reviewer's own upload takes
# ---------------------------------------------------------------------------


def test_a_domestic_sample_sends_no_country_of_origin(client, recorder):
    """The manifest records a domestic application's `origin` as the producing
    state, which is not what the form's country-of-origin field means. Sending
    it would show a reviewer 'ILLINOIS' in a box labelled country of origin."""
    domestic = next(
        sample_id
        for sample_id, entry in _manifest_entries().items()
        if entry.get("application", {}).get("source_of_product") == "Domestic"
    )
    assert _posted_from(_manifest_entries()[domestic])["origin"] == ""


def test_an_unknown_sample_is_a_404(client):
    assert client.post("/samples/no-such-label").status_code == 404


def test_a_sample_id_cannot_name_a_file_outside_the_samples_directory(client):
    """The id indexes the manifest rather than being joined to a path, so a
    traversal attempt finds no entry."""
    for probe in ("../../etc/passwd", "..%2F..%2Fetc%2Fpasswd"):
        assert client.post(f"/samples/{probe}").status_code in {404, 405}


def test_the_sample_route_and_the_upload_route_render_the_same_shell(client):
    """One result page, not two. If these diverge, a reviewer's own upload stops
    demonstrating what the sample demonstrated."""
    sample_id = offered_samples()[0]["id"]
    sample_page = client.post(f"/samples/{sample_id}")
    upload_page = client.post(
        "/",
        files={"label": ("x.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"beverage_type": "distilled_spirits"},
    )
    for marker in ('id="root"', 'data-mode="single"', 'id="envelope"'):
        assert marker in sample_page.text
        assert marker in upload_page.text


def _jpeg_bytes() -> bytes:
    """The smallest thing the mime sniffer accepts as a JPEG. The evaluator is
    a stub here, so the bytes never have to decode."""
    return b"\xff\xd8\xff" + b"\x00" * 2048
