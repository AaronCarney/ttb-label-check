"""The shipped labels a reviewer can try without having any of their own.

Two ways in, because a reviewer arrives with two different amounts of patience:

- ``GET /batches/sample.zip`` downloads a handful of real TTB Public COLA
  Registry images (CC0) to drop into the bulk-upload form.
- ``POST /samples/{sample_id}`` checks one shipped label straight away, with
  the application it was really filed with already filled in. Without it, the
  first thing the product asks of a reviewer with no labels is a download, an
  unzip, a file picker and ten typed fields before anything happens at all.

Both read the same shipped images, one directory per TTB ID, so neither
fetches anything over the network: the product works with outbound traffic
blocked (PRD C-4) and a clone needs no extra step.

The application values come from ``tests/fixtures/labels/manifest.json``, which
records, for each label, the application actually filed for it in the registry,
under the same ten key names this form posts.
"""

from __future__ import annotations

import io
import json
import random
import zipfile
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app.api.ui._page import _get_settings
from app.api.ui._result_page import render_single_result
from app.api.ui._submission import _detect_image_mime, _get_upload_evaluator
from app.api.ui.images import UploadImageStore, _get_image_store
from app.api.ui.results import SingleResultStore, _get_result_store
from app.config import Settings
from app.schemas.label import Face, FaceTag

router = APIRouter()

_SAMPLE_LABELS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "labels"
)
_SAMPLE_FACE = "front.jpg"


def _load_sample_ttbids() -> list[str]:
    """TTB IDs of the sample labels installed with the app."""
    if not _SAMPLE_LABELS_DIR.is_dir():
        return []
    return sorted(d.name for d in _SAMPLE_LABELS_DIR.iterdir() if (d / _SAMPLE_FACE).is_file())


def _read_label_bytes(ttbid: str) -> bytes | None:
    """The front-face JPEG for one TTB ID, or None if it is not installed."""
    local = _SAMPLE_LABELS_DIR / ttbid / _SAMPLE_FACE
    if local.is_file():
        return local.read_bytes()
    return None


def _installed_faces(ttbid: str) -> list[tuple[FaceTag, bytes]]:
    """Every face installed for one TTB ID, front first.

    Most of these labels carry their government warning on the back, so a zip
    of fronts sends a reviewer into the batch with images that cannot pass the
    warning check. Both faces go, named the way the batch upload reads them
    back — see `app/api/ui/_faces.py`.
    """
    faces: list[tuple[FaceTag, bytes]] = []
    for face_tag in ("front", "back"):
        path = _SAMPLE_LABELS_DIR / ttbid / f"{face_tag}.jpg"
        if path.is_file():
            faces.append((face_tag, path.read_bytes()))
    return faces


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
            for face_tag, body in _installed_faces(ttbid):
                zf.writestr(f"{ttbid}-{face_tag}.jpg", body)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"content-disposition": 'attachment; filename="sample.zip"'},
    )


# ---------------------------------------------------------------------------
# One shipped label, checked on a click.
# ---------------------------------------------------------------------------

_MANIFEST = _SAMPLE_LABELS_DIR / "manifest.json"

# The labels offered on the landing page, in the order they appear there. Four
# rather than thirty-eight, because the point is to show four different things
# happening, not to list a catalogue.
#
# Every description here is what the label actually did, measured on this route
# with both faces sent on 2026-09-17 — `plans/probes/item6_all_samples.json`,
# the sweep after `8ca3ecc` and `a47d03c`. Two facts from that sweep decide the
# list:
#
#   - **No label in the corpus passes outright**, so none is offered as one. The
#     nearest is a wine with a single point for a reviewer.
#   - **The two samples this list used to lead with described a pass that does
#     not happen.** `ttb-26231001000662`, offered as "a bourbon where everything
#     matches", returns five review points, three of them the reader misreading
#     the label (the brand logo, a two-line class and type, and the
#     name-and-address line). `var-brand-case-punctuation` is the same two
#     photographs with the brand typed without its apostrophe, and it returns
#     findings identical to the bourbon's — including a brand review — so it no
#     longer demonstrates that case and punctuation do not fail a brand. Both
#     are dropped rather than described around.
#
# No distilled spirit is offered. Every one in the corpus is either rejected on
# a warning the reader garbled or carries the reader faults above; that is a
# gap in what the reader can do, not a gap in the catalogue.
#
# Each of the four clears the image-quality gate, checked 2026-09-16 by running
# `app.vision.quality.assess` over every front in the manifest; a sample that
# short-circuits on its photo would demonstrate nothing about the rules.
#
# The button text is carried here rather than taken from the brand, because two
# of these labels are the same wine and two buttons reading "Check FABIO
# SIGNORELLI" tell a reviewer nothing about which is which.
_OFFERED = (
    (
        "ttb-26236001000652",
        "PATRIA",
        "Domestic wine, and the closest thing here to a clean label: one point "
        "for a reviewer, where the label's CHARDONNAY meets the application's "
        "TABLE WHITE WINE.",
    ),
    (
        "ttb-26239001000132",
        "FABIO SIGNORELLI",
        "Imported, so the country-of-origin check runs — and it passes. Two "
        "other points go to a reviewer.",
    ),
    (
        "ttb-26230001000420",
        "THE BRUERY",
        "Neither photograph of this beer shows a bottler's name and address, "
        "and the check says so.",
    ),
    (
        "var-warning-wording",
        "FABIO SIGNORELLI, warning reworded",
        "The same wine with one word of its GOVERNMENT WARNING repainted — "
        "“may impair” for “impairs”. Rejected.",
    ),
)


