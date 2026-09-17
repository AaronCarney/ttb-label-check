"""presence_check on an element the reader did and did not find.

An element the reader did not find on the label is not the same finding as an
element the label does not carry, and the two used to be one: both arrived as an
empty reading and both were rejected. A rule now has to say, with
`unlocated_is_absent`, that its element is one the reader is reliable enough at
finding for its silence to be evidence. Only `common.warning.present` says so.

The
'conditional_presence' alias enforces presence only when the precondition in
rule.parameters['precondition'] is satisfied (a Python expression evaluated
against expected.parameters and observed_value)."""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.presence_check import presence_check, conditional_presence  # noqa: F401
from app.schemas.rejection import Outcome, Severity
from app.services.disposition import rule_disposition
from tests.rules.fixtures import (
    make_context,
    make_evidence,
    make_expected,
    make_obs,
    make_rule,
)


def _rule(validator: str, **kw):
    return make_rule(
        rule_id=f"x.{validator}",
        cfr_citation="27 CFR §0.0",
        validator=validator,
        reason_code="BRAND.PRESENCE.MISSING",
        **kw,
    )


def test_presence_check_pass_with_value() -> None:
    obs = make_obs(field_id="brand", value="Foo")
    exp = make_expected(field_id="brand")
    res = presence_check(obs, exp, _rule("presence_check"), make_context())
    assert res.outcome is Outcome.PASS


def test_an_element_the_reader_did_not_find_goes_to_a_reviewer() -> None:
    # No reading, no box, no extracted text: the reader did not find a brand mark.
    # Reporting that as BRAND.PRESENCE.MISSING would state, to a reviewer, that
    # the label carries no brand - which nobody checked.
    obs = make_obs(field_id="brand", value=None)
    exp = make_expected(field_id="brand")
    res = presence_check(obs, exp, _rule("presence_check"), make_context())
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"
    assert rule_disposition(res) == "needs_review"


def test_whitespace_is_not_a_reading_either() -> None:
    obs = make_obs(field_id="brand", value="   ")
    exp = make_expected(field_id="brand")
    res = presence_check(obs, exp, _rule("presence_check"), make_context())
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"


def test_a_rule_may_declare_that_not_finding_it_means_it_is_absent() -> None:
    # What `common.warning.present` sets, and the only way a rejection is reached
    # from an empty reading. The reader finds the government warning on 30 of the
    # 30 corpus labels, so its silence about that one element is evidence.
    obs = make_obs(field_id="brand", value=None)
    exp = make_expected(field_id="brand")
    rule = _rule("presence_check", parameters={"unlocated_is_absent": True})
    res = presence_check(obs, exp, rule, make_context())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "BRAND.PRESENCE.MISSING"
    assert rule_disposition(res) == "fail"


def test_an_element_the_reader_located_but_read_nothing_in_still_fails() -> None:
    # The reader found a region for this field and read no text there. It looked,
    # so the empty reading is a finding about the label rather than about the read.
    obs = make_obs(
        field_id="brand",
        value="",
        extra_evidence=(make_evidence(field_id="brand", text="", bbox=(1, 2, 3, 4)),),
    )
    exp = make_expected(field_id="brand")
    res = presence_check(obs, exp, _rule("presence_check"), make_context())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "BRAND.PRESENCE.MISSING"


def test_conditional_presence_sends_an_unfound_element_to_a_reviewer() -> None:
    obs = make_obs(field_id="alc_text", value=None)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": True})
    rule = _rule(
        "conditional_presence",
        parameters={"required_when": "abv_required"},
    )
    res = conditional_presence(obs, exp, rule, make_context())
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"


def test_conditional_presence_not_applicable_beats_not_read() -> None:
    # A rule that does not apply to this label does not apply whether or not the
    # reader found anything, so NOT_APPLICABLE is settled before the guard runs.
    obs = make_obs(field_id="alc_text", value=None)
    exp = make_expected(field_id="alc_text", parameters={"abv_required": False})
    rule = _rule(
        "conditional_presence",
        parameters={"required_when": "abv_required"},
    )
    res = conditional_presence(obs, exp, rule, make_context())
    assert res.outcome is Outcome.NOT_APPLICABLE


def test_validators_registered() -> None:
    assert "presence_check" in VALIDATOR_REGISTRY
    assert "conditional_presence" in VALIDATOR_REGISTRY
