"""Playwright and axe-core: zero WCAG 2.0 AA violations on every screen.

Loads the Jinja shell against the live uvicorn fixture, streams a recorded
result into it the way the worker does, then runs axe-core inside the page and
asserts no AA violations.

`app/api/ui/shells.py` serves one form and one results page, and NFR-3 in
`docs/PRD.md` asks for "an automated scan on every screen", so both are scanned
here — the results page in each of the three states a reviewer meets it in:
waiting, one label, and a submission of many.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from tests._browser import SINGLE_FIXTURES, envelope_fixture, open_results

ROOT = Path(__file__).resolve().parent.parent
BATCH_EVENTS = ROOT / "tests" / "fixtures" / "envelopes" / "batch" / "05-batch-of-50-events.jsonl"
AXE_PATH = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"


_SINGLE_FIXTURES = sorted(p.name for p in SINGLE_FIXTURES.glob("*.json"))


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
        r"""async () => {
          const r = await window.axe.run(document, {
            runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] },
          });
          // The node targets, not just a count: a reviewer reading a failure
          // has to know which element axe meant before they can judge it.
          const node = n => ({
            target: n.target,
            summary: (n.failureSummary || '').replace(/\s+/g, ' ').trim(),
          });
          // For an undecided check, also carry what axe measured. axe reports a
          // contrast check as undecided when it computed both colours and they
          // came out identical, so the two colours are the whole of the
          // evidence a reviewer needs and the summary text does not carry them.
          const nodeWithData = n => ({
            ...node(n),
            checks: [...(n.any || []), ...(n.all || []), ...(n.none || [])]
              .map(c => ({ id: c.id, data: c.data })),
          });
          const shape = f => v => ({
            id: v.id,
            impact: v.impact,
            help: v.help,
            nodes: v.nodes.map(f),
          });
          return {
            violations: r.violations.map(shape(node)),
            incomplete: r.incomplete.map(shape(nodeWithData)),
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
def test_axe_zero_aa_violations_one_result(
    fixture_name: str, page: Page, live_server_url: str
) -> None:
    """The results page showing one checked label, which is what a reviewer who
    submitted one label sees: the result and no list beside it."""
    open_results(page, live_server_url, [envelope_fixture(fixture_name)])
    _assert_accessible(_run_axe(page), fixture_name)


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_axe_zero_aa_violations_entry_form(page: Page, live_server_url: str) -> None:
    """The form a reviewer arrives at. It mounts no island — the whole page is
    server-rendered HTML — so there is no `[data-mounted]` to wait for."""
    page.goto(f"{live_server_url}/")
    page.wait_for_load_state("domcontentloaded")
    _assert_accessible(_run_axe(page), "/")


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_axe_zero_aa_violations_waiting(page: Page, live_server_url: str) -> None:
    """The results page in the moment after a check is started, before the
    first label is done. The stream is held open with nothing on it."""
    open_results(page, live_server_url, [], end=False, wait_for_result=False)
    _assert_accessible(_run_axe(page), "/batch (waiting)")


def _batch_envelopes() -> list[dict[str, Any]]:
    """The fifty recorded results of a batch, as the fixture stores them."""
    return [json.loads(line) for line in BATCH_EVENTS.read_text().splitlines() if line.strip()]


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_axe_zero_aa_violations_batch_populated(page: Page, live_server_url: str) -> None:
    """The submission list with rows in it, beside the label the reviewer has open.

    This is the state a reviewer checking a folder of labels actually sees, and
    it is the only one that renders the table at all: a submission of one shows
    its result and no list. Fifty rows of real dispositions is what gives axe
    data cells to decide `th-has-data-cells` against.

    The stream is stubbed rather than driven, because what is under test here is
    the rendered table's accessibility, not the transport.
    """
    envelopes = _batch_envelopes()
    open_results(page, live_server_url, envelopes)
    page.wait_for_selector("tbody tr", timeout=5000)
    rows = page.eval_on_selector_all("tbody tr", "els => els.length")
    assert rows == len(envelopes), f"expected {len(envelopes)} rows, rendered {rows}"
    _assert_accessible(_run_axe(page), "/batch (populated)")


# The smallest contrast ratio WCAG 2.0 AA accepts for normal-sized text, from
# success criterion 1.4.3. docs/PRD.md NFR-3 commits the console to AA.
_AA_NORMAL_TEXT_MIN_RATIO = 4.5

# A button carrying only an icon shows no text, so 1.4.3 does not reach it.
# The nearest criterion is 1.4.11 Non-text Contrast at 3:1, which is WCAG 2.1
# and sits above the WCAG 2.0 AA level NFR-3 commits to. It is held here as a
# deliberate choice — kept and not claimed, the same way globals.css keeps the
# reduced-motion gate — because an icon nobody can see is not a control.
_NON_TEXT_MIN_RATIO = 3.0

# WCAG's own relative-luminance and contrast formulas, run inside the page so
# they read the colours the browser actually painted rather than the colours the
# stylesheet asks for.
_CONTRAST_JS = r"""
  el => {
    const channel = c => {
      c /= 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    const luminance = ([r, g, b]) =>
      0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
    const parse = s => (s.match(/[\d.]+/g) || []).map(Number);
    // An element painted transparent shows whatever its nearest painted
    // ancestor shows, which is what the reader sees behind the text.
    const painted = start => {
      for (let n = start; n; n = n.parentElement) {
        const c = parse(getComputedStyle(n).backgroundColor);
        if (c.length >= 3 && (c.length < 4 || c[3] > 0)) return c.slice(0, 3);
      }
      return [255, 255, 255];
    };
    const style = getComputedStyle(el);
    const fg = parse(style.color).slice(0, 3);
    const bg = painted(el);
    const [hi, lo] = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
    const hex = c => '#' + c.map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
    return { color: hex(fg), background: hex(bg), ratio: (hi + 0.05) / (lo + 0.05) };
  }
"""


def _settle(page: Page, button: Any) -> None:
    """Wait for a background transition to finish before the colour is read.

    `globals.css` gives every `.primary-button` `transition: background-color
    120ms`, so the colour painted the instant the pointer arrives is the colour
    the button is leaving, not the colour it is going to. Reading it immediately recorded
    the resting background twice and reported the hover state as clean while two
    close buttons and a cancel button were painting white text on #f4f4f6 —
    1.06:1 — the exact defect the hover pass exists to catch.

    The wait is on the pixel value rather than on a fixed sleep: sample until
    two reads agree, so a button with no transition costs one extra sample and a
    slower machine is not a flake.
    """
    previous = None
    for _ in range(40):
        current = button.evaluate("el => getComputedStyle(el).backgroundColor")
        if current == previous:
            return
        previous = current
        page.wait_for_timeout(50)


def _visible_button_contrasts(page: Page, screen: str) -> list[dict[str, Any]]:
    """Measure every button the screen is currently showing, resting and hovered.

    Hover is measured because a background utility can win the cascade in the
    hover state alone, and axe never enters that state: it scans the document as
    loaded. A control that becomes unreadable under the pointer is unreadable in
    the only moment the reader is using it.

    A disabled button is measured too, and reported, but it is not held to a
    floor. SC 1.4.3 carries its own exception and this is it, verbatim:
    "Incidental: Text or images of text that are part of an inactive user
    interface component, that are pure decoration, that are not visible to
    anyone, or that are part of a picture that contains significant other visual
    content, have no contrast requirement." A disabled control is an inactive
    user interface component, so the criterion this suite enforces does not
    reach it. It stays in the measurements because a reviewer doing the
    conformance review NFR-3 also asks for should see the number and judge it.
    """
    measured: list[dict[str, Any]] = []
    buttons = page.get_by_role("button")
    for index in range(buttons.count()):
        button = buttons.nth(index)
        if not button.is_visible():
            continue
        label = (button.inner_text() or "").strip()
        name = label or (button.get_attribute("aria-label") or "").strip() or f"button {index}"
        floor = _AA_NORMAL_TEXT_MIN_RATIO if label else _NON_TEXT_MIN_RATIO
        inactive = button.is_disabled()
        for state in ("resting", "hovered"):
            if state == "hovered":
                button.hover()
                _settle(page, button)
            measured.append(
                {
                    "screen": screen,
                    "button": name,
                    "state": state,
                    "floor": floor,
                    "exempt": inactive,
                }
                | button.evaluate(_CONTRAST_JS)
            )
    return measured


def _assert_buttons_legible(measured: list[dict[str, Any]]) -> None:
    assert measured, "no visible buttons were measured, so nothing was actually checked"
    held = [m for m in measured if not m["exempt"]]
    assert held, "every measured button was exempt, so no floor was actually applied"
    illegible = [m for m in held if m["ratio"] < m["floor"]]
    assert not illegible, "buttons below their contrast floor: " + "; ".join(
        f'{m["screen"]} "{m["button"]}" {m["state"]}: {m["color"]} on {m["background"]} '
        f"is {m['ratio']:.2f}:1, below {m['floor']}:1"
        for m in illegible
    )


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_result_screen_buttons_are_legible(page: Page, live_server_url: str) -> None:
    """Every button on the results screen, in both states.

    axe reports the "Copy message" button's contrast as undecided rather than as
    a violation: it computed a foreground and a background, they came out
    identical, and its color-contrast check returns undefined on a 1:1 ratio
    because 1:1 is also how deliberately invisible text looks (the `equalRatio`
    branch in `axe.js`). Undecided is not a pass, so the ratio is measured here
    directly and both colours are reported, which is what tells a reviewer
    whether the label can be read at all.
    """
    open_results(page, live_server_url, [envelope_fixture("04-low-res-blurry.json")])
    page.get_by_role("button", name="Copy message").wait_for(timeout=5000)
    _assert_buttons_legible(_visible_button_contrasts(page, "/batch"))


@pytest.mark.usefixtures("live_server", "pnpm_built_island")
def test_override_drawer_buttons_are_legible(page: Page, live_server_url: str) -> None:
    """The override drawer's own buttons, which no scan has ever reached.

    The drawer renders through a React portal and only once it is open, so the
    document axe scans on load does not contain it. Pressing "O" is how a
    reviewer opens it (`useKeyboardShortcuts`), so that is how it is opened here.
    """
    open_results(page, live_server_url, [envelope_fixture("04-low-res-blurry.json")])
    page.keyboard.press("o")
    page.get_by_role("button", name="Cancel").wait_for(timeout=5000)
    _assert_buttons_legible(_visible_button_contrasts(page, "/batch (override drawer)"))
