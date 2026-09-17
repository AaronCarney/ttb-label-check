"""A label carrying no government warning must be reported as violating
27 CFR §16.21 — not as "we could not read it confidently".

§16.21 makes the *absence* of the health warning the finding itself, and
`rules/common/health_warning.yaml` is the one place in any pack allowed to read
"the reader did not find it" as "the label does not carry it"
(`unlocated_is_absent: true`). This file proves that policy actually reaches a
reviewer's answer.

Why it needs its own file, through `engine.evaluate`:
`tests/rules/test_warning_rules.py` calls the validator directly, which is the
one path that skips `YamlRuleEngine._finish` — and `_finish` is where the
confidence floor runs. A validator-level test cannot see what the floor does to
the validator's verdict, so the absent-warning rejection could be rewritten on
its way out and no test would notice.

`tests/rules/test_confidence_floor.py` looks like it covers the carve-out, but
its case builds `evidence=()` by hand. The local reader never emits that: it
attaches one `Evidence` item to every field it was asked about, including the
ones it did not find. So the carve-out's condition is satisfied only in a
fixture, never in production.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest

from app.rules.loader import YamlRuleLoader
from app.rules.yaml_engine import YamlRuleEngine
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import Outcome, Severity
from app.services.disposition import compute_disposition, rule_disposition
from app.vision.local import _parse
from tests.rules.fixtures import make_context, make_expected


@pytest.fixture(scope="module")
def ruleset():
    """The shipped rule pack, loaded the way the application loads it."""
    import app.rules._validators as _validators

    for _, modname, _ in pkgutil.iter_modules(_validators.__path__):
        importlib.import_module(f"{_validators.__name__}.{modname}")
    return YamlRuleLoader().load(Path("rules"))


def _unfound_warning_payload() -> dict:
    """What the local reader really reports for a label with no warning on it.

    Taken from the reader's own parser rather than written out here, so the
    fixture cannot drift away from production: `_parse` is what `extract` calls,
    and an empty reading is what a label with no warning block produces.
    """
    payload, bbox, text = _parse(boxes=[], warning_boxes=[], rotation=0, heading_measurement=None)[
        "gov_warning"
    ]
    assert payload["text"] == ""
    assert payload["confidence"] == 0.0
    assert bbox is None and text is None
    return payload


def _unfound_warning_observation() -> FieldObservation:
    """The observation `LocalVisionExtractor.extract` builds from that payload.

    One `Evidence` item, no box, no text, confidence 0.0 — the reader attaches
    one to every field in `_FIELD_NAMES` whether it found the field or not.
    """
    return FieldObservation(
        field_id="gov_warning",
        beverage_class=BeverageClass.SPIRITS,
        observed_value=_unfound_warning_payload(),
        evidence=(
            Evidence(
                field_id="gov_warning",
                source=EvidenceSource.OCR,
                bbox=None,
                extracted_text=None,
                match_kind=MatchKind.NONE,
                confidence=0.0,
            ),
        ),
        upstream_meta={"bbox": None},
    )


@pytest.mark.asyncio
async def test_a_label_with_no_warning_is_reported_as_a_16_21_violation(ruleset) -> None:
    """The finding §16.21 requires, as it leaves the engine.

    An applicant who submits a label with no government warning must be told the
    warning is missing. Reporting it as a reading problem tells them to take a
    better photograph of a label that is non-compliant however well it is
    photographed.
    """
    engine = YamlRuleEngine(ruleset)
    results = await engine.evaluate(
        [_unfound_warning_observation()],
        [make_expected(field_id="gov_warning")],
        make_context(assets=ruleset.assets, decision_tables=ruleset.decision_tables),
    )
    present = [r for r in results if r.rule_id == "common.warning.present"]
    assert len(present) == 1, [r.rule_id for r in results]
    result = present[0]

    assert result.outcome is Outcome.FAIL
    assert result.reason_code == "WARNING.PRESENCE.MISSING"
    assert result.severity is Severity.REJECT
    assert rule_disposition(result) == "fail"


@pytest.mark.asyncio
async def test_the_submission_is_rejected_not_sent_to_a_reviewer(ruleset) -> None:
    """The answer the applicant actually reads. A missing warning is a rejection,
    not a queue entry."""
    engine = YamlRuleEngine(ruleset)
    results = await engine.evaluate(
        [_unfound_warning_observation()],
        [make_expected(field_id="gov_warning")],
        make_context(assets=ruleset.assets, decision_tables=ruleset.decision_tables),
    )
    assert compute_disposition(results) == "fail"
