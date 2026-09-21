"""The regulation wording this product holds, looked up by a finding's citation.

The text is in `assets/cfr/`, fetched from the eCFR by `tools/fetch_cfr.py` and
committed with a manifest recording, per section, where it came from, which
issue date it is, when it was retrieved and its SHA-256.
`tests/test_cfr_corpus.py` checks the files against that manifest.

**A lookup either answers with the regulation or answers with nothing.** There
is no nearest match and no fallback to the part or the subpart. A compliance
tool showing a reviewer the wrong section is worse than one showing none
(`docs/decisions.md#0034`), and a reviewer who is shown a section has to be able
to take it as the section the rule cites.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from app.cfr.citations import Section, Target, parse_citation

MANIFEST_PATH = Path("assets/cfr/manifest.json")


class HeldSection(NamedTuple):
    """One section of the regulation, as the panel shows it."""

    key: str
    heading: str
    text: str
    paragraph: str | None
    source_url: str
    version_date: str
    retrieved: str


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, dict[str, str]]:
    """The manifest, read once per process.

    Cached because a results page asks for a section per citation chip and the
    manifest does not change while the service runs. A corpus that is missing
    entirely gives an empty manifest rather than an error: the panel's answer is
    then "not held", which is true.
    """
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=256)
def _read(path: str) -> str | None:
    """One section's wording, read once per process."""
    file = Path(path)
    if not file.exists():
        return None
    return file.read_text(encoding="utf-8")


def _key_for(target: Target) -> str:
    """The manifest key a target is stored under.

    Kept in step with `tools.fetch_cfr.asset_key` by
    `tests/test_cfr_corpus.py`, which looks up every citation the rule pack
    makes and fails if any of them misses.
    """
    if isinstance(target, Section):
        return f"title-{target.title}-section-{target.section}"
    return f"title-{target.title}-part-{target.part}-subpart-{target.subpart}"


def _body(text: str, heading: str) -> str:
    """The section's wording without the heading line the panel prints itself.

    Every file under `assets/cfr/` opens with its own heading, because that is
    how the eCFR serves the section and the file is kept as fetched — it is
    compared against the live section by `tests/test_cfr_corpus_matches_ecfr.py`.
    The panel renders the heading above the text, so the line is dropped here,
    once, rather than shown to a reviewer twice. A file that does not open with
    its heading is returned whole.
    """
    first, separator, rest = text.partition("\n")
    if separator and first.strip() == heading.strip():
        return rest.lstrip("\n")
    return text


def held_sections(citation: str) -> list[HeldSection]:
    """The regulation behind one citation string, or nothing.

    Nothing means one of three things, and the panel does not distinguish them
    to a reviewer because the consequence is the same: the citation could not be
    read, or it names a section the corpus does not hold, or the file behind a
    manifest entry is gone. In every case the product does not have the wording
    and says so.
    """
    targets = parse_citation(citation)
    if not targets:
        return []

    manifest = load_manifest()
    held: list[HeldSection] = []
    for target in targets:
        entry = manifest.get(_key_for(target))
        if entry is None:
            return []
        text = _read(entry["path"])
        if text is None:
            return []
        held.append(
            HeldSection(
                key=_key_for(target),
                heading=entry["heading"],
                text=_body(text, entry["heading"]),
                paragraph=target.paragraph if isinstance(target, Section) else None,
                source_url=entry["source_url"],
                version_date=entry["version_date"],
                retrieved=entry["retrieved"],
            )
        )
    return held
