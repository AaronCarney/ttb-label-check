"""Playwright harness smoke test: the fixture starts uvicorn and serves /."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.usefixtures("live_server")
def test_playwright_loads_single_shell(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/")
    # The Jinja shell renders before the island JS runs (404 on bundle is OK).
    content = page.content()
    assert 'id="root"' in content
    assert 'data-mode="single"' in content


@pytest.mark.usefixtures("live_server")
def test_playwright_loads_batch_shell(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/batch/abc-123")
    content = page.content()
    assert 'data-mode="batch"' in content
    assert 'data-batch-id="abc-123"' in content
