"""A reviewer corrects one field's result on the page, and the label follows.

A result stands with no action. Where the reviewer finds it wrong, the field's
own control corrects it, and the label's result on the page and its row in the
batch table both show the result the server returns (docs/decisions.md#0064).
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page

from tests._browser import envelope_fixture, open_results

FAILED = "03-warning-title-case.json"
PASSED = "01-spirits-clean.json"


def _accepting_correction(captured: list[dict]):
    def _route(route, request) -> None:
        posted = request.post_data_json or {}
        captured.append(posted)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "field_name": posted.get("field_name"),
                    "original_disposition": "fail",
                    "applied_disposition": posted.get("applied_disposition"),
                    "reason_code": posted.get("reason_code", ""),
                    "justification_text": None,
                    "reviewer_id": "session-test",
                    "timestamp": "2026-09-22T00:00:00Z",
                    "label_disposition": "pass",
                }
            ),
        )

    return _route


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_correcting_the_failed_field_passes_the_label(page: Page, live_server_url: str) -> None:
    captured: list[dict] = []
    page.route("**/labels/*/overrides", _accepting_correction(captured))
    failed = envelope_fixture(FAILED)
    open_results(page, live_server_url, [failed, envelope_fixture(PASSED)])

    result = page.get_by_role("region", name=f"Check results for {failed['label_ref']}")
    result.wait_for(timeout=5000)
    card = result.get_by_role("region", name="Field: warning")
    card.get_by_role("button", name="This result is wrong").click()
    card.get_by_role("group", name="Correct the result for Warning").get_by_role(
        "button", name="Pass"
    ).click()

    card.get_by_text("Corrected by the reviewer. The check reported Fail.").wait_for(timeout=2000)
    assert captured == [
        {
            "field_name": "warning",
            "applied_disposition": "pass",
            "reason_code": "REVIEWER.CORRECTION.PASS",
            "justification_text": None,
        }
    ]
    header = result.locator("header").first
    assert header.get_by_role("status", name="Disposition: Pass").is_visible()
    # The batch table's row for the label now reads Pass too: both rows do.
    table = page.get_by_role("table")
    assert table.get_by_role("status", name="Disposition: Fail").count() == 0
    assert table.get_by_role("status", name="Disposition: Pass").count() == 2


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_the_correction_is_reached_from_the_keyboard(page: Page, live_server_url: str) -> None:
    captured: list[dict] = []
    page.route("**/labels/*/overrides", _accepting_correction(captured))
    open_results(page, live_server_url, [envelope_fixture(FAILED)])

    control = page.get_by_role("button", name="This result is wrong")
    control.focus()
    page.keyboard.press("Enter")
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")

    page.get_by_text("Corrected by the reviewer. The check reported Fail.").wait_for(timeout=2000)
    assert captured[0]["applied_disposition"] == "pass"
