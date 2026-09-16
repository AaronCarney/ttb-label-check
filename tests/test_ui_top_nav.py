"""Top-level nav present on every page shell so a grader can switch between
single-label review and bulk-batch upload without typing a URL by hand.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _strip_existing_bulk_link(html: str) -> str:
    """The single-page upload form already has a 'Bulk upload →' link inside
    the form. We want to assert the *top-level* nav also surfaces these,
    independent of any per-page in-content links — strip the in-content
    bulk-link before searching, so the assertion proves a separate nav
    landmark exists."""
    return re.sub(r'<a[^>]*class="bulk-link"[^>]*>.*?</a>', "", html, flags=re.DOTALL)


def test_top_nav_landmark_present_on_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    # A <nav> with the site-nav role/aria label is the landmark
    assert 'aria-label="Primary"' in response.text


def test_top_nav_links_to_single_on_root(client: TestClient) -> None:
    response = client.get("/")
    body = _strip_existing_bulk_link(response.text)
    # Single-label entry point — the root URL itself
    assert re.search(r'<a[^>]+href="/"[^>]*>\s*Single label', body) is not None


def test_top_nav_links_to_bulk_on_root(client: TestClient) -> None:
    response = client.get("/")
    body = _strip_existing_bulk_link(response.text)
    assert re.search(r'<a[^>]+href="/batches"[^>]*>\s*Bulk batch', body) is not None


def test_top_nav_present_on_bulk_page(client: TestClient) -> None:
    response = client.get("/batches")
    assert response.status_code == 200
    assert 'aria-label="Primary"' in response.text
    assert re.search(r'<a[^>]+href="/"[^>]*>\s*Single label', response.text) is not None
    assert re.search(r'<a[^>]+href="/batches"[^>]*>\s*Bulk batch', response.text) is not None


def test_top_nav_present_on_batch_progress_page(client: TestClient) -> None:
    response = client.get("/batch/B-anything")
    assert response.status_code == 200
    assert 'aria-label="Primary"' in response.text
    assert re.search(r'<a[^>]+href="/"[^>]*>\s*Single label', response.text) is not None
    assert re.search(r'<a[^>]+href="/batches"[^>]*>\s*Bulk batch', response.text) is not None
