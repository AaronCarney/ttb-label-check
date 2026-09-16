"""DI container — selects VisionExtractor and Orchestrator per env."""
from __future__ import annotations

from collections import deque

from app.config import Settings
from app.orchestrator.base import Orchestrator
from app.orchestrator.openai_strict import OpenAIStrictOrchestrator
from app.orchestrator.anthropic_strict import AnthropicStrictOrchestrator
from app.vision.base import VisionExtractor
from app.vision.cloud import CloudVisionExtractor
from app.vision.local import LocalVisionExtractor


def build_vision_extractor(settings: Settings) -> VisionExtractor:
    """The reader named by VISION_MODE (decision 0005).

    `local` is the default and needs nothing from outside the process.
    `cloud` is selected explicitly and needs a key; asking for it without one
    is a configuration error, and saying so here beats failing per request
    with an authentication error from the vendor.
    """
    ring: deque = deque(maxlen=200)
    if settings.vision_mode == "cloud":
        if not settings.openai_api_key:
            raise ValueError(
                "VISION_MODE=cloud needs OPENAI_API_KEY. Unset VISION_MODE to "
                "use the local reader, which needs no key."
            )
        return CloudVisionExtractor(
            settings=settings,
            ring_buffer=ring,
            api_key=settings.openai_api_key,
        )
    return LocalVisionExtractor(settings=settings, ring_buffer=ring)


def build_orchestrator(settings: Settings) -> Orchestrator:
    backend = settings.orchestrator_backend
    ring: deque = deque(maxlen=200)
    if backend == "openai":
        return OpenAIStrictOrchestrator(
            settings=settings, ring_buffer=ring, api_key=settings.openai_api_key or ""
        )
    if backend == "anthropic":
        return AnthropicStrictOrchestrator(
            settings=settings, ring_buffer=ring, api_key=settings.anthropic_api_key or "",
        )
    raise ValueError(f"Unknown orchestrator_backend: {backend!r}")


_session_cache_singleton: "SessionCache | None" = None


def _get_session_cache() -> "SessionCache":
    """Process-wide singleton so the session cache survives across requests.
    Fresh-per-request would defeat the cache: identical (app, image) inputs
    must hit the same SessionCache instance to be deduplicated."""
    global _session_cache_singleton
    if _session_cache_singleton is None:
        from app.services.cache import SessionCache
        _session_cache_singleton = SessionCache(maxsize=128)
    return _session_cache_singleton


def reset_session_cache() -> None:
    """Test-only: drop the singleton so a fresh cache is constructed on next
    build_evaluator call. Use in tests that need cache-empty preconditions."""
    global _session_cache_singleton
    _session_cache_singleton = None


def build_evaluator(settings: "Settings") -> "Evaluator":
    """Construct an Evaluator wired to all four real dependencies."""
    from app.rules import build_rule_engine
    from app.services.evaluator import Evaluator
    vision = build_vision_extractor(settings)
    rules = build_rule_engine(settings)
    orchestrator = build_orchestrator(settings)
    cache = _get_session_cache()
    return Evaluator(vision=vision, rules=rules, orchestrator=orchestrator, settings=settings, cache=cache)
