"""Shared pytest fixtures for the TTB Label Verification test suite."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from app.schemas.label import Label


@pytest.fixture
def wire_fixtures_dir() -> Path:
    return Path(__file__).parent / "wire_fixtures"


@pytest.fixture
def synthetic_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (32, 32), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _redact_authorization_headers(payload: dict) -> dict:
    """Strip Authorization headers from a recording payload before write.
    Prevents an API key leaking into a committed recording."""
    import copy
    out = copy.deepcopy(payload)
    headers = out.get("headers")
    if isinstance(headers, dict):
        for key in list(headers.keys()):
            if key.lower() == "authorization" or key.lower() == "x-api-key":
                headers[key] = "REDACTED"
    return out


def _stub_label(
    *,
    label_id: str = "lbl-test",
    batch_id: str = "B-test",
    image_bytes: bytes = b"\x89PNG\r\n\x1a\n",
    content_type: str = "image/png",
    face_tag: str = "front",
    dimensions=None,
) -> Label:
    return Label(
        label_id=label_id,
        batch_id=batch_id,
        image_bytes=image_bytes,
        content_type=content_type,
        face_tag=face_tag,
        dimensions=dimensions,
    )


# === Batch-test helpers ===
from collections.abc import Iterable

from app.schemas.wire.disposition import DispositionEnvelope


def _stub_disposition_envelope(idx: int = 0, *, disposition: str = "pass") -> DispositionEnvelope:
    """Minimal `DispositionEnvelope` for batch tests.

    If `Metrics` or `AuditRecord` grow further required fields, add them here
    with the simplest schema-conforming defaults."""
    from datetime import datetime, timezone

    from app.schemas.audit import AuditRecord
    from app.schemas.metrics import Metrics
    from app.schemas.wire.disposition import ConfidenceBand

    now = datetime.now(timezone.utc)
    return DispositionEnvelope(
        evaluation_id=f"EV-{idx:04d}",
        label_ref=f"lbl-{idx:04d}",
        disposition=disposition,
        disposition_confidence=ConfidenceBand(band="high", numeric=0.95),
        fields=(),
        audit_trail=AuditRecord(
            evaluation_id=f"EV-{idx:04d}",
            rule_set_version="t",
            input_hash="0" * 64,
            output_hash="0" * 64,
            started_at=now,
            completed_at=now,
            per_rule_trace=(),
        ),
        metrics=Metrics(
            total_duration_ms=10,
            per_rule_durations_ms=(),
            vision_duration_ms=5,
        ),
    )


def _fake_evaluator(
    plan: Iterable[tuple[float, DispositionEnvelope]] | None = None,
    *,
    n_items: int = 1,
    latency_s: float = 0.0,
    envelope_factory=None,
):
    """Build a FakeEvaluator. If `plan` is None, repeats `(latency_s, envelope_factory(i))`
    for `n_items` invocations."""
    from tests._fakes.evaluator import FakeEvaluator

    if plan is not None:
        return FakeEvaluator(plan)
    factory = envelope_factory or _stub_disposition_envelope
    return FakeEvaluator((latency_s, factory(i)) for i in range(n_items))


@pytest.fixture(autouse=True)
def _reset_reason_code_cache():
    """Test isolation: the override endpoint caches the reason-code registry
    on first request. Reset between tests so a test that monkeypatches the
    YAML or cwd does not silently use the cached set from a prior test."""
    try:
        import app.api.overrides as _overrides_mod
    except ImportError:
        # The overrides module is not importable here — nothing to reset.
        yield
        return
    _overrides_mod._ACCEPTED_REASON_CODES_CACHE = None
    yield
    _overrides_mod._ACCEPTED_REASON_CODES_CACHE = None


# ---------------------------------------------------------------------------
# live_server and pnpm_built_island fixtures
# ---------------------------------------------------------------------------
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator

import uvicorn

from app.main import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _LiveServer:
    def __init__(self) -> None:
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        config = uvicorn.Config(
            app=create_app(),
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
            loop="asyncio",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run, daemon=True
        )
        self._thread.start()
        # Poll until the server accepts connections (≤2 s).
        deadline = time.time() + 2.0
        while time.time() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", self.port)) == 0:
                    return
            time.sleep(0.05)
        raise RuntimeError(
            f"uvicorn did not bind to {self.port} within 2 s"
        )

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)


@pytest.fixture(scope="session")
def live_server() -> Iterator[_LiveServer]:
    server = _LiveServer()
    server.start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def live_server_url(live_server: _LiveServer) -> str:
    return live_server.url


@pytest.fixture(scope="session")
def pnpm_built_island() -> Path:
    """Build the React island once per session; return the output dir.

    Shared by the browser-driven accessibility, keyboard and reflow tests, so
    the build runs once rather than once per test module.
    """
    root = Path(__file__).resolve().parent.parent
    frontend = root / "frontend"
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        pytest.skip("pnpm not on PATH")
    subprocess.run([pnpm, "install", "--frozen-lockfile"], cwd=frontend, check=True)
    subprocess.run([pnpm, "build"], cwd=frontend, check=True)
    out_dir = root / "app" / "ui" / "static" / "island"
    assert (out_dir / "single.js").exists(), "vite build did not produce single.js"
    return out_dir


def pytest_collection_modifyitems(config, items):
    """Run sync-Playwright tests last.

    Playwright's sync API installs a thread-local event loop that pytest-asyncio
    cannot reuse cleanly; if any Playwright test runs first, every subsequent
    `@pytest.mark.asyncio` test fails with `Cannot run the event loop while
    another loop is running` at teardown. Pushing all `page`-fixture tests to
    the end of the run keeps the asyncio block uncontaminated.
    """
    playwright_items = [it for it in items if "page" in it.fixturenames]
    if not playwright_items:
        return
    other_items = [it for it in items if "page" not in it.fixturenames]
    items[:] = other_items + playwright_items
