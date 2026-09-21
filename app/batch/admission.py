"""Which batch the service is holding, and whether it will take another.

One batch at a time (`docs/decisions.md#0041`). A batch is started from the
form on `POST /` or from `POST /batches`; the reviewer is taken to its results
and watches them arrive. While it is being checked, a second one is refused. Once
it is finished it is kept only until the next one starts, so its results stay
readable until then and no longer.

There is no login, so the service cannot tell the reviewer who started the
running batch from anyone else. The limit is therefore one batch per running
copy of the service, and whoever uploads while one runs is told to wait.
"""

from __future__ import annotations

import asyncio
import time

from app.api import _background
from app.api._sse_bus import SSEBus
from app.batch.state import InFlightBatch


class BatchInProgress(Exception):
    """A batch is still being checked, so another cannot start."""

    def __init__(self, checked: int, total: int) -> None:
        self.checked = checked
        self.total = total
        super().__init__(
            f"Another batch is still being checked ({checked} of {total} labels done). "
            "This service checks one batch at a time; upload again when it has finished."
        )


def _running(app) -> InFlightBatch | None:
    """The batch whose worker has not ended, or None.

    Read off the worker task rather than the results: a worker that stopped on
    an error leaves its results short but is not running, and must not hold the
    service shut.
    """
    if not any(not task.done() for task in app.state.batch_tasks):
        return None
    for in_flight in app.state.batches.values():
        if len(in_flight.results) < len(in_flight.items):
            return in_flight
    return None


def start(app, in_flight: InFlightBatch, bus: SSEBus, worker) -> None:
    """Drop the finished batch, register this one, and start its worker.

    Raises `BatchInProgress` if a batch is still being checked. The check and
    the start run with no `await` between them, so two uploads arriving
    together cannot both pass it.
    """
    running = _running(app)
    if running is not None:
        raise BatchInProgress(len(running.results), len(running.items))
    app.state.batches.clear()
    app.state.buses.clear()
    app.state.batches[in_flight.batch_id] = in_flight
    app.state.buses[in_flight.batch_id] = bus
    _background.spawn(app, worker.run(), name=f"batch-worker:{in_flight.batch_id}")


def _checked(app, in_flight: InFlightBatch) -> bool:
    """Whether the batch has every result, or its worker has ended without them."""
    if len(in_flight.results) >= len(in_flight.items):
        return True
    name = f"batch-worker:{in_flight.batch_id}"
    return not any(task.get_name() == name and not task.done() for task in app.state.batch_tasks)


async def wait_until_checked(app, in_flight: InFlightBatch, *, timeout: float) -> None:
    """Return once the batch is checked, or after `timeout` seconds.

    The caller's request stays open for as long as this runs, and an open
    request is what keeps the service allocated CPU (`docs/decisions.md#0049`).
    """
    deadline = time.monotonic() + timeout
    while not _checked(app, in_flight) and time.monotonic() < deadline:
        await asyncio.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
