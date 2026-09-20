"""Fetch the regulation text the rule pack cites, and pin it.

Run from the repository root:

    uv run python -m tools.fetch_cfr

It reads every `cfr_citation` in `rules/`, parses each into the sections it
names (`app.cfr.citations`), fetches those sections from the eCFR's versioner
API, and writes each one into `assets/cfr/` beside a manifest recording the
source URL, the version date asked for, the date of retrieval and a SHA-256 of
the text. `tests/test_cfr_corpus.py` checks the corpus against that manifest on
every run; `tests/test_cfr_corpus_matches_ecfr.py` checks it against the eCFR
itself when asked.

**Why a tool and not a runtime call.** The product makes no outbound network
call (`README.md`), and a compliance tool whose regulation text depends on a
third party being up is worse than one that ships the text. Fetching here and
committing the result also means a change in the regulation arrives as a diff
somebody reviews, which is the same bargain
`assets/warnings/govt_warning_16_21.txt` already makes for §16.21.

**Why whole sections.** A rule cites a paragraph; this fetches the section that
paragraph is in. A reviewer deciding whether a label complies needs the clause
in its context, and a tool that quotes one clause of a section is making an
editorial choice about the regulation that it has no standing to make.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import yaml

from app.cfr.citations import Section, Target, parse_citation

ECFR = "https://www.ecfr.gov/api/versioner/v1/full/{version}/title-{title}.xml"
TITLES = "https://www.ecfr.gov/api/versioner/v1/titles.json"
ASSETS = Path("assets/cfr")
MANIFEST = ASSETS / "manifest.json"
RULES = "rules/**/*.yaml"


def rule_pack_citations(pattern: str = RULES) -> set[str]:
    """Every distinct `cfr_citation` string in the rule pack."""
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "cfr_citation" and isinstance(value, str):
                    found.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for path in glob.glob(pattern, recursive=True):
        walk(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    return found


def asset_key(target: Target) -> str:
    """The name a target is stored and looked up under.

    A paragraph is not in the key: two rules citing `§4.32(a)(1)` and
    `§4.32(b)(2)` read the same section, and holding it twice would let the two
    copies drift.
    """
    if isinstance(target, Section):
        return f"title-{target.title}-section-{target.section}"
    return f"title-{target.title}-part-{target.part}-subpart-{target.subpart}"


def query_for(target: Target) -> dict[str, str]:
    """The eCFR query parameters that address one target."""
    if isinstance(target, Section):
        return {"part": target.part, "section": target.section}
    return {"part": target.part, "subpart": target.subpart}


def _fetch(url: str) -> bytes:
    """GET a URL, decompressing if the server compressed it.

    The eCFR refuses a request that does not permit compression — it answers 406
    with "This endpoint requires response compression" — so the header is not
    optional politeness.
    """
    request = urllib.request.Request(
        url,
        headers={
            "Accept-Encoding": "gzip",
            "User-Agent": "ttb-label-check/asset-fetch (+https://github.com/AaronCarney/ttb-label-check)",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return body


def _text_of(node: ET.Element) -> str:
    """Every character under a node, with the inline emphasis tags dropped.

    The regulation italicises defined terms inside a paragraph. The italics are
    not the wording, and a reader of the panel is reading the wording.
    """
    return "".join(node.itertext())


def extract(xml_body: bytes) -> tuple[str, str]:
    """The heading and the wording, from one eCFR XML response.

    Returns the heading on its own as well as in the body, because the panel
    shows it as a title and a reviewer reading the body should still see which
    section they are in.
    """
    root = ET.fromstring(xml_body)
    heading_node = root.find(".//HEAD")
    heading = _text_of(heading_node).strip() if heading_node is not None else ""

    lines: list[str] = []
    for node in root.iter():
        # A heading and a paragraph are both wording a reader reads, in the
        # order the regulation prints them. Nothing else in the XML is — the
        # amendment note at the foot is editorial history, not the rule.
        if node.tag in ("HEAD", "P"):
            lines.append(_text_of(node).strip())
    return heading, "\n\n".join(line for line in lines if line)


def latest_issue_dates() -> dict[int, str]:
    """The date each title was last issued, as the eCFR reports it.

    Asked for rather than assumed, because the titles do not move together: on
    the day this was written title 27 was issued 2026-09-16 and title 19
    2026-08-26, and a request naming a date a title has no issue for is a 404.
    Pinning each title at its own latest issue also makes the manifest say
    exactly which text is held, rather than which date somebody typed.
    """
    body = json.loads(_fetch(TITLES))
    return {
        int(t["number"]): t["latest_issue_date"]
        for t in body["titles"]
        if t.get("latest_issue_date")
    }


def fetch_target(target: Target, version: str) -> tuple[str, str, str]:
    """The heading, the wording and the URL they came from."""
    query = query_for(target)
    url = (
        ECFR.format(version=version, title=target.title)
        + "?"
        + "&".join(f"{k}={v}" for k, v in query.items())
    )
    heading, text = extract(_fetch(url))
    return heading, text, url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        default=None,
        help=(
            "the date whose text to fetch, as the eCFR versioner wants it. "
            "Default: each title's own latest issue date, asked of the API."
        ),
    )
    args = parser.parse_args(argv)

    citations = sorted(rule_pack_citations())
    targets: dict[str, Target] = {}
    unparsed: list[str] = []
    for citation in citations:
        parsed = parse_citation(citation)
        if not parsed:
            unparsed.append(citation)
            continue
        for target in parsed:
            targets[asset_key(target)] = target

    if unparsed:
        print("these citations could not be parsed, so their text is not held:", file=sys.stderr)
        for citation in unparsed:
            print(f"  {citation}", file=sys.stderr)

    if args.version is None:
        try:
            issued = latest_issue_dates()
        except (urllib.error.URLError, KeyError, ValueError) as exc:
            print(f"FAILED to ask the eCFR which dates it has: {exc}", file=sys.stderr)
            return 1
    else:
        issued = {}

    ASSETS.mkdir(parents=True, exist_ok=True)
    retrieved = date.today().isoformat()
    manifest: dict[str, dict[str, str]] = {}

    for key in sorted(targets):
        target = targets[key]
        version = args.version or issued.get(target.title)
        if version is None:
            print(
                f"FAILED {key}: the eCFR lists no issue date for title {target.title}",
                file=sys.stderr,
            )
            return 1
        try:
            heading, text, url = fetch_target(target, version)
        except (urllib.error.URLError, ET.ParseError) as exc:
            print(f"FAILED {key}: {exc}", file=sys.stderr)
            return 1
        if not text.strip():
            print(f"FAILED {key}: the eCFR returned no wording", file=sys.stderr)
            return 1
        path = ASSETS / f"{key}.txt"
        path.write_text(text + "\n", encoding="utf-8")
        manifest[key] = {
            "heading": heading,
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_url": url,
            "version_date": version,
            "retrieved": retrieved,
        }
        print(f"{key}: {heading}")

    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\n{len(manifest)} sections written to {ASSETS}/, manifest at {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
