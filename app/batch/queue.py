"""Bounded queue — typed wrapper around ``asyncio.Queue(maxsize=k+1)``.

The single structural enforcement of pull-based demand. The wrapper
exists so (1) the worker depends on a stable import shape, (2) tests can
assert ``saturated`` deterministically, and (3) a future swap to a different
bounded primitive is a one-file change.
"""

from __future__ import annotations

import asyncio


class BoundedQueue[T]:
    """Thin typed wrapper around ``asyncio.Queue``."""

    def __init__(self, *, lookahead_k: int) -> None:
        if lookahead_k < 1:
            raise ValueError(f"lookahead_k must be >= 1, got {lookahead_k}")
        self._inner: asyncio.Queue[T] = asyncio.Queue(maxsize=lookahead_k + 1)
        self._lookahead_k = lookahead_k

    @property
    def maxsize(self) -> int:
        return self._inner.maxsize

    @property
    def saturated(self) -> bool:
        return self._inner.full()

    def qsize(self) -> int:
        return self._inner.qsize()

    async def put(self, item: T) -> None:
        await self._inner.put(item)

    async def get(self) -> T:
        return await self._inner.get()
