"""verbatim_hash compares the canonicalized observed text against the sha256
recorded in ctx.assets[<key>]. The asset key comes from rule.parameters['asset_key'].
Used by the rule that pins the health warning's wording word for word.

The hash is taken over the canonical form, not over the regulation's text as
printed, because the loader hashes the asset file through the same op pipeline
(`canonicalize_text`). Hashing the raw string here would compare two different
things and every real label would fail.

What the cases below assert is the shape of the comparison: the words, the
numbers and the punctuation are fixed; letter case, spacing and a line break
that splits a word are not. The manifest's own `check_rules.warning_exact`
states exactly that, and each pass case here is a real label from
tests/fixtures/labels/manifest.json.
"""

from __future__ import annotations

import hashlib

import pytest

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.verbatim_hash import canonicalize_text, verbatim_hash
from app.schemas.rejection import Outcome
from app.schemas.rules import AssetRef, MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

CANONICAL = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects. (2) "
    "Consumption of alcoholic beverages impairs your ability to drive a car or operate "
    "machinery, and may cause health problems."
)
SHA = hashlib.sha256(canonicalize_text(CANONICAL).encode("utf-8")).hexdigest()


def _rule():
    return make_rule(
        rule_id="common.warning.verbatim",
        cfr_citation="27 CFR §16.21",
        validator="verbatim_hash",
        reason_code="WARNING.VERBATIM.MISMATCH",
        match_policy=MatchPolicy.VERBATIM_HASH,
        parameters={"asset_key": "govt_warning_16_21"},
    )


def _ctx():
    return make_context(
        assets={
            "govt_warning_16_21": AssetRef(
                path="assets/warnings/govt_warning_16_21.txt", sha256=SHA
            )
        },
    )


def _outcome(text: str) -> Outcome:
    obs = make_obs(field_id="warning_block", value=text)
    return verbatim_hash(obs, make_expected(field_id="warning_block"), _rule(), _ctx()).outcome


def test_verbatim_hash_pass_when_match() -> None:
    assert _outcome(CANONICAL) is Outcome.PASS


def test_all_capitals_body_passes() -> None:
    """ttb-26231001000662 prints the whole statement in capitals and is approved.

    16.22(a)(2) rules the heading's capitals only; the body's case is regulated
    nowhere, and `common.warning.heading_caps_bold` scores the heading separately.
    """
    assert _outcome(CANONICAL.upper()) is Outcome.PASS


def test_extra_space_before_the_colon_passes() -> None:
    """The same label prints `GOVERNMENT WARNING  :` — spacing, not wording."""
    assert _outcome(CANONICAL.replace("WARNING:", "WARNING  :")) is Outcome.PASS


def test_missing_space_after_the_numeral_passes() -> None:
    """ttb-26237001000107 prints `(1)ACCORDING` with no space at all.

    So "spacing is ignored" cannot mean "collapse runs of spaces": there is no
    run here to collapse. Every space comes out instead.
    """
    assert _outcome(CANONICAL.replace("(1) According", "(1)According")) is Outcome.PASS


def test_two_words_run_together_pass() -> None:
    """ttb-26239001000217 prints `IMPAIRS YOUR`, and the reader returns
    `IMPAIRSYOUR`: the gap between two words is lost, which is spacing, not
    wording. Collapsing whitespace could not reach it — there is no space left
    to collapse — so every space comes out of the comparison."""
    assert _outcome(CANONICAL.replace("impairs your", "impairsyour")) is Outcome.PASS


def test_a_changed_letter_still_fails_with_spaces_removed() -> None:
    """ttb-26229001000034 prints `the RISKS of birth defects`, and TTB's text is
    `the risk`. Removing spaces leaves every letter to match in order, so a label
    that prints a different word is still rejected."""
    assert _outcome(CANONICAL.replace("the risk of", "the risks of")) is Outcome.FAIL


def test_line_break_splitting_a_word_passes() -> None:
    """ttb-26231001000333 breaks `PREG-\\nNANCY` across two printed lines."""
    assert _outcome(CANONICAL.replace("pregnancy", "preg-\nnancy")) is Outcome.PASS


