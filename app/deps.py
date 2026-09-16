"""DI container — selects the VisionExtractor named by the environment."""
from __future__ import annotations

from app.config import Settings
from app.logging.ring_buffer import new_call_ring_buffer
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
    ring = new_call_ring_buffer()
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


_vision_singleton: "tuple[str, VisionExtractor] | None" = None


def get_vision_extractor(settings: Settings) -> VisionExtractor:
    """Process-wide reader, so a label does not pay for loading the models.

    The local reader reads about a second of OCR models off disk the first time
    it is asked for text. Built per request, that second landed on every label,
    ``/healthz`` warmed a reader it then threw away, and the reader's call ring
    buffer died with the request that made it. One reader for the process pays
    the load once and keeps the record.

    Keyed by ``VISION_MODE`` so a process told to use the other reader gets the
    one it asked for rather than the one it built first (decision 0005).
    """
    global _vision_singleton
    if _vision_singleton is None or _vision_singleton[0] != settings.vision_mode:
        _vision_singleton = (settings.vision_mode, build_vision_extractor(settings))
    return _vision_singleton[1]


def reset_vision_extractor() -> None:
    """Test-only: drop the shared reader so the next call builds a new one."""
    global _vision_singleton
    _vision_singleton = None


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
    """Construct an Evaluator wired to all three real dependencies."""
    from app.rules import build_rule_engine
    from app.services.evaluator import Evaluator
    vision = get_vision_extractor(settings)
    rules = build_rule_engine(settings)
    cache = _get_session_cache()
    return Evaluator(vision=vision, rules=rules, settings=settings, cache=cache)
