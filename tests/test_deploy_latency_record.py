"""The parts of the deploy latency harness that do not need the deployed URL.

`tests/test_deploy_healthz.py` times each check to the result arriving on the
batch's stream and writes every row to a file, so a run says what came back
rather than only how long it took. Previously it kept the status code and the
wall clock and discarded both on a pass, which is why four consecutive runs
against production yielded the same two facts and no way to tell a check that
was cut off from one that was merely slow.

These exercise that reading and that summary on captured envelopes and a stand-in
transport, so the logic is covered on every run rather than only when someone
points the suite at a live service.
"""

import json
from pathlib import Path

import httpx

from tests.test_deploy_healthz import _check_once, _row_from_result, _summarise

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


def _service(stream_status: int = 200, post_status: int = 303) -> httpx.MockTransport:
    """The deployed service as the harness meets it: `POST /` starts a batch and
    redirects to it, and the batch's stream carries its result and then ends."""

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            if post_status != 303:
                return httpx.Response(post_status)
            return httpx.Response(303, headers={"location": "/batch/B-1"})
        if stream_status != 200:
            return httpx.Response(stream_status)
        body = (
            "event: label-result\n"
            f"data: {json.dumps({'queue_position': 0, 'envelope': _COMPLETE})}\n\n"
            "event: stream-end\ndata: {}\n\n"
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    return httpx.MockTransport(handle)


def _face(tmp_path: Path) -> list[Path]:
    face = tmp_path / "front.jpg"
    face.write_bytes(b"\xff\xd8\xff")
    return [face]


def test_a_check_is_the_result_its_stream_delivers(tmp_path):
    status, seconds, envelope = _check_once("http://svc", _face(tmp_path), {}, _service())
    assert status == 200
    assert seconds >= 0
    assert envelope == _COMPLETE


def test_a_refused_submission_is_its_status_and_no_result(tmp_path):
    """The service takes one batch at a time and answers 409 to the next."""
    status, _, envelope = _check_once("http://svc", _face(tmp_path), {}, _service(post_status=409))
    assert (status, envelope) == (409, None)


def test_a_stream_that_is_not_found_is_no_result(tmp_path):
    """What a reviewer sees when their results are asked for from an instance
    that does not hold the batch."""
    status, _, envelope = _check_once(
        "http://svc", _face(tmp_path), {}, _service(stream_status=404)
    )
    assert (status, envelope) == (None, None)


def test_a_row_records_what_came_back_not_only_how_long_it_took():
    row = _row_from_result("ttb-1", 200, 2.89, _COMPLETE, 2)
    assert row == {
        "label_id": "ttb-1",
        "status": 200,
        "wall_seconds": 2.89,
        "faces": 2,
        "disposition": "fail",
        "field_count": 7,
        "total_duration_ms": 2555,
        "vision_duration_ms": 2229,
        "cache_hit": False,
        "stopped_early": False,
        "trace": ["ENGINE.RULE_PACK.SELECTED"],
    }


def test_a_row_tells_a_check_that_was_stopped_apart_from_one_that_was_slow():
    """Both cross five seconds and both come back with a result. Only the trace
    says which is which, and the harness recorded neither."""
    stopped = _row_from_result("ttb-2", 200, 5.04, _STOPPED, 2)
    slow = _row_from_result("ttb-3", 200, 5.12, _COMPLETE, 2)
    assert stopped["stopped_early"] is True
    assert slow["stopped_early"] is False


def test_the_summary_counts_what_the_requirement_asks_about():
    rows = [
        _row_from_result("a", 200, 1.2, _COMPLETE, 2),
        _row_from_result("b", 200, 2.0, _COMPLETE, 1),
        _row_from_result("c", 200, 5.04, _STOPPED, 2),
    ]
    summary = _summarise(rows)
    assert summary["checked"] == 3
    assert summary["inside_budget"] == 2
    assert summary["share_inside_budget"] == 2 / 3
    assert summary["stopped_early"] == 1
    assert summary["cache_hits"] == 0
    assert summary["median_wall_seconds"] == 2.0
    assert summary["two_faced"] == 2


def test_a_refused_submission_is_not_a_check_inside_the_budget():
    """A 409 comes back in under a second. Counted as a check, a busy service
    would read as a fast one."""
    rows = [
        _row_from_result("a", 200, 1.2, _COMPLETE, 2),
        _row_from_result("b", 409, 0.4, None, 2),
    ]
    summary = _summarise(rows)
    assert summary["inside_budget"] == 1
    assert summary["no_result"] == 1


def test_the_summary_says_how_many_checks_carried_a_back():
    """A run mixing one-faced and two-faced submissions cannot be read without
    it: the second face is a second read, and four of the test labels have no
    back to send."""
    fronts_only = [_row_from_result("a", 200, 1.2, _COMPLETE, 1)]
    assert _summarise(fronts_only)["two_faced"] == 0
