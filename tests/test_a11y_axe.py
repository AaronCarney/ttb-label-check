"""Playwright and axe-core: zero WCAG 2.0 AA violations on every screen.

Loads the Jinja shell against the live uvicorn fixture, injects the canned
envelope into the DOM before the React island reads it, then runs axe-core
inside the page and asserts no AA violations.

`app/api/ui/shells.py` serves three GET routes and NFR-3 in `docs/PRD.md` asks
for "an automated scan on every screen", so all three are scanned here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "envelopes" / "single"
AXE_PATH = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"


_SINGLE_FIXTURES = sorted(p.name for p in FIXTURES.glob("*.json"))


# axe sorts every check it runs into four buckets: `violations`, `passes`,
# `incomplete` and `inapplicable`. `incomplete` is the one axe could not decide
# by itself — a contrast check over a background image, say, where the answer
# depends on pixels it will not judge. It is NOT a pass. Reading only
# `violations` therefore makes an undecidable check indistinguishable from a
# clean one, which is the single thing this project is built not to do.
#
# NFR-3 asks for an automated scan *and* a conformance review before each
# release. This bucket is where the first hands work to the second: it is the
# machine saying which checks a person still has to make. So it is asserted
# rather than dropped.
#
# A rule id is listed here only after a person has looked at what axe could not
# decide and written down what they found. The reason is the record of that
# review. An empty mapping means nobody has looked yet, and any undecided check
# fails the suite until somebody does.
REVIEWED_INCOMPLETE: dict[str, str] = {}


def _run_axe(page: Page) -> dict[str, Any]:
    """Run axe against the loaded page and return its violations and its undecided checks."""
    page.add_script_tag(path=str(AXE_PATH))
    return page.evaluate(
        """async () => {
          const r = await window.axe.run(document, {
            runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] },
          });
          const shape = v => ({
            id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
          });
          return {
            violations: r.violations.map(shape),
            incomplete: r.incomplete.map(shape),
          };
        }"""
    )


def _assert_accessible(result: dict[str, Any], screen: str) -> None:
    """Fail on a violation, and fail just as loudly on a check axe could not decide."""
    assert result["violations"] == [], f"axe violations on {screen}: {result['violations']}"
    undecided = {item["id"] for item in result["incomplete"]}
    unreviewed = sorted(undecided - set(REVIEWED_INCOMPLETE))
    assert not unreviewed, (
        f"axe could not decide these checks on {screen} and no one has reviewed them: "
        f"{unreviewed}. Full detail: {result['incomplete']}. "
        "An undecided check is not a pass. Look at each one, then record it in "
        "REVIEWED_INCOMPLETE with what you found."
    )


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
    _assert_accessible(_run_axe(page), fixture_name)


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_axe_zero_aa_violations_batch(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/batch/abc-123")
    page.wait_for_selector('[data-mounted="true"]', timeout=5000)
    _assert_accessible(_run_axe(page), "/batch")


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_axe_zero_aa_violations_batch_list(page: Page, live_server_url: str) -> None:
    """The third screen. `app/api/ui/shells.py` serves three GET routes and this
    scan visited two of them, while NFR-3 in `docs/PRD.md` asks for "an
    automated scan on every screen" — so the requirement was unmet on coverage
    even with every existing case green.

    This page renders server-side without the island, so there is no
    `[data-mounted]` to wait for; the shell being loaded is the whole page.
    """
    page.goto(f"{live_server_url}/batches")
    page.wait_for_load_state("domcontentloaded")
    _assert_accessible(_run_axe(page), "/batches")
