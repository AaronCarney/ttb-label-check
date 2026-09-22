"""An import whose origin statement the reader did not find goes to a reviewer,
under the origin rule's own code.

FR-3: the reader not finding an element does not show the label lacks it, and
for country of origin the product also reads only the English name, so it
cannot tell a label with no statement from one that states it in another form
19 CFR 134.45 accepts. The check reached needs review before this, but only
because the confidence floor caught a rejection built on a reading of nothing,
and the reviewer was told the reading was poor rather than that no origin
statement was found.

Through `engine.evaluate` and the shipped pack, because the floor runs in
`YamlRuleEngine._finish` and a validator-level test cannot see it.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest

from app.rules.loader import YamlRuleLoader
from app.rules.yaml_engine import BELOW_CONFIDENCE_FLOOR, YamlRuleEngine
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import Outcome, Severity
from app.services.disposition import rule_disposition
from app.vision.local import _parse
from tests.rules.fixtures import make_context, make_expected


@pytest.fixture(scope="module")
def ruleset():
    """The shipped rule pack, loaded the way the application loads it."""
    import app.rules._validators as _validators

    for _, modname, _ in pkgutil.iter_modules(_validators.__path__):
        importlib.import_module(f"{_validators.__name__}.{modname}")
    return YamlRuleLoader().load(Path("rules"))


def _unfound_origin(beverage_class: BeverageClass) -> FieldObservation:
    """What the local reader reports for a label on which it found no origin
    statement, taken from its own parser so the fixture cannot drift."""
    payload, bbox, text = _parse(boxes=[], warning_boxes=[], rotation=0, heading_measurement=None)[
        "country_origin"
    ]
    assert payload["country"] == "" and bbox is None and text is None
    return FieldObservation(
        field_id="country_origin",
        beverage_class=beverage_class,
        observed_value=payload,
        evidence=(
            Evidence(
                field_id="country_origin",
                source=EvidenceSource.OCR,
                bbox=None,
                extracted_text=None,
                match_kind=MatchKind.NONE,
                confidence=0.0,
            ),
        ),
        upstream_meta={"bbox": None},
    )


async def _origin_result(ruleset, beverage_class: BeverageClass, source: str):
    engine = YamlRuleEngine(ruleset)
    results = await engine.evaluate(
        [_unfound_origin(beverage_class)],
        [
            make_expected(
                field_id="country_of_origin",
                value="IRELAND",
                parameters={"source_of_product": source},
            )
        ],
        make_context(assets=ruleset.assets, decision_tables=ruleset.decision_tables),
    )
    found = [r for r in results if r.rule_id.endswith(".origin.matches_application")]
    assert len(found) == 1, [r.rule_id for r in results]
    return found[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "beverage_class", [BeverageClass.SPIRITS, BeverageClass.WINE, BeverageClass.MALT]
)
async def test_an_unread_origin_on_an_import_is_a_review_under_an_origin_code(
    ruleset, beverage_class
) -> None:
    result = await _origin_result(ruleset, beverage_class, "imported")

    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.severity is Severity.WARN
    assert result.reason_code == "ORIGIN.PRESENCE.NOT_READ"
    assert result.reason_code != BELOW_CONFIDENCE_FLOOR
    assert rule_disposition(result) == "needs_review"
    assert "134.45" in (result.message or "")


@pytest.mark.asyncio
async def test_a_domestic_product_still_has_no_origin_check(ruleset) -> None:
    result = await _origin_result(ruleset, BeverageClass.SPIRITS, "domestic")

    assert result.outcome is Outcome.NOT_APPLICABLE
    assert result.reason_code is None
