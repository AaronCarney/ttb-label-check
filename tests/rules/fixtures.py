"""Test builders for the rule-engine unit tests. The rule set itself is YAML;
the rule inputs here are Python builders, so the tests stay skim-readable.
"""
from __future__ import annotations

import importlib
import pkgutil
from decimal import Decimal
from typing import Any

from app.rules._validators import ValidatorContext
from app.schemas.expected import BeverageClass, ExpectedValue
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import EngineMeta, Severity
from app.schemas.rules import AssetRef, DecisionTable, MatchPolicy, RuleDefinition


def load_all_validators() -> None:
    """Register every validator, the way the running app does.

    A validator registers itself when its module is imported, and
    `YamlRuleLoader` refuses to load a pack that names a validator the registry
    has not got. The app never hits that: `app/rules/__init__.py` walks the
    validator package and imports every module before it loads the pack. A test
    that loads the pack itself has to do the same thing, and the ones that
    listed the modules by hand instead loaded only while some other test file in
    the same run happened to import the rest first.
    """
    package = importlib.import_module("app.rules._validators")
    for module in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"app.rules._validators.{module.name}")


def make_evidence(
    *,
    field_id: str = "field",
    text: str = "",
    confidence: float = 0.95,
    kind: MatchKind = MatchKind.NORMALIZED,
    source: EvidenceSource = EvidenceSource.OCR,
    bbox: tuple[int, int, int, int] | None = None,
    notes: str | None = None,
) -> Evidence:
    return Evidence(
        field_id=field_id,
        source=source,
        bbox=bbox,
        extracted_text=text or None,
        normalized_text=text or None,
        match_kind=kind,
        confidence=confidence,
        notes=notes,
    )


def _evidence_text(value: Any) -> str:
    """The text a reader would have recorded for this payload.

    Both readers put the string they read on the label into
    `Evidence.extracted_text`, and leave it empty for a field they did not find
    (`app/vision/local.py`, `app/vision/cloud.py`). This fixture used to put
    `str(value)` there, so a dict payload whose reading was empty carried the
    dict's repr as its evidence text and looked like a field the reader had
    found - which is the one thing `unlocated` in
    `app/rules/_validators/_helpers.py` asks about.
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        for v in value.values():
            if isinstance(v, str) and v.strip():
                return v
        return ""
    return str(value)


def make_obs(
    *,
    field_id: str,
    value: Any,
    beverage_class: BeverageClass = BeverageClass.SPIRITS,
    confidence: float = 0.95,
    extra_evidence: tuple[Evidence, ...] = (),
    upstream_meta: dict[str, Any] | None = None,
) -> FieldObservation:
    base = make_evidence(field_id=field_id, text=_evidence_text(value), confidence=confidence)
    return FieldObservation(
        field_id=field_id,
        beverage_class=beverage_class,
        observed_value=value,
        evidence=(base, *extra_evidence),
        upstream_meta=upstream_meta or {},
    )


def make_expected(
    *,
    field_id: str,
    value: Any = None,
    aliases: tuple[str, ...] = (),
    abv_labeled_pct: Decimal | None = None,
    container_volume_ml: Decimal | None = None,
    parameters: dict[str, Any] | None = None,
) -> ExpectedValue:
    return ExpectedValue(
        field_id=field_id,
        value=value,
        aliases=aliases,
        abv_labeled_pct=abv_labeled_pct,
        container_volume_ml=container_volume_ml,
        parameters=parameters or {},
    )


def make_rule(
    *,
    rule_id: str,
    cfr_citation: str,
    validator: str,
    reason_code: str,
    applies_to_classes: tuple[BeverageClass, ...] = (BeverageClass.SPIRITS,),
    severity: Severity = Severity.REJECT,
    match_policy: MatchPolicy = MatchPolicy.EXACT,
    parameters: dict[str, Any] | None = None,
    tolerance: dict[str, Any] | None = None,
    decision_table: dict[str, Any] | None = None,
    decision_table_ref: str | None = None,
    asset: dict[str, Any] | None = None,
    rule_pack: str = "test_pack",
    rule_pack_version: str = "0.1.0",
    test_fixtures: tuple[str, ...] = ("F-TEST-01",),
    evidence_required: tuple[str, ...] = (),
) -> RuleDefinition:
    return RuleDefinition(
        rule_id=rule_id,
        cfr_citation=cfr_citation,
        applies_to_classes=applies_to_classes,
        reason_code=reason_code,
        severity=severity,
        match_policy=match_policy,
        validator=validator,
        evidence_required=evidence_required,
        parameters=parameters or {},
        tolerance=tolerance,
        decision_table=decision_table,
        decision_table_ref=decision_table_ref,
        asset=asset,
        effective_date="2026-09-09",
        rule_pack=rule_pack,
        rule_pack_version=rule_pack_version,
        test_fixtures=test_fixtures,
    )


def make_engine_meta(
    *,
    engine_version: str = "0.1.0",
    rule_pack: str = "test_pack",
    rule_pack_version: str = "0.1.0",
    started_at_ms: int = 0,
    elapsed_ms: int = 0,
) -> EngineMeta:
    return EngineMeta(
        engine_version=engine_version,
        rule_pack_version=rule_pack_version,
        rule_pack=rule_pack,
        started_at_ms=started_at_ms,
        elapsed_ms=elapsed_ms,
    )


def make_context(
    *,
    assets: dict[str, AssetRef] | None = None,
    decision_tables: dict[str, DecisionTable] | None = None,
    started_at_ms: int = 0,
    engine_version: str = "0.1.0",
) -> ValidatorContext:
    return ValidatorContext(
        assets=assets or {},
        decision_tables=decision_tables or {},
        started_at_ms=started_at_ms,
        engine_version=engine_version,
    )
