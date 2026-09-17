"""The request-body cap, enforced before any route sees the request.

This is the memory guard. The per-file and per-batch caps in the upload routes
are what a person reads — they can name the file that was too big — but they can
only run after multipart parsing has already pulled the whole body into memory.
Something has to refuse a body before that, and it has to cover every route,
including ones written later: a cap that each route opts into is a cap the next
route forgets.

How it refuses:

  * When the request declares `Content-Length` over the cap, nothing is read at
    all. The refusal costs one header.
  * When it declares no length — a chunked upload — the body is counted as it
    arrives and refused the moment it passes the cap. The bytes held are
    therefore bounded by the cap itself, which is the guarantee this exists to
    give. The app reads the same body into memory a moment later anyway, so
    buffering here costs nothing extra.

The reply is `ErrorEnvelope` JSON for an API caller and the page's own words for
a browser, because at this point the only thing known about the request is what
its headers say.
"""
from __future__ import annotations

import json

from app.api import limits

_METHODS_WITH_BODIES = frozenset({"POST", "PUT", "PATCH"})

_HTML_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Upload too large</title></head>
<body><main><h1>That upload is too large</h1><p>{message}</p></main></body></html>
"""


class BodySizeLimitMiddleware:
    """Refuse a request body over `limits.MAX_REQUEST_BYTES`.

    Pure ASGI rather than a Starlette `BaseHTTPMiddleware`, because the cap has
    to act on `receive` before the application is called, and `BaseHTTPMiddleware`
    only sees the request once Starlette has built one.

    The cap is read from `limits` on every request rather than captured at
    construction, so a test can change it without rebuilding the application.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("method") not in _METHODS_WITH_BODIES:
            await self.app(scope, receive, send)
            return

        cap = limits.MAX_REQUEST_BYTES
        declared = _declared_length(scope)
        if declared is not None and declared > cap:
            await _refuse(scope, send, cap)
            return

        body, disconnected = await _read_capped(receive, cap)
        if body is None:
            await _refuse(scope, send, cap)
            return

        await self.app(scope, _replay(body, disconnected), send)


def _declared_length(scope) -> int | None:
    for name, value in scope.get("headers", ()):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _accepts_html(scope) -> bool:
    for name, value in scope.get("headers", ()):
        if name == b"accept":
            return b"text/html" in value
    return False


async def _read_capped(receive, cap: int) -> tuple[bytearray | None, bool]:
    """The whole body, or `None` if it passes `cap` on the way in.

    Stops at the first byte over the cap: a body twice the cap is never held,
    only the cap plus one message.
    """
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return body, True
        body.extend(message.get("body", b""))
        if len(body) > cap:
            return None, False
        if not message.get("more_body", False):
            return body, False


def _replay(body: bytearray, disconnected: bool):
    """Hand the buffered body to the application as if it were arriving now."""
    sent = False

    async def _receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}
        return {"type": "http.disconnect"} if disconnected else {"type": "http.disconnect"}

    return _receive


async def _refuse(scope, send, cap: int) -> None:
    message = limits.request_too_large_message(cap)
    if _accepts_html(scope):
        payload = _HTML_PAGE.format(message=message).encode()
        content_type = b"text/html; charset=utf-8"
    else:
        payload = limits.rejected_input(
            limits.REQUEST_TOO_LARGE, message, limit_bytes=cap
        ).model_dump_json().encode()
        content_type = b"application/json"
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", content_type),
            (b"content-length", str(len(payload)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": payload})
