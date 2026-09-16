"""Turn the application fields a grader types into the record the rules use.

The single-label page asks for the application's own values beside the label
image, because without them there is nothing to compare the label against.
This module is the one place those posted strings become an
`ApplicationRecord`; `app.services.application_mapper` then turns that record
into the reference values the rule engine reads.

Three things happen here that the form itself cannot do.

The beverage type decides which rule pack applies, so it is a declaration in
its own right: a form carrying nothing else still says "check this against the
wine rules". A form carrying no type at all declares no application, and the
label is checked only for what must be on every label regardless.

A declared quantity is words, and the rules compare numbers. Alcohol content
keeps its words and yields the first percentage in them. Net contents keeps
its words and yields millilitres, converted with the same table the rule pack
uses, so adding a unit stays an edit to the rule pack.

A blank field is not a value. It means the application declared nothing for
that element, and the check against it reports that it does not apply.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

# The unit words are matched exactly as the net-contents validator matches
# them, so the form and the rule cannot read the same table two ways.
from app.rules._validators._helpers import (
    first_number,
    normalize_words,
    word_run_present,
)
from app.schemas.application_record import (
    ApplicationRecord,
    BeverageType,
    DeclaredQuantity,
    SourceOfProduct,
)

_BEVERAGE_TYPES: tuple[BeverageType, ...] = ("distilled_spirits", "wine", "malt_beverage")
_SOURCES: tuple[SourceOfProduct, ...] = ("domestic", "imported")

_BEVERAGE_TYPE_LABELS = {
    "distilled_spirits": "distilled spirits",
    "wine": "wine",
    "malt_beverage": "malt beverage",
}

# The same table `rules/tables/volume_units.yaml` is registered under for the
# net-contents rule: the loader keys a decision table by its file name.
_VOLUME_UNITS_TABLE = Path("tables") / "volume_units.yaml"


class ApplicationFormError(ValueError):
    """The posted application cannot be read. The message is shown to the user."""


def _clean(value: str | None) -> str | None:
    """A field's value, or nothing when the grader left it blank."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@lru_cache(maxsize=4)
def _volume_factors(rules_root: Path) -> tuple[tuple[tuple[str, ...], float | None], ...]:
    """Each net-contents unit as its plain words, and the millilitres it makes.

    Longest first, so "fluid ounces" is recognised before any shorter unit
    whose words it contains.
    """
    path = rules_root / _VOLUME_UNITS_TABLE
    if not path.is_file():
        return ()
    table = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    factors: list[tuple[tuple[str, ...], float | None]] = []
    for entry in table.get("entries", []):
        unit = normalize_words(str(entry.get("unit", "")))
        if not unit:
            continue
        factor = entry.get("factor")
        factors.append((unit, None if factor is None else float(factor)))
    factors.sort(key=lambda pair: len(pair[0]), reverse=True)
    return tuple(factors)


def _millilitres(text: str, rules_root: Path) -> float | None:
    """The millilitres a declared net contents means, or nothing.

    Nothing when the words name no number, and nothing when they name a unit
    the rule pack lists but cannot convert — in both cases the comparison has
    no two numbers to put side by side and a reviewer decides.
    """
    amount = first_number(text)
    if amount is None:
        return None
    # Only the words after the number can be its unit; a "750" in a brand name
    # ahead of it is not.
    match = re.search(r"[0-9]+(?:\.[0-9]+)?", text)
    remainder = normalize_words(text[match.end():]) if match else ()
    for unit, factor in _volume_factors(rules_root):
        if word_run_present(remainder, unit):
            return None if factor is None else amount * factor
    # A unit the table does not list converts by 1, which is the rule pack's
    # own reading of an unrecognised unit.
    return amount


def _quantity(text: str | None, amount: float | None) -> DeclaredQuantity | None:
    if text is None:
        return None
    return DeclaredQuantity(text=text, amount=amount)


def record_from_form(
    *,
    rules_root: Path,
    beverage_type: str = "",
    brand_name: str = "",
    fanciful_name: str = "",
    class_type: str = "",
    alcohol_content: str = "",
    net_contents: str = "",
    applicant_name_address: str = "",
    source_of_product: str = "",
    origin: str = "",
    wine_appellation: str = "",
) -> ApplicationRecord | None:
    """The application one submitted form declares, or nothing if it declares none."""
    declared = {
        "brand_name": _clean(brand_name),
        "fanciful_name": _clean(fanciful_name),
        "class_type": _clean(class_type),
        "applicant_name_address": _clean(applicant_name_address),
        "origin": _clean(origin),
        "wine_appellation": _clean(wine_appellation),
    }
    alcohol_text = _clean(alcohol_content)
    net_text = _clean(net_contents)
    source = _clean(source_of_product)
    kind = _clean(beverage_type)

    if kind is None:
        if any(declared.values()) or alcohol_text or net_text or source:
            raise ApplicationFormError(
                "Pick the beverage type — it decides which rules the label is "
                "checked against, and the other application fields cannot be "
                "compared without it."
            )
        return None

    if kind not in _BEVERAGE_TYPES:
        allowed = ", ".join(_BEVERAGE_TYPE_LABELS[t] for t in _BEVERAGE_TYPES)
        raise ApplicationFormError(f"Unknown beverage type {kind!r} — pick one of: {allowed}.")

    if source is not None:
        source = source.lower()
        if source not in _SOURCES:
            raise ApplicationFormError(
                f"Unknown source of product {source_of_product.strip()!r} — "
                "the application says either domestic or imported."
            )

    return ApplicationRecord(
        beverage_type=kind,
        alcohol_content=_quantity(alcohol_text, first_number(alcohol_text)),
        net_contents=_quantity(
            net_text, _millilitres(net_text, rules_root) if net_text else None
        ),
        source_of_product=source,
        **declared,
    )
