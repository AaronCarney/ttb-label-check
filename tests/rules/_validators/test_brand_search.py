"""fuzzy_brand searches the label's text for the brand the application declares.

The application states the brand, so the check asks whether the label shows it,
not what the brand is. The reader still picks the text set in the largest type,
but it also hands over every line of text it read on every face, and the rule
looks there for the declared name. The picked text is only what a reviewer sees
when the name is nowhere to be found, and then the check goes to a reviewer: a
guess at which text is the brand is not evidence the label names a different
one, so this check never reports a mismatch.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.rules._validators.fuzzy_brand import fuzzy_brand
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import DecisionTable, MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

TRAILING_WORDS = DecisionTable(
    entries=(
        {"words": ["distillery", "distilling", "spirits", "company", "co"]},
        {"words": ["bourbon", "whiskey"]},
    )
)


def _rule():
    return make_rule(
        rule_id="brand.match",
        cfr_citation="27 CFR §5.64",
        validator="fuzzy_brand",
        reason_code="BRAND.IDENTIFY.UNCERTAIN",
        severity=Severity.WARN,
        match_policy=MatchPolicy.FUZZY,
        decision_table_ref="brand_trailing_words",
        parameters={
            "pass_threshold": 0.92,
            "needs_review_threshold": 0.85,
            "needs_review_reason_code": "BRAND.NAME.NEEDS_REVIEW",
            "search_min_length": 3,
            "search_within_min_length": 5,
            "search_misread_min_length": 8,
        },
    )


def _candidate(text, face="front", bbox=(10, 20, 110, 60), confidence=0.9):
    return {"text": text, "bbox": list(bbox), "confidence": confidence, "face": face}


def _verdict(picked, candidates, declared, **parameters):
    obs = make_obs(
        field_id="brand_name",
        value={"brand_name": picked, "confidence": 0.7, "candidates": candidates},
    )
    exp = make_expected(field_id="brand", value=declared, parameters=parameters or None)
    ctx = make_context(decision_tables={"brand_trailing_words": TRAILING_WORDS})
    return fuzzy_brand(obs, exp, _rule(), ctx)


# ---------------------------------------------------------------------------
# Found
# ---------------------------------------------------------------------------


def test_the_brand_is_found_where_the_largest_type_is_something_else() -> None:
    """The label's statutory line is set larger than its stylised mark."""
    res = _verdict(
        "DISTILLED IN IRELAND IRISH",
        [
            _candidate("DISTILLED IN IRELAND IRISH", bbox=(0, 0, 400, 80)),
            _candidate("AODH", face="back", bbox=(40, 300, 160, 340)),
        ],
        "AODH",
    )
    assert res.outcome is Outcome.PASS
    found = res.evidence[0]
    assert found.extracted_text == "AODH"
    assert found.bbox == (40, 300, 160, 340)
    assert found.panel == "back"
    assert res.message and '"AODH"' in res.message and "back" in res.message


def test_a_brand_inside_the_bottlers_line_is_found() -> None:
    res = _verdict(
        "BOURBON",
        [_candidate("BOURBON"), _candidate("BOTTLED BY LONERIDER SPIRITS DURHAM, NC")],
        "LONERIDER SPIRITS",
    )
    assert res.outcome is Outcome.PASS
    assert res.evidence[0].extracted_text == "BOTTLED BY LONERIDER SPIRITS DURHAM, NC"


def test_a_brand_with_different_punctuation_is_found() -> None:
    res = _verdict("USA", [_candidate("USA"), _candidate("DODGYFOX")], "DODGY FOX")
    assert res.outcome is Outcome.PASS
    assert res.message and "punctuation or spacing" in res.message


def test_a_brand_without_its_trailing_business_word_is_found() -> None:
    """The application's brand field often carries the company's full trade
    name; the label prints the name the product is sold under."""
    res = _verdict("AGED 7 YEARS", [_candidate("Vikre")], "VIKRE DISTILLERY")
    assert res.outcome is Outcome.PASS
    assert res.message and '"DISTILLERY"' in res.message, res.message


