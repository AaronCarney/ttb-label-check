"""The confidence floor: a mismatch measured from a reading the reader was
unsure of is reported as needs review, under the element's own code.

This is FR-9: a mismatch only where the product is confident it read the text
correctly, and a match may rest on the value itself, because a misread rarely
equals the application's value by chance. The mechanism
behind it is `YamlRuleEngine._apply_confidence_floor`, which every result passes
through on its way out of `_finish`. Until this file existed nothing in the suite
exercised it: the engine's floor code appeared in `app/rules/yaml_engine.py`
and nowhere in `tests/`. The rule tests that look like
they would cover it call the validator directly
(`tests/rules/test_warning_rules.py`), which is the one path that skips `_finish`.

Every case here goes through `engine.evaluate`, because the floor is the engine's
and not any validator's.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest

import app.rules._validators as _validators
from app.rules._validators import VALIDATOR_REGISTRY, register
from app.rules.loader import YamlRuleLoader
from app.rules.yaml_engine import YamlRuleEngine, read_uncertain_code
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import ReasonCodeEntry, RuleSet
from tests.rules.fixtures import (
    make_context,
    make_engine_meta,
    make_expected,
    make_obs,
    make_rule,
)

# The reason code's own description, as the shipped registry carries it, so one
# case can prove the sentence reaches a reviewer and not just the code.
_FLOOR_DESCRIPTION = (
    "The brand name as read differs from what is required, but the reader scored "
    "that reading below the confidence a rejection needs, so a reviewer checks the "
    "brand name on the label."
)
_BRAND_READ_UNCERTAIN = "BRAND.READ.UNCERTAIN"


def _validator_returning(outcome: Outcome, confidence: float, *, with_evidence: bool = True):
    """A validator that reports `outcome` at `confidence`, and nothing else.

    The engine does not compute `aggregated_confidence` — each validator states
    it — so a test of the floor has to state it too.
    """

    def _v(obs, exp, rule, ctx) -> ValidationResult:
        return ValidationResult(
            rule_id=rule.rule_id,
            cfr_citation=rule.cfr_citation,
            beverage_class=obs.beverage_class,
            outcome=outcome,
            severity=rule.severity,
            reason_code=None if outcome is Outcome.PASS else rule.reason_code,
            aggregated_confidence=confidence,
            evidence=obs.evidence if with_evidence else (),
            expected=exp,
            observed=obs,
            # Replaced by the engine in `_finish`; the field is required, so a
            # placeholder stands in.
            engine_meta=make_engine_meta(),
        )

    return _v


@pytest.fixture
def run_one(request):
    """Run one rule through the engine and return its single result."""

    async def _run(
        *,
        outcome: Outcome,
        confidence: float,
        floor: float,
        with_evidence: bool = True,
        reason_codes: dict | None = None,
    ) -> ValidationResult:
        name = f"__floor_{request.node.name}__"
        register(name)(_validator_returning(outcome, confidence, with_evidence=with_evidence))
        try:
            rule = make_rule(
                rule_id="x.floor",
                cfr_citation="27 CFR §0.0",
                validator=name,
                reason_code="BRAND.NAME.MISMATCH",
                confidence_floor=floor,
            )
            rs = RuleSet(
                version="0.1.0",
                effective_date="2026-09-09",
                rules=(rule,),
                reason_codes=reason_codes or {},
                assets={},
                decision_tables={},
            )
            obs = [
                make_obs(
                    field_id="brand_name", value="Old Tom", beverage_class=BeverageClass.SPIRITS
                )
            ]
            exp = [make_expected(field_id="brand_name", value="Old Tom")]
            results = await YamlRuleEngine(rs).evaluate(obs, exp, make_context())
            assert len(results) == 1, results
            return results[0]
        finally:
            del VALIDATOR_REGISTRY[name]

    return _run


@pytest.mark.asyncio
async def test_a_pass_below_the_floor_stands(run_one) -> None:
    """FR-9: finding the application's value on the label shows it was read,
    whatever score the reader gave the characters."""
    result = await run_one(outcome=Outcome.PASS, confidence=0.40, floor=0.60)
    assert result.outcome is Outcome.PASS
    assert result.reason_code is None


@pytest.mark.asyncio
async def test_a_fail_below_the_floor_becomes_needs_review(run_one) -> None:
    """The half that matters more. A rule that rejects a label on a reading the
    reader was unsure of would reject a compliant label for being photographed
    badly, and the rule's own severity here is `reject`."""
    result = await run_one(outcome=Outcome.FAIL, confidence=0.40, floor=0.60)
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.reason_code == _BRAND_READ_UNCERTAIN
    # WARN, not REJECT: nothing was settled, so nothing is held against the label.
    assert result.severity is Severity.WARN


