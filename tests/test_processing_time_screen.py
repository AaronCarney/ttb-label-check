"""The time a check took is on the screen, not only in the envelope.

`metrics` has carried `total_duration_ms` since the envelope was first written,
and until now the only route to it was the raw-JSON drawer, which is off unless
`DEV_MODE` is set. The owner asked to see the processing time; a number nobody
can reach is not shown.

These load the real page in a browser rather than rendering the component in
jsdom, because "it is on the screen" is the claim being made. The component's
own wording cases are in `frontend/src/components/ProcessingTime.test.tsx`.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page

from tests._browser import envelope_fixture, open_results

SLA_TIMEOUT_CODE = "ENGINE.SLA.TIMEOUT"


def _envelope() -> dict[str, Any]:
    return envelope_fixture("01-spirits-clean.json")


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_result_screen_shows_how_long_the_check_took(page: Page, live_server_url: str) -> None:
    envelope = _envelope()
    assert envelope["metrics"]["total_duration_ms"] == 1230, (
        "fixture retimed; update the expectation below"
    )
    open_results(page, live_server_url, [envelope])
    assert page.get_by_text("Checked in 1.2 s").is_visible()


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_result_screen_says_a_cached_answer_is_cached(page: Page, live_server_url: str) -> None:
    """A cache hit costs milliseconds, and those milliseconds describe serving
    the stored answer rather than checking the label. Shown bare beside a
    verdict, the number would claim a speed the check never had."""
    envelope = _envelope()
    envelope["metrics"]["cache_hit"] = True
    envelope["metrics"]["total_duration_ms"] = 12
    open_results(page, live_server_url, [envelope])
    assert page.get_by_text("Served from cache in 12 ms").is_visible()


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_result_screen_says_a_stopped_check_was_stopped(page: Page, live_server_url: str) -> None:
    """The evaluation guard now reports real elapsed time instead
    of 0, so the number on a stopped check is how far it got, not how long a
    whole check takes. The screen has to say so."""
    envelope = _envelope()
    envelope["metrics"]["total_duration_ms"] = 5000
    envelope["audit_trail"]["per_rule_trace"].append(
        {
            "rule_id": SLA_TIMEOUT_CODE,
            "outcome": "error",
            "evidence_ref": f"engine_failure/{SLA_TIMEOUT_CODE}",
        }
    )
    open_results(page, live_server_url, [envelope])
    assert page.get_by_text("Stopped after 5.0 s").is_visible()
