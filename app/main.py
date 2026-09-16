"""Builds the FastAPI application.

Boot sequence:
1. Read ``Settings``.
2. Configure logging (JSON-line stdout + redaction filter).
3. Construct the FastAPI app.
4. Register routers: /healthz, UI page shells.
5. Mount static files at /static.

Also wired into the app: rule-loader startup, reader wiring, label/batch/
override routes, SSE.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.healthz import router as healthz_router
from app.api.ui import router as ui_router
from app.config import Settings
from app.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings)

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.getLogger("app.main").info(
            "app_startup",
            extra={
                "reason_code": "ENGINE.OK.NONE",
                "rule_set_version": "0.0.0",  # Overwritten when the rule pack loads.
                "model_version": settings.llm_model_snapshot,
                "prompt_version": settings.prompt_version,
            },
        )
        app.state.batches = {}  # In-flight batches, process-local: nothing is persisted.
        app.state.buses = {}    # Per-batch SSEBus registry, keyed by batch_id.
        yield
        # Teardown evicts every in-flight batch and its bus subscribers and queues.
        evicted_batches = len(app.state.batches)
        evicted_buses = len(app.state.buses)
        app.state.batches.clear()
        app.state.buses.clear()
        logging.getLogger("app.main").info(
            f"app_shutdown evicted_batches={evicted_batches} evicted_buses={evicted_buses}",
            extra={"reason_code": "ENGINE.OK.NONE"},
        )

    application = FastAPI(
        title="TTB Label Verification (prototype)",
        version=settings.app_version,
        lifespan=_lifespan,
    )
    application.include_router(healthz_router)
    application.include_router(ui_router)
    _static_dir = Path(__file__).resolve().parent / "ui" / "static"
    application.mount(
        "/static",
        StaticFiles(directory=str(_static_dir)),
        name="static",
    )

    from app.api import labels as labels_module
    application.include_router(labels_module.router)

    from app.api import batches as batches_module
    application.include_router(batches_module.router)

    from app.api import overrides as overrides_module
    application.include_router(overrides_module.router)

    # Pre-init state so routes work even when lifespan hasn't fired (e.g. httpx tests).
    # Lifespan startup will re-assign; shutdown will clear.
    application.state.batches = {}
    application.state.buses = {}

    return application


app: FastAPI = create_app()
