"""The shared validator helpers, tested directly.

`_helpers.py` had no test file of its own. Every sibling validator imports it,
so a defect here reaches thirteen modules at once and shows up in each of them
as a wrong finding about a different element - which is the hardest shape of
bug to trace back to its cause. The sibling suites exercise these functions
only incidentally, through whichever paths their own validator happens to take.

These tests pin the behaviour each caller relies on, and they are written
against the cases that distinguish this implementation from a plausible wrong
one: the join that makes a name and address one line, the word boundary that
keeps "gin" out of "Virginia", the boolean that is not a number, and the
element names a reviewer reads.
"""

from __future__ import annotations

from app.rules._validators._helpers import (
    NOT_READ_CODE,
    _build_meta,
    _conf,
    element_name,
    first_number,
    normalize_words,
    not_read_result,
    project_reading,
    unlocated,
    unlocated_is_absent,
    verdict_result,
    word_run_present,
)
from app.schemas.rejection import Outcome, Severity
from tests.rules.fixtures import (
    make_context,
    make_evidence,
    make_expected,
    make_obs,
    make_rule,
)


def _rule(**kw):
    return make_rule(
        rule_id="x.helpers",
        cfr_citation="27 CFR §0.0",
        validator="presence_check",
        reason_code="BRAND.PRESENCE.MISSING",
        **kw,
    )


# --- _build_meta -------------------------------------------------------------


def test_build_meta_carries_every_field_from_the_rule_and_the_context() -> None:
    rule = _rule(rule_pack="spirits", rule_pack_version="2.4.0")
    ctx = make_context(engine_version="9.9.9", started_at_ms=1234)
    meta = _build_meta(rule, ctx)
    assert meta.engine_version == "9.9.9"
    assert meta.rule_pack == "spirits"
    assert meta.rule_pack_version == "2.4.0"
    assert meta.started_at_ms == 1234


def test_build_meta_elapsed_defaults_to_zero_because_the_engine_overrides_it() -> None:
    # yaml_engine._run_one replaces this on every return path with the real
    # monotonic delta. A non-zero default here would be a made-up timing.
    assert _build_meta(_rule(), make_context()).elapsed_ms == 0
    assert _build_meta(_rule(), make_context(), 42).elapsed_ms == 42


def test_build_meta_names_an_unidentified_pack_rather_than_leaving_it_empty() -> None:
    meta = _build_meta(_rule(rule_pack="", rule_pack_version=""), make_context())
    assert meta.rule_pack == "unknown"
    assert meta.rule_pack_version == "0.0.0"


# --- _conf -------------------------------------------------------------------


def test_conf_is_zero_when_there_is_no_evidence() -> None:
    obs = make_obs(field_id="brand", value="Foo")
    obs = obs.model_copy(update={"evidence": ()})
    assert _conf(obs) == 0.0


def test_conf_is_the_lowest_confidence_not_the_average() -> None:
    # The aggregate has to be the weakest link: a label read with one confident
    # field and one doubtful one is only as trustworthy as the doubtful one.
    obs = make_obs(
        field_id="brand",
        value="Foo",
        confidence=0.9,
        extra_evidence=(make_evidence(field_id="brand", text="Foo", confidence=0.4),),
    )
    assert _conf(obs) == 0.4


# --- project_reading ---------------------------------------------------------


def test_project_reading_passes_a_plain_string_through() -> None:
    assert project_reading(make_obs(field_id="brand", value="Stone's Throw")) == "Stone's Throw"


def test_project_reading_of_a_missing_value_is_empty() -> None:
    assert project_reading(make_obs(field_id="brand", value=None)) == ""


def test_project_reading_stringifies_a_value_that_is_neither_string_nor_dict() -> None:
    assert project_reading(make_obs(field_id="abv", value=40)) == "40"


def test_project_reading_takes_the_named_key_out_of_a_reader_payload() -> None:
    # The reader returns a dict per field. A validator that stringified the
    # whole payload would compare "{'brand_name': 'Lost Lantern'}" and report a
    # compliant label as non-compliant.
    obs = make_obs(
        field_id="brand_name",
        value={"brand_name": "Lost Lantern", "confidence": 0.91},
    )
    assert project_reading(obs) == "Lost Lantern"


def test_project_reading_joins_a_name_and_address_into_one_line() -> None:
    obs = make_obs(
        field_id="name_address",
        value={"name": "Lost Lantern", "city": "Vergennes", "state": "VT"},
    )
    assert project_reading(obs) == "Lost Lantern, Vergennes, VT"


