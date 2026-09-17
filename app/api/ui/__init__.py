"""The browser-facing surface: the pages a reviewer sees and the forms they post.

One module per job, because these jobs share almost nothing beyond the Jinja
environment:

- ``shells`` — the three page shells, ``/``, ``/batch/{batch_id}`` and
  ``/batches``. Template rendering only.
- ``single_upload`` — ``POST /``, one label checked against one application.
- ``images`` — ``GET /labels/{eval_id}/image``, and the store the uploaded
  image is kept in so a result page can still show it later.
- ``samples`` — the shipped labels a reviewer can try without having any of
  their own: ``GET /batches/sample.zip`` to download a starter pack, and
  ``POST /samples/{sample_id}`` to check one of them on a click.
- ``bulk_upload`` — ``POST /batches/upload``, a folder of images as one batch.
- ``_page``, ``_submission`` and ``_result_page`` — what more than one of the
  above needs: the templates and settings, the pieces that turn a posted form
  into an image and an application the engine can take, and the one path from
  those two things to the result page. ``POST /`` and ``POST /samples/{id}``
  share that last one, so a sample cannot demonstrate a path a reviewer's own
  upload does not take.

``router`` here is all of them mounted together, so ``app/main.py`` includes one
router and a new page route is added by writing it in the module it belongs
to rather than by touching the app factory. See `docs/decisions.md#0019`.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.ui import bulk_upload, images, samples, shells, single_upload
from app.api.ui._page import _get_settings
from app.api.ui._submission import _get_upload_evaluator

router = APIRouter(tags=["ui"])
for _part in (shells, single_upload, images, samples, bulk_upload):
    router.include_router(_part.router)

# The two dependencies a caller overrides — a test swaps the settings to turn
# dev mode on, and swaps the evaluator so an upload never reaches a vision
# model. Re-exported here so the import path does not move when a route does.
__all__ = ["_get_settings", "_get_upload_evaluator", "router"]
