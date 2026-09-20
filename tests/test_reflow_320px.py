"""The layout reflows at 320 CSS px with no two-dimensional scrolling
(WCAG 1.4.10)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests._browser import envelope_fixture, open_results


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_no_horizontal_scroll_at_320px(page: Page, live_server_url: str) -> None:
    page.set_viewport_size({"width": 320, "height": 640})
    open_results(page, live_server_url, [envelope_fixture("01-spirits-clean.json")])
    scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
    client_width = page.evaluate("() => document.documentElement.clientWidth")
    # Tolerance of 1 px for sub-pixel rounding.
    assert scroll_width <= client_width + 1, (
        f"320 px viewport shows horizontal scroll: scrollWidth={scroll_width}, "
        f"clientWidth={client_width}"
    )
