"""``GET /cfr`` — the wording of the regulation a finding cites.

The results island asks for a citation exactly as the card prints it and gets
back the sections that citation names, from text committed under `assets/cfr/`.
No request here reaches the network: the text was fetched once by
`tools/fetch_cfr.py` and pinned (`docs/decisions.md#0046`).

**Why the parse is here and not in the island.** The grammar of a citation
string is the one part of this that can mislink a reviewer to the wrong
regulation, which is what `docs/decisions.md#0034` refused the panel over. One
implementation, in `app.cfr.citations`, with one test table over every string
the rule pack uses, is defensible; a second copy in TypeScript would be two
grammars that agree until they do not.

**Why an unheld citation is a 200 and not a 404.** The panel renders "this
product does not hold the text of that section" as an ordinary state, and it has
to be able to tell that state from a request that failed on the way. An empty
list under a 200 says the product looked and has nothing; a non-200 says try
again.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.cfr.corpus import held_sections

router = APIRouter()


class HeldSectionOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    heading: str
    text: str
    paragraph: str | None
    source_url: str
    version_date: str
    retrieved: str


class CitationOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    citation: str
    sections: tuple[HeldSectionOut, ...]


@router.get("/cfr", response_model=CitationOut)
async def cfr(citation: str = Query(...)) -> CitationOut:
    """The sections one citation names, or an empty list if none are held."""
    return CitationOut(
        citation=citation,
        sections=tuple(HeldSectionOut(**s._asdict()) for s in held_sections(citation)),
    )
