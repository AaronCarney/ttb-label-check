"""The Evaluator's constructor signature: every dependency arrives by injection,
so a test can substitute any of them."""
import inspect

from app.services.evaluator import Evaluator


def test_evaluator_init_accepts_4_deps():
    sig = inspect.signature(Evaluator.__init__)
    params = list(sig.parameters.keys())
    for name in ("vision", "rules", "settings", "cache"):
        assert name in params


def test_evaluate_is_coroutine():
    assert inspect.iscoroutinefunction(Evaluator.evaluate)


def test_evaluate_signature():
    sig = inspect.signature(Evaluator.evaluate)
    params = list(sig.parameters.keys())
    assert params == ["self", "application", "label"]
