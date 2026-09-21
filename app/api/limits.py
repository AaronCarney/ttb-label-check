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
(https://docs.cloud.google.com/run/quotas). `scripts/deploy.sh`
sets no `--use-http2`, so this service is HTTP/1 and the 32 MiB cap applies.

It matters which side refuses. Over this line Google answers with its own error
page, and the user is never told what the limit is or which file broke it. Our
cap therefore sits below it, so our message is the one they read.
"""

MAX_REQUEST_BYTES = 63 * _MIB // 2
"""The largest request body this service will read, across every route: 31.5 MiB.

The owner's number: as close to the platform ceiling as is safe,
so a batch upload gets every byte the platform will carry. He asked for a cap
that fits a hundred files at once; 50 MB and 75 MB were both put to him and both
are unreachable, because `CLOUD_RUN_HTTP1_REQUEST_BYTES` above is refused by
Google before this process is reached. 31.5 MiB is the largest round number
under it.

The half-MiB of headroom is for the request headers, which count towards the
platform's limit and sit outside the body this service measures. The multipart
boundaries and the form fields travel *inside* the body, so they are already
counted here and need no reservation. A hundred parts cost roughly 20 KB of
boundary and header text, and the HTTP request headers a few more; half a
mebibyte covers both many times over.

Held as MiB rather than as 31,500,000 bytes so it is in the same unit as the
limit it sits under, and the comparison between them is exact.
"""

# --------------------------------------------------------------------------
# One image
# --------------------------------------------------------------------------

MAX_UPLOAD_BYTES = 3 * _MIB // 2
"""The largest single image this service will accept: TTB's own number.

COLAs Online refuses a label image over **1.5 MB**
(`docs/research/2026-09-15-cola-operational-context.md`), so no image that
reached TTB through the system of record is larger than this. Matching that
number means this service accepts exactly what the registry accepts and nothing
beyond it. A file above the line is not a submission we are turning away — it is
a file that could never have been filed in the first place.

Held as 1.5 MiB rather than 1,500,000 bytes so that whichever unit TTB means,
ours is never the stricter one, and we never refuse an image the registry took.

The bound is the registry's and not this repository's: what our own test
images happen to weigh is a property of a demo corpus, and a cap a real filer's
upload has to clear cannot be argued from it. The reader would not use the extra
bytes in any case — it downscales to `MAX_EDGE_PX = 1600` on the long edge
before reading (`app/vision/local.py`).

The earlier cap was 10 MB, sized for a phone photograph rather than for a
filing. That was the wrong constraint to derive from: a bound should be as tight
as the real input allows, because every byte admitted above it is memory this
service agreed to hold for an input it can never usefully receive.

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
that is three batches, run one after another, which the 900-second request
timeout in `scripts/deploy.sh` is already sized for. And 100 real
labels fit in one request: the corpus median is about 184 KB, so a full batch of
label-sized images is roughly 18 MiB, inside `MAX_REQUEST_BYTES`.

A batch of larger images is refused by the request cap rather than by this one,
which is the right way round — the file count is a fairness limit, the byte caps
are the memory guard.
"""


MULTIPART_PART_BYTES = 256
"""What one file's multipart framing costs inside the request body.

A part is not just its bytes: it carries a boundary line, a
`Content-Disposition` header naming the field and the filename, a
`Content-Type`, and the blank lines between them. A browser's boundary runs to
about 40 characters and a label filename to about 30, which puts a real part's
framing near 160 bytes; 256 is the round number above it, so a count derived
from it is never optimistic. This matches the "roughly 20 KB of boundary and
header text" for a hundred parts recorded under `MAX_REQUEST_BYTES`.

It exists so `files_that_fit` counts what the request actually carries. Without
it the count is wrong at exactly the place it matters: 21 images at
`MAX_UPLOAD_BYTES` come to 31.5 MiB, `MAX_REQUEST_BYTES` to the byte, so the
framing is the whole of what tips a 21-file upload over.
"""


def files_that_fit(image_bytes: int) -> int:
    """How many images of a given size one upload can actually carry.

    `MAX_BATCH_FILES` is the count a batch is *allowed*; this is the count the
    request cap will *carry*, and for any image above `BATCH_AVERAGE_BYTES` it
    is the smaller of the two. A reviewer told only the file count cannot work
    out why a hundred ordinary labels were refused, which is why both graded
    documents state this figure rather than the bare 100.
    """
    return min(MAX_BATCH_FILES, MAX_REQUEST_BYTES // (image_bytes + MULTIPART_PART_BYTES))


BATCH_AVERAGE_BYTES = MAX_REQUEST_BYTES // MAX_BATCH_FILES - MULTIPART_PART_BYTES
"""The average image size at which a full `MAX_BATCH_FILES` batch still fits.

The file count and the byte cap only agree below this line. Above it the byte
cap is the real limit and the advertised 100 is unreachable — not a fault in
either number, but the thing a reader has to be told alongside them.
"""


# --------------------------------------------------------------------------
# Reason codes, registered in `rules/reason_codes.yaml`
# --------------------------------------------------------------------------

REQUEST_TOO_LARGE = "ENGINE.INPUT.REQUEST_TOO_LARGE"
UPLOAD_TOO_LARGE = "ENGINE.INPUT.UPLOAD_TOO_LARGE"
TOO_MANY_FILES = "ENGINE.INPUT.TOO_MANY_FILES"
IMAGE_TOO_MANY_PIXELS = "ENGINE.INPUT.IMAGE_TOO_MANY_PIXELS"


def _mib(value: int) -> str:
    """A byte count as a person reads it, so a message can name the limit.

    One decimal place, trailing `.0` dropped. Whole-number rounding would print
    the 1.5 MiB `MAX_UPLOAD_BYTES` as "2 MB" and tell the user a limit this
    service does not enforce.
    """

    def _trim(number: float) -> str:
        return f"{number:.1f}".removesuffix(".0")

    if value >= _MIB:
        return f"{_trim(value / _MIB)} MB"
    if value >= 1024:
        return f"{_trim(value / 1024)} KB"
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


def oversized_batch_message(refused: int, total: int) -> str:
    """The lead line when a batch is refused for size, above the per-file list.

    Every file over a cap is named in one reply rather than the first alone.
    Stopping at the first made a set with four bad files four round trips, each
    one hiding the next, and the reviewer could not tell whether they were
    halfway through or at the start.
    """
    return (
        f"The batch was not started: {refused} of the {total} files cannot be checked. "
        "Fix the files listed below and upload the set again."
    )


def too_many_pixels_message(filename: str, pixels: int, limit: int) -> str:
    return (
        f"{filename} decodes to {pixels:,} pixels, more than the {limit:,} this "
        "service will open. A file this small that unpacks this large is refused "
        "rather than read."
    )


def rejected_input(reason_code: str, message: str, **details: Any) -> ErrorEnvelope:
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

    Pillow's bomb guard fires inside `Image.open`, which would stop us reading
    the very number we want to refuse on, and would leave the user with Pillow's
    exception instead of a sentence naming their file. So this does what
    `Image.open` does up to that point — finds the format whose signature the
    bytes carry and has its plugin read the header — and stops there. A plugin
    reads the header and decodes nothing, so no pixels are allocated.

    It used to switch the guard off around an `Image.open` instead. The guard is
    a Pillow-wide global, so that was safe only while the service took one
    request at a time, and it takes several now (`CONCURRENCY` in
    `scripts/deploy.sh`): a decode in another request during that window would
    have run unguarded.
    """
    Image.init()
    prefix = image_bytes[:16]
    for name in Image.ID:
        factory, accept = Image.OPEN[name]
        # Pillow's own rule: a string is a warning about the format, not a match.
        result = accept(prefix) if accept else True
        if isinstance(result, str) or not result:
            continue
        try:
            img = factory(io.BytesIO(image_bytes), "")
        except Exception:
            continue
        with img:
            width, height = img.size
        return width * height
    return None


def bomb_refusal(filename: str, image_bytes: bytes) -> tuple[str, int] | None:
    """`(message, pixels)` when the file declares more pixels than we open.

    `None` when it is within the ceiling, or is not an image at all.
    """
    pixels = declared_pixels(image_bytes)
    if pixels is None or pixels <= MAX_IMAGE_PIXELS:
        return None
    return too_many_pixels_message(filename, pixels, MAX_IMAGE_PIXELS), pixels
