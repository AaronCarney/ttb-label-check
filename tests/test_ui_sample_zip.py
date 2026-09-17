"""GET /batches/sample.zip — downloadable sample batch of installed labels.

Deployed-app demo affordance: a reviewer can pull a sample of real TTB Public
COLA Registry labels (CC0) and upload them through POST /batches/upload to
exercise the real worker pipeline (no simulation).
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.ui import samples
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def sample_ids() -> list[str]:
    """The TTB IDs the endpoint can draw from, read the way the app reads them."""
    return samples._load_sample_ttbids()


def test_sample_zip_default_returns_zip(client: TestClient) -> None:
    response = client.get("/batches/sample.zip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "sample.zip" in response.headers["content-disposition"]


def test_sample_zip_default_count_is_ten(client: TestClient) -> None:
    response = client.get("/batches/sample.zip")
    z = zipfile.ZipFile(io.BytesIO(response.content))
    names = [n for n in z.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
    assert len(names) == 10


def test_sample_zip_n_param_controls_count(client: TestClient) -> None:
    response = client.get("/batches/sample.zip?n=5")
    z = zipfile.ZipFile(io.BytesIO(response.content))
    names = [n for n in z.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
    assert len(names) == 5


def test_sample_zip_n_capped_at_sample_size(client: TestClient, sample_ids: list[str]) -> None:
    """Asking for more than we have caps cleanly rather than 4xx."""
    response = client.get(f"/batches/sample.zip?n={len(sample_ids) + 100}")
    assert response.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(response.content))
    names = [n for n in z.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
    assert len(names) == len(sample_ids)


def test_sample_zip_n_zero_is_400(client: TestClient) -> None:
    response = client.get("/batches/sample.zip?n=0")
    assert response.status_code == 400


def test_sample_zip_entries_named_for_an_installed_label(
    client: TestClient, sample_ids: list[str]
) -> None:
    """Every zipped image's name carries the TTB ID it came from, so a
    reviewer can trace a sample back to its COLA registry record."""
    installed = set(sample_ids)
    response = client.get(f"/batches/sample.zip?n={len(sample_ids)}")
    z = zipfile.ZipFile(io.BytesIO(response.content))
    for name in z.namelist():
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        assert any(tid in name for tid in installed), f"{name!r} references unknown ttbid"


def test_sample_zip_entries_are_valid_images(client: TestClient) -> None:
    response = client.get("/batches/sample.zip?n=3")
    z = zipfile.ZipFile(io.BytesIO(response.content))
    image_names = [n for n in z.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
    assert image_names, "zip must contain images"
    for name in image_names:
        body = z.read(name)
        # JPEG magic
        assert body.startswith((b"\xff\xd8\xff", b"\x89PNG")), (
            f"{name!r} is not a valid JPEG/PNG (first bytes {body[:4]!r})"
        )


def test_upload_page_links_to_sample_zip(client: TestClient) -> None:
    """The /batches upload form must surface the sample-zip download —
    otherwise a reviewer without their own labels can't try the bulk flow."""
    response = client.get("/batches")
    assert response.status_code == 200
    assert "/batches/sample.zip" in response.text


def test_sample_zip_makes_no_outbound_request(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PRD C-4: the product works with outbound traffic blocked. The samples
    ship in the app, so a download must not reach the network for them."""
    import urllib.request

    def _blocked(*args, **kwargs):
        raise AssertionError("sample.zip attempted an outbound request")

    monkeypatch.setattr(urllib.request, "urlopen", _blocked)

    response = client.get("/batches/sample.zip?n=3")
    assert response.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(response.content))
    assert len(z.namelist()) == 3


def test_sample_zip_500_when_no_labels_installed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A build with no sample labels says so rather than serving an empty zip
    that looks like a working download."""
    monkeypatch.setattr(samples, "_SAMPLE_LABELS_DIR", tmp_path)

    response = client.get("/batches/sample.zip?n=2")
    assert response.status_code == 500
    assert b"no sample labels" in response.content
