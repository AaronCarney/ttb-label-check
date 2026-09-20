"""The held regulation text, checked against the eCFR that issued it.

`docs/decisions.md#0034` refused a citation panel because filling it meant
"writing regulation text by hand into a compliance tool with no test that can
check it against the regulation". This is that test. It re-fetches every section
in the corpus and compares it, character for character, with the committed file.

It reaches the network, so it does not run by default — the same bargain
`tests/test_deploy_healthz.py` makes for the deployed service. Set
`TTB_CHECK_ECFR=1` to run it:

    TTB_CHECK_ECFR=1 uv run pytest tests/test_cfr_corpus_matches_ecfr.py

A failure here is not necessarily a defect. The regulation may have been
amended since the corpus was pinned, in which case the fix is to re-run
`uv run python -m tools.fetch_cfr` and review the diff — which is the point of
holding the text this way rather than typing it in.
"""

from __future__ import annotations

import json
import os
import urllib.error
from pathlib import Path

import pytest

from tools.fetch_cfr import MANIFEST, _fetch, extract

pytestmark = pytest.mark.skipif(
    not os.environ.get("TTB_CHECK_ECFR"),
    reason="TTB_CHECK_ECFR not set; skipping the live eCFR comparison",
)


def _manifest() -> dict[str, dict[str, str]]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", sorted(_manifest()) if MANIFEST.exists() else [])
def test_held_text_is_what_the_ecfr_serves(key: str) -> None:
    entry = _manifest()[key]
    try:
        _, fetched = extract(_fetch(entry["source_url"]))
    except urllib.error.URLError as exc:  # pragma: no cover - network weather
        pytest.skip(f"eCFR unreachable: {exc}")

    held = Path(entry["path"]).read_text(encoding="utf-8")
    assert fetched + "\n" == held, (
        f"{key} differs from {entry['source_url']}. If the regulation was amended, "
        f"re-run `uv run python -m tools.fetch_cfr` and review the diff."
    )
