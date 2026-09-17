"""The decision document's numbering and its citations hold together.

Entry numbers and index anchors used to be assigned by hand, by whoever wrote
the record, and the three failures that produced were all the same failure:
two records written under number 0013 on the same day, four records with no
way to link to them, and two plans citing numbers that had since moved. None
of those is a judgement call, so none of them needs a person to catch it.

Three properties, checked against the document and against every tracked file
that cites it:

1. No number is used twice.
2. Every entry carries a `<a id="NNNN">` anchor, and every anchor carries an
   entry, so `docs/decisions.md#NNNN` is a link that lands somewhere.
3. Every `decisions.md#NNNN` citation anywhere in the repository names an
   entry that exists.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

DOC = Path("docs/decisions.md")

# "## 0015. The brand check compares an admissible set, not one string"
HEADING = re.compile(r"^## (\d{4})\. \S", re.MULTILINE)
ANCHOR = re.compile(r'^<a id="(\d{4})"></a>$', re.MULTILINE)
# Any citation of an entry: "docs/decisions.md#0015", "../decisions.md#0015",
# and the in-document form "](#0015)".
CITATION = re.compile(r"decisions\.md#(\d{4})|\]\(#(\d{4})\)")

# Built bundles and binaries carry no citations and are slow to read.
SKIP = re.compile(r"^(app/ui/static/|frontend/dist/)|\.(png|jpg|jpeg|pdf|ico|svg|woff2?|lock)$")


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _tracked_text_files() -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return [Path(p) for p in listing if not SKIP.search(p)]


def test_no_entry_number_is_used_twice() -> None:
    numbers = HEADING.findall(_doc_text())
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    assert not duplicates, f"entry numbers used more than once: {duplicates}"


def test_every_entry_has_an_anchor_and_every_anchor_has_an_entry() -> None:
    text = _doc_text()
    entries = set(HEADING.findall(text))
    anchors = set(ANCHOR.findall(text))
    assert entries, "no entries found — the heading shape changed"
    assert not entries - anchors, f"entries with no anchor to link to: {sorted(entries - anchors)}"
    assert not anchors - entries, f"anchors naming no entry: {sorted(anchors - entries)}"


def test_the_anchor_sits_immediately_above_its_own_entry() -> None:
    """An anchor that drifts away from its heading lands a reader on the
    entry above or below it, which is worse than a broken link."""
    pairs = re.findall(r'^<a id="(\d{4})"></a>\n## (\d{4})\. ', _doc_text(), re.MULTILINE)
    mismatched = [(a, h) for a, h in pairs if a != h]
    assert not mismatched, f"anchor and heading disagree: {mismatched}"
    assert len(pairs) == len(set(ANCHOR.findall(_doc_text()))), (
        "an anchor is not directly above a heading"
    )


def test_every_citation_in_the_repository_names_a_real_entry() -> None:
    entries = set(HEADING.findall(_doc_text()))
    unresolved: dict[str, list[str]] = {}
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for whole, in_doc in CITATION.findall(text):
            number = whole or in_doc
            if number not in entries:
                unresolved.setdefault(number, []).append(str(path))
    assert not unresolved, f"citations naming no entry: {unresolved}"
