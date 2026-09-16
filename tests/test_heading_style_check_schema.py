"""heading_style_check reads the consolidated gov_warning schema produced by
the cloud extractor (heading_text/heading_all_caps/heading_bold), and still
honours the legacy heading_styles sub-object for hand-built fixtures."""
from app.rules._validators import ValidatorContext
from app.rules._validators.heading_style_check import heading_style_check
from app.schemas.expected import BeverageClass, ExpectedValue
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import RuleDefinition


def _rule() -> RuleDefinition:
    return RuleDefinition(
        rule_id="common.warning.heading_caps_bold",
        cfr_citation="27 CFR §16.22(a)(2)",
        applies_to_classes=(BeverageClass.SPIRITS,),
        reason_code="WARNING.STYLE.HEADING_NOT_BOLD_CAPS",
        severity=Severity.REJECT,
        match_policy="layout",
        validator="heading_style_check",
        parameters={
            "target_phrase": "GOVERNMENT WARNING",
            "required_case": "upper",
            "required_weight": "bold",
        },
        evidence_required=("warning_block",),
        effective_date="1989-11-18",
        test_fixtures=(),
    )


def _ctx() -> ValidatorContext:
    return ValidatorContext(assets={}, decision_tables={}, started_at_ms=0, engine_version="t")


def _obs(payload: dict) -> FieldObservation:
    return FieldObservation(
        field_id="gov_warning",
        beverage_class=BeverageClass.SPIRITS,
        observed_value=payload,
        evidence=(Evidence(field_id="gov_warning", source=EvidenceSource.LAYOUT,
                            match_kind=MatchKind.NONE, confidence=0.9),),
        upstream_meta={},
    )


def test_consolidated_shape_passes_when_caps_and_bold():
    obs = _obs({
        "text": "GOVERNMENT WARNING: …",
        "heading_text": "GOVERNMENT WARNING",
        "heading_all_caps": True,
        "heading_bold": True,
        "type_size_pt": 8.0,
        "confidence": 0.95,
    })
    result = heading_style_check(obs, ExpectedValue(field_id="gov_warning"), _rule(), _ctx())
    assert result.outcome == Outcome.PASS
    assert result.reason_code is None


def test_consolidated_shape_fails_when_not_bold():
    obs = _obs({
        "text": "GOVERNMENT WARNING: …",
        "heading_text": "GOVERNMENT WARNING",
        "heading_all_caps": True,
        "heading_bold": False,  # the §16.22(a)(2) trip wire
        "type_size_pt": 8.0,
        "confidence": 0.95,
    })
    result = heading_style_check(obs, ExpectedValue(field_id="gov_warning"), _rule(), _ctx())
    assert result.outcome == Outcome.FAIL
    assert result.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_consolidated_shape_fails_when_not_all_caps():
    obs = _obs({
        "text": "Government warning: …",
        "heading_text": "Government Warning",
        "heading_all_caps": False,
        "heading_bold": True,
        "type_size_pt": 8.0,
        "confidence": 0.95,
    })
    result = heading_style_check(obs, ExpectedValue(field_id="gov_warning"), _rule(), _ctx())
    assert result.outcome == Outcome.FAIL


def test_legacy_heading_styles_shape_still_works():
    """Fixtures that pre-date schema consolidation use heading_styles.case +
    heading_styles.weight; that shape must keep passing/failing correctly."""
    obs = _obs({
        "heading_text": "GOVERNMENT WARNING",
        "heading_styles": {"case": "upper", "weight": "bold"},
    })
    result = heading_style_check(obs, ExpectedValue(field_id="gov_warning"), _rule(), _ctx())
    assert result.outcome == Outcome.PASS


def test_warning_block_alias_routes_gov_warning_observation():
    """The yaml_engine rule-routing alias map must surface gov_warning
    observations to rules whose evidence_required = [warning_block]."""
    from app.rules.yaml_engine import _matches_evidence_required
    assert _matches_evidence_required("gov_warning", ("warning_block",))
    assert not _matches_evidence_required("brand_name", ("warning_block",))
