"""Hits the deployed URL. Skipped unless TTB_DEPLOY_URL is set."""
import os

import httpx
import pytest


@pytest.fixture
def deploy_url() -> str:
    url = os.environ.get("TTB_DEPLOY_URL")
    if not url:
        pytest.skip("TTB_DEPLOY_URL env var not set; skipping live deploy smoke")
    return url.rstrip("/")


def test_deployed_healthz_200(deploy_url):
    r = httpx.get(f"{deploy_url}/healthz", timeout=10.0)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


def test_deployed_ui_shell_200(deploy_url):
    """The single-label UI shell route returns HTML."""
    r = httpx.get(f"{deploy_url}/", timeout=10.0)
    assert r.status_code == 200
    # The shell is rendered Jinja2 + island bundle reference.
    assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()


def test_deployed_static_island_bundle_200(deploy_url):
    """The island bundle is served from /static/island/."""
    r = httpx.get(f"{deploy_url}/static/island/single.js", timeout=10.0)
    assert r.status_code == 200
    # JS content-type or any reasonable text/JS detection
    ct = r.headers.get("content-type", "").lower()
    assert "javascript" in ct or "text" in ct, f"unexpected content-type {ct!r}"


def test_deployed_tls_chain_valid(deploy_url):
    """HF-issued cert; no insecure flag."""
    r = httpx.get(f"{deploy_url}/healthz", verify=True, timeout=10.0)
    assert r.status_code == 200
