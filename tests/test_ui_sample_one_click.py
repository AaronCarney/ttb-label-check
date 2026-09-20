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

"The same path" is now literal: the route starts a batch of one through
`launch_batch` and answers with a redirect to the results page, exactly as
`POST /` does (`docs/decisions.md#0045`). Nothing about the result is in the
reply any more — the page is a shell and the result arrives over the stream —
so these read the check's own record rather than the HTML. What the page then
draws from that record is `frontend/src/components/`'s own tests and the
browser suites.
"""

from __future__ import annotations

import time

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
    # Entered as a context manager: the check runs as a background task on the
    # app's own loop, and a bare TestClient tears that loop down between
    # requests.
    with TestClient(app) as entered:
        yield entered


def _check_sample(client, sample_id: str) -> list[dict]:
    """Check one shipped sample and return its batch's finished items."""
    response = client.post(f"/samples/{sample_id}", follow_redirects=False)
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert location.startswith("/batch/"), location
    batch_id = location.removeprefix("/batch/")
    deadline = time.monotonic() + 20.0
    items: list[dict] = []
    while time.monotonic() < deadline:
        items = client.get(f"/batches/{batch_id}").json()["items"]
        if items and all(item["state"] in ("ready", "failed") for item in items):
            return items
        time.sleep(0.02)
    raise AssertionError(f"batch {batch_id} did not finish")


# One shipped label, named here rather than taken from a list, because these
# tests are about the route and not about which labels a page happens to offer.
_ANY_SAMPLE = "ttb-26236001000652"


# ---------------------------------------------------------------------------
# It checks the label against the application really filed for it
# ---------------------------------------------------------------------------


def test_checking_a_sample_starts_a_check_and_sends_the_reviewer_to_it(client):
    items = _check_sample(client, _ANY_SAMPLE)
    assert len(items) == 1, items
    assert items[0]["state"] == "ready", items[0]
    assert items[0]["result"] is not None, "the check produced no result to show"


def test_checking_a_sample_sends_the_real_image_to_the_evaluator(client, recorder):
    _check_sample(client, _ANY_SAMPLE)
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
    _check_sample(client, sample_id)
    application, _ = recorder.calls[0]

    expected = {e.field_id: e.value for e in application.expected_values}
    assert expected, "the sample arrived with no reference values at all"
    assert expected.get("brand_name") == entry["application"]["brand_name"]
    assert expected.get("country_of_origin") == entry["application"]["origin"]


def test_every_value_the_manifest_files_reaches_the_check(client, recorder):
    """A reviewer has to be able to see what the label was checked against, or
    a pass means nothing to them — and they see it field by field, so every
    field the manifest files has to arrive, not a representative two.

    Three of the ten the route posts are not reference values and are not
    expected here: `beverage_type` picks the rule pack rather than being
    compared, and no rule compares a fanciful name or whether the product was
    imported.
    """
    sample_id = "ttb-26239001000132"  # imported wine: the widest set of fields
    _check_sample(client, sample_id)
    application, _ = recorder.calls[0]

    posted = _posted_from(_manifest_entries()[sample_id])
    expected = {entry.field_id: entry.value for entry in application.expected_values}
    assert expected == {
        "brand_name": posted["brand_name"],
        "class_type": posted["class_type"],
        "alcohol_content": posted["alcohol_content"],
        "net_contents": posted["net_contents"],
        "name_and_address": posted["applicant_name_address"],
        "country_of_origin": posted["origin"],
        "wine_appellation": posted["wine_appellation"],
    }


def test_the_sample_label_image_is_there_for_the_page_to_show(client):
    """The result names an evaluation, and the photographs it was read from
    have to be fetchable under that name or the page renders a broken figure.
    """
    items = _check_sample(client, _ANY_SAMPLE)
    evaluation_id = items[0]["result"]["evaluation_id"]
    faces = client.get(f"/labels/{evaluation_id}/faces").json()["faces"]
    assert faces, "the check kept no photograph for its own result page"
    for face in faces:
        assert client.get(face["url"]).status_code == 200, face["url"]


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


def test_the_sample_route_and_the_upload_route_land_on_the_same_page(client):
    """One result page, not two. If these diverge, a reviewer's own upload stops
    demonstrating what the sample demonstrated.

    They are compared by the page each redirect lands on, with the batch id
    taken out — that id is the only thing about the two pages that may differ.
    """
    _check_sample(client, _ANY_SAMPLE)

    upload = client.post(
        "/",
        files={"labels": ("x.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"beverage_type": "distilled_spirits"},
        follow_redirects=False,
    )
    assert upload.status_code == 303, upload.text
    upload_batch = upload.headers["location"].removeprefix("/batch/")

    sample = client.post(f"/samples/{_ANY_SAMPLE}", follow_redirects=False)
    assert sample.status_code == 303, sample.text
    sample_batch = sample.headers["location"].removeprefix("/batch/")

    def _shell(batch_id: str) -> str:
        page = client.get(f"/batch/{batch_id}")
        assert page.status_code == 200
        assert 'id="root"' in page.text, "the results page mounts no island"
        return page.text.replace(batch_id, "{batch_id}")

    assert _shell(sample_batch) == _shell(upload_batch)


def _jpeg_bytes() -> bytes:
    """The smallest thing the mime sniffer accepts as a JPEG. The evaluator is
    a stub here, so the bytes never have to decode."""
    return b"\xff\xd8\xff" + b"\x00" * 2048