def test_verbatim_hash_fail_when_paraphrase() -> None:
    obs = make_obs(
        field_id="warning_block", value=CANONICAL.replace("birth defects", "birth complications")
    )
    res = verbatim_hash(obs, make_expected(field_id="warning_block"), _rule(), _ctx())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.VERBATIM.MISMATCH"


def test_changed_punctuation_is_never_a_match() -> None:
    """ttb-26240001000454 ends `HEALTH PROBLEMS"` and the manifest marks it false.

    Punctuation is part of the mandated statement, so it is never normalized
    away. One swapped mark is also a kind the reader invents, so it goes to a
    reviewer rather than being reported as the label's.
    """
    got = _outcome(CANONICAL.replace("health problems.", 'health problems"'))
    assert got is Outcome.INSUFFICIENT_EVIDENCE


# Each is a reading the reader made of a TTB-approved label that prints the
# statement correctly, reduced to the one difference it made.
READER_MISREADS = [
    ("ttb-26233001000189", "beverages impairs", "beveráges impairs"),
    ("ttb-26233001000566", "beverages impairs", "beverages ímpairs"),
    ("ttb-26233001000569", "women should", "womèn should"),
    ("ttb-26237001000107", "(1) According", "(I)According"),
    ("ttb-26239001000239", "drive a car", "drive,a car"),
    ("ttb-26239001000079", "General, women", "General women"),
    ("ttb-26240001000563", "not drink", "not orink"),
    ("ttb-26239001000081", "(1) According to", "(1). According _to"),
]


@pytest.mark.parametrize(("label", "printed", "read"), READER_MISREADS)
def test_a_difference_the_reader_invents_goes_to_a_reviewer(
    label: str, printed: str, read: str
) -> None:
    obs = make_obs(field_id="warning_block", value=CANONICAL.replace(printed, read))
    res = verbatim_hash(obs, make_expected(field_id="warning_block"), _rule(), _ctx())
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE, label
    assert res.reason_code == "WARNING.VERBATIM.NOT_CONFIRMED"
    assert res.message is not None and "misread" in res.message


def test_the_finding_names_where_the_reading_differs() -> None:
    res = verbatim_hash(
        make_obs(field_id="warning_block", value=CANONICAL.replace("not drink", "not orink")),
        make_expected(field_id="warning_block"),
        _rule(),
        _ctx(),
    )
    assert res.message is not None and '"o" for "d"' in res.message


# Each is a label that really prints something other than the statement.
TRUE_DIFFERENCES = [
    ("ttb-26229001000034", "the risk of", "the risks of"),
    ("ttb-26212001000085", "beverages impairs", "beverage impairs"),
    ("var-warning-wording", "beverages impairs", "beverages may impair"),
]


@pytest.mark.parametrize(("label", "printed", "read"), TRUE_DIFFERENCES)
def test_an_added_or_dropped_letter_or_word_is_a_mismatch(
    label: str, printed: str, read: str
) -> None:
    assert _outcome(CANONICAL.replace(printed, read)) is Outcome.FAIL, label


def test_one_real_difference_outweighs_any_misread() -> None:
    text = CANONICAL.replace("women should", "womèn should").replace("the risk of", "the risks of")
    assert _outcome(text) is Outcome.FAIL


@pytest.mark.parametrize("words", ["surgeon general", "Surgeon general", "surgeon General"])
def test_a_lower_case_surgeon_general_is_not_a_match(words: str) -> None:
    """TTB's checklists ask whether the S and G of Surgeon General are capitals;
    folding case for the rest of the body must not wave a lower-case one through."""
    assert _outcome(CANONICAL.replace("Surgeon General", words)) is Outcome.INSUFFICIENT_EVIDENCE


def test_an_unknown_op_is_refused_by_name() -> None:
    """The loader reports this message against the rule that named the op, so
    the op's name is what tells a rule author what to fix."""
    with pytest.raises(ValueError, match=r"^unknown normalization op: 'ascii_quotes'$"):
        canonicalize_text(CANONICAL, ops=("nfkc", "ascii_quotes"))


def test_verbatim_hash_registered() -> None:
    assert "verbatim_hash" in VALIDATOR_REGISTRY
