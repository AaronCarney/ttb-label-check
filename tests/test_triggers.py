"""The orchestrator-trigger predicate, exactly: which reason codes call the
orchestrator in and which do not."""
from app.schemas.expected import BeverageClass
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.triggers import should_invoke_orchestrator


def _em():
    return EngineMeta(engine_version="t", rule_pack_version="t", rule_pack="t", started_at_ms=0, elapsed_ms=0)


def _vr(reason_code: str | None):
    return ValidationResult(
        rule_id="X.brand.present", cfr_citation="27 CFR §5.42", beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.INSUFFICIENT_EVIDENCE, severity=Severity.WARN, reason_code=reason_code,
        aggregated_confidence=0.6, engine_meta=_em(),
    )


def test_trigger_fires_on_brand_needs_review():
    assert should_invoke_orchestrator((_vr("BRAND.NAME.NEEDS_REVIEW"),)) is True


def test_trigger_does_not_fire_on_unrelated_code():
    assert should_invoke_orchestrator((_vr("BRAND.NAME.MISSING"),)) is False
    assert should_invoke_orchestrator((_vr(None),)) is False


def test_trigger_empty_results_no_fire():
    assert should_invoke_orchestrator(()) is False


def test_trigger_multi_result_fires_on_any_match():
    pass_vr = ValidationResult(
        rule_id="R-OK", cfr_citation="27 CFR §x", beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.PASS, severity=Severity.INFO, aggregated_confidence=0.95, engine_meta=_em(),
    )
    assert should_invoke_orchestrator((pass_vr, _vr("BRAND.NAME.NEEDS_REVIEW"))) is True
