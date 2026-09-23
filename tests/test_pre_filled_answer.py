"""Every result carries a pre-filled answer, and a confirmation settles it.

A field the check settled shows its verdict with nothing to confirm. A field it
sent to review shows the answer it leans to, and the reviewer confirms or
corrects it. One field that leans to a mismatch makes the label lean that way,
because one element that does not match rejects the application
(docs/decisions.md#0065).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.schemas.audit import PerRuleTraceEntry
from app.schemas.wire.disposition import DispositionEnvelope
from app.services.disposition import field_lean, label_lean
from tests.conftest import _stub_field_finding
from tests.test_override_corrects_result import _corrected, _envelope, _seeded


def _leaning(
    fields: dict[str, tuple[str, str | None]],
    *,
    disposition: str,
    extra_trace: tuple[PerRuleTraceEntry, ...] = (),
) -> DispositionEnvelope:
    """`_envelope`, with each field's rule leaning as given."""
    env = _envelope({n: v for n, (v, _) in fields.items()}, disposition=disposition)
    cards = tuple(_stub_field_finding(n, f"R-{n}", v, lean) for n, (v, lean) in fields.items())
    trail = env.audit_trail.model_copy(
        update={"per_rule_trace": (*env.audit_trail.per_rule_trace, *extra_trace)}
    )
    # Rebuilt rather than copied, so the label's lean is worked out afresh.
    return DispositionEnvelope.model_validate(
        {**env.model_dump(exclude={"lean"}), "fields": cards, "audit_trail": trail}
    )


# --------------------------------------------------------------------------
# One rule on the wire
# --------------------------------------------------------------------------


def test_a_settled_verdict_is_its_own_pre_filled_answer() -> None:
    [rule] = _stub_field_finding("brand_name", "R", "fail", "pass").rule_findings
    assert rule.lean == "fail"


def test_a_rule_sent_to_review_keeps_the_way_it_leans() -> None:
    [rule] = _stub_field_finding("brand_name", "R", "needs_review", "pass").rule_findings
    assert rule.lean == "pass"


def test_a_rule_sent_to_review_with_no_lean_leans_to_a_mismatch() -> None:
    [rule] = _stub_field_finding("brand_name", "R", "needs_review").rule_findings
    assert rule.lean == "fail"


# --------------------------------------------------------------------------
# A field and a label
# --------------------------------------------------------------------------


def test_a_field_leans_to_a_match_only_if_every_rule_does() -> None:
    env = _leaning(
        {"brand_name": ("needs_review", "pass"), "warning": ("needs_review", "fail")},
        disposition="needs_review",
    )
    assert field_lean(env, "brand_name") == "pass"
    assert field_lean(env, "warning") == "fail"


def test_a_label_leans_to_a_mismatch_if_one_field_does() -> None:
    env = _leaning(
        {"brand_name": ("needs_review", "pass"), "warning": ("needs_review", "fail")},
        disposition="needs_review",
    )
    assert env.lean == "fail"


def test_a_label_whose_fields_all_lean_to_a_match_leans_to_a_match() -> None:
    env = _leaning(
        {"brand_name": ("needs_review", "pass"), "alcohol_content": ("pass", None)},
        disposition="needs_review",
    )
    assert env.lean == "pass"


def test_a_settled_label_is_its_own_answer() -> None:
    env = _leaning({"brand_name": ("fail", None)}, disposition="fail")
    assert env.lean == "fail"


def test_an_unfinished_check_off_the_cards_leans_the_label_to_a_mismatch() -> None:
    """A stopped evaluation has no evidence of a match, so nothing points there."""
    stopped = PerRuleTraceEntry(
        rule_id="ENGINE.SLA.TIMEOUT", disposition="needs_review", evidence_ref="engine_failure/x"
    )
    env = _leaning(
        {"brand_name": ("needs_review", "pass")},
        disposition="needs_review",
        extra_trace=(stopped,),
    )
    assert env.lean == "fail"


def test_a_reviewers_answer_is_the_fields_answer() -> None:
    env = _leaning({"warning": ("needs_review", "fail")}, disposition="needs_review")
    assert field_lean(_corrected(env, ("warning", "pass")), "warning") == "pass"
    # A field sent back to review keeps the check's own lean.
    assert field_lean(_corrected(env, ("warning", "needs_review")), "warning") == "fail"
    assert label_lean(_corrected(env, ("warning", "needs_review"))) == "fail"
    # The latest word counts, so a field sent back to review leans afresh.
    assert (
        field_lean(_corrected(env, ("warning", "pass"), ("warning", "needs_review")), "warning")
        == "fail"
    )


def test_a_field_no_rule_checked_does_not_lean_the_label() -> None:
    env = _leaning({"brand_name": ("needs_review", "pass")}, disposition="needs_review")
    unchecked = env.fields[0].model_copy(
        update={"field_name": "country_of_origin", "rule_findings": ()}
    )
    env = DispositionEnvelope.model_validate(
        {**env.model_dump(exclude={"lean"}), "fields": (*env.fields, unchecked.model_dump())}
    )
    assert field_lean(env, "country_of_origin") is None
    assert env.lean == "pass"


# --------------------------------------------------------------------------
# Confirming
# --------------------------------------------------------------------------


def _confirm(client: TestClient, field_name: str, applied: str):
    return client.post(
        "/labels/EV-C/overrides",
        json={
            "field_name": field_name,
            "applied_disposition": applied,
            "reason_code": f"REVIEWER.CONFIRMATION.{applied.upper()}",
        },
    )


def test_confirming_the_last_guess_settles_the_label() -> None:
    env = _leaning(
        {"brand_name": ("needs_review", "pass"), "alcohol_content": ("pass", None)},
        disposition="needs_review",
    )
    app, in_flight, bus = _seeded(env)
    broadcasts: list[dict] = []
    bus.broadcast = broadcasts.append  # type: ignore[method-assign]

    resp = _confirm(TestClient(app), "brand_name", "pass")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reason_code"] == "REVIEWER.CONFIRMATION.PASS"
    assert body["label_disposition"] == "pass"
    assert body["label_lean"] == "pass"
    assert in_flight.results["lbl-c"].lean == "pass"
    [event] = broadcasts
    assert event["data"]["label_lean"] == "pass"


def test_confirming_one_mismatch_fails_the_label_while_others_wait() -> None:
    """The label is rejected at once; the other guesses stay open to confirm,
    because the applicant is sent every correction together."""
    env = _leaning(
        {"brand_name": ("needs_review", "fail"), "warning": ("needs_review", "pass")},
        disposition="needs_review",
    )
    app, in_flight, _bus = _seeded(env)

    resp = _confirm(TestClient(app), "brand_name", "fail")

    assert resp.status_code == 200, resp.text
    assert resp.json()["label_disposition"] == "fail"
    stored = in_flight.results["lbl-c"]
    assert field_lean(stored, "warning") == "pass"
