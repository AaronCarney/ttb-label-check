"""The patcher never lets the orchestrator overturn a rule-engine decision.

Applying an orchestrator's refined output to the validation results may add
explanation to the message, but outcome, severity and reason code stay as the
rule engine set them — including in the synthetic case where the orchestrator
disagrees outright."""
import pytest

from app.schemas.expected import BeverageClass
from app.schemas.refined import Refined, TaskSlice
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.patcher import patch_validation_results


def _em():
    return EngineMeta(engine_version="t", rule_pack_version="t", rule_pack="t", started_at_ms=0, elapsed_ms=0)


def test_patcher_does_not_override_fail():
    """Orchestrator says 'match' but rule engine said FAIL — disposition stays FAIL."""
    fail_vr = ValidationResult(
        rule_id="X.brand.present", cfr_citation="27 CFR §5.42", beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.FAIL, severity=Severity.REJECT, reason_code="BRAND.NAME.MISMATCH",
        aggregated_confidence=0.95, engine_meta=_em(),
    )
    refined = Refined(evaluation_id="EV-001", tasks=(
        TaskSlice(task="brand_disambig", rule_id="X.brand.present",
                  payload={"decision": "match", "justification": "phonetic"}),
    ))
    patched = patch_validation_results((fail_vr,), refined)
    assert patched[0].outcome == Outcome.FAIL
    assert patched[0].reason_code == "BRAND.NAME.MISMATCH"
    assert patched[0].severity == Severity.REJECT


def test_patcher_annotates_message_with_orchestrator_view():
    vr = ValidationResult(
        rule_id="X.brand.present", cfr_citation="27 CFR §5.42", beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.INSUFFICIENT_EVIDENCE, severity=Severity.WARN,
        reason_code="BRAND.NAME.NEEDS_REVIEW",
        aggregated_confidence=0.6, engine_meta=_em(), message=None,
    )
    refined = Refined(evaluation_id="EV-001", tasks=(
        TaskSlice(task="brand_disambig", rule_id="X.brand.present",
                  payload={"decision": "match", "justification": "phonetic"}),
    ))
    patched = patch_validation_results((vr,), refined)
    assert patched[0].message is not None
    assert "brand_disambig" in patched[0].message.lower()


def test_patcher_unmatched_rule_returns_unchanged():
    """A ValidationResult with no matching slice returns unchanged."""
    vr = ValidationResult(
        rule_id="R-OTHER", cfr_citation="27 CFR §x", beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.PASS, severity=Severity.INFO,
        aggregated_confidence=0.9, engine_meta=_em(),
    )
    refined = Refined(evaluation_id="EV-001", tasks=())
    patched = patch_validation_results((vr,), refined)
    assert patched == (vr,)


def test_patcher_qualifier_only_slice_annotates_qualifier():
    """A slice with no payload but a qualifier annotates the message with the qualifier."""
    vr = ValidationResult(
        rule_id="X.brand.present", cfr_citation="27 CFR §5.42", beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.INSUFFICIENT_EVIDENCE, severity=Severity.WARN,
        aggregated_confidence=0.6, engine_meta=_em(),
    )
    refined = Refined(evaluation_id="EV-001", tasks=(
        TaskSlice(task="brand_disambig", rule_id="X.brand.present", qualifier="ENGINE.MODEL.UNAVAILABLE"),
    ))
    patched = patch_validation_results((vr,), refined)
    assert "ENGINE.MODEL.UNAVAILABLE" in (patched[0].message or "")
