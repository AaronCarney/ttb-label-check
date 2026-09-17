"""An override can be completed in three keystrokes, with no mouse."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "envelopes" / "single" / "03-warning-title-case.json"


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_three_keystroke_override(page: Page, live_server_url: str) -> None:
    envelope = json.loads(FIXTURE.read_text())

    def _route(route, request):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "field_name": None,
                    "original_disposition": "pass",
                    "applied_disposition": "needs_review",
                    "reason_code": (request.post_data_json or {}).get("reason_code", ""),
                    "justification_text": (request.post_data_json or {}).get("justification_text"),
                    "reviewer_id": "session-test",
                    "timestamp": "2026-09-15T00:00:00Z",
                }
            ),
        )

    page.route("**/labels/*/overrides", _route)

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

    # Keystroke 1: 'O' → drawer opens, picker auto-focuses.
    page.keyboard.press("o")
    page.wait_for_selector('[role="dialog"]', timeout=2000)
    assert page.locator('[role="combobox"]').count() == 1

    # Keystroke 2: 'W' → unique prefix → ReasonCodePicker auto-selects WARNING.*.
    page.keyboard.type("w")

    # Keystroke 3: ENTER → submit.
    page.keyboard.press("Enter")

    # The LiveRegion announces the saved override; wait for the message.
    page.wait_for_selector(
        "text=/Override saved: WARNING\\.STYLE\\.HEADING_NOT_BOLD_CAPS/",
        timeout=2000,
    )


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_three_keystroke_override_posts_to_endpoint(page: Page, live_server_url: str) -> None:
    envelope = json.loads(FIXTURE.read_text())
    captured: dict = {}

    def _route(route, request):
        captured["url"] = request.url
        captured["method"] = request.method
        captured["body"] = request.post_data_json
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "field_name": None,
                    "original_disposition": "pass",
                    "applied_disposition": "needs_review",
                    "reason_code": (request.post_data_json or {}).get("reason_code", ""),
                    "justification_text": (request.post_data_json or {}).get("justification_text"),
                    "reviewer_id": "session-test",
                    "timestamp": "2026-09-15T00:00:00Z",
                }
            ),
        )

    page.route("**/labels/*/overrides", _route)

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

    page.keyboard.press("o")
    page.wait_for_selector('[role="dialog"]', timeout=2000)
    page.keyboard.type("w")
    page.keyboard.press("Enter")
    page.wait_for_selector(
        "text=/Override saved: WARNING\\.STYLE\\.HEADING_NOT_BOLD_CAPS/",
        timeout=2000,
    )
    assert captured["method"] == "POST"
    assert f"/labels/{envelope['evaluation_id']}/overrides" in captured["url"]
    body = captured["body"]
    assert body["reason_code"] == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"
    # Per V15 (commit d1a4895): override applied_disposition is pinned per-code
    # via _REASON_CODES instead of prefix-matching. This code's registry severity
    # is `reject` → applied_disposition="fail", not "needs_review".
    assert body["applied_disposition"] == "fail"
    assert body["field_name"] is None
    assert "evaluation_id" not in body
    assert "reviewer_id" not in body


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_override_failure_path_surfaces_toast(page: Page, live_server_url: str) -> None:
    envelope = json.loads(FIXTURE.read_text())

    def _route_422(route):
        route.fulfill(
            status=422,
            content_type="application/json",
            body=json.dumps(
                {
                    "detail": "reason_code 'WARNING.STYLE.HEADING_NOT_BOLD_CAPS' is not in the loaded registry",
                }
            ),
        )

    page.route("**/labels/*/overrides", _route_422)

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

    page.keyboard.press("o")
    page.wait_for_selector('[role="dialog"]', timeout=2000)
    page.keyboard.type("w")
    page.keyboard.press("Enter")

    # Toast renders with role=status; select by unique error text since
    # disposition badges also use role=status on the page.
    toast = page.get_by_text("not in the loaded registry")
    toast.wait_for(state="visible", timeout=2000)
    assert page.locator('[role="dialog"]').is_visible()
    assert "not in the loaded registry" in toast.inner_text()


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_jk_navigation_does_not_steal_typing(page: Page, live_server_url: str) -> None:
    """J/K are reserved for batch navigation but must not fire while typing."""
    envelope = json.loads(FIXTURE.read_text())
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
    page.keyboard.press("o")
    page.wait_for_selector('[role="dialog"]', timeout=2000)
    page.keyboard.type("j")  # 'j' should land in the picker as text, not navigate.
    assert page.locator('[role="combobox"]').input_value().lower() == "j"
