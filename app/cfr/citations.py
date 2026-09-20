"""A citation string, as the rule pack writes it, read as the sections it names.

The pack cites in prose — `27 CFR §4.32(a)(1), §4.33`, `27 CFR §5 Subpart I`,
`27 CFR §4.35(e), 19 CFR §134.45` — and the eCFR is addressed by title, part and
section. This module is the whole of the distance between the two.

`docs/decisions.md#0034` refused a citation panel partly because "the citation
strings are heterogeneous enough that parsing them into section URLs would
mislink some, and a compliance tool showing the wrong regulation is worse than
one showing none." That objection is answered here by refusing rather than
guessing: a string the grammar does not cover in full yields nothing, and the
panel then says the text is not held. It is never answered by a best effort.

**The grammar.** A citation is a title (`27 CFR`) followed by references
separated by commas. A reference is a section (`§4.33`), optionally with the
paragraph the rule rests on (`§4.32(a)(1)`), or a part and a subpart
(`§5 Subpart I`), or a bare subpart (`Subpart I`). A later `NN CFR` resets the
title for the references after it; a bare reference inherits the title before
it, and a bare subpart inherits the part before it as well, because "Subpart I"
standing alone names no part and there is no other reading available.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class Section(NamedTuple):
    """One section of one part, and the paragraph the rule rests on if it named one.

    `paragraph` is carried so the panel can point at the clause inside a section
    it shows whole. It is never used to fetch less than the section: a reviewer
    reading why a label failed needs the paragraph in its context, and a
    paragraph served alone is the kind of half-quotation a compliance tool
    should not produce.
    """

    title: int
    part: str
    section: str
    paragraph: str | None


class Subpart(NamedTuple):
    """A whole subpart, which some rules cite because no single section carries
    what they enforce — the standards of identity, for one, are a subpart."""

    title: int
    part: str
    subpart: str


Target = Section | Subpart

# `27 CFR` — a title, stated in full, which begins a citation and may reappear
# inside one to change titles.
_TITLE = re.compile(r"^(\d+)\s+CFR\s*(.*)$")

# `§4.32(a)(1)` — a section, with any number of parenthesised levels after it.
# The section number carries its part, which is the text before the first dot.
_SECTION = re.compile(r"^§\s*(\d+)\.(\d+[a-z]?)((?:\([^()]+\))*)$")

# `§5 Subpart I` — a part and one of its subparts.
_PART_SUBPART = re.compile(r"^§\s*(\d+)\s+Subpart\s+([A-Z]+)$")

# `Subpart I` — a subpart whose part has to come from the reference before it.
_BARE_SUBPART = re.compile(r"^Subpart\s+([A-Z]+)$")


def parse_citation(citation: str) -> list[Target]:
    """The sections a citation names, or an empty list if it cannot be read whole.

    Returning nothing for a partly readable string is deliberate. Showing a
    reviewer the one reference of three that parsed would tell them the rule
    rests on that reference alone, which is a claim about the regulation that
    the parser is in no position to make.
    """
    text = citation.strip()
    if not text:
        return []

    first = _TITLE.match(text)
    if first is None:
        return []
    title = int(first.group(1))
    rest = first.group(2).strip()
    if not rest:
        return []

    targets: list[Target] = []
    part: str | None = None

    for chunk in rest.split(","):
        ref = chunk.strip()
        if not ref:
            return []

        # A reference may restate the title, which changes it for this one and
        # for every reference after it, and clears the part a bare subpart
        # would otherwise inherit across a title boundary.
        again = _TITLE.match(ref)
        if again is not None:
            title = int(again.group(1))
            part = None
            ref = again.group(2).strip()
            if not ref:
                return []

        if (m := _SECTION.match(ref)) is not None:
            part = m.group(1)
            targets.append(Section(title, part, f"{m.group(1)}.{m.group(2)}", m.group(3) or None))
        elif (m := _PART_SUBPART.match(ref)) is not None:
            part = m.group(1)
            targets.append(Subpart(title, part, m.group(2)))
        elif (m := _BARE_SUBPART.match(ref)) is not None:
            if part is None:
                return []
            targets.append(Subpart(title, part, m.group(1)))
        else:
            return []

    return targets