def test_project_reading_skips_the_parts_the_reader_left_empty() -> None:
    obs = make_obs(
        field_id="name_address",
        value={"name": "Lost Lantern", "city": "", "state": None},
    )
    assert project_reading(obs) == "Lost Lantern"


def test_project_reading_falls_back_to_a_payloads_own_keys_for_an_unmapped_field() -> None:
    obs = make_obs(field_id="not_a_mapped_field", value={"reading": "Forty", "confidence": 0.8})
    assert project_reading(obs) == "Forty"


def test_a_mapped_field_takes_only_its_named_key_not_every_key_in_the_payload() -> None:
    # The warning payload carries the heading alongside the warning text, and
    # `_READING_KEYS` names only "text". Scanning the payload's own keys instead
    # would put the heading into the reading twice over - once in the heading
    # and once in the text - and the equality comparison would fail on a label
    # that is correct.
    obs = make_obs(
        field_id="gov_warning",
        value={
            "text": "GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL...",
            "heading": "GOVERNMENT WARNING",
        },
    )
    assert project_reading(obs) == "GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL..."


def test_a_payload_holding_only_metadata_projects_to_nothing() -> None:
    # Otherwise the confidence score itself would read as the label's text, and
    # a field the reader never read would pass a presence check.
    obs = make_obs(field_id="not_a_mapped_field", value={"confidence": 0.8, "unit": "pct"})
    assert project_reading(obs) == ""


# --- normalize_words ---------------------------------------------------------


def test_normalize_words_reduces_case_punctuation_and_spacing() -> None:
    assert normalize_words("STONE'S THROW") == ("stone", "s", "throw")
    assert normalize_words("Stone's  Throw") == ("stone", "s", "throw")


def test_normalize_words_folds_accents_away() -> None:
    assert normalize_words("Café Crème") == ("cafe", "creme")


def test_normalize_words_spells_out_the_ampersand() -> None:
    # "Smith & Sons" and "Smith and Sons" are the same producer. Dropping the
    # ampersand instead of spelling it out would make them different values.
    assert normalize_words("Smith & Sons") == ("smith", "and", "sons")


def test_normalize_words_folds_the_permitted_whisky_spellings_together() -> None:
    # The regulations permit either spelling and the registry and the label
    # routinely differ on it.
    assert normalize_words("Whisky") == ("whiskey",)
    assert normalize_words("WHISKIES") == ("whiskey",)
    assert normalize_words("Whiskey") == ("whiskey",)


def test_normalize_words_drops_empty_runs_rather_than_emitting_blanks() -> None:
    assert normalize_words("  --- ") == ()
    assert normalize_words("") == ()


def test_normalize_words_keeps_digits() -> None:
    assert normalize_words("Old No. 7") == ("old", "no", "7")


# --- word_run_present --------------------------------------------------------


def test_word_run_present_finds_a_run_at_each_position() -> None:
    hay = ("straight", "bourbon", "whiskey")
    assert word_run_present(hay, ("straight",)) is True
    assert word_run_present(hay, ("bourbon", "whiskey")) is True
    assert word_run_present(hay, ("whiskey",)) is True
    assert word_run_present(hay, hay) is True


def test_word_run_present_matches_whole_words_not_letters() -> None:
    # "gin" inside "Virginia" is the case this function exists for.
    assert word_run_present(normalize_words("Virginia Highlands"), ("gin",)) is False


def test_word_run_present_requires_the_words_to_be_consecutive() -> None:
    assert word_run_present(("straight", "bourbon", "whiskey"), ("straight", "whiskey")) is False


def test_word_run_present_is_false_for_an_empty_needle() -> None:
    # An empty needle is not "present in everything": the caller has nothing to
    # look for, and answering True would pass a rule nobody checked.
    assert word_run_present(("bourbon",), ()) is False
    assert word_run_present((), ()) is False


def test_word_run_present_is_false_when_the_needle_is_longer_than_the_haystack() -> None:
    assert word_run_present(("bourbon",), ("bourbon", "whiskey")) is False


# --- first_number ------------------------------------------------------------


def test_first_number_reads_a_number_that_arrived_as_a_number() -> None:
    assert first_number(40) == 40.0
    assert first_number(40.5) == 40.5


def test_first_number_reads_the_first_number_out_of_text() -> None:
    assert first_number("40.5% ALC/VOL") == 40.5
    assert first_number("ALC 40 PCT BY VOL") == 40.0


