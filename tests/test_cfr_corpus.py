"""The regulation text the product holds, and what it says when it holds none.

`docs/decisions.md#0034` refused the citation panel because filling it meant
"writing regulation text by hand into a compliance tool with no test that can
check it against the regulation". These are those tests: the corpus matches the
manifest it was written with, it covers every citation the rule pack makes, and
the one section this repository already pinned by an independent route — the
§16.21 warning — says the same thing in both places.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.cfr.corpus import held_sections, load_manifest
from tests.test_cfr_citations import _rule_pack_citations

MANIFEST = Path("assets/cfr/manifest.json")


def test_manifest_exists() -> None:
    assert MANIFEST.exists(), "run `uv run python -m tools.fetch_cfr` to build the corpus"


def test_every_held_file_matches_its_recorded_hash() -> None:
    """An edit to the wording is a change to what the product claims the
    regulation says, so it has to be a change somebody made on purpose."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    drifted = []
    for key, entry in sorted(manifest.items()):
        path = Path(entry["path"])
        if not path.exists():
            drifted.append(f"{key}: missing {path}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            drifted.append(f"{key}: {actual} != {entry['sha256']}")
    assert drifted == [], drifted


def test_every_entry_records_where_and_when_it_came_from() -> None:
    """Text with no provenance is text somebody typed."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest, "the manifest is empty"
    for key, entry in sorted(manifest.items()):
        assert entry["source_url"].startswith("https://www.ecfr.gov/"), key
        assert entry["version_date"], key
        assert entry["retrieved"], key
        assert entry["heading"], key


def test_every_rule_pack_citation_has_its_text_held() -> None:
    """A finding whose citation the panel cannot fill is a finding a reviewer
    cannot check, so the gap fails here rather than showing up in the panel."""
    missing = sorted(c for c in _rule_pack_citations() if not held_sections(c))
    assert missing == [], f"cited but not held: {missing}"


def test_the_warning_section_agrees_with_the_asset_pinned_separately() -> None:
    """The one independent check available on the fetched text.

    `assets/warnings/govt_warning_16_21.txt` was pinned for the verbatim
    validator by a different route entirely, and the §16.21 this tool fetched
    has to carry the same sentences. If the fetcher or its XML extraction were
    mangling the regulation, this is where it would show.
    """
    asset = Path("assets/warnings/govt_warning_16_21.txt").read_text(encoding="utf-8").strip()
    held = Path("assets/cfr/title-27-section-16.21.txt").read_text(encoding="utf-8")

    # The asset is one line; the regulation prints the two numbered sentences as
    # separate paragraphs. Compare sentence by sentence rather than as one blob.
    first, second = asset.split(" (2) ")
    assert first in held.replace("\n", " ")
    assert f"(2) {second}" in held.replace("\n", " ")


@pytest.mark.parametrize(
    ("citation", "expected_keys"),
    [
        ("27 CFR §4.33", ["title-27-section-4.33"]),
        ("27 CFR §16.22(a)(2)", ["title-27-section-16.22"]),
        (
            "27 CFR §4.32(a)(1), §4.33",
            ["title-27-section-4.32", "title-27-section-4.33"],
        ),
        (
            "27 CFR §4.35(e), 19 CFR §134.45",
            ["title-27-section-4.35", "title-19-section-134.45"],
        ),
        ("27 CFR §5 Subpart I", ["title-27-part-5-subpart-I"]),
        (
            "27 CFR §7.63(a)(2), Subpart I",
            ["title-27-section-7.63", "title-27-part-7-subpart-I"],
        ),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_a_citation_answers_with_the_sections_it_names(
    citation: str, expected_keys: list[str]
) -> None:
    assert [s.key for s in held_sections(citation)] == expected_keys


def test_the_cited_paragraph_travels_with_the_section() -> None:
    """The panel shows the section whole and points at the clause the rule
    rests on, so the clause has to survive the lookup."""
    (section,) = held_sections("27 CFR §16.22(a)(2)")
    assert section.paragraph == "(a)(2)"
    assert section.heading.startswith("§ 16.22")
    assert section.text.strip()


def test_a_citation_with_no_paragraph_says_so_rather_than_inventing_one() -> None:
    (section,) = held_sections("27 CFR §4.33")
    assert section.paragraph is None


def test_an_unreadable_citation_holds_nothing() -> None:
    """The panel's honest empty state. It must come from here, not from the
    panel guessing that an empty answer means a failed fetch."""
    assert held_sections("see the regulation") == []
    assert held_sections("") == []


def test_a_citation_that_parses_but_is_not_held_holds_nothing() -> None:
    """A section nobody fetched is not a section the panel may describe.

    §4.39 is a real section of a part the corpus covers and no rule cites it, so
    the corpus does not hold it — which is exactly the case that must not
    fall back to the part, the subpart, or the nearest thing it has.
    """
    assert held_sections("27 CFR §4.39") == []


def test_the_loader_reads_the_manifest_once() -> None:
    """Serving a panel must not re-read 24 files per request."""
    assert load_manifest() is load_manifest()
