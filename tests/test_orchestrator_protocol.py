import inspect

import pytest

from app.orchestrator.base import Orchestrator


def test_orchestrator_is_abstract():
    with pytest.raises(TypeError):
        Orchestrator()  # type: ignore[abstract]


def test_refine_is_abstract_coroutine():
    assert inspect.iscoroutinefunction(Orchestrator.refine)
    assert getattr(Orchestrator.refine, "__isabstractmethod__", False)


def test_ensure_client_is_abstract_coroutine():
    assert inspect.iscoroutinefunction(Orchestrator.ensure_client)
    assert getattr(Orchestrator.ensure_client, "__isabstractmethod__", False)


def test_orchestrator_signature():
    sig = inspect.signature(Orchestrator.refine)
    params = list(sig.parameters.keys())
    assert params == ["self", "application", "observations", "validation_results"]
