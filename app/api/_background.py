"""Holding on to a background task for as long as it runs.

`asyncio.create_task` returns the only strong reference to the task it makes;
the event loop keeps a weak one. Drop the return value and the garbage
collector may take the task mid-execution, which ends the work with nothing
logged and nothing raised. asyncio's own documentation says to save the
result for this reason.

Every background task this application starts goes through `spawn`, so there
is one place that holds them and one place that can wait for them at shutdown.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any


def spawn(app, coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> asyncio.Task:
    """Start `coro`, and keep it on `app.state.batch_tasks` until it ends.

    The done callback removes it again, so the set holds what is running
    rather than growing for the life of the process.
    """
    task = asyncio.create_task(coro, name=name)
    tasks: set[asyncio.Task] = app.state.batch_tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return task


async def drain(app) -> int:
    """Cancel every task still running and wait for it. Returns how many.

    Shutdown clears the in-flight batch state these tasks are working
    against, so leaving them running would have them write into state that
    has been thrown away.
    """
    tasks: set[asyncio.Task] = app.state.batch_tasks
    outstanding = [t for t in tasks if not t.done()]
    for task in outstanding:
        task.cancel()
    if outstanding:
        await asyncio.gather(*outstanding, return_exceptions=True)
    tasks.clear()
    return len(outstanding)
