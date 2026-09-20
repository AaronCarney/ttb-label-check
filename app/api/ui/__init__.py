"""The browser-facing surface: the pages a reviewer sees and the form they post.

One module per job, because these jobs share almost nothing beyond the Jinja
environment:

- ``shells`` — the two page shells, ``/`` and ``/batch/{batch_id}``, plus the
  redirect that keeps the old bulk-upload URL working. Template rendering only.
- ``submit`` — ``POST /``, the one way a check is started, for one label or
  three hundred.
- ``images`` — ``GET /labels/{eval_id}/image`` and ``GET /labels/{eval_id}/faces``,
  and the store a checked label's photographs are kept in so the results page
  can show them.
- ``samples`` — the shipped labels a reviewer can try without having any of
  their own: ``GET /batches/sample.zip`` to download a starter pack, and
  ``POST /samples/{sample_id}`` to check one of them on a click.
- ``_page``, ``_submission``, ``_faces`` and ``_application_csv`` — what more
  than one of the above needs: the templates and settings, the pieces that turn
  a posted form into an image and an application the engine can take, which
  uploaded files are two faces of one label, and the CSV that carries an
  application per label.

``router`` here is all of them mounted together, so ``app/main.py`` includes one
router and a new page route is added by writing it in the module it belongs
to rather than by touching the app factory. See `docs/decisions.md#0019`.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.ui import images, samples, shells, submit
from app.api.ui._page import _get_settings
from app.api.ui._submission import _get_upload_evaluator

router = APIRouter(tags=["ui"])
for _part in (shells, submit, images, samples):
    router.include_router(_part.router)

# The two dependencies a caller overrides — a test swaps the settings to turn
# dev mode on, and swaps the evaluator so an upload never reaches a vision
# model. Re-exported here so the import path does not move when a route does.
__all__ = ["_get_settings", "_get_upload_evaluator", "router"]