def test_a_brand_with_one_misread_character_is_found() -> None:
    res = _verdict("Store chilled", [_candidate("Sweete Lizzy™")], "SWEET LIZZY")
    assert res.outcome is Outcome.PASS
    assert res.message and "one character" in res.message


def test_the_strongest_finding_is_the_one_reported() -> None:
    """An exact line beats a line that merely contains the name, whichever the
    reader listed first."""
    res = _verdict(
        "USA",
        [
            _candidate("BOTTLED BY LONERIDER SPIRITS DURHAM, NC", bbox=(0, 500, 300, 520)),
            _candidate("LONERIDER SPIRITS", bbox=(20, 40, 380, 120)),
        ],
        "LONERIDER SPIRITS",
    )
    assert res.evidence[0].bbox == (20, 40, 380, 120)


def test_a_plain_match_on_the_pick_is_unchanged() -> None:
    res = _verdict("STONE'S THROW", [_candidate("STONE'S THROW")], "Stone's Throw")
    assert res.outcome is Outcome.PASS
    assert res.message is None


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


def test_a_name_that_is_not_on_the_label_goes_to_a_reviewer() -> None:
    """A stylised mark read as noise beside a larger statutory line."""
    res = _verdict(
        "DISTILLED IN IRELAND IRISH",
        [_candidate("DISTILLED IN IRELAND IRISH"), _candidate("A0d#")],
        "AODH",
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == "BRAND.IDENTIFY.UNCERTAIN"
    assert res.message and "DISTILLED IN IRELAND IRISH" in res.message and "AODH" in res.message


def test_a_shortened_name_is_not_found_inside_other_words() -> None:
    """Dropping the trailing word leaves a place name, and a place name sits
    in the address line of many labels. The shortened name has to be the
    whole line to count."""
    res = _verdict("USA", [_candidate("BEND, OREGON")], "OREGON DISTILLERY")
    assert res.outcome is not Outcome.PASS


def test_one_misread_character_is_not_found_on_a_short_name() -> None:
    res = _verdict("USA", [_candidate("SOUTHERN")], "SOUTHERN CROSS")
    assert res.outcome is not Outcome.PASS


def test_a_name_too_short_to_search_for_is_not_searched() -> None:
    """A one-letter brand is a word in every sentence on the label."""
    res = _verdict("BOURBON", [_candidate("A")], '"A"')
    assert res.outcome is not Outcome.PASS


def test_a_short_name_is_not_found_inside_a_sentence() -> None:
    res = _verdict("USA", [_candidate("NOW IS THE TIME")], "NOW")
    assert res.outcome is not Outcome.PASS


def test_the_fanciful_name_is_not_searched_for() -> None:
    """The fanciful name describes the product ("BARREL PROOF") and is printed
    on labels of many brands, so finding it says nothing about the brand."""
    res = _verdict(
        "Old Stuff", [_candidate("BARREL PROOF")], "HARBOR SPIRITS", fanciful_name="BARREL PROOF"
    )
    assert res.outcome is not Outcome.PASS


def test_a_trade_name_used_on_the_label_is_searched_for() -> None:
    res = _verdict(
        "USA",
        [_candidate("BONEFISH")],
        "TACONIC DISTILLERY",
        trade_names_used_on_label=("BONEFISH",),
    )
    assert res.outcome is Outcome.PASS
    assert res.matched_value == "BONEFISH"


def test_a_reading_without_candidates_falls_back_to_the_pick() -> None:
    """The cloud reader lists no candidates; its pick is still compared."""
    obs = make_obs(field_id="brand_name", value={"brand_name": "Acme", "confidence": 0.9})
    exp = make_expected(field_id="brand", value="Bizmark")
    res = fuzzy_brand(obs, exp, _rule(), make_context())
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "BRAND.IDENTIFY.UNCERTAIN"


_text = st.text(alphabet="ABCDEFGHIJ &'.-0123", max_size=20)


@given(picked=_text, candidates=st.lists(_text, max_size=6), declared=_text)
def test_the_brand_check_never_reports_a_mismatch(picked, candidates, declared) -> None:
    res = _verdict(picked, [_candidate(c) for c in candidates], declared)
    assert res.outcome is not Outcome.FAIL
