"""``POST /samples/{sample_id}`` — one shipped label against its filed application.

Everything the product does needs a label and the application filed for it.
This route supplies both from the shipped corpus, so a single label can be
checked in one request without a download, an unzip and ten typed fields.

The landing page no longer offers a row of buttons onto it. A demo that opens
with a tour of itself is not the product, and the buttons carried blurbs
describing outcomes — one of them an outcome the engine explicitly refuses to
assert. The bulk path carries the demonstration now: `/batches/sample.zip`
ships the images and the applications filed for them, and the reviewer drops
the pack into the same form their own labels go through.

What these tests hold is what makes the route worth keeping: it checks a real
shipped image against the application really filed for that label, and it runs
the same path a reviewer's own upload runs rather than a path of its own.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.ui import _get_upload_evaluator
from app.api.ui.samples import _manifest_entries, _posted_from
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


# One shipped label, named here rather than taken from a list, because these
# tests are about the route and not about which labels a page happens to offer.
_ANY_SAMPLE = "ttb-26236001000652"


# ---------------------------------------------------------------------------
# It checks the label against the application really filed for it
# ---------------------------------------------------------------------------


def test_checking_a_sample_returns_a_result_page(client):
    sample_id = _ANY_SAMPLE
    response = client.post(f"/samples/{sample_id}")
    assert response.status_code == 200
    assert 'id="envelope"' in response.text, "the page carries no envelope to render"


def test_checking_a_sample_sends_the_real_image_to_the_evaluator(client, recorder):
    sample_id = _ANY_SAMPLE
    client.post(f"/samples/{sample_id}")
    assert len(recorder.calls) == 1
    _, label = recorder.calls[0]
    assert label.faces[0].content_type in {"image/jpeg", "image/png"}
    assert len(label.faces[0].image_bytes) > 1000, "a real label image, not a placeholder"


def test_checking_a_sample_sends_the_application_filed_for_that_label(client, recorder):
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
    sample_id = _ANY_SAMPLE
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
    sample_id = _ANY_SAMPLE
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
