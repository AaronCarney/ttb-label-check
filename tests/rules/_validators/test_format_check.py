"""format_check, registered as 'regex_match', judges the label's alcohol wording.

Both readers return the alcohol statement as the label prints it, under
`alc_text`, and the validator matches the rule's pattern against that. The
patterns are the shipped ones, read from the rule pack, so these tests hold the
three `alcohol.format` rules to the forms 27 CFR §4.36(b), §5.65(b) and
§7.65(b) give, and to the examples those sections print.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path

import pytest

from app.rules._validators.format_check import _project_alc_text, regex_match
from app.rules.loader import YamlRuleLoader
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome, Severity
from tests.rules.fixtures import make_context, make_expected, make_obs

CLASSES = {
    "spirits": BeverageClass.SPIRITS,
    "wine": BeverageClass.WINE,
    "malt": BeverageClass.MALT,
}

# Each section's own examples, verbatim, and each form it lists with a figure in
# the blank.
PERMITTED = {
    "spirits": [
        # §5.65(b)(4)
        "40% alc/vol",
        "Alc. 40 percent by vol.",
        "Alc 40% by vol",
        "40% Alcohol by Volume.",
        # §5.65(b)(2)(i) (A), (B), (C)
        "Alcohol 40 percent by volume",
        "40 percent alcohol by volume",
        "Alcohol by volume 40 percent.",
        # §5.65(b)(2)(ii): parentheses around any word or symbol
        "(Alc.) 40 (%) (by) (vol.)",
        "40% (alc/vol)",
        # §5.65(b)(1)(i): proof alongside
        "40% alc/vol (80 proof)",
        "40%ALC/VOL/80 PROOF",
        "45% alc./vol., 90° proof",
    ],
    "malt": [
        # §7.65(b)(5)
        "4.2% alc/vol",
        "Alc. 4.0 percent by vol.",
        "Alc 4% by vol",
        "5.9% Alcohol by Volume.",
        # §7.65(b)(3)(i) (A), (B), (C)
        "Alcohol 4.2 percent by volume",
        "4.2 percent alcohol by volume",
        "Alcohol by volume: 4.2 percent.",
        "ALC./VOL.: 4.2%",
        # §7.65(b)(2): hundredths below 0.5 percent; §7.65(e) prints ".5%"
        "0.45% alc/vol",
        ".5% alc/vol",
    ],
    "wine": [
        # §4.36(b)(1) and (b)(2), and the abbreviations they allow
        "Alcohol 12% by volume",
        "Alc. 12% by vol.",
        "alc 12 % by vol",
        "Alcohol 11% to 13% by volume",
        "Alcohol 11 to 13 % by volume",
        # similar appropriate phrases
        "12% alc. by vol.",
        "ALC. 12.5% BY VOLUME",
        "Alcohol by volume 12%",
        "Alc. by vol.: 12%",
        "12.5 percent alcohol by volume",
        "12% alc/vol",
        "11%-13% alc. by vol.",
        "11–13% alc. by vol.",
    ],
}

# Statements no listed form covers. Each goes to a reviewer.
UNRECOGNISED = {
    "spirits": [
        "45% ABV",
        "12.5%",
        "Alcohol 40%",
        "40% by volume",
        "40% ALC VOL",
        "80 PROOF",
        "ALC. 12,5% BY VOL.",
        "Alc. by vol.: 40%",  # §5.65(b)(2)(i) (C) carries no colon
        "40% alc/vol 80 proof extra",
        "Alcohol 11% to 13% by volume",
    ],
    "malt": [
        "ALC. BY VOL. 5%",  # §7.65(b)(3)(i) (C) carries its colon
        "ALC. / VOL. 8.0 %",
        "5% alc/vol, 10 proof",
        "ALC. 20.3%",
        "4.2% ABV",
    ],
    "wine": [
        "12% alc/vol (24 proof)",
        "ALC. 12,5% BY VOL.",
        "12.5%",
        "Alcohol 12%",
        "12% ABV",
    ],
}


@pytest.fixture(scope="module")
def ruleset():
    # The loader checks every rule's validator name against the registry, and
    # a validator registers when its module is imported, so the whole set has
    # to be imported before the pack will load in a run of this file alone.
    pkg = importlib.import_module("app.rules._validators")
    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"app.rules._validators.{mod.name}")
    return YamlRuleLoader().load(Path("rules"))


def _rule(ruleset, cls: str):
    return next(r for r in ruleset.rules if r.rule_id == f"{cls}.alcohol.format")


def _judge(ruleset, cls: str, statement: str):
    reading = {"abv_pct": 40.0, "unit": "%", "alc_text": statement, "confidence": 0.9}
    obs = make_obs(field_id="abv", value=reading, beverage_class=CLASSES[cls])
    return regex_match(obs, make_expected(field_id="abv"), _rule(ruleset, cls), make_context())


@pytest.mark.parametrize("cls", CLASSES)
def test_the_rule_is_on_and_cannot_reject(ruleset, cls) -> None:
    rule = _rule(ruleset, cls)
    assert rule.validator == "regex_match"
    assert rule.disabled is False
    assert rule.severity is Severity.WARN
    assert rule.reason_code == "ALCOHOL_CONTENT.FORMAT.NEEDS_REVIEW"


@pytest.mark.parametrize(
    ("cls", "statement"), [(c, s) for c, forms in PERMITTED.items() for s in forms]
)
def test_a_form_the_regulation_gives_passes(ruleset, cls, statement) -> None:
    res = _judge(ruleset, cls, statement)
    assert res.outcome is Outcome.PASS
    assert res.reason_code is None


@pytest.mark.parametrize(
    ("cls", "statement"), [(c, s) for c, forms in UNRECOGNISED.items() for s in forms]
)
def test_a_form_the_pattern_does_not_list_goes_to_a_reviewer(ruleset, cls, statement) -> None:
    res = _judge(ruleset, cls, statement)
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == "ALCOHOL_CONTENT.FORMAT.NEEDS_REVIEW"
    assert res.rule_id == f"{cls}.alcohol.format"
    assert res.evidence and res.observed is not None


def test_a_located_statement_with_no_wording_goes_to_a_reviewer(ruleset) -> None:
    # The reader placed the alcohol statement, so this is not "not found", but
    # returned none of its wording. There is nothing to judge the form of.
    res = _judge(ruleset, "spirits", "")
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "ALCOHOL_CONTENT.FORMAT.NEEDS_REVIEW"


def test_the_pattern_judges_the_label_s_wording_not_a_sentence_built_from_the_number(
    ruleset,
) -> None:
    # A bare "12.5%" carries none of the wording the forms ask for, and must not
    # pass on a sentence the validator writes from the number.
    reading = {"abv_pct": 12.5, "unit": "%", "alc_text": "12.5%"}
    assert _project_alc_text(reading) == "12.5%"
    assert _judge(ruleset, "wine", "12.5%").outcome is Outcome.INSUFFICIENT_EVIDENCE


def test_a_statement_the_reader_did_not_find_goes_to_a_reviewer(ruleset) -> None:
    # Both readers send `alc_text: ""` when they place no statement, and attach
    # no box. That is the reader not finding it, which is its own finding.
    reading = {"abv_pct": None, "unit": "", "alc_text": "", "confidence": 0.0}
    assert _project_alc_text(reading) == ""
    obs = make_obs(field_id="abv", value=reading)
    res = regex_match(obs, make_expected(field_id="abv"), _rule(ruleset, "spirits"), make_context())
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "LEGIBILITY.FIELD.NOT_READ"


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


def test_a_string_reading_is_the_wording_itself(ruleset) -> None:
    obs = make_obs(field_id="alc_text", value="ALCOHOL 12.5% BY VOLUME")
    res = regex_match(
        obs, make_expected(field_id="alc_text"), _rule(ruleset, "wine"), make_context()
    )
    assert res.outcome is Outcome.PASS


# The alcohol statements of the approved labels in the fixture corpus, as each
# label prints them. Three are in no form the regulation lists: two malt labels
# print form (C) without the colon §7.65(b)(3)(i) gives it, and one wine label
# writes its figure with a decimal comma.
_MANIFEST = Path("tests/fixtures/labels/manifest.json")
_MANIFEST_CLASSES = {"distilled_spirits": "spirits", "wine": "wine", "malt_beverage": "malt"}
_CORPUS_REVIEWS = {"ttb-26238001000795", "ttb-26240001000454", "ttb-26239001000331"}


def _corpus_statements() -> list[tuple[str, str, str]]:
    labels = json.loads(_MANIFEST.read_text(encoding="utf-8"))["labels"]
    return [
        (
            label["id"],
            _MANIFEST_CLASSES[label["beverage_type"]],
            label["label_observed"]["abv"]["text"],
        )
        for label in labels
        if label["id"].startswith("ttb-")
    ]


def test_the_corpus_holds_the_thirty_approved_labels() -> None:
    statements = _corpus_statements()
    assert len(statements) == 30
    assert _CORPUS_REVIEWS <= {label_id for label_id, _, _ in statements}


@pytest.mark.parametrize(("label_id", "cls", "statement"), _corpus_statements())
def test_an_approved_label_s_statement_passes_or_goes_to_a_reviewer(
    ruleset, label_id, cls, statement
) -> None:
    expected = Outcome.INSUFFICIENT_EVIDENCE if label_id in _CORPUS_REVIEWS else Outcome.PASS
    assert _judge(ruleset, cls, statement).outcome is expected
