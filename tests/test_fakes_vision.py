"""FakeVisionExtractor — Protocol-compatible (extract + ensure_loaded + warm)."""

import pytest

from app.schemas.extracted import FieldObservation
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label  # the canonical Label factory


def test_fake_vision_satisfies_protocol():
    from app.vision.base import VisionExtractor

    fake = FakeVisionExtractor(observations=[])
    assert isinstance(fake, VisionExtractor)


@pytest.mark.asyncio
async def test_fake_vision_returns_canned():
    obs: list[FieldObservation] = []
    fake = FakeVisionExtractor(observations=obs)
    result = await fake.extract(_stub_label())
    assert result == obs


@pytest.mark.asyncio
async def test_fake_vision_ensure_loaded_is_noop():
    fake = FakeVisionExtractor(observations=[])
    # Protocol method must exist and be awaitable.
    await fake.ensure_loaded()


@pytest.mark.asyncio
async def test_fake_vision_warm_is_noop():
    fake = FakeVisionExtractor(observations=[])
    # Protocol method must exist and be awaitable.
    await fake.warm()
