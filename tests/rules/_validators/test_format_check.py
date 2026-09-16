"""format_check, registered as 'regex_match', does not read the label.

It takes the reader's alcohol observation — a percentage and a unit — builds
the sentence "alcohol N% by volume" from it, and matches the rule's regex
against that construction. So it passes whenever a number was read, whatever
the label printed, and fails when none was. The three rules that used it are
switched off for that reason (docs/decisions.md#0011), and the tests below say
what the validator is rather than exercising it as a live check.

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
from app.rules._validators.format_check import _project_alc_text, regex_match  # noqa: F401
from app.rules.loader import YamlRuleLoader
from app.schemas.rejection import Outcome
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


PAT = r"^\s*(?:alcohol|alc\.?)\s*[0-9]{1,2}(?:\.[0-9]+)?\s*%?\s*(?:by\s+volume|/\s*vol\.?|vol\.?)\s*$"

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


def test_the_reading_is_a_projection_of_the_reader_numbers_not_the_label() -> None:
    # This is the defect the switch-off is for: whatever the label printed, the
    # validator matches its own canonical sentence.
    projected = _project_alc_text({"abv_pct": 12.5, "unit": "%"}, "abv")
    assert projected == "alcohol 12.5% by volume"


def test_a_reading_with_no_percentage_projects_to_nothing() -> None:
    # And this is the other half: with no number the projection is empty, and
    # an empty string fails the pattern, so a label lawfully stating no alcohol
    # content was rejected on a format it never showed.
    assert _project_alc_text({"unit": "%"}, "abv") == ""
    obs = make_obs(field_id="alc_text", value={"unit": "%"})
    res = regex_match(obs, make_expected(field_id="alc_text"), _rule(), make_context())
    assert res.outcome is Outcome.FAIL


def test_a_string_reading_passes_through_to_the_pattern() -> None:
    # The path that would make the rule real: a reading that is already the
    # label's own wording reaches the pattern unchanged. No reader returns one
    # today — both discard the matched text and keep the number — which is what
    # docs/decisions.md#0011 names as the condition for switching the rules on.
    obs = make_obs(field_id="alc_text", value="ALCOHOL 12.5% BY VOLUME")
    res = regex_match(obs, make_expected(field_id="alc_text"), _rule(), make_context())
    assert res.outcome is Outcome.PASS
