"""format_check, registered as 'regex_match', judges the label's alcohol wording.

Both readers return the alcohol statement as the label prints it, under
`alc_text`, and the validator matches the rule's regex against that. The three
rules that use it are off (docs/decisions.md#0011); these tests pin what the
validator does when they run.

It stays registered because app/rules/loader.py refuses startup when a rule
names a validator the registry does not carry, and it makes that check for
disabled rules too.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.format_check import _project_alc_text, regex_match
from app.rules.loader import YamlRuleLoader
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

PAT = (
    r"^\s*(?:alcohol|alc\.?)\s*[0-9]{1,2}(?:\.[0-9]+)?\s*%?\s*(?:by\s+volume|/\s*vol\.?|vol\.?)\s*$"
)

DISABLED_RULES = ["spirits.alcohol.format", "wine.alcohol.format", "malt.alcohol.format"]


def _rule():
    return make_rule(
        rule_id="x.format",
        cfr_citation="27 CFR §0.0",
        validator="regex_match",
        reason_code="ALCOHOL_CONTENT.FORMAT.INVALID",
        match_policy=MatchPolicy.REGEX,
        parameters={"pattern": PAT, "ignore_case": True},
    )


@pytest.fixture(scope="module")
def ruleset():
    # The loader checks every rule's validator name against the registry, and
    # a validator registers when its module is imported, so the whole set has
    # to be imported before the pack will load in a run of this file alone.
    pkg = importlib.import_module("app.rules._validators")
    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"app.rules._validators.{mod.name}")
    return YamlRuleLoader().load(Path("rules"))


@pytest.mark.parametrize("rule_id", DISABLED_RULES)
def test_every_rule_using_this_validator_is_disabled(ruleset, rule_id) -> None:
    rule = next(r for r in ruleset.rules if r.rule_id == rule_id)
    assert rule.validator == "regex_match"
    assert rule.disabled is True


def test_validator_stays_registered_for_the_disabled_rules(ruleset) -> None:
    # The loader raises rather than returning when a rule names a validator the
    # registry does not carry, and it checks disabled rules too. So a ruleset
    # that loaded at all is the proof: deleting this validator alongside its
    # three rules would stop the app starting.
    assert "regex_match" in VALIDATOR_REGISTRY
    assert any(r.rule_id in DISABLED_RULES for r in ruleset.rules)


def test_the_pattern_judges_the_label_s_wording_not_a_sentence_built_from_the_number() -> None:
    # The defect behind the switch-off: a bare "12.5%" carries none of the
    # wording the pattern asks for, and used to pass because the validator
    # matched "alcohol 12.5% by volume", which it had written itself.
    reading = {"abv_pct": 12.5, "unit": "%", "alc_text": "12.5%"}
    assert _project_alc_text(reading) == "12.5%"
    obs = make_obs(field_id="abv", value=reading)
    res = regex_match(obs, make_expected(field_id="abv"), _rule(), make_context())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "ALCOHOL_CONTENT.FORMAT.INVALID"


def test_the_label_s_own_wording_in_a_permitted_form_passes() -> None:
    reading = {"abv_pct": 40.0, "unit": "%", "alc_text": "Alcohol 40% by volume"}
    obs = make_obs(field_id="abv", value=reading)
    res = regex_match(obs, make_expected(field_id="abv"), _rule(), make_context())
    assert res.outcome is Outcome.PASS


def test_a_statement_the_reader_did_not_find_goes_to_a_reviewer() -> None:
    # The other half of the defect: with no number read the projection was
    # empty and the rule rejected at reject severity, on a format it never saw.
    # Both readers send `alc_text: ""` when they place no statement.
    reading = {"abv_pct": None, "unit": "", "alc_text": "", "confidence": 0.0}
    assert _project_alc_text(reading) == ""
    obs = make_obs(field_id="abv", value=reading)
    res = regex_match(obs, make_expected(field_id="abv"), _rule(), make_context())
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    "value",
    [
        None,
        12.5,
        {"abv_pct": 40.0, "unit": "%"},
        {"abv_pct": 40.0, "alc_text": None},
        {"text": "Alcohol 40% by volume"},
    ],
)
def test_nothing_but_the_label_s_wording_is_projected(value) -> None:
    # No number, no other key, and nothing that is not a string stands in for
    # the wording; each of these is a reading with no statement in it.
    assert _project_alc_text(value) == ""


def test_a_string_reading_is_the_wording_itself() -> None:
    obs = make_obs(field_id="alc_text", value="ALCOHOL 12.5% BY VOLUME")
    res = regex_match(obs, make_expected(field_id="alc_text"), _rule(), make_context())
    assert res.outcome is Outcome.PASS
