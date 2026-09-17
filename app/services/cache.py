"""SessionCache — bounded LRU keyed by canonical input hash.

Within a session, the same canonicalized input returns the same envelope, with
a refreshed evaluation_id at the call site, so a repeated check is deterministic
and costs nothing. Nothing is persisted across process restarts.
"""

from __future__ import annotations

from collections import OrderedDict

from app.schemas.wire.disposition import DispositionEnvelope


class SessionCache:
    def __init__(self, *, maxsize: int = 128) -> None:
        self._maxsize = maxsize
        self._items: OrderedDict[str, DispositionEnvelope] = OrderedDict()

    def get(self, key: str) -> DispositionEnvelope | None:
        env = self._items.get(key)
        if env is not None:
            self._items.move_to_end(key)
        return env

    def put(self, key: str, envelope: DispositionEnvelope) -> None:
        self._items[key] = envelope
        self._items.move_to_end(key)
        while len(self._items) > self._maxsize:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
