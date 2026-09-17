"""The layout reflows at 320 CSS px with no two-dimensional scrolling
(WCAG 1.4.10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "envelopes" / "single" / "01-spirits-clean.json"


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_no_horizontal_scroll_at_320px(page: Page, live_server_url: str) -> None:
    envelope = json.loads(FIXTURE.read_text())
    page.set_viewport_size({"width": 320, "height": 640})
    page.add_init_script(
        script=f"""
          window.addEventListener('DOMContentLoaded', () => {{
            const tag = document.createElement('script');
            tag.id = 'envelope';
            tag.type = 'application/json';
            tag.textContent = {json.dumps(json.dumps(envelope))};
            document.body.appendChild(tag);
          }});
        """
    )
    page.goto(f"{live_server_url}/")
    page.wait_for_selector('[data-mounted="true"]', timeout=5000)
    scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
    client_width = page.evaluate("() => document.documentElement.clientWidth")
    # Tolerance of 1 px for sub-pixel rounding.
    assert scroll_width <= client_width + 1, (
        f"320 px viewport shows horizontal scroll: scrollWidth={scroll_width}, clientWidth={client_width}"
    )
