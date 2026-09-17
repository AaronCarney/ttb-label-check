"""The net-contents unit table, and the one parser that reads it.

A net-contents figure is written three different ways in this app and has to
mean the same thing in all three:

  - the rule pack's comparison of a label against an application
    (`app.rules._validators.quantity_match`), which is handed the table through
    the loaded rule set;
  - the application form a reviewer types (`app.services.application_form`),
    which reads the shipped table off disk;
  - the reading-accuracy harness (`eval.read_accuracy`), which reads the same
    file so a score means what a verdict in the running app means.

They used to hold three copies of the unit list, and the copies disagreed: the
harness knew "FL. OUNCES" while the rule pack did not, and the form silently
treated a unit nobody could convert as millilitres. One table, one parser, and
adding a unit stays an edit to `rules/tables/volume_units.yaml`.

A unit is matched on its letters and digits alone, because a label and a reader
each spell it as they find it: "FL. OZ.", "FL OZ" and "fl.oz" are one entry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from app.rules._validators._helpers import normalize_words

# The table lives here relative to the rules root, and the rule pack's loader
# keys a decision table by its file name, so this file is `volume_units`.
VOLUME_UNITS_TABLE = Path("tables") / "volume_units.yaml"

_NUMBER_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def unit_key(unit: object) -> str:
    """A unit reduced to the letters and digits that identify it."""
    return "".join(normalize_words(str(unit or "")))


@dataclass(frozen=True)
class UnitTable:
    """Every unit the table lists, ready to look up.

    `factors` maps a unit's key to the millilitres one of it makes, or to None
    for a unit listed with no factor — one nobody can convert, which is a
    reviewer's to settle rather than a number to compare.

    `metric` holds the keys of the units the application itself records in.
    The application declares net contents in millilitres, so where a declared
    text names a metric figure that figure is the declaration, and a customary
    one beside it is the same quantity written a second way.
    """

    factors: Mapping[str, float | None]
    metric: frozenset[str]
    longest_unit_words: int

    def factor(self, unit: object) -> float | None:
        """The millilitres one of `unit` makes, or None when the table does not
        list it or lists it with no factor."""
        return self.factors.get(unit_key(unit))

    def lists(self, unit: object) -> bool:
        return unit_key(unit) in self.factors

    def is_metric(self, unit: object) -> bool:
        return unit_key(unit) in self.metric


def table_from_entries(entries: Iterable[Mapping[str, Any]]) -> UnitTable:
    """Build the lookup from the table's own rows."""
    factors: dict[str, float | None] = {}
    metric: set[str] = set()
    longest = 1
    for entry in entries:
        words = normalize_words(str(entry.get("unit", "")))
        if not words:
            continue
        key = "".join(words)
        raw = entry.get("factor")
        factors[key] = None if raw is None else float(raw)
        if entry.get("metric"):
            metric.add(key)
        longest = max(longest, len(words))
    return UnitTable(factors=factors, metric=frozenset(metric), longest_unit_words=longest)


@lru_cache(maxsize=4)
def shipped_table(rules_root: Path) -> UnitTable:
    """The table as shipped in the rule pack. Empty if the file is missing, so
    a caller without a rule tree degrades to "no unit converts" rather than
    raising."""
    path = rules_root / VOLUME_UNITS_TABLE
    if not path.is_file():
        return UnitTable(factors={}, metric=frozenset(), longest_unit_words=1)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return table_from_entries(raw.get("entries", []))


def millilitres(amount: object, unit: object, table: UnitTable) -> float | None:
    """One figure and its unit in millilitres, or None where there is none.

    None when there is no figure, and None when the unit is one the table
    cannot convert — including no unit at all. A caller that knows what a
    missing unit means in its own context decides that for itself.
    """
    if amount is None:
        return None
    factor = table.factor(unit)
    if factor is None:
        return None
    return float(amount) * factor


def _figures(text: str, table: UnitTable) -> tuple[list[tuple[float, str]], bool]:
    """Every number in a declared text paired with the unit written next to it.

    Returns the pairs whose unit the table lists, and whether any number
    carried a unit the table does not list. Only the words immediately after a
    number can be its unit: a "750" inside a brand name ahead of the figure is
    not, and neither is a unit further along belonging to a second figure.
    """
    listed: list[tuple[float, str]] = []
    unlisted = False
    for match in _NUMBER_RE.finditer(text):
        words = normalize_words(text[match.end():])
        found = ""
        for count in range(min(table.longest_unit_words, len(words)), 0, -1):
            candidate = "".join(words[:count])
            if candidate.isdigit():
                continue
            if candidate in table.factors:
                found = candidate
                break
        if found:
            listed.append((float(match.group()), found))
        elif words and not words[0].isdigit():
            unlisted = True
    return listed, unlisted


def _one_quantity(converted: list[float | None]) -> float | None:
    """One figure when every figure named the same quantity, else None.

    A declared text often writes the same contents twice — "1 PINT (16 FL OZ)",
    where a pint is sixteen fluid ounces by definition. Those are one quantity.
    Four sizes on a keg collar with three struck through, or the two halves of
    a compound "1 PT. 9 FL. OZ." this check does not add up, are not: nothing
    here can say which the application meant, so a reviewer decides.

    The margin is there only because a figure that travelled through a float
    cannot be trusted to compare exactly against the same value written another
    way.
    """
    if not converted or any(value is None for value in converted):
        return None
    values = [float(value) for value in converted if value is not None]
    spread = max(values) - min(values)
    return values[0] if spread <= 1e-9 * max(abs(v) for v in values) else None


def millilitres_from_text(text: str, table: UnitTable) -> float | None:
    """The millilitres a declared net contents means, or None for a reviewer.

    The application records net contents in millilitres, so what counts as the
    declaration follows from that:

      - a metric figure is the declaration itself, and is taken as written. It
        wins over a customary figure beside it, which is the same quantity
        rounded: an application reading "NET CONT. 350 ML / 12 FL OZ" declares
        350, not the 354.88 its twelve fluid ounces convert to.
      - otherwise every customary figure must name one quantity, and it is
        converted;
      - a bare number with no unit anywhere is already millilitres;
      - a unit the table cannot convert leaves nothing to compare, and a
        reviewer decides.
    """
    listed, unlisted = _figures(text, table)
    metric = [(amount, unit) for amount, unit in listed if table.is_metric(unit)]
    figures = metric or listed
    if figures:
        return _one_quantity([millilitres(amount, unit, table) for amount, unit in figures])
    if unlisted:
        return None
    match = _NUMBER_RE.search(text)
    return float(match.group()) if match else None
