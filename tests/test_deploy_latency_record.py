"""The parts of the deploy latency harness that do not need the deployed URL.

`tests/test_deploy_healthz.py` reads the envelope off the result page and
writes every row to a file, so a run says what came back rather than only how
long it took. Previously it kept the status code and the wall clock and
discarded both on a pass, which is why four consecutive runs against production
yielded the same two facts and no way to tell a check that was cut off from one
that was merely slow.

These exercise that reading and that summary on captured page text, so the
logic is covered on every run rather than only when someone points the suite at
a live service.
"""

import json

from tests.test_deploy_healthz import _envelope_from_page, _row_from_page, _summarise

_COMPLETE = {
    "disposition": "fail",
    "fields": [{"field_name": "brand_name"}] * 7,
    "audit_trail": {"per_rule_trace": [{"rule_id": "ENGINE.RULE_PACK.SELECTED"}]},
    "metrics": {"total_duration_ms": 2555, "vision_duration_ms": 2229, "cache_hit": False},
}

_STOPPED = {
    "disposition": "needs_review",
    "fields": [],
    "audit_trail": {
        "per_rule_trace": [
            {"rule_id": "ENGINE.RULE_PACK.SELECTED"},
            {"rule_id": "ENGINE.SLA.TIMEOUT"},
        ]
    },
    "metrics": {"total_duration_ms": 5001, "vision_duration_ms": 4911, "cache_hit": False},
}


def _page(envelope: dict) -> str:
    """The result page as `app/ui/templates/single.html` renders it."""
    body = json.dumps(envelope)
    tag = f'<script id="envelope" type="application/json">{body}</script>'
    return f"<html><body>{tag}</body></html>"


def test_reads_the_envelope_the_page_carries():
    assert _envelope_from_page(_page(_COMPLETE))["disposition"] == "fail"


def test_reports_no_envelope_rather_than_raising_on_a_page_without_one():
    assert _envelope_from_page("<html><body>error</body></html>") is None


def test_a_row_records_what_came_back_not_only_how_long_it_took():
    row = _row_from_page("ttb-1", 200, 2.89, _page(_COMPLETE))
    assert row == {
        "label_id": "ttb-1",
        "status": 200,
        "wall_seconds": 2.89,
        "disposition": "fail",
        "field_count": 7,
        "total_duration_ms": 2555,
        "vision_duration_ms": 2229,
        "cache_hit": False,
        "stopped_early": False,
        "trace": ["ENGINE.RULE_PACK.SELECTED"],
    }


def test_a_row_tells_a_check_that_was_stopped_apart_from_one_that_was_slow():
    """Both cross five seconds and both return HTTP 200. Only the trace says
    which is which, and the harness recorded neither."""
    stopped = _row_from_page("ttb-2", 200, 5.04, _page(_STOPPED))
    slow = _row_from_page("ttb-3", 200, 5.12, _page(_COMPLETE))
    assert stopped["stopped_early"] is True
    assert slow["stopped_early"] is False


def test_the_summary_counts_what_the_requirement_asks_about():
    rows = [
        _row_from_page("a", 200, 1.2, _page(_COMPLETE)),
        _row_from_page("b", 200, 2.0, _page(_COMPLETE)),
        _row_from_page("c", 200, 5.04, _page(_STOPPED)),
    ]
    summary = _summarise(rows)
    assert summary["checked"] == 3
    assert summary["inside_budget"] == 2
    assert summary["share_inside_budget"] == 2 / 3
    assert summary["stopped_early"] == 1
    assert summary["cache_hits"] == 0
    assert summary["median_wall_seconds"] == 2.0
