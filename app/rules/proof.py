"""The proof figures a line of label text states for the bottle's contents.

27 CFR §5.1 defines proof as twice the percentage of alcohol by volume, and
§5.65(b)(1)(i) lets a spirits label state it beside the alcohol content. Both
readers and the rule that checks the two against each other need the same
answer to "which numbers on this line are the bottle's proof", so it is
answered once, here, as a pure function of the text.

Labels print proof in both orders and in several spellings: "90 Proof",
"86° PROOF", "90 US PROOF", "90-proof", "PROOF 90", "Proof: 124.6", "Barrel
Proof 124.6", with a comma for the decimal point on some imports and the OCR's
"PR00F" on others. Some numbers followed by "proof" are not the bottle's proof,
and those are refused:

  - a range — "VODKA 80-89 PROOF" is the registry's class shorthand, not a
    statement about any one bottle;
  - a distillation or barrel-entry proof — "distilled at 160 proof", "entered
    the barrel at 125 proof" — which the standards of identity and some labels
    state about the spirit before it was bottled. "Barrel Proof 124.6" is not
    one of these: it says the bottle holds the spirit at the strength it left
    the barrel, and 124.6 is the bottle's proof.

A figure above 200 cannot be a proof, since it would be more than pure alcohol.
It is still returned, as printed, so the caller can record a proof it could
not read rather than miss one; `PROOF_CEILING` is the bound it compares with.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

PROOF_CEILING = Decimal(200)

_FIGURE = r"\d{2,3}(?:[.,]\d)?(?!\d)"
_WORD = r"\bPR[O0]{2}F\b"

_PROOF_RE = re.compile(
    # "90 PROOF", "86° PROOF", "90 US PROOF", "90-proof", "124.6 BARREL PROOF"
    rf"(?<![\d.,])(?P<before>{_FIGURE})\s*°?\s*(?:-\s*)?(?:(?:U\.?\s?S\.?|BARREL)\s*)?{_WORD}"
    r"|"
    # "PROOF 90", "Proof: 124.6", "Barrel Proof 124.6"
    rf"{_WORD}\s*:?\s*(?P<after>{_FIGURE})",
    re.I,
)

# The upper end of a range: the figure follows another figure and a dash.
_RANGE_BEFORE_RE = re.compile(r"\d\s*[-–]\s*$")
# The lower end of a range, in the reversed form: "PROOF 80-89".
_RANGE_AFTER_RE = re.compile(r"^\s*[-–]\s*\d")

# What says a figure is the spirit's strength before bottling. Searched in the
# clause just before the figure, so "DISTILLED IN KENTUCKY" earlier on the same
# line as "90 PROOF" does not count: only "distilled at", "distilled to" and the
# like tie the figure to distillation.
_NOT_THE_BOTTLES_RE = re.compile(
    r"\bDISTILL\w*\s+(?:AT|TO|ABOVE|BELOW|UNDER|OVER)\b|\bENTRY\b|\bENTER(?:ED|S|ING)?\b",
    re.I,
)
# Where one clause of a line ends and the next begins. A percentage ends the
# alcohol statement, so the words before it are not about the proof after it.
_CLAUSE_BREAK_RE = re.compile(r"[,;|•%()]")
_CLAUSE_REACH = 40


@dataclass(frozen=True)
class ProofFigure:
    """One proof statement: its figure as printed, and where it sits."""

    value: str
    text: str
    start: int
    end: int


def _clause_before(text: str, start: int) -> str:
    window = text[max(0, start - _CLAUSE_REACH) : start]
    breaks = list(_CLAUSE_BREAK_RE.finditer(window))
    return window[breaks[-1].end() :] if breaks else window


def find_proofs(text: str) -> list[ProofFigure]:
    """Every proof figure `text` states for the bottle's contents, in order.

    `value` is the figure as printed, with a decimal comma read as a point, so
    `Decimal(value)` keeps the precision the label printed it at.
    """
    found: list[ProofFigure] = []
    for match in _PROOF_RE.finditer(text):
        figure = match.group("before") or match.group("after")
        figure_start = match.start("before") if match.group("before") else match.start("after")
        if match.group("before") and _RANGE_BEFORE_RE.search(text[:figure_start]):
            continue
        if match.group("after") and _RANGE_AFTER_RE.match(text[match.end() :]):
            continue
        if _NOT_THE_BOTTLES_RE.search(_clause_before(text, match.start())):
            continue
        found.append(
            ProofFigure(
                value=figure.replace(",", "."),
                text=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        )
    return found


def proofs_in_statement(statement: str, confidence: float) -> list[dict[str, Any]]:
    """The proof entries an alcohol statement carries, as a reading lists them.

    For a reader that returns the statement as printed and no proof figures of
    its own. Anything found is inside the statement, so it is beside it, and it
    is as confident as the reading of the statement it came from.
    """
    return [
        {"value": p.value, "text": p.text, "confidence": confidence, "beside_abv": True}
        for p in find_proofs(statement)
    ]
