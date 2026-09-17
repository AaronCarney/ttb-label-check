"""equality_match.py registers one name: 'enumerated_match', a lookup against
an allow-list provided in `rule.parameters['allowed_values']`.

The module's other name, 'equality_match', went when the only rule using it was
deleted (docs/decisions.md#0013); its cases went with it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.equality_match import (
    _contains_designation,
    enumerated_match,
)
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


def _rule(validator: str, params: dict | None = None, policy: MatchPolicy = MatchPolicy.EXACT):
    return make_rule(
        rule_id=f"x.{validator}",
        cfr_citation="27 CFR §0.0",
        validator=validator,
        reason_code="BRAND.PRESENCE.MISSING",
        match_policy=policy,
        parameters=params or {},
    )


def test_enumerated_match_pass_when_in_allow_list() -> None:
    obs = make_obs(field_id="class_type", value="Bourbon Whisky")
    exp = make_expected(field_id="class_type", value=None)
    rule = _rule(
        "enumerated_match",
        params={"allowed_values": ["Bourbon Whisky", "Rye Whisky"]},
        policy=MatchPolicy.LOOKUP,
    )
    result = enumerated_match(obs, exp, rule, make_context())
    assert result.outcome is Outcome.PASS


def test_enumerated_match_fail_when_not_in_allow_list() -> None:
    obs = make_obs(field_id="class_type", value="Mystery Hooch")
    exp = make_expected(field_id="class_type", value=None)
    rule = _rule(
        "enumerated_match",
        params={"allowed_values": ["Bourbon Whisky", "Rye Whisky"]},
        policy=MatchPolicy.LOOKUP,
    )
    result = enumerated_match(obs, exp, rule, make_context())
    assert result.outcome is Outcome.FAIL


def test_enumerated_match_registered() -> None:
    assert "enumerated_match" in VALIDATOR_REGISTRY
    assert "equality_match" not in VALIDATOR_REGISTRY


# --------------------------------------------------------------------------
# `match_mode: contains_designation`
#
# The mode had no test at all until 2026-09-17: `mutmut` reported 15 mutants
# of `_contains_designation` as "no tests" rather than as survivors, meaning
# nothing executed the function. One shipped rule uses it,
# `spirits.class_type.matches_soi` in `rules/spirits-deep.yaml`.
# --------------------------------------------------------------------------


def _designation_rule(allowed: list[str]):
    return _rule(
        "enumerated_match",
        params={"allowed_values": allowed, "match_mode": "contains_designation"},
        policy=MatchPolicy.LOOKUP,
    )


@pytest.mark.parametrize(
    ("designation", "why"),
    [
        ("STRAIGHT BOURBON WHISKEY, 40% ALC/VOL", "a comma against the class word"),
        ("BLENDED WHISKEY.", "a designation ending in a full stop"),
        ("WHISKEY-STRAIGHT", "a hyphen where a label sets the qualifier after"),
        ("KENTUCKY STRAIGHT BOURBON WHISKEY", "the plain case, qualifiers in front"),
        ("WHISKEY", "the bare standard of identity on its own"),
    ],
)
def test_punctuation_against_the_class_word_does_not_hide_it(designation: str, why: str) -> None:
    """Splitting on whitespace alone handed back "whiskey," and "whiskey.",
    neither of which equals "whiskey", so a label plainly carrying a listed
    class was reported as not carrying it."""
    obs = make_obs(field_id="class_type", value=designation)
    result = enumerated_match(
        obs,
        make_expected(field_id="class_type", value=None),
        _designation_rule(["Whiskey"]),
        make_context(),
    )
    assert result.outcome is Outcome.PASS, f"{why}: {designation!r} should carry 'Whiskey'"


@pytest.mark.parametrize(
    ("designation", "allowed"),
    [
        ("VIRGINIA APPLE BRANDY", "Gin"),
        ("OLD VIRGINIA", "Gin"),
        ("SPIRITS NEUTRAL", "Neutral Spirits"),
        ("MYSTERY HOOCH", "Whiskey"),
    ],
)
def test_a_designation_is_matched_by_whole_words_only(designation: str, allowed: str) -> None:
    """The guarantee the docstring exists for, and the one the punctuation fix
    had to keep: "gin" must not match inside "Virginia", and a multi-word
    standard of identity must appear in its own order."""
    obs = make_obs(field_id="class_type", value=designation)
    result = enumerated_match(
        obs,
        make_expected(field_id="class_type", value=None),
        _designation_rule([allowed]),
        make_context(),
    )
    assert result.outcome is Outcome.FAIL


def test_an_accented_allow_value_stays_one_word() -> None:
    """`Cachaça` is in the shipped allow-list. Treating a non-ASCII letter as a
    word break would split it into "cacha" and "a" and stop it matching
    itself, which is why the word break is `str.isalnum` and not a character
    class."""
    assert _contains_designation("CACHAÇA 40% ALC/VOL", "Cachaça") is True


def test_an_empty_reading_or_an_empty_allow_value_matches_nothing() -> None:
    assert _contains_designation("", "Gin") is False
    assert _contains_designation("GIN", "") is False


def test_the_shipped_spirits_allow_list_matches_a_real_designation() -> None:
    """Read from the pack rather than restated here, so a pack edit that breaks
    the mode fails this test rather than passing a copy of itself."""
    pack = yaml.safe_load(Path("rules/spirits-deep.yaml").read_text(encoding="utf-8"))
    rule = next(r for r in pack["rules"] if r["rule_id"] == "spirits.class_type.matches_soi")
    allowed = rule["parameters"]["allowed_values"]
    assert rule["parameters"]["match_mode"] == "contains_designation"

    obs = make_obs(field_id="class_type", value="FINE BARBADOS RUM / SINGLE BLENDED RUM")
    result = enumerated_match(
        obs,
        make_expected(field_id="class_type", value=None),
        _designation_rule(allowed),
        make_context(),
    )
    assert result.outcome is Outcome.PASS


def test_exact_is_the_default_mode_and_needs_the_whole_reading() -> None:
    """The other branch of the mode switch. No shipped pack selects `exact`,
    so nothing else covers it."""
    exp = make_expected(field_id="class_type", value=None)
    params = {"allowed_values": ["Whiskey"]}
    whole = enumerated_match(
        make_obs(field_id="class_type", value="whiskey"),
        exp,
        _rule("enumerated_match", params=params, policy=MatchPolicy.LOOKUP),
        make_context(),
    )
    partial = enumerated_match(
        make_obs(field_id="class_type", value="BOURBON WHISKEY"),
        exp,
        _rule("enumerated_match", params=params, policy=MatchPolicy.LOOKUP),
        make_context(),
    )
    assert whole.outcome is Outcome.PASS, "exact ignores case, so a fold still matches"
    assert partial.outcome is Outcome.FAIL, "exact must not accept a reading that merely contains"
