"""``CallRecord`` deque construction.

This module ships the constructor only, so a layer can hold a reference at
startup; the reader and orchestrator do the recording into it.
"""
from __future__ import annotations

from collections import deque
from typing import Any


DEFAULT_MAXLEN = 200


def new_call_ring_buffer(maxlen: int = DEFAULT_MAXLEN) -> deque[Any]:
    """Return an empty bounded deque for ``CallRecord`` entries (FIFO eviction)."""

    return deque(maxlen=maxlen)
