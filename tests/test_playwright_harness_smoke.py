"""Playwright harness smoke test: the fixture starts uvicorn and serves both pages."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.usefixtures("live_server")
def test_playwright_loads_the_entry_form(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/")
    # The form is server-rendered and mounts no island, so it is complete as
    # soon as the shell is served.
    content = page.content()
    assert 'enctype="multipart/form-data"' in content
    assert 'name="labels"' in content


@pytest.mark.usefixtures("live_server")
def test_playwright_loads_the_results_shell(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/batch/abc-123")
    # The Jinja shell renders before the island JS runs (404 on bundle is OK).
    content = page.content()
    assert 'id="root"' in content
    assert 'data-batch-id="abc-123"' in content
