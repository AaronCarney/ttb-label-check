"""Playwright and axe-core: zero WCAG 2.0 AA violations on every fixture.

Loads the Jinja shell against the live uvicorn fixture, injects the canned
envelope into the DOM before the React island reads it, then runs axe-core
inside the page and asserts no AA violations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "envelopes" / "single"
AXE_PATH = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"


_SINGLE_FIXTURES = sorted(p.name for p in FIXTURES.glob("*.json"))


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
@pytest.mark.parametrize("fixture_name", _SINGLE_FIXTURES)
def test_axe_zero_aa_violations_single(fixture_name: str, page: Page, live_server_url: str) -> None:
    envelope = json.loads((FIXTURES / fixture_name).read_text())
    # Inject the envelope BEFORE the island imports.
    page.add_init_script(
        script=f"""
          (() => {{
            const tag = document.createElement('script');
            tag.id = 'envelope';
            tag.type = 'application/json';
            tag.textContent = {json.dumps(json.dumps(envelope))};
            const insert = () => {{
              if (document.body) {{
                document.body.appendChild(tag);
              }} else {{
                setTimeout(insert, 0);
              }}
            }};
            if (document.readyState === 'loading') {{
              document.addEventListener('DOMContentLoaded', insert);
            }} else {{
              insert();
            }}
          }})();
        """
    )
    page.goto(f"{live_server_url}/")
    # Wait for the island to mount.
    page.wait_for_selector('[data-mounted="true"]', timeout=5000)
    page.add_script_tag(path=str(AXE_PATH))
    result = page.evaluate(
        """async () => {
          const r = await window.axe.run(document, {
            runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] },
          });
          return r.violations.map(v => ({
            id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
          }));
        }"""
    )
    assert result == [], f"axe violations on {fixture_name}: {result}"


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_axe_zero_aa_violations_batch(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/batch/abc-123")
    page.wait_for_selector('[data-mounted="true"]', timeout=5000)
    page.add_script_tag(path=str(AXE_PATH))
    result = page.evaluate(
        """async () => {
          const r = await window.axe.run(document, {
            runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] },
          });
          return r.violations.map(v => ({
            id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
          }));
        }"""
    )
    assert result == [], f"axe violations on /batch: {result}"
