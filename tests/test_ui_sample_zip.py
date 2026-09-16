"""GET /batches/sample.zip — downloadable sample batch from the active corpus.

Deployed-app demo affordance: a grader can pull a sample of real TTB Public
COLA Registry labels (CC0) and upload them through POST /batches/upload to
exercise the real worker pipeline (no simulation).
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def active_ids() -> list[str]:
    path = Path("fixtures/_corpus/_active.txt")
    return [l.strip() for l in path.read_text().splitlines() if l.strip()]


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


def test_sample_zip_n_capped_at_active_size(client: TestClient, active_ids: list[str]) -> None:
    """Asking for more than we have caps cleanly rather than 4xx."""
    response = client.get(f"/batches/sample.zip?n={len(active_ids) + 100}")
    assert response.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(response.content))
    names = [n for n in z.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
    assert len(names) == len(active_ids)


def test_sample_zip_n_zero_is_400(client: TestClient) -> None:
    response = client.get("/batches/sample.zip?n=0")
    assert response.status_code == 400


def test_sample_zip_entries_drawn_from_active_set(
    client: TestClient, active_ids: list[str]
) -> None:
    """Every zipped image's name must reference a ttbid in _active.txt — the
    pool labels are excluded from the deployed container per .dockerignore."""
    active_set = set(active_ids)
    response = client.get(f"/batches/sample.zip?n={len(active_ids)}")
    z = zipfile.ZipFile(io.BytesIO(response.content))
    for name in z.namelist():
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        # Filenames embed the ttbid: cola-{ttbid}-...jpg or similar
        assert any(tid in name for tid in active_set), f"{name!r} references unknown ttbid"


def test_sample_zip_entries_are_valid_images(client: TestClient) -> None:
    response = client.get("/batches/sample.zip?n=3")
    z = zipfile.ZipFile(io.BytesIO(response.content))
    image_names = [n for n in z.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
    assert image_names, "zip must contain images"
    for name in image_names:
        body = z.read(name)
        # JPEG magic
        assert body.startswith(b"\xff\xd8\xff") or body.startswith(b"\x89PNG"), (
            f"{name!r} is not a valid JPEG/PNG (first bytes {body[:4]!r})"
        )


def test_upload_page_links_to_sample_zip(client: TestClient) -> None:
    """The /batches upload form must surface the sample-zip download —
    otherwise a grader without their own labels can't try the bulk flow."""
    response = client.get("/batches")
    assert response.status_code == 200
    assert "/batches/sample.zip" in response.text


def test_sample_zip_falls_back_to_github_raw_when_disk_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On HF Space the corpus jpgs aren't bundled (binary-blob policy), so
    the endpoint must fetch from GitHub raw at request time."""
    from app.api import ui

    fake_jpeg = b"\xff\xd8\xff\xe0fake"
    fetched_urls: list[str] = []

    def fake_urlopen(url, timeout=10):
        fetched_urls.append(url)

        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def read(self):
                return fake_jpeg

        return FakeResp()

    # Disable disk path: point the active-corpus root at a tmp dir with no jpgs
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    active_path = tmp / "_active.txt"
    active_path.write_text("cola-21210001000878\ncola-22032001001017\n")
    monkeypatch.setattr(ui, "_ACTIVE_CORPUS_PATH", active_path)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    response = client.get("/batches/sample.zip?n=2")
    assert response.status_code == 200

    z = zipfile.ZipFile(io.BytesIO(response.content))
    names = z.namelist()
    assert len(names) == 2
    for n in names:
        assert z.read(n) == fake_jpeg
    # Both ttbids fetched from the GitHub raw base
    assert all(
        "http" in u
        for u in fetched_urls
    )


def test_sample_zip_skips_entries_when_both_disk_and_remote_fail(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If a label can't be sourced anywhere (corrupted active list, GH down),
    skip it — don't 500. Caller still gets a usable zip with whatever we
    could fetch."""
    from app.api import ui
    import tempfile
    import urllib.error

    tmp = Path(tempfile.mkdtemp())
    active_path = tmp / "_active.txt"
    active_path.write_text("cola-99999999999999\n")  # bogus, not on disk
    monkeypatch.setattr(ui, "_ACTIVE_CORPUS_PATH", active_path)

    def always_fail(url, timeout=10):
        raise urllib.error.URLError("offline")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", always_fail)

    response = client.get("/batches/sample.zip?n=1")
    assert response.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(response.content))
    assert z.namelist() == []  # nothing fetched, but request still succeeds
