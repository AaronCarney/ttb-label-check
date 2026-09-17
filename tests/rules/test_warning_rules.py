"""The common-pack health-warning rules.

Two kinds of case live here. The first is a positive and a negative for each
rule, built by hand: every rule is looked up in the loaded RuleSet by name, so
a rename in the YAML breaks the test — deliberately.

The second is the one that matters, and it is at the bottom: every label in
`tests/fixtures/labels/manifest.json` is scored against what the manifest says
a correct check reports for it. 27 CFR 16.21 is the brief's loudest ask, and
until that test existed nothing in the suite compared a warning reading with
the answer key at all.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

import pytest

from app.config import Settings
from app.rules import build_rule_engine
from app.rules._validators import VALIDATOR_REGISTRY
from app.rules.loader import YamlRuleLoader
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome, Severity
from tests.rules.fixtures import make_context, make_expected, make_obs
from tests.rules.manifest_labels import accepted_verdicts, application_record, manifest


@pytest.fixture(scope="module")
def ruleset():
    """The whole rule pack, loaded the way the application loads it.

    The loader checks the validator name of every rule in `rules/`, not only
    the warning rules this file scores, so every validator module has to be
    registered before the load. `build_rule_engine` force-imports them at
    startup for exactly that reason; a hand-written import list here goes stale
    the moment any rule pack gains a validator.
    """
    import app.rules._validators as _validators

    for _, modname, _ in pkgutil.iter_modules(_validators.__path__):
        importlib.import_module(f"{_validators.__name__}.{modname}")
    return YamlRuleLoader().load(Path("rules"))


def _by_id(ruleset, rule_id):
    return next(r for r in ruleset.rules if r.rule_id == rule_id)


def _ctx(ruleset):
    return make_context(assets=ruleset.assets, decision_tables=ruleset.decision_tables)


CANONICAL_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects. (2) "
    "Consumption of alcoholic beverages impairs your ability to drive a car or operate "
    "machinery, and may cause health problems."
)


def test_warning_present_pos(ruleset) -> None:
    rule = _by_id(ruleset, "common.warning.present")
    obs = make_obs(
        field_id="warning_block", value=CANONICAL_WARNING, beverage_class=BeverageClass.SPIRITS
    )
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="warning_block"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.PASS


def test_warning_present_neg(ruleset) -> None:
    rule = _by_id(ruleset, "common.warning.present")
    obs = make_obs(field_id="warning_block", value=None, beverage_class=BeverageClass.SPIRITS)
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="warning_block"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.PRESENCE.MISSING"


def test_warning_verbatim_pos(ruleset) -> None:
    rule = _by_id(ruleset, "common.warning.verbatim")
    obs = make_obs(field_id="warning_block", value=CANONICAL_WARNING)
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="warning_block"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.PASS


def test_warning_verbatim_neg(ruleset) -> None:
    rule = _by_id(ruleset, "common.warning.verbatim")
    obs = make_obs(
        field_id="warning_block", value=CANONICAL_WARNING.replace("birth defects", "complications")
    )
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="warning_block"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.VERBATIM.MISMATCH"


def test_heading_style_pos(ruleset) -> None:
    rule = _by_id(ruleset, "common.warning.heading_caps_bold")
    obs = make_obs(
        field_id="warning_block",
        value={
            "heading_text": "GOVERNMENT WARNING",
            "heading_styles": {"weight": "bold", "case": "upper"},
        },
    )
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="warning_block"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.PASS


def test_heading_style_neg(ruleset) -> None:
    rule = _by_id(ruleset, "common.warning.heading_caps_bold")
    obs = make_obs(
        field_id="warning_block",
        value={
            "heading_text": "Government Warning",
            "heading_styles": {"weight": "bold", "case": "title"},
        },
    )
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="warning_block"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


# ---------------------------------------------------------------------------
# The requirements this product cannot measure
# ---------------------------------------------------------------------------

# Rule id -> the code that says, in the registry's own words, what was not
# measured. One code per rule, because each rule asks a different question and
# a reviewer reads the answer as a sentence.
UNMEASURABLE_RULES = {
    "common.warning.contrasting_bg": "WARNING.LEGIBILITY.CONTRAST_NOT_MEASURED",
    "common.warning.cpi_max": "WARNING.TYPE_SIZE.CPI_NOT_MEASURED",
    "common.warning.separate_apart": "WARNING.PLACEMENT.ISOLATION_NOT_MEASURED",
    "common.warning.type_size_min": "WARNING.TYPE_SIZE.HEIGHT_NOT_MEASURED",
}


@pytest.mark.parametrize("rule_id,reason_code", sorted(UNMEASURABLE_RULES.items()))
def test_unmeasurable_rule_reports_insufficient_evidence(ruleset, rule_id, reason_code) -> None:
    """Contrast, type height, characters per inch and separation from other
    text are real §16.22 requirements that this product cannot measure: no
    reader reports ink colour, the physical scale of the label, or the distance
    to the nearest neighbouring text.

    The honest answer is neither a pass (claiming a requirement was checked
    that nobody looked at) nor a rejection (rejecting a compliant label for the
    product's own blindness). Each rule answers insufficient evidence at warn
    severity under its own code, so a reviewer is told which measurement is
    missing. Decision 0013 carries the argument; the rules also stay disabled,
    so this is what they answer the day anyone switches one on.
    """
    rule = _by_id(ruleset, rule_id)
    assert rule.validator == "unmeasurable"
    assert rule.disabled is True
    assert rule.reason_code == reason_code
    # The payload the deleted validators used to read. Whatever it carries, the
    # answer is the same: nothing here was measured.
    obs = make_obs(
        field_id="warning_block",
        value={"contrast_ratio": 7.2, "cpi": 30, "height_mm": 1, "min_neighbor_distance_px": 10},
    )
    res = VALIDATOR_REGISTRY[rule.validator](
        obs, make_expected(field_id="warning_block"), rule, _ctx(ruleset)
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == reason_code


def test_unmeasurable_codes_are_declared_in_the_registry(ruleset) -> None:
    """A code with no registry entry reaches a reviewer as a bare identifier."""
    for reason_code in UNMEASURABLE_RULES.values():
        assert reason_code in ruleset.reason_codes
        assert ruleset.reason_codes[reason_code].description


# ---------------------------------------------------------------------------
# Every label in the manifest, scored against the manifest's own answer
# ---------------------------------------------------------------------------

# Rule id -> the manifest's name for the same check. The fourth warning rule
# set, bold type, is deliberately absent: the manifest's `check_rules` says
# bold "is not scored by this set", so nothing here asserts on it.
_CHECK_BY_RULE = {
    "common.warning.present": "warning_present",
    "common.warning.verbatim": "warning_exact",
    "common.warning.heading_caps_bold": "warning_heading_caps",
}

# The heading is the statement's opening words up to and including "WARNING",
# with the colon that separates it from the body. The real reader returns it as
# its own field; here it is cut from the transcribed statement the same way.
_HEADING = re.compile(r"(?i)^\s*(.*?warning\s*:?)")


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setenv("RULES_ROOT", str(Path("rules").resolve()))
    return build_rule_engine(Settings())


def _warning_observation(entry):
    """What a reader returns for this label's warning block.

    The text is the manifest's own transcription of what the label prints, and
    the heading's capitals are derived from it exactly as `app/vision/local.py`
    derives them — from the heading's own letters — so the reading is not
    copied from the answer it is about to be scored against.

    Bold weight is held at measured-and-bold because the manifest does not
    score it. Leaving it unmeasured would make every heading answer "not
    measured" and the capitals, which the manifest does score, would never be
    reached. The unmeasured branch has its own cases in
    tests/rules/_validators/test_heading_style_check.py.
    """
    observed = entry["label_observed"]
    text = observed.get("warning_text") or ""
    match = _HEADING.match(text)
    heading_text = match.group(1) if match else ""
    letters = [c for c in heading_text if c.isalpha()]
    return make_obs(
        field_id="gov_warning",
        value={
            "text": text,
            "heading_text": heading_text,
            "heading_all_caps": bool(letters) and all(c.isupper() for c in letters),
            "heading_bold": True,
            "heading_bold_measured_confident": True,
            "confidence": 0.95,
        },
        beverage_class=application_record(entry).beverage_class,
    )


def _verdict(result):
    """One rule outcome in the manifest's vocabulary for the warning checks.

    The manifest states these three as booleans — the label satisfies the
    requirement, or it does not — and accepts `needs_review` where a reviewer
    should decide. A failure the engine marks `warn` is a reviewer's call, not
    a rejection.
    """
    if result.outcome is Outcome.PASS:
        return True
    if result.outcome is Outcome.FAIL:
        return "needs_review" if result.severity is Severity.WARN else False
    return "needs_review"


def _manifest_cases():
    return [pytest.param(entry, id=entry["id"]) for entry in manifest()["labels"]]


@pytest.mark.parametrize("entry", _manifest_cases())
@pytest.mark.parametrize("check", sorted(set(_CHECK_BY_RULE.values())))
async def test_warning_check_reaches_the_outcome_the_manifest_states(engine, entry, check):
    """The three enabled warning rules, run from the rule pack over the
    label's transcribed warning text, reach the manifest's own answer.

    38 labels: 33 compliant on all three, four whose wording differs from
    §16.21 (a dropped clause, "RISKS" for "RISK", a closing quotation mark for
    the full stop, "MAY IMPAIR" for "IMPAIRS"), and one repainted with a
    title-case heading, which the manifest marks compliant on wording and not
    on capitals — the case that settles that the verbatim comparison ignores
    letter case and the heading rule is what scores it.
    """
    ctx = engine.build_validator_context(started_at_ms=0)
    results = await engine.evaluate((_warning_observation(entry),), (), ctx)
    produced = [(r.rule_id, _verdict(r)) for r in results if _CHECK_BY_RULE.get(r.rule_id) == check]
    assert produced, (
        f"no rule checked {check} for {entry['id']}; the manifest states an "
        "answer for it and nothing produced one"
    )
    accepted = accepted_verdicts(entry, check)
    for rule_id, verdict in produced:
        assert verdict in accepted, (
            f"{entry['id']}: {rule_id} reported {verdict!r}; the manifest accepts {accepted}"
        )


@pytest.mark.parametrize("entry", _manifest_cases())
def test_heading_capitals_read_from_the_text_match_the_transcription(entry):
    """The capitals the reading derives are the ones the manifest transcribed.

    Without this, the previous test could pass on a heading cut wrongly out of
    the statement: a heading of "" has no letters, reports not-capitals, and
    would fail the one label whose capitals are wrong for the wrong reason.
    """
    payload = _warning_observation(entry).observed_value
    assert payload["heading_text"], f"{entry['id']}: no heading found in the warning text"
    assert payload["heading_all_caps"] is entry["label_observed"]["warning_heading_all_caps"]
