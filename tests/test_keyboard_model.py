"""An override can be completed in three keystrokes, with no mouse."""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page

from tests._browser import envelope_fixture, open_results

FIXTURE_NAME = "03-warning-title-case.json"


def _accepting_override(route, request) -> None:
    """Answer the override endpoint as it answers when it records one."""
    posted = request.post_data_json or {}
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                "field_name": None,
                "original_disposition": "pass",
                "applied_disposition": "needs_review",
                "reason_code": posted.get("reason_code", ""),
                "justification_text": posted.get("justification_text"),
                "reviewer_id": "session-test",
                "timestamp": "2026-09-15T00:00:00Z",
            }
        ),
    )


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_three_keystroke_override(page: Page, live_server_url: str) -> None:
    page.route("**/labels/*/overrides", _accepting_override)
    open_results(page, live_server_url, [envelope_fixture(FIXTURE_NAME)])

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
    envelope = envelope_fixture(FIXTURE_NAME)
    captured: dict = {}

    def _route(route, request):
        captured["url"] = request.url
        captured["method"] = request.method
        captured["body"] = request.post_data_json
        _accepting_override(route, request)

    page.route("**/labels/*/overrides", _route)
    open_results(page, live_server_url, [envelope])

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
    # The applied disposition is pinned per code in `REASON_CODES` rather than
    # read off the code name. This code's registry severity is `reject`, so it
    # applies "fail"; prefix-matching produced "needs_review" and wrote a wrong
    # audit entry.
    assert body["applied_disposition"] == "fail"
    assert body["field_name"] is None
    assert "evaluation_id" not in body
    assert "reviewer_id" not in body


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_override_failure_path_surfaces_toast(page: Page, live_server_url: str) -> None:
    def _route_422(route):
        route.fulfill(
            status=422,
            content_type="application/json",
            body=json.dumps(
                {
                    "detail": "reason_code 'WARNING.STYLE.HEADING_NOT_BOLD_CAPS' is not in the "
                    "loaded registry",
                }
            ),
        )

    page.route("**/labels/*/overrides", _route_422)
    open_results(page, live_server_url, [envelope_fixture(FIXTURE_NAME)])

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
    open_results(page, live_server_url, [envelope_fixture(FIXTURE_NAME)])
    page.keyboard.press("o")
    page.wait_for_selector('[role="dialog"]', timeout=2000)
    page.keyboard.type("j")  # 'j' should land in the picker as text, not navigate.
    assert page.locator('[role="combobox"]').input_value().lower() == "j"
