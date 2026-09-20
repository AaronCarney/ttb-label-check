"""`GET /cfr` — the regulation behind a finding's citation, for the panel.

The parse lives on the server rather than in the island, so there is one
implementation of the grammar rather than two that can drift apart. What the
island sends is the citation string exactly as it appears on the card.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_a_held_citation_answers_with_its_wording() -> None:
    response = client.get("/cfr", params={"citation": "27 CFR §4.33"})
    assert response.status_code == 200
    body = response.json()
    assert body["citation"] == "27 CFR §4.33"
    (section,) = body["sections"]
    assert section["heading"] == "§ 4.33 Brand names."
    assert "brand name" in section["text"]
    assert section["paragraph"] is None
    assert section["source_url"].startswith("https://www.ecfr.gov/")
    assert section["version_date"]
    assert section["retrieved"]


def test_a_compound_citation_answers_with_every_section_it_names() -> None:
    response = client.get("/cfr", params={"citation": "27 CFR §4.35(e), 19 CFR §134.45"})
    assert response.status_code == 200
    sections = response.json()["sections"]
    assert [s["heading"].split()[1] for s in sections] == ["4.35", "134.45"]
    assert sections[0]["paragraph"] == "(e)"
    assert sections[1]["paragraph"] is None


def test_a_citation_the_product_does_not_hold_is_an_answer_not_an_error() -> None:
    """The panel has an honest empty state to render, and it must be able to
    tell that state from a request that failed. An empty list at 200 says "we
    do not have this"; a non-200 says "ask again"."""
    response = client.get("/cfr", params={"citation": "see the regulation"})
    assert response.status_code == 200
    assert response.json() == {"citation": "see the regulation", "sections": []}


def test_a_missing_citation_parameter_is_refused() -> None:
    assert client.get("/cfr").status_code == 422


def test_every_citation_the_rule_pack_makes_is_answerable() -> None:
    """The panel is only worth reserving room for if the chips fill it."""
    from tests.test_cfr_citations import _rule_pack_citations

    empty = []
    for citation in sorted(_rule_pack_citations()):
        body = client.get("/cfr", params={"citation": citation}).json()
        if not body["sections"]:
            empty.append(citation)
    assert empty == [], f"chips that would open an empty panel: {empty}"
