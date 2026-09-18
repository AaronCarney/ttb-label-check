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
    give. The pieces are handed on as they arrived, not joined into a copy, so
    the body is held once.

The reply is `ErrorEnvelope` JSON for an API caller and the page's own words for
a browser, because at this point the only thing known about the request is what
its headers say.
"""

from __future__ import annotations

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

        chunks, disconnected = await _read_capped(receive, cap)
        if chunks is None:
            await _refuse(scope, send, cap)
            return

        await self.app(scope, _replay(chunks, disconnected, receive), send)


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


async def _read_capped(receive, cap: int) -> tuple[list[bytes] | None, bool]:
    """The whole body as the pieces it arrived in, or `None` if it passes `cap`.

    Stops at the first byte over the cap: a body twice the cap is never held,
    only the cap plus one message.
    """
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return chunks, True
        chunk = message.get("body", b"")
        size += len(chunk)
        if size > cap:
            return None, False
        if chunk:
            chunks.append(chunk)
        if not message.get("more_body", False):
            return chunks, False


def _replay(chunks: list[bytes], disconnected: bool, receive):
    """Hand the buffered body to the application as if it were arriving now.

    Each piece goes on as it arrived, and the middleware lets go of it as it
    does, so the application's copy is the only one.

    After the body, the two cases part. If the client disconnected while the
    body was being read, `receive` has already said so and is drained, so the
    answer comes from here. If the client is still connected there is no more
    body but also nothing known about the connection, and saying
    `http.disconnect` would tell the application the client had gone when it
    had not — so the real transport is awaited, which is what the application
    would have been awaiting without this middleware in front of it.
    """
    pending = list(reversed(chunks))
    chunks.clear()
    sent = False

    async def _receive():
        nonlocal sent
        if not sent:
            body = pending.pop() if pending else b""
            sent = not pending
            return {"type": "http.request", "body": body, "more_body": not sent}
        if disconnected:
            return {"type": "http.disconnect"}
        return await receive()

    return _receive


async def _refuse(scope, send, cap: int) -> None:
    message = limits.request_too_large_message(cap)
    if _accepts_html(scope):
        payload = _HTML_PAGE.format(message=message).encode()
        content_type = b"text/html; charset=utf-8"
    else:
        payload = (
            limits.rejected_input(limits.REQUEST_TOO_LARGE, message, limit_bytes=cap)
            .model_dump_json()
            .encode()
        )
        content_type = b"application/json"
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", content_type),
                (b"content-length", str(len(payload)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})
