"""The three pages the reviewer navigates: single label, one batch, bulk upload.

Template rendering only. This module imports nothing from ``app.services``,
``app.vision``, ``app.rules`` or ``app.deps``, because serving a page needs
none of them: the React island it mounts fetches its data from the JSON API
(``app.api.labels``, ``app.api.batches``, ``app.api.overrides``), and the two
upload routes that do run the engine live beside this module rather than in it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.api.ui._page import _get_settings, templates
from app.api.ui.samples import offered_samples
from app.config import Settings

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def single_page_shell(
    request: Request,
    settings: Settings = Depends(_get_settings),
) -> HTMLResponse:
    """Render the empty-inbox single-label landing. No pre-loaded results; the
    reviewer sees a drop-zone CTA and three ways on: upload their own label, try
    one of the shipped samples on a click (`POST /samples/{sample_id}`), or
    pull a starter pack from `/batches/sample.zip`. The React island mounts on
    `<div id="root" data-mode="single">` and renders an envelope only after a
    real check returns one."""
    return templates.TemplateResponse(
        request=request,
        name="single.html",
        context={
            "envelope_json": None,
            "dev_mode": settings.dev_mode,
            "samples": offered_samples(),
        },
    )


@router.get("/batch/{batch_id}", response_class=HTMLResponse)
async def batch_page_shell(
    request: Request,
    batch_id: str,
    settings: Settings = Depends(_get_settings),
) -> HTMLResponse:
    """Render the batch review shell for a given batch_id. The React island
    subscribes via SSE to ``/batches/{batch_id}/stream``."""
    return templates.TemplateResponse(
        request=request,
        name="batch.html",
        context={"batch_id": batch_id, "dev_mode": settings.dev_mode},
    )


@router.get("/batches", response_class=HTMLResponse)
async def batches_upload_page(
    request: Request,
    settings: Settings = Depends(_get_settings),
) -> HTMLResponse:
    """Render the bulk-upload form. Submitting it lands at POST /batches/upload
    which spawns a worker and redirects into the existing batch shell."""
    return templates.TemplateResponse(
        request=request,
        name="batches_upload.html",
        context={"dev_mode": settings.dev_mode},
    )
