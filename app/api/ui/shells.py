"""The two pages a reviewer sees: where they submit, and where results arrive.

Template rendering only. This module imports nothing from ``app.services``,
``app.vision``, ``app.rules`` or ``app.deps``, because serving a page needs
none of them: the React island it mounts fetches its data from the JSON API
(``app.api.batches``, ``app.api.overrides``), and the route that runs the
engine lives beside this module rather than in it (``app.api.ui.submit``).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.ui._page import _get_settings, templates
from app.config import Settings

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def entry_page(
    request: Request,
    settings: Settings = Depends(_get_settings),
) -> HTMLResponse:
    """The way in, for one label or three hundred.

    A plain form with no island on it: nothing here has a result to render yet,
    and the results page is where a check is watched. The reviewer uploads the
    label's photographs and the application filed for them, or a folder of
    labels and the applications as a CSV, and `POST /` starts the check.
    """
    return templates.TemplateResponse(
        request=request,
        name="check.html",
        context={"dev_mode": settings.dev_mode},
    )


@router.get("/batch/{batch_id}", response_class=HTMLResponse)
async def results_page(
    request: Request,
    batch_id: str,
    settings: Settings = Depends(_get_settings),
) -> HTMLResponse:
    """Where a check is watched: one label's findings in full, the rest of the
    submission listed behind it.

    The React island subscribes to ``/batches/{batch_id}/stream`` and opens the
    first result the moment it arrives, so a reviewer reads one graded label
    while the others are still being checked.
    """
    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={"batch_id": batch_id, "dev_mode": settings.dev_mode},
    )


@router.get("/batches")
async def batches_moved() -> RedirectResponse:
    """The bulk-upload page was a second way in and no longer exists.

    Kept as a redirect rather than deleted because it is the URL the deployed
    service has been handing out, and a bookmark that 404s tells a reviewer the
    product is broken when what happened is that it got simpler.
    """
    return RedirectResponse(url="/", status_code=308)
