"""Validators must read primitives from the cloud extractor's dict-shaped
observed_value, and must report NOT_APPLICABLE — not FAIL — when the rule
requires an expected value that was never supplied."""
from __future__ import annotations

from app.rules._validators import ValidatorContext
from app.rules._validators.format_check import regex_match
from app.rules._validators.fuzzy_brand import fuzzy_brand
from app.schemas.expected import BeverageClass, ExpectedValue
from app.schemas.extracted import (
    Evidence,
    EvidenceSource,
    FieldObservation,
    MatchKind,
)
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import RuleDefinition


def _ctx() -> ValidatorContext:
    return ValidatorContext(
        assets={}, decision_tables={}, started_at_ms=0, engine_version="t"
    )


def _obs(field_id: str, value) -> FieldObservation:
    return FieldObservation(
        field_id=field_id,
        beverage_class=BeverageClass.SPIRITS,
        observed_value=value,
        evidence=(Evidence(field_id=field_id, source=EvidenceSource.LAYOUT,
                            match_kind=MatchKind.NONE, confidence=0.95),),
        upstream_meta={},
    )


def _brand_rule() -> RuleDefinition:
    return RuleDefinition(
        rule_id="spirits.brand.present",
        cfr_citation="27 CFR §5.63(a)",
        applies_to_classes=(BeverageClass.SPIRITS,),
        reason_code="BRAND.PRESENCE.MISSING",
        severity=Severity.REJECT,
        match_policy="fuzzy",
        validator="fuzzy_brand",
        parameters={
            "pass_threshold": 0.92,
            "needs_review_threshold": 0.85,
            "needs_review_reason_code": "BRAND.NAME.NEEDS_REVIEW",
        },
        evidence_required=("brand",),
        effective_date="2022-02-09",
        test_fixtures=(),
    )


def _alcohol_format_rule() -> RuleDefinition:
    return RuleDefinition(
        rule_id="spirits.alcohol.format",
        cfr_citation="27 CFR §5.65(b)",
        applies_to_classes=(BeverageClass.SPIRITS,),
        reason_code="ALCOHOL_CONTENT.FORMAT.INVALID",
        severity=Severity.REJECT,
        match_policy="regex",
        validator="regex_match",
        parameters={
            "pattern": r"^\s*(?:alcohol|alc\.?)\s*[0-9]{1,2}(?:\.[0-9]+)?\s*%?\s*(?:by\s+volume|/\s*vol\.?|vol\.?)\s*$",
            "ignore_case": True,
        },
        evidence_required=("alc_text",),
        effective_date="2022-02-09",
        test_fixtures=(),
    )


# ---- fuzzy_brand --------------------------------------------------------

def test_fuzzy_brand_projects_dict_via_brand_name_key():
    """Cloud extractor emits {brand_name, confidence}; the validator must
    extract the brand string, not stringify the dict."""
    obs = _obs("brand_name", {"brand_name": "ACME BOURBON", "confidence": 0.95})
    exp = ExpectedValue(field_id="brand_name", value="ACME BOURBON")
    result = fuzzy_brand(obs, exp, _brand_rule(), _ctx())
    assert result.outcome == Outcome.PASS, "exact dict-projected match must pass"


def test_fuzzy_brand_no_expected_returns_not_applicable():
    """When no application supplied an expected brand, the rule has nothing
    to compare and must report NOT_APPLICABLE — not silently fail."""
    obs = _obs("brand_name", {"brand_name": "ACME BOURBON", "confidence": 0.95})
    exp = ExpectedValue(field_id="brand_name")  # no value
    result = fuzzy_brand(obs, exp, _brand_rule(), _ctx())
    assert result.outcome == Outcome.NOT_APPLICABLE


def test_fuzzy_brand_string_observation_still_works():
    """Backwards compat: hand-built fixtures pass strings."""
    obs = _obs("brand_name", "ACME BOURBON")
    exp = ExpectedValue(field_id="brand_name", value="ACME BOURBON")
    result = fuzzy_brand(obs, exp, _brand_rule(), _ctx())
    assert result.outcome == Outcome.PASS


# ---- regex_match (alcohol.format) --------------------------------------

def test_regex_match_synthesizes_alc_text_from_dict():
    """ABV dict {abv_pct, unit, confidence} must project to the string
    'ALCOHOL <pct>% BY VOLUME' the alc-format regex expects."""
    obs = _obs("abv", {"abv_pct": 40.0, "unit": "%", "confidence": 0.9})
    exp = ExpectedValue(field_id="abv")
    result = regex_match(obs, exp, _alcohol_format_rule(), _ctx())
    assert result.outcome == Outcome.PASS


def test_regex_match_dict_off_pattern_fails():
    obs = _obs("abv", {"abv_pct": 40.0, "unit": "PROOF", "confidence": 0.9})
    exp = ExpectedValue(field_id="abv")
    result = regex_match(obs, exp, _alcohol_format_rule(), _ctx())
    assert result.outcome == Outcome.FAIL


def test_regex_match_string_observation_still_works():
    """Backwards compat: legacy string observations match directly."""
    obs = _obs("abv", "ALCOHOL 40% BY VOLUME")
    exp = ExpectedValue(field_id="abv")
    result = regex_match(obs, exp, _alcohol_format_rule(), _ctx())
    assert result.outcome == Outcome.PASS