def test_a_boolean_is_not_a_number() -> None:
    # bool is a subclass of int, so an unguarded isinstance check turns True
    # into an alcohol content of 1.0%.
    assert first_number(True) is None
    assert first_number(False) is None


def test_first_number_of_nothing_is_none() -> None:
    assert first_number(None) is None
    assert first_number("no digits here") is None


# --- unlocated ---------------------------------------------------------------


def test_a_reading_the_reader_produced_is_located_even_when_it_is_wrong() -> None:
    assert unlocated(make_obs(field_id="brand", value="[OSTL")) is False


def test_an_empty_reading_with_no_box_and_no_text_is_unlocated() -> None:
    assert unlocated(make_obs(field_id="brand", value=None)) is True
    assert unlocated(make_obs(field_id="brand", value="   ")) is True


def test_an_empty_reading_is_located_when_evidence_carries_a_box() -> None:
    # The reader found the element and failed to read it. That is a different
    # finding from not finding it at all.
    obs = make_obs(field_id="brand", value=None)
    obs = obs.model_copy(update={"evidence": (make_evidence(field_id="brand", bbox=(1, 2, 3, 4)),)})
    assert unlocated(obs) is False


def test_unlocated_accepts_a_reading_the_caller_projected_itself() -> None:
    # heading_style_check, regex_match and same_field_of_vision_check read their
    # own payloads. Asking the generic projection about those would call a field
    # the reader found "not found".
    obs = make_obs(field_id="gov_warning", value={"text": "", "heading": "GOVERNMENT WARNING"})
    assert unlocated(obs, reading="GOVERNMENT WARNING") is False


# --- unlocated_is_absent -----------------------------------------------------


def test_a_rule_that_has_not_thought_about_it_does_not_read_silence_as_absence() -> None:
    assert unlocated_is_absent(_rule()) is False
    assert unlocated_is_absent(_rule(parameters={"something_else": True})) is False


def test_a_rule_may_opt_in_to_reading_silence_as_absence() -> None:
    assert unlocated_is_absent(_rule(parameters={"unlocated_is_absent": True})) is True


def test_unlocated_is_absent_is_off_when_the_pack_says_false() -> None:
    assert unlocated_is_absent(_rule(parameters={"unlocated_is_absent": False})) is False


# --- element_name ------------------------------------------------------------


def test_element_name_gives_a_reviewer_the_words_for_each_element() -> None:
    # A reviewer reads a list of findings and has to know which line of the
    # label each one is about. "This element" tells them nothing.
    expected = {
        "brand_name": "a brand name",
        "class_type": "a class or type designation",
        "abv": "an alcohol content statement",
        "net_contents": "a net contents statement",
        "gov_warning": "the government warning",
        "name_address": "a name and address",
        "country_origin": "a country of origin statement",
    }
    for field_id, words in expected.items():
        assert element_name(make_obs(field_id=field_id, value="x")) == words


def test_element_name_falls_back_only_for_a_field_it_does_not_know() -> None:
    assert element_name(make_obs(field_id="not_a_known_field", value="x")) == "this element"


# --- not_read_result ---------------------------------------------------------


def test_not_read_result_goes_to_a_reviewer_and_cannot_reject_on_its_own() -> None:
    from app.services.disposition import rule_disposition

    obs = make_obs(field_id="brand_name", value=None)
    exp = make_expected(field_id="brand_name")
    rule = _rule(severity=Severity.REJECT, rule_pack="spirits", rule_pack_version="2.4.0")
    res = not_read_result(obs, exp, rule, make_context(engine_version="9.9.9"))

    # WARN whatever severity the rule carries, so disposition routes it to a
    # human rather than letting it reject the submission.
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == NOT_READ_CODE
    assert rule_disposition(res) == "needs_review"

    assert res.rule_id == rule.rule_id
    assert res.cfr_citation == rule.cfr_citation
    assert res.beverage_class is obs.beverage_class
    assert res.expected is exp
    assert res.observed is obs
    assert res.evidence == obs.evidence
    assert res.engine_meta.engine_version == "9.9.9"
    assert res.engine_meta.rule_pack == "spirits"


def test_not_read_result_names_the_element_from_the_observation() -> None:
    obs = make_obs(field_id="gov_warning", value=None)
    res = not_read_result(obs, make_expected(field_id="gov_warning"), _rule(), make_context())
    assert "the government warning" in res.message


