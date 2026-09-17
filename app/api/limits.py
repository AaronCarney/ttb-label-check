"""What the service accepts from an upload, and where each number came from.

Nothing bounded an upload before this module: no byte cap on any of the four
upload paths, no `Content-Length` check, no body-size middleware. One request
could decide how much memory the instance spent, and
`app/api/ui/bulk_upload.py` reads every file in a batch into memory before it
looks at any of them.

Every limit here is derived from a measured constraint rather than picked, and
the derivation is written beside it, because a limit nobody can trace back to a
constraint gets moved the first time it is inconvenient.
`tests/test_upload_limits.py` holds the derivations to their constraints.
"""
from __future__ import annotations

import io
from typing import Any

from PIL import Image

from app.schemas.wire.error import ErrorEnvelope


_MIB = 1024 * 1024

# --------------------------------------------------------------------------
# The platform's own limit, which ours has to sit under
# --------------------------------------------------------------------------

CLOUD_RUN_HTTP1_REQUEST_BYTES = 32 * _MIB
"""Cloud Run refuses an HTTP/1 request body larger than this itself.

Google's published quota: *"Maximum HTTP/1 request size: 32 MiB per request.
Limit applies if using HTTP/1 server. No limit if using HTTP/2 server"*
(https://docs.cloud.google.com/run/quotas, read 2026-09-16). `scripts/deploy.sh`
sets no `--use-http2`, so this service is HTTP/1 and the 32 MiB cap applies.

It matters which side refuses. Over this line Google answers with its own error
page, and the user is never told what the limit is or which file broke it. Our
cap therefore sits below it, so our message is the one they read.
"""

MAX_REQUEST_BYTES = 28 * _MIB
"""The largest request body this service will read, across every route.

4 MiB under the platform's cap, which is headroom for the multipart boundaries,
the headers and the application form fields that travel beside the images.
"""

# --------------------------------------------------------------------------
# One image
# --------------------------------------------------------------------------

MAX_UPLOAD_BYTES = 10 * _MIB
"""The largest single image this service will accept.

Sized for what a person actually uploads, not for what the reader needs: a
full-resolution photograph from a current phone is a few megabytes, and this
leaves room above that. The reader gains nothing from the extra pixels — it
downscales to `MAX_EDGE_PX = 1600` on the long edge before reading
(`app/vision/local.py`) — and the project's own 62 corpus images run from 13 KB
to 560 KB. The cap is generous on purpose: refusing a real submission is a worse
failure than reading a larger file than we needed.

Well under `MAX_REQUEST_BYTES`, so one image can never fill a request on its own
and the two caps cannot contradict each other about which fired.
"""

MAX_IMAGE_PIXELS = 50_000_000
"""The largest decoded image this service will accept, in pixels.

A decompression bomb is a small file that expands to an enormous image: a few
kilobytes of PNG can declare a 50,000 x 50,000 canvas, which no byte cap catches
because the file really is small. The cost is paid at decode, so the ceiling has
to be checked against the header before the pixels are read.

50 megapixels is above any camera a submission plausibly comes from — a current
48 MP phone sensor is 48 MP — and a 50 MP RGB decode is about 150 MB, which the
4 GiB instance (`scripts/deploy.sh`) carries without trouble. Pillow's own
default ceiling is roughly 89 MP and only warns; this one is acted on.
"""

# --------------------------------------------------------------------------
# One batch
# --------------------------------------------------------------------------

MAX_BATCH_FILES = 100
"""The most images one batch upload may carry.

The owner's number, kept because it survives the two constraints that could have
broken it. NFR-2 asks for 300 submissions inside 10 minutes; at 100 per batch
that is three batches, which the 900-second request timeout and the
two-instance cap in `scripts/deploy.sh` are already sized for. And 100 real
labels fit in one request: the corpus median is about 184 KB, so a full batch of
label-sized images is roughly 18 MiB, inside `MAX_REQUEST_BYTES`.

A batch of larger images is refused by the request cap rather than by this one,
which is the right way round — the file count is a fairness limit, the byte caps
are the memory guard.
"""


