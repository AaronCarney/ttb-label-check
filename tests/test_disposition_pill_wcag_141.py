"""The disposition pill encodes colour, shape and text, so a disposition is
never carried by colour alone (WCAG 1.4.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "envelopes" / "single"


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
@pytest.mark.parametrize(
    "fixture_name,expected_disposition,expected_shape,expected_text",
    [
        ("01-spirits-clean.json", "pass", "check", "Pass"),
        ("03-warning-title-case.json", "fail", "x", "Fail"),
        ("04-low-res-blurry.json", "needs_review", "question", "Needs review"),
        ("06-abv-application-disagreement.json", "fail", "x", "Fail"),
        ("07-borderline-confidence.json", "needs_review", "question", "Needs review"),
    ],
)
def test_disposition_pill_three_channels(
    fixture_name: str,
    expected_disposition: str,
    expected_shape: str,
    expected_text: str,
    page: Page,
    live_server_url: str,
) -> None:
    envelope = json.loads((FIXTURES / fixture_name).read_text())
    assert envelope["disposition"] == expected_disposition
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

    # Disposition-level pill is in the header next to the label_ref.
    pill = page.locator(f'[role="status"][aria-label="Disposition: {expected_text}"]').first
    assert pill.count() == 1
    # Text channel.
    assert expected_text in (pill.inner_text() or "")
    # Shape channel.
    assert pill.locator(f'[data-shape="{expected_shape}"]').count() == 1
    # Color channel — computed background-color is not the document body bg.
    pill_bg = pill.evaluate("(el) => getComputedStyle(el).backgroundColor")
    body_bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    assert pill_bg not in {"rgba(0, 0, 0, 0)", "transparent", body_bg}, (
        f"Pill background ({pill_bg}) is not visually distinct from body ({body_bg})"
    )
