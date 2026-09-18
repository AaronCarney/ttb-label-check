"""Every check leaves one log line saying how it came out.

Before this, a check that succeeded logged nothing, so an operator could tell
the service was running and could not tell what it was answering. The line
carries the outcome, the reason code behind it, and what the check cost, under
the evaluation's id — and nothing from the application or the label
(`docs/PRD.md` C-2).
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from app.config import Settings
from app.logging.otel_genai import OtelGenAIFormatter
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label
from tests.test_evaluator_timeouts import _reading

# Text that only the label carries. It must reach no log line.
_READ_OFF_THE_LABEL = "Old Overholt Straight Rye"


@pytest.fixture(autouse=True)
def _readable_image(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )


def _finished_lines(caplog) -> list[dict]:
    formatter = OtelGenAIFormatter()
    return [
        json.loads(formatter.format(r))
        for r in caplog.records
        if r.name == "app.services.evaluator" and r.getMessage().startswith("evaluation_finished")
    ]


async def _check(evaluator: Evaluator, evaluation_id: str):
    return await evaluator.evaluate(
        application=Application(
            application_id="A",
            evaluation_id=evaluation_id,
            beverage_class=BeverageClass.SPIRITS,
        ),
        label=_stub_label(),
    )


async def test_a_check_that_succeeds_logs_its_outcome(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.services.evaluator")
    evaluator = Evaluator(
        vision=FakeVisionExtractor(observations=[_reading("brand_name", _READ_OFF_THE_LABEL)]),
        rules=FakeRuleEngine(results=()),
        settings=Settings(),
    )
    envelope = await _check(evaluator, "EV-LOG-1")

    lines = _finished_lines(caplog)
    assert len(lines) == 1, lines
    line = lines[0]
    assert line["evaluation_id"] == "EV-LOG-1"
    assert f"disposition={envelope.disposition}" in line["msg"]
    assert line["reason_code"]
    assert isinstance(line["duration_ms"], int)


async def test_a_check_that_times_out_names_the_timeout(caplog) -> None:
    """The fieldless envelope's first trace row is the rule-pack selection, and
    naming that would say the check was about which rules applied."""
    caplog.set_level(logging.INFO, logger="app.services.evaluator")

    class SlowRules(FakeRuleEngine):
        async def evaluate(self, *a, **kw):
            await asyncio.sleep(10)
            return ()

    evaluator = Evaluator(
        vision=FakeVisionExtractor(observations=[]),
        rules=SlowRules(results=()),
        settings=Settings(),
    )
    evaluator._sla_seconds = 0.1
    await _check(evaluator, "EV-LOG-2")

    lines = _finished_lines(caplog)
    assert len(lines) == 1, lines
    assert lines[0]["reason_code"] == "ENGINE.SLA.TIMEOUT"
    assert "disposition=needs_review" in lines[0]["msg"]


async def test_nothing_read_off_the_label_reaches_a_log_line(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    evaluator = Evaluator(
        vision=FakeVisionExtractor(observations=[_reading("brand_name", _READ_OFF_THE_LABEL)]),
        rules=FakeRuleEngine(results=()),
        settings=Settings(),
    )
    await _check(evaluator, "EV-LOG-3")

    formatter = OtelGenAIFormatter()
    written = "\n".join(formatter.format(r) for r in caplog.records)
    assert "evaluation_finished" in written
    assert _READ_OFF_THE_LABEL not in written
