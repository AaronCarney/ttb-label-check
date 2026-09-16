"""origin_match asks whether an imported product's label states the country
the application declared.

The application answers domestic or imported before it names a place, and that
answer decides whether there is a check at all. For an import, the declared
country has to appear inside the label's origin statement as whole words,
because the label wraps it in wording of its own: "PRODUCT OF LITHUANIA",
"DISTILLED IN IRELAND".

Where it does not appear, the check reports that it could not be settled, not
that the label is wrong. It cannot tell the two cases apart: customs marking
rules accept the country's name in the language of the country, an
abbreviation that unmistakably indicates it, and the adjectival form (19 CFR
134.45(b) and (c)), none of which are built here. The cost is stated plainly
in the tests below — a label that genuinely names the wrong country reaches a
reviewer rather than being rejected outright. A label carrying no origin
statement at all is a different matter, and that branch does reject.
"""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.origin_match import origin_match
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _rule():
    return make_rule(
        rule_id="wine.origin.matches_application",
        cfr_citation="27 CFR §4.35(e), 19 CFR §134.45",
        validator="origin_match",
        reason_code="ORIGIN.PRESENCE.MISSING",
        severity=Severity.REJECT,
        match_policy=MatchPolicy.NORMALIZED,
        parameters={
            "source_field": "source_of_product",
            "imported_value": "imported",
            "needs_review_reason_code": "ORIGIN.MATCH.NEEDS_REVIEW",
            "disagreement_reason_code": "ORIGIN.MATCH.APPLICATION_LABEL_DISAGREE",
        },
    )


def _verdict(origin_statement: str | None, country: str | None, source: str = "imported"):
    obs = make_obs(field_id="country_origin", value={"country": origin_statement or ""})
    exp = make_expected(
        field_id="country_of_origin",
        value=country,
        parameters={"source_of_product": source},
    )
    return origin_match(obs, exp, _rule(), make_context())


# ---------------------------------------------------------------------------
# The check that does settle
# ---------------------------------------------------------------------------

def test_the_label_states_the_declared_country() -> None:
    assert _verdict("PRODUCT OF LITHUANIA", "LITHUANIA").outcome is Outcome.PASS


def test_the_country_may_sit_inside_wording_the_label_chooses() -> None:
    assert _verdict("DISTILLED IN IRELAND", "IRELAND").outcome is Outcome.PASS


def test_a_domestic_application_has_no_country_check() -> None:
    """A domestic application states positively that no country-of-origin
    statement is required, whatever the label happens to say."""
    res = _verdict("PRODUCT OF THE U.S.A.", "CALIFORNIA", source="domestic")
    assert res.outcome is Outcome.NOT_APPLICABLE
    assert res.reason_code is None


def test_an_import_with_no_origin_statement_is_rejected() -> None:
    """Nothing was stated, so there is nothing to interpret."""
    res = _verdict("", "LITHUANIA")
    assert res.outcome is Outcome.FAIL
    assert res.severity is Severity.REJECT
    assert res.reason_code == "ORIGIN.PRESENCE.MISSING"


# ---------------------------------------------------------------------------
# The check that does not settle, and why it does not reject
# ---------------------------------------------------------------------------

def test_a_statement_in_another_language_goes_to_a_reviewer() -> None:
    """The application declares SPAIN and the label says PRODUCTO DE ESPAÑA.
    19 CFR 134.45(b) allows the country's name in the language of the country;
    this product does not read Spanish, so it asks a person rather than
    rejecting a compliant import."""
    res = _verdict("PRODUCTO DE ESPAÑA", "SPAIN")
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == "ORIGIN.MATCH.APPLICATION_LABEL_DISAGREE"


def test_an_adjectival_form_goes_to_a_reviewer() -> None:
    """"Irish Whiskey" against a declared IRELAND. 19 CFR 134.45(c) allows the
    adjectival form; the check does not read it."""
    res = _verdict("PRODUCT OF IRISH ORIGIN", "IRELAND")
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "ORIGIN.MATCH.APPLICATION_LABEL_DISAGREE"


def test_a_genuinely_different_country_also_goes_to_a_reviewer() -> None:
    """The stated cost of the branch above, kept in front of a reader rather
    than left implicit. The check cannot distinguish a label naming the wrong
    country from one naming the right country in a form it does not read, so
    both reach a person. A wrong verdict on a real label is the failure this
    product cannot have; an extra review is not."""
    res = _verdict("PRODUCT OF FRANCE", "ITALY")
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == "ORIGIN.MATCH.APPLICATION_LABEL_DISAGREE"


def test_an_import_naming_no_country_goes_to_a_reviewer() -> None:
    """The gap is in the application, not the label."""
    res = _verdict("PRODUCT OF LITHUANIA", None)
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "ORIGIN.MATCH.NEEDS_REVIEW"


def test_validator_registered() -> None:
    assert "origin_match" in VALIDATOR_REGISTRY
