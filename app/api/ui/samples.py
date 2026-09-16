"""``GET /batches/sample.zip`` — a starter pack of real labels to try.

A reviewer with no labels of their own can download a handful of real TTB
Public COLA Registry images (CC0) and drop them straight into the bulk-upload
form, so the first thing they see is the real pipeline rather than a fixture.

The images ship inside the application, one directory per TTB ID, so a
download fetches nothing over the network: the product works with outbound
traffic blocked (PRD C-4) and a clone needs no extra step.
"""
from __future__ import annotations

import io
import random
import zipfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()

_SAMPLE_LABELS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "labels"
)
_SAMPLE_FACE = "front.jpg"


def _load_sample_ttbids() -> list[str]:
    """TTB IDs of the sample labels installed with the app."""
    if not _SAMPLE_LABELS_DIR.is_dir():
        return []
    return sorted(
        d.name for d in _SAMPLE_LABELS_DIR.iterdir() if (d / _SAMPLE_FACE).is_file()
    )


def _read_label_bytes(ttbid: str) -> bytes | None:
    """The front-face JPEG for one TTB ID, or None if it is not installed."""
    local = _SAMPLE_LABELS_DIR / ttbid / _SAMPLE_FACE
    if local.is_file():
        return local.read_bytes()
    return None


@router.get("/batches/sample.zip")
async def batches_sample_zip(n: int = 10) -> Response:
    """Stream a zip of N sample labels, drawn at random from those installed.

    Each entry is named for the TTB ID it came from, so a reviewer can trace a
    sample back to its registry record.
    """
    if n <= 0:
        return Response(
            content=b"n must be a positive integer",
            status_code=400,
            media_type="text/plain",
        )

    available = _load_sample_ttbids()
    if not available:
        return Response(
            content=b"no sample labels are installed with this build",
            status_code=500,
            media_type="text/plain",
        )

    take = min(n, len(available))
    chosen = random.sample(available, take)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ttbid in chosen:
            body = _read_label_bytes(ttbid)
            if body is None:
                continue
            zf.writestr(f"{ttbid}-front.jpg", body)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"content-disposition": 'attachment; filename="sample.zip"'},
    )
