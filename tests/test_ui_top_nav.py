"""The top-level nav landmark, on every page shell.

It carries one link now, because there is one way in: a reviewer with one label
and a reviewer with three hundred use the same form. Two links were a choice
between two systems that a reviewer had to make before they had checked
anything (`docs/decisions.md#0045`).
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PAGES = ("/", "/batch/B-anything")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.mark.parametrize("path", PAGES)
def test_top_nav_landmark_present(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert 'aria-label="Primary"' in response.text


@pytest.mark.parametrize("path", PAGES)
def test_top_nav_links_back_to_the_form(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert re.search(r'<a[^>]+href="/"[^>]*>\s*Check labels', response.text) is not None


@pytest.mark.parametrize("path", PAGES)
def test_top_nav_offers_no_second_system(client: TestClient, path: str) -> None:
    """The nav names one destination. A second entry point in it is the defect
    the merge removed, so it is asserted against rather than left to review."""
    nav = re.search(r'<nav[^>]*aria-label="Primary".*?</nav>', client.get(path).text, re.S)
    assert nav is not None
    assert len(re.findall(r"<a\b", nav.group(0))) == 1, nav.group(0)
