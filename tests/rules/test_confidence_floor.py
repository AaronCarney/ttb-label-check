"""The confidence floor: a verdict measured from a reading the reader was
unsure of is reported as needs review, not as a match or a mismatch.

This is requirement R9, a P0 — *"an element that cannot be read with confidence
is reported as needs review, not as match or mismatch"* — and the mechanism
behind it is `YamlRuleEngine._apply_confidence_floor`, which every result passes
through on its way out of `_finish`. Until this file existed nothing in the suite
exercised it: `ENGINE.EVIDENCE.BELOW_CONFIDENCE_FLOOR` appeared in
`app/rules/yaml_engine.py` and nowhere in `tests/`. The rule tests that look like
they would cover it call the validator directly
(`tests/rules/test_warning_rules.py`), which is the one path that skips `_finish`.

Every case here goes through `engine.evaluate`, because the floor is the engine's
and not any validator's.
"""
from __future__ import annotations

import pytest

from app.rules._validators import VALIDATOR_REGISTRY, register
from app.rules.yaml_engine import BELOW_CONFIDENCE_FLOOR, YamlRuleEngine
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
    "The label reading this check rests on scored below the confidence the rule "
    "requires, so the check could not be settled; a reviewer reads the label."
)


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
            obs = [make_obs(field_id="brand_name", value="Old Tom", beverage_class=BeverageClass.SPIRITS)]
            exp = [make_expected(field_id="brand_name", value="Old Tom")]
            results = await YamlRuleEngine(rs).evaluate(obs, exp, make_context())
            assert len(results) == 1, results
            return results[0]
        finally:
            del VALIDATOR_REGISTRY[name]

    return _run


@pytest.mark.asyncio
async def test_a_pass_below_the_floor_becomes_needs_review(run_one) -> None:
    """The case R9 names. A match the reader was unsure of is not a match."""
    result = await run_one(outcome=Outcome.PASS, confidence=0.40, floor=0.60)
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.reason_code == BELOW_CONFIDENCE_FLOOR
    # WARN, not REJECT: nothing was settled, so nothing is held against the label.
    assert result.severity is Severity.WARN


@pytest.mark.asyncio
async def test_a_fail_below_the_floor_becomes_needs_review(run_one) -> None:
    """The half that matters more. A rule that rejects a label on a reading the
    reader was unsure of would reject a compliant label for being photographed
    badly, and the rule's own severity here is `reject`."""
    result = await run_one(outcome=Outcome.FAIL, confidence=0.40, floor=0.60)
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.reason_code == BELOW_CONFIDENCE_FLOOR
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
        outcome=Outcome.PASS,
        confidence=0.40,
        floor=0.60,
        reason_codes={
            BELOW_CONFIDENCE_FLOOR: ReasonCodeEntry(
                description=_FLOOR_DESCRIPTION, cfr_anchors=(), severity=Severity.WARN
            )
        },
    )
    assert result.reason_code == BELOW_CONFIDENCE_FLOOR
    assert result.message == _FLOOR_DESCRIPTION
