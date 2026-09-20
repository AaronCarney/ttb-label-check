"""Opening the results page in a browser with recorded results already on it.

Five browser-driven suites need the same thing: `/batch/{id}` showing one or
more recorded envelopes, without the engine having run. The page gets its
results from `/batches/{id}/stream`, so that is what is stubbed — an
`EventSource` replacement that replays the envelopes it was handed and then
ends the stream.

The stub is the transport and nothing else. Every envelope is delivered through
the same `label-result` / `stream-end` events the worker broadcasts and the
same `{batch_id, queue_position, envelope}` wrapper `useBatchStream` parses, so
a suite here exercises the parsing the product does rather than a shortcut past
it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parent.parent
SINGLE_FIXTURES = ROOT / "tests" / "fixtures" / "envelopes" / "single"

# Any string will do: the stub answers before the request reaches the server,
# so no batch of this id has to exist.
BATCH_ID = "B-browser-test"


def envelope_fixture(name: str) -> dict[str, Any]:
    """One recorded envelope, by filename, from `tests/fixtures/envelopes/single`."""
    return json.loads((SINGLE_FIXTURES / name).read_text())


def _wrap(envelopes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The envelopes in the shape the worker broadcasts them."""
    return [
        {
            "batch_id": envelope.get("batch_id", BATCH_ID),
            "queue_position": envelope.get("queue_position", position),
            "envelope": {
                key: value
                for key, value in envelope.items()
                if key not in ("batch_id", "queue_position")
            },
        }
        for position, envelope in enumerate(envelopes, start=1)
    ]


def stub_stream(page: Page, envelopes: list[dict[str, Any]], *, end: bool = True) -> None:
    """Replace `EventSource` with one that replays `envelopes`, then ends.

    Registered as an init script so it is installed before the island's module
    runs and opens the real stream.

    `end=False` holds the stream open after the last envelope, which is how a
    check still running looks. With no envelopes and no end it is how a check
    looks in the moment after it is started, before the first label is done.
    """
    payloads = _wrap(envelopes)
    end_js = "true" if end else "false"
    page.add_init_script(
        script=f"""
          (() => {{
            const payloads = {json.dumps(payloads)};
            class FakeEventSource {{
              constructor(url) {{
                this.url = url;
                this.readyState = 1;
                this._listeners = new Map();
                this.onerror = null;
                // Deferred past the effect that registers the listeners.
                setTimeout(() => {{
                  for (const payload of payloads) {{
                    this._fire('label-result', JSON.stringify(payload));
                  }}
                  if ({end_js}) {{
                    this._fire('stream-end', JSON.stringify({{ total_count: payloads.length }}));
                  }}
                }}, 0);
              }}
              addEventListener(name, handler) {{
                if (!this._listeners.has(name)) this._listeners.set(name, []);
                this._listeners.get(name).push(handler);
              }}
              removeEventListener(name, handler) {{
                const handlers = this._listeners.get(name) || [];
                const at = handlers.indexOf(handler);
                if (at >= 0) handlers.splice(at, 1);
              }}
              close() {{ this.readyState = 2; }}
              _fire(name, data) {{
                if (this.readyState === 2) return;
                for (const handler of this._listeners.get(name) || []) handler({{ data }});
              }}
            }}
            window.EventSource = FakeEventSource;
          }})();
        """
    )


def open_results(
    page: Page,
    live_server_url: str,
    envelopes: list[dict[str, Any]],
    *,
    end: bool = True,
    wait_for_result: bool = True,
) -> None:
    """Open `/batch/{id}` with `envelopes` already streaming into it.

    Waits for the island to mount, and for the first result's own region to
    render, because the island mounts before any event has arrived and a suite
    that measures the mounted-but-empty page measures the wrong thing.
    """
    stub_stream(page, envelopes, end=end)
    page.goto(f"{live_server_url}/batch/{BATCH_ID}")
    page.wait_for_selector('[data-mounted="true"]', timeout=5000)
    if wait_for_result and envelopes:
        page.wait_for_selector('[role="region"][aria-label^="Check results for"]', timeout=5000)
