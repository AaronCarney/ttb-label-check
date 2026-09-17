"""DI container — selects the VisionExtractor named by the environment."""

from __future__ import annotations

import threading

from app.config import Settings
from app.logging.ring_buffer import new_call_ring_buffer
from app.services.cache import SessionCache
from app.services.evaluator import Evaluator
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


_local_reader_singleton: VisionExtractor | None = None
_local_reader_build_lock = threading.Lock()


def get_vision_extractor(settings: Settings) -> VisionExtractor:
    """The reader for this request, sharing the local one across the process.

    The local reader reads about a second of OCR models off disk the first time
    it is asked for text. Built per request, that second landed on every label,
    ``/healthz`` warmed a reader it then threw away, and the reader's call ring
    buffer died with the request that made it. One local reader for the process
    pays the load once and keeps the record.

    The cloud reader is still built per request, because sharing it buys nothing
    and costs something. It loads no models — its ``ensure_loaded`` returns
    immediately — and it holds an ``asyncio.Semaphore``, which binds to the
    first event loop that awaits it and rejects the next. A per-request
    instance never meets a second loop; a process-wide one would.
    """
    if settings.vision_mode == "cloud":
        return build_vision_extractor(settings)

    global _local_reader_singleton
    if _local_reader_singleton is None:
        with _local_reader_build_lock:
            # Checked again inside the lock: two threads arriving together must
            # load the models once, not twice.
            if _local_reader_singleton is None:
                _local_reader_singleton = build_vision_extractor(settings)
    return _local_reader_singleton


def reset_vision_extractor() -> None:
    """Test-only: drop the shared reader so the next call builds a new one."""
    global _local_reader_singleton
    _local_reader_singleton = None


_session_cache_singleton: SessionCache | None = None


def _get_session_cache() -> SessionCache:
    """Process-wide singleton so the session cache survives across requests.
    Fresh-per-request would defeat the cache: identical (app, image) inputs
    must hit the same SessionCache instance to be deduplicated."""
    global _session_cache_singleton
    if _session_cache_singleton is None:
        _session_cache_singleton = SessionCache(maxsize=128)
    return _session_cache_singleton


def reset_session_cache() -> None:
    """Test-only: drop the singleton so a fresh cache is constructed on next
    build_evaluator call. Use in tests that need cache-empty preconditions."""
    global _session_cache_singleton
    _session_cache_singleton = None


def build_evaluator(settings: Settings) -> Evaluator:
    """Construct an Evaluator wired to all three real dependencies."""
    # `app.rules` imports this module, so this one import stays deferred.
    from app.rules import build_rule_engine

    vision = get_vision_extractor(settings)
    rules = build_rule_engine(settings)
    cache = _get_session_cache()
    return Evaluator(vision=vision, rules=rules, settings=settings, cache=cache)