def test_a_validator_serving_one_element_may_name_it_in_its_own_words() -> None:
    obs = make_obs(field_id="brand_name", value=None)
    res = not_read_result(
        obs,
        make_expected(field_id="brand_name"),
        _rule(),
        make_context(),
        element="the brand mark",
    )
    assert "the brand mark" in res.message


def test_the_message_says_this_is_not_a_finding_that_the_label_lacks_the_element() -> None:
    # The whole point of this result: a reviewer must not read it as a claim
    # about the label, and must be told to look at the label themselves.
    obs = make_obs(field_id="brand_name", value=None)
    res = not_read_result(obs, make_expected(field_id="brand_name"), _rule(), make_context())
    assert "did not find" in res.message
    assert "That is not a finding that the label lacks it" in res.message
    assert "compare the label against the application yourself" in res.message


def test_not_read_result_carries_the_aggregated_confidence() -> None:
    obs = make_obs(field_id="brand_name", value=None, confidence=0.33)
    res = not_read_result(obs, make_expected(field_id="brand_name"), _rule(), make_context())
    assert res.aggregated_confidence == 0.33


# --- verdict_result ----------------------------------------------------------


def test_a_failing_verdict_carries_the_rule_s_own_reason_code() -> None:
    # Five validators built this envelope inline and identically, and two of the
    # copies drifted out of coverage: nothing pinned that a failing check says
    # why it failed. A rejection with no reason code tells a reviewer that the
    # label is wrong and nothing about what is wrong with it.
    obs = make_obs(field_id="brand_name", value="")
    exp = make_expected(field_id="brand_name")
    rule = _rule(severity=Severity.REJECT, rule_pack="spirits", rule_pack_version="2.4.0")
    res = verdict_result(obs, exp, rule, make_context(engine_version="9.9.9"), ok=False)

    assert res.outcome is Outcome.FAIL
    assert res.severity is Severity.REJECT
    assert res.reason_code == "BRAND.PRESENCE.MISSING"


def test_a_passing_verdict_carries_no_reason_code() -> None:
    # There is nothing to report about a label that satisfies the rule, and a
    # reason code on a PASS would be read as a finding against it.
    obs = make_obs(field_id="brand_name", value="Old Overholt")
    res = verdict_result(
        obs, make_expected(field_id="brand_name"), _rule(), make_context(), ok=True
    )
    assert res.outcome is Outcome.PASS
    assert res.reason_code is None


def test_a_verdict_carries_what_it_compared_so_a_reviewer_can_check_it() -> None:
    # `evidence`, `expected` and `observed` are how a reviewer sees the verdict
    # against the label instead of taking it on trust. Dropping any of the three
    # left every validator's tests green.
    obs = make_obs(
        field_id="brand_name",
        value="Old Overholt",
        extra_evidence=(make_evidence(field_id="brand_name", text="second crop"),),
    )
    exp = make_expected(field_id="brand_name")
    rule = _rule(severity=Severity.REJECT, rule_pack="spirits", rule_pack_version="2.4.0")
    res = verdict_result(obs, exp, rule, make_context(engine_version="9.9.9"), ok=False)

    assert res.evidence == obs.evidence
    assert res.expected is exp
    assert res.observed is obs

    assert res.rule_id == rule.rule_id
    assert res.cfr_citation == rule.cfr_citation
    assert res.beverage_class is obs.beverage_class
    assert res.engine_meta.engine_version == "9.9.9"
    assert res.engine_meta.rule_pack == "spirits"
    assert res.engine_meta.rule_pack_version == "2.4.0"


def test_a_verdict_carries_the_aggregated_confidence() -> None:
    obs = make_obs(field_id="brand_name", value="Old Overholt", confidence=0.42)
    res = verdict_result(
        obs, make_expected(field_id="brand_name"), _rule(), make_context(), ok=True
    )
    assert res.aggregated_confidence == 0.42


def test_the_severity_is_the_rule_s_own_on_a_failure() -> None:
    # Unlike `not_read_result`, which forces WARN so it cannot reject on its
    # own, a verdict that actually ran reports at the severity the rule sets.
    obs = make_obs(field_id="brand_name", value="")
    exp = make_expected(field_id="brand_name")
    for severity in (Severity.REJECT, Severity.WARN, Severity.INFO):
        res = verdict_result(obs, exp, _rule(severity=severity), make_context(), ok=False)
        assert res.severity is severity
