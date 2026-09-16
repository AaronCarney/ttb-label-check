"""FakeEvaluator — controllable per-call latency + canned envelopes."""
import asyncio
import time

import pytest

from app.schemas.application import Application
from app.schemas.label import Label
from app.schemas.wire.disposition import DispositionEnvelope
from tests._fakes.evaluator import FakeEvaluator


def _stub_app(idx: int = 0) -> Application:
    return Application(application_id=f"app-{idx:04d}", evaluation_id=f"EV-{idx:04d}")


def _stub_label(idx: int = 0) -> Label:
    from tests.conftest import _stub_label as helper
    return helper(label_id=f"lbl-{idx:04d}")


@pytest.mark.asyncio
async def test_fake_evaluator_emits_canned_envelope_in_order():
    from tests.conftest import _stub_disposition_envelope

    plan = [(0.0, _stub_disposition_envelope(0)), (0.0, _stub_disposition_envelope(1))]
    fake = FakeEvaluator(plan)

    env_0 = await fake.evaluate(_stub_app(0), _stub_label(0))
    env_1 = await fake.evaluate(_stub_app(1), _stub_label(1))

    assert env_0.evaluation_id == "EV-0000"
    assert env_1.evaluation_id == "EV-0001"


@pytest.mark.asyncio
async def test_fake_evaluator_observes_per_call_latency():
    from tests.conftest import _stub_disposition_envelope

    plan = [(0.05, _stub_disposition_envelope(0))]
    fake = FakeEvaluator(plan)

    t0 = time.perf_counter()
    await fake.evaluate(_stub_app(0), _stub_label(0))
    elapsed = time.perf_counter() - t0
    assert 0.04 <= elapsed <= 0.20, f"latency outside band: {elapsed}"


@pytest.mark.asyncio
async def test_fake_evaluator_raises_when_plan_depleted():
    from tests.conftest import _stub_disposition_envelope

    plan = [(0.0, _stub_disposition_envelope(0))]
    fake = FakeEvaluator(plan)

    await fake.evaluate(_stub_app(0), _stub_label(0))
    with pytest.raises(AssertionError, match="depleted"):
        await fake.evaluate(_stub_app(1), _stub_label(1))


@pytest.mark.asyncio
async def test_fake_evaluator_factory_repeats_envelope_for_n_items():
    from tests.conftest import _fake_evaluator

    fake = _fake_evaluator(n_items=3, latency_s=0.0)
    out = []
    for i in range(3):
        out.append(await fake.evaluate(_stub_app(i), _stub_label(i)))
    assert len(out) == 3
    assert all(isinstance(env, DispositionEnvelope) for env in out)


@pytest.mark.asyncio
async def test_stub_disposition_envelope_is_schema_conformant():
    """The stub must round-trip through Pydantic without `extra=forbid` rejection."""
    from tests.conftest import _stub_disposition_envelope

    env = _stub_disposition_envelope(0)
    # Round-trip
    dump = env.model_dump(mode="json")
    rebuilt = DispositionEnvelope.model_validate(dump)
    assert rebuilt.evaluation_id == env.evaluation_id