@lru_cache(maxsize=1)
def _manifest_entries() -> dict[str, dict]:
    """Every manifest label, keyed by its id, read once per process.

    An absent or unreadable manifest yields nothing rather than raising: the
    samples are a convenience, and a build without them must still serve the
    page and accept a reviewer's own upload.
    """
    try:
        raw = json.loads(_MANIFEST.read_text())
    except (OSError, ValueError):
        return {}
    return {entry["id"]: entry for entry in raw.get("labels", []) if "id" in entry}


def _str(value: object) -> str:
    """A manifest value as the form would carry it; absent becomes blank, and a
    blank field means the application declared nothing for that element."""
    return "" if value is None else str(value)


def _posted_from(entry: dict) -> dict[str, str]:
    """The ten application fields the form posts, taken from one manifest entry.

    Alcohol content and net contents are read from their `value` — the words
    the application itself used — because that is what the form asks for and
    what the rules compare against.

    Country of origin is passed only for an imported product. The manifest
    records a domestic application's `origin` as the producing state, which is
    not what the form's country-of-origin field means; the rules ignore it for
    a domestic product either way (`app/services/application_mapper.py`), so
    sending it would only mislead the reviewer reading the filled-in form.
    """
    application = entry.get("application", {})
    source = _str(application.get("source_of_product"))
    quantities = {
        key: _str((application.get(key) or {}).get("value"))
        for key in ("alcohol_content", "net_contents")
    }
    return {
        "beverage_type": _str(entry.get("beverage_type")),
        "brand_name": _str(application.get("brand_name")),
        "fanciful_name": _str(application.get("fanciful_name")),
        "class_type": _str(application.get("class_type")),
        "alcohol_content": quantities["alcohol_content"],
        "net_contents": quantities["net_contents"],
        "applicant_name_address": _str(application.get("applicant_name_address")),
        "source_of_product": source,
        "origin": _str(application.get("origin")) if source.lower() == "imported" else "",
        "wine_appellation": _str(application.get("wine_appellation")),
    }


def offered_samples() -> list[dict[str, str]]:
    """The samples the landing page offers: the text on each button and the
    line beside it. A sample whose manifest entry or image is not installed is
    left out, so a partial build shows fewer buttons rather than a broken one."""
    entries = _manifest_entries()
    out: list[dict[str, str]] = []
    for sample_id, button, blurb in _OFFERED:
        entry = entries.get(sample_id)
        if entry is None:
            continue
        front = entry.get("images", {}).get("front")
        if not front or not (_SAMPLE_LABELS_DIR / front).is_file():
            continue
        out.append(
            {
                "id": sample_id,
                "button": button,
                "blurb": blurb,
            }
        )
    return out


@router.post("/samples/{sample_id}", response_class=HTMLResponse)
async def check_shipped_sample(
    request: Request,
    sample_id: str,
    settings: Settings = Depends(_get_settings),
    evaluator=Depends(_get_upload_evaluator),
    images: UploadImageStore = Depends(_get_image_store),
    results: SingleResultStore = Depends(_get_result_store),
) -> HTMLResponse:
    """Check one shipped label against the application it was really filed with.

    Runs exactly the path `POST /` runs — same application parsing, same
    evaluator, same result page — with the image and the ten application fields
    supplied from the manifest instead of typed. A reviewer clicking this and a
    reviewer uploading their own label therefore see the same product.
    """
    entry = _manifest_entries().get(sample_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no sample label {sample_id!r}")

    faces = _faces_of(sample_id, entry)

    return await render_single_result(
        request=request,
        settings=settings,
        evaluator=evaluator,
        images=images,
        results=results,
        posted=_posted_from(entry),
        faces=faces,
        label_id=sample_id,
    )


def _faces_of(sample_id: str, entry: dict) -> tuple[Face, ...]:
    """Every face the manifest ships for this sample, front first.

    Every real sample in the manifest carries both a front and a back, and on
    most of them the government warning is printed on the back. Sending only
    the front was checking the label against a photograph that was never meant
    to show most of what the check is about.

    The manifest's own `warning_image` hint is deliberately not read. A real
    applicant does not annotate which face carries the warning, so an engine
    that learned to expect the annotation would pass the samples and fail the
    filings.
    """
    images = entry.get("images", {})
    faces: list[Face] = []
    wanted: tuple[FaceTag, ...] = ("front", "back")
    for face_tag in wanted:
        name = images.get(face_tag)
        if not name:
            continue
        path = _SAMPLE_LABELS_DIR / name
        # The manifest ships inside the repository and names its own images, so
        # a path here is not attacker-controlled; it is still resolved against
        # the samples directory rather than trusted, because a manifest edit
        # should not be able to read a file outside it.
        if not _is_inside(path, _SAMPLE_LABELS_DIR) or not path.is_file():
            continue
        image_bytes = path.read_bytes()
        mime = _detect_image_mime(image_bytes)
        if mime is None:
            raise HTTPException(
                status_code=500,
                detail=f"sample label {sample_id!r} {face_tag} image is not a PNG or JPEG",
            )
        faces.append(
            Face(
                image_bytes=image_bytes,
                content_type=mime,
                face_tag=face_tag,
                dimensions=None,
            )
        )

    if not faces:
        raise HTTPException(
            status_code=404, detail=f"sample label {sample_id!r} is not installed in this build"
        )
    return tuple(faces)


def _is_inside(path: Path, root: Path) -> bool:
    """Whether `path` resolves to somewhere under `root`."""
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True
