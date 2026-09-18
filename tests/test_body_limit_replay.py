"""What `BodySizeLimitMiddleware` hands the application after it has buffered.

The middleware reads the whole request body before the application runs, then
replays it through a substitute `receive`. Everything the application learns
about the connection after that point comes from this substitute, so what it
answers on the second call is a statement about the client — and it has to be
a true one.

Two cases, and they differ:

  * The client is still connected. The middleware has no more body to give,
    but it also has no standing to say the client has gone. It must defer to
    the real transport, which is what an application running without this
    middleware would have been awaiting.
  * The client disconnected while the body was being read. The transport has
    already said so and is drained; the middleware answers from what it knows
    and must not call the transport again.
"""

from __future__ import annotations

import pytest

from app.api.body_limit import BodySizeLimitMiddleware

_SCOPE = {"type": "http", "method": "POST", "headers": [(b"content-length", b"3")]}


class _Transport:
    """An ASGI `receive` that hands out a fixed script and counts its calls."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)
        self.calls = 0

    async def __call__(self) -> dict:
        self.calls += 1
        if self._messages:
            return self._messages.pop(0)
        return {"type": "http.disconnect", "from_transport": True}


class _TwiceReceivingApp:
    """An application that reads the body and then asks once more."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, scope, receive, send) -> None:
        self.messages.append(await receive())
        self.messages.append(await receive())


async def _drive(transport: _Transport) -> _TwiceReceivingApp:
    app = _TwiceReceivingApp()
    await BodySizeLimitMiddleware(app)(_SCOPE, transport, _noop_send)
    return app


async def _noop_send(message) -> None:
    return None


@pytest.mark.anyio
async def test_connected_client_second_receive_defers_to_the_transport() -> None:
    transport = _Transport([{"type": "http.request", "body": b"abc", "more_body": False}])
    app = await _drive(transport)

    assert app.messages[0]["body"] == b"abc"
    assert transport.calls == 2, (
        "the client had not disconnected, so the second receive must reach the "
        "real transport rather than be answered by the middleware"
    )
    assert app.messages[1].get("from_transport") is True


@pytest.mark.anyio
async def test_disconnected_client_is_answered_without_touching_the_transport() -> None:
    transport = _Transport(
        [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.disconnect"},
        ]
    )
    app = await _drive(transport)

    assert app.messages[0]["body"] == b"abc"
    assert app.messages[1]["type"] == "http.disconnect"
    assert transport.calls == 2, (
        "the transport already reported the disconnect while the body was being "
        "read; it must not be called a third time"
    )


@pytest.mark.anyio
async def test_the_body_is_handed_on_as_it_arrived_not_copied() -> None:
    """The middleware holds the body once. Replaying it as a fresh copy held the
    whole upload twice, up to twice the request cap, until the replay ended."""
    first, second = b"a" * 10, b"b" * 10
    transport = _Transport(
        [
            {"type": "http.request", "body": first, "more_body": True},
            {"type": "http.request", "body": second, "more_body": False},
        ]
    )
    app = _TwiceReceivingApp()
    await BodySizeLimitMiddleware(app)(_SCOPE, transport, _noop_send)

    assert app.messages[0]["body"] is first
    assert app.messages[0]["more_body"] is True
    assert app.messages[1]["body"] is second
    assert app.messages[1]["more_body"] is False
