"""Sliding-window anomaly detector.

Default M=5, N=10. Fires an advisory when M of the last N observations share
the same reason code. The advisory carries a UUID4 ``advisory_id`` so the
dismiss endpoint can validate the dismissal corresponds to the still-outstanding
advisory (idempotent against double-dismissal; rejects stale tabs).
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class AnomalyAdvisory:
    """One anomaly-advisory event."""

    advisory_id: str
    reason_code: str
    count: int
    window: int


class AnomalyDetector:
    """Sliding M-of-N detector. Stateful; not thread-safe (asyncio single-threaded)."""

    def __init__(self, *, window_n: int = 10, threshold_m: int = 5) -> None:
        if threshold_m < 1 or threshold_m > window_n:
            raise ValueError(
                f"threshold_m must satisfy 1 <= m <= n; got m={threshold_m} n={window_n}"
            )
        self.window_n = window_n
        self.threshold_m = threshold_m
        self._window: deque[str | None] = deque(maxlen=window_n)
        self._outstanding_advisory_id: str | None = None

    def observe(self, reason_code: str | None) -> AnomalyAdvisory | None:
        """Record one observation. Return an advisory iff the threshold is
        crossed AND no advisory is currently outstanding (dismiss-required-first)."""
        self._window.append(reason_code)
        if self._outstanding_advisory_id is not None:
            return None  # already fired — wait for dismiss
        if reason_code is None:
            return None  # None doesn't count toward any threshold

        # Count occurrences of reason_code in the window
        count = sum(1 for c in self._window if c == reason_code)
        if count >= self.threshold_m:
            advisory = AnomalyAdvisory(
                advisory_id=str(uuid.uuid4()),
                reason_code=reason_code,
                count=count,
                window=self.window_n,
            )
            self._outstanding_advisory_id = advisory.advisory_id
            return advisory
        return None

    def dismiss(self, advisory_id: str) -> None:
        """Clear the window iff ``advisory_id`` matches the outstanding advisory.
        Idempotent against double-dismissal and stale tabs."""
        if self._outstanding_advisory_id == advisory_id:
            self._window.clear()
            self._outstanding_advisory_id = None
