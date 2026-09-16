"""Regression: build_evaluator must share one SessionCache across calls.

A fresh SessionCache(maxsize=128) per invocation would make the cache useless
in production, where the endpoint calls build_evaluator once per request and
the same submission would be read again every time. The SessionCache is a
module-level singleton reached through _get_session_cache(); this test anchors
that."""
from app.config import Settings
from app.deps import build_evaluator, reset_session_cache


def test_build_evaluator_shares_session_cache_across_calls():
    reset_session_cache()
    settings = Settings()
    e1 = build_evaluator(settings)
    e2 = build_evaluator(settings)
    assert e1._cache is e2._cache, (
        "SessionCache must be a process singleton; per-request "
        "construction would make the cache dead code"
    )


def test_reset_session_cache_drops_singleton():
    reset_session_cache()
    settings = Settings()
    e1 = build_evaluator(settings)
    reset_session_cache()
    e2 = build_evaluator(settings)
    assert e1._cache is not e2._cache, "reset_session_cache must drop the singleton"