@pytest.mark.asyncio
async def test_a_reading_exactly_at_the_floor_is_kept(run_one) -> None:
    """The floor is the lowest confidence the rule accepts, not the first it
    refuses: the comparison is `>=`. A rule declaring 0.60 and a reading of
    exactly 0.60 is a settled verdict."""
    result = await run_one(outcome=Outcome.PASS, confidence=0.60, floor=0.60)
    assert result.outcome is Outcome.PASS
    assert result.reason_code is None


@pytest.mark.asyncio
async def test_a_reading_above_the_floor_is_untouched(run_one) -> None:
    result = await run_one(outcome=Outcome.FAIL, confidence=0.95, floor=0.60)
    assert result.outcome is Outcome.FAIL
    assert result.reason_code == "BRAND.NAME.MISMATCH"
    assert result.severity is Severity.REJECT


@pytest.mark.asyncio
async def test_a_verdict_with_no_evidence_is_not_downgraded(run_one) -> None:
    """The carve-out the mechanism declares. A required statement that is simply
    absent scores zero because nothing was read, not because the reading was
    poor, and the rule that found it missing is entitled to say so. Without this
    the floor would turn every missing-element rejection into a needs-review and
    R4 would never fail a label."""
    result = await run_one(outcome=Outcome.FAIL, confidence=0.0, floor=0.60, with_evidence=False)
    assert result.outcome is Outcome.FAIL
    assert result.reason_code == "BRAND.NAME.MISMATCH"
    assert result.severity is Severity.REJECT


@pytest.mark.asyncio
async def test_an_outcome_that_settles_nothing_is_not_downgraded(run_one) -> None:
    """Only `pass` and `fail` assert something about the label. An outcome that
    already says no comparison was reached keeps its own reason code, so a
    timeout or a validator error is not relabelled as a poor reading."""
    result = await run_one(outcome=Outcome.INSUFFICIENT_EVIDENCE, confidence=0.10, floor=0.60)
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.reason_code == "BRAND.NAME.MISMATCH"


@pytest.mark.asyncio
async def test_the_downgrade_carries_the_sentence_a_reviewer_reads(run_one) -> None:
    """The reason code is not the deliverable — the words are. `_finish` looks
    the code up in the pack's own registry, so a reviewer is told why the check
    could not be settled."""
    result = await run_one(
        outcome=Outcome.FAIL,
        confidence=0.40,
        floor=0.60,
        reason_codes={
            _BRAND_READ_UNCERTAIN: ReasonCodeEntry(
                description=_FLOOR_DESCRIPTION, cfr_anchors=(), severity=Severity.WARN
            )
        },
    )
    assert result.reason_code == _BRAND_READ_UNCERTAIN
    assert result.message == _FLOOR_DESCRIPTION


def test_every_rejecting_rule_has_its_element_code_registered() -> None:
    """The floor's code is built from the rule's, so each rule that can reject
    needs its element's code in the registry for a reviewer to read."""
    for _, modname, _ in pkgutil.iter_modules(_validators.__path__):
        importlib.import_module(f"{_validators.__name__}.{modname}")
    ruleset = YamlRuleLoader().load(Path("rules"))
    for rule in ruleset.rules:
        if rule.severity is Severity.REJECT:
            code = read_uncertain_code(rule)
            entry = ruleset.reason_codes.get(code)
            assert entry is not None, (rule.rule_id, code)
            assert entry.severity is Severity.WARN, code