# --------------------------------------------------------------------------
# Reason codes, registered in `rules/reason_codes.yaml`
# --------------------------------------------------------------------------

REQUEST_TOO_LARGE = "ENGINE.INPUT.REQUEST_TOO_LARGE"
UPLOAD_TOO_LARGE = "ENGINE.INPUT.UPLOAD_TOO_LARGE"
TOO_MANY_FILES = "ENGINE.INPUT.TOO_MANY_FILES"
IMAGE_TOO_MANY_PIXELS = "ENGINE.INPUT.IMAGE_TOO_MANY_PIXELS"


def _mib(value: int) -> str:
    """A byte count as a person reads it, so a message can name the limit."""
    if value >= _MIB:
        return f"{value / _MIB:.0f} MB"
    if value >= 1024:
        return f"{value / 1024:.0f} KB"
    return f"{value} bytes"


def request_too_large_message(limit: int) -> str:
    return (
        f"That upload is larger than the {_mib(limit)} this service accepts in one "
        "request. Send fewer files at a time, or smaller ones."
    )


def upload_too_large_message(filename: str, size: int, limit: int) -> str:
    return (
        f"{filename} is {_mib(size)}, larger than the {_mib(limit)} limit for one "
        "image. Save it at a smaller size and upload it again."
    )


def too_many_files_message(count: int, limit: int) -> str:
    return (
        f"That batch has {count} files, more than the {limit} this service checks in "
        f"one upload. Split it into batches of {limit} or fewer."
    )


def too_many_pixels_message(filename: str, pixels: int, limit: int) -> str:
    return (
        f"{filename} decodes to {pixels:,} pixels, more than the {limit:,} this "
        "service will open. A file this small that unpacks this large is refused "
        "rather than read."
    )


def rejected_input(
    reason_code: str, message: str, **details: Any
) -> ErrorEnvelope:
    """The boundary's refusal, in the wire contract the API declares.

    `ErrorEnvelope` was defined and fixture-tested but never constructed by any
    route — rejections returned FastAPI's default `{"detail": "..."}`, which
    carries no reason code a caller can branch on. The size rejections are its
    first real user.
    """
    return ErrorEnvelope(
        error_kind="rejected_input",
        reason_code=reason_code,
        message=message,
        details=details,
    )


# Pillow's own ceiling, set to ours. Its default is roughly 89 megapixels and it
# only warns there, raising at twice that; leaving it at the default means any
# decode anywhere in the process — the reader, the quality check, a thumbnail —
# is unguarded. Setting it here makes every one of them refuse, and
# `declared_pixels` below is the boundary check that refuses first, with a
# message naming the file.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def declared_pixels(image_bytes: bytes) -> int | None:
    """How many pixels the file says it holds, read from its header.

    `None` when the bytes are not an image whose header can be read at all —
    that is the MIME check's answer to give, not this one's.

    Pillow's own bomb guard is switched off around this one call. The guard
    fires inside `Image.open`, which would stop us reading the very number we
    want to refuse on, and would leave the user with Pillow's exception instead
    of a sentence naming their file. `Image.open` reads the header and decodes
    nothing, so no pixels are allocated either way.

    The guard is a Pillow-wide global, so this is safe because the service runs
    one request at a time (`CONCURRENCY=1` in `scripts/deploy.sh`). If that ever
    changes, this has to become a lock or a hand-written header read.
    """
    guard = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
        return width * height
    except Exception:
        return None
    finally:
        Image.MAX_IMAGE_PIXELS = guard


def bomb_refusal(filename: str, image_bytes: bytes) -> tuple[str, int] | None:
    """`(message, pixels)` when the file declares more pixels than we open.

    `None` when it is within the ceiling, or is not an image at all.
    """
    pixels = declared_pixels(image_bytes)
    if pixels is None or pixels <= MAX_IMAGE_PIXELS:
        return None
    return too_many_pixels_message(filename, pixels, MAX_IMAGE_PIXELS), pixels
