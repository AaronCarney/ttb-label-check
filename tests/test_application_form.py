"""What a reviewer types into the application form becomes reference values.

The single-label page asks for the application's own fields beside the image.
This module is the contract for turning those posted strings into an
`ApplicationRecord`: which beverage types are accepted, what a blank field
means, and how a declared quantity written in words becomes the number the
comparison rules need.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.schemas.expected import BeverageClass
from app.services.application_form import ApplicationFormError, record_from_form

RULES_ROOT = Path("rules").resolve()
MANIFEST = Path("tests/fixtures/labels/manifest.json").resolve()


def _rule_tolerance() -> float:
    """The tolerance the net-contents rule ships, as a fraction of the declared
    figure.

    The answer key below allows exactly this much, and no more. What the form
    parses is what the rule then compares, so a form reading further from the
    application's own figure than the rule forgives would fail the label the
    form was filled in for. Read from the pack rather than written here, so the
    two cannot drift.
    """
    rules = yaml.safe_load((RULES_ROOT / "malt" / "malt.yaml").read_text())["rules"]
    rule = next(r for r in rules if r["rule_id"] == "malt.net_contents.matches_application")
    return float(rule["tolerance"]["cross_unit_relative"])


def _form(**overrides):
    fields = {
        "beverage_type": "distilled_spirits",
        "brand_name": "",
        "fanciful_name": "",
        "class_type": "",
        "alcohol_content": "",
        "net_contents": "",
        "applicant_name_address": "",
        "source_of_product": "",
        "origin": "",
        "wine_appellation": "",
    }
    fields.update(overrides)
    return record_from_form(rules_root=RULES_ROOT, **fields)


def test_an_untouched_form_declares_nothing():
    """A reviewer who only picks an image declares no application. Nothing is
    compared, and the presence and warning checks still run."""
    assert _form(beverage_type="") is None


def test_the_beverage_type_alone_is_an_application():
    """The type decides which rule pack applies, so it is a declaration even
    when every other field is blank."""
    record = _form()
    assert record is not None
    assert record.beverage_class is BeverageClass.SPIRITS


@pytest.mark.parametrize(
    ("posted", "expected"),
    [
        ("distilled_spirits", BeverageClass.SPIRITS),
        ("wine", BeverageClass.WINE),
        ("malt_beverage", BeverageClass.MALT),
    ],
)
def test_each_beverage_type_selects_its_rule_pack(posted, expected):
    assert _form(beverage_type=posted).beverage_class is expected


def test_an_unknown_beverage_type_is_refused():
    with pytest.raises(ApplicationFormError):
        _form(beverage_type="cider")


def test_fields_declared_without_a_beverage_type_are_refused():
    """Silently dropping them would compare nothing while the page implied a
    comparison had run."""
    with pytest.raises(ApplicationFormError):
        _form(beverage_type="", brand_name="Stone's Throw")


def test_surrounding_space_is_not_a_declaration():
    assert _form(brand_name="   ").brand_name is None


def test_plain_fields_arrive_as_typed():
    record = _form(
        brand_name="Stone's Throw",
        fanciful_name="Old Reserve",
        class_type="Kentucky Straight Bourbon Whiskey",
        applicant_name_address="Stone's Throw Distillery, Bardstown, KY",
        wine_appellation="Napa Valley",
    )
    assert record.brand_name == "Stone's Throw"
    assert record.fanciful_name == "Old Reserve"
    assert record.class_type == "Kentucky Straight Bourbon Whiskey"
    assert record.applicant_name_address == "Stone's Throw Distillery, Bardstown, KY"
    assert record.wine_appellation == "Napa Valley"


def test_alcohol_content_keeps_its_words_and_yields_its_percentage():
    record = _form(alcohol_content="40% ALC/VOL")
    assert record.alcohol_content.text == "40% ALC/VOL"
    assert record.alcohol_content.amount == 40.0


def test_alcohol_content_naming_no_number_goes_to_a_reviewer():
    """No number to compare, so the record carries the words alone and the
    check reports that a reviewer must read them."""
    record = _form(alcohol_content="see attached")
    assert record.alcohol_content.text == "see attached"
    assert record.alcohol_content.amount is None


@pytest.mark.parametrize(
    ("typed", "millilitres"),
    [
        ("750 mL", 750.0),
        ("1 liter", 1000.0),
        ("1.75 L", 1750.0),
        ("50 cL", 500.0),
        ("12 fl oz", 354.8823547500),
        ("1 pint", 473.176473),
        ("750", 750.0),
    ],
)
def test_net_contents_converts_to_millilitres(typed, millilitres):
    """The application records millilitres; the reviewer types the unit the
    application declares. Conversions come from the rule pack's own table."""
    record = _form(net_contents=typed)
    assert record.net_contents.text == typed
    assert record.net_contents.amount == pytest.approx(millilitres)


def test_net_contents_naming_no_number_goes_to_a_reviewer():
    record = _form(net_contents="see keg collar")
    assert record.net_contents.amount is None


def test_the_unit_is_the_one_written_next_to_the_number():
    """A compound statement names two quantities and this does not add them up,
    so nobody can say which the application meant and a reviewer decides.

    It used to read `1 PINT 9 FL OZ` as **1 fluid ounce**: the whole remainder
    after the first number was searched for any unit at all, longest first, and
    the fluid ounces belonging to the second figure were taken as the first
    figure's unit.
    """
    assert _form(net_contents="1 PINT 9 FL OZ").net_contents.amount is None


def test_a_number_in_a_name_is_not_a_net_contents_figure():
    """Only a number with a unit written next to it declares a quantity."""
    assert _form(net_contents="Cask 750 Reserve, 500 mL").net_contents.amount == pytest.approx(500)


def test_a_unit_nobody_can_convert_goes_to_a_reviewer():
    """It used to convert by 1 and declare 1 millilitre. The comparison then
    ran on a number that means nothing, and told the reviewer the label
    disagreed with the application on that basis."""
    assert _form(net_contents="1 HOGSHEAD").net_contents.amount is None


def test_a_metric_figure_beside_a_customary_one_is_the_declaration():
    """The application records millilitres. Where the declared words carry
    both, the metric figure is what was declared and the customary one is the
    same quantity rounded — 350, not the 354.88 its twelve fluid ounces
    convert to."""
    assert _form(net_contents="NET CONT. 350 ML / 12 FL OZ").net_contents.amount == pytest.approx(350)


def test_two_customary_figures_naming_one_quantity_are_that_quantity():
    """A pint is sixteen fluid ounces by definition, so `1 PINT (16 FL OZ)` is
    one container stated twice, not two."""
    assert _form(net_contents="1 PINT (16 FL OZ)").net_contents.amount == pytest.approx(473.176473)


def _application_net_contents() -> list[tuple[str, int | None]]:
    """Every distinct net-contents string a real application in the fixture set
    declares, with the millilitres the manifest records for it."""
    labels = json.loads(MANIFEST.read_text())["labels"]
    seen: dict[str, int | None] = {}
    for entry in labels:
        declared = (entry.get("application") or {}).get("net_contents")
        if declared:
            seen.setdefault(declared["value"], declared["ml"])
    return sorted(seen.items())


@pytest.mark.parametrize(("typed", "millilitres"), _application_net_contents())
def test_every_real_application_string_parses_to_what_the_manifest_records(typed, millilitres):
    """The answer key: the 20 distinct net-contents strings the real COLA
    applications in `tests/fixtures/labels/manifest.json` declare.

    Within the rule's own tolerance rather than exactly, because a customary
    declaration cannot convert exactly into the metric figure the manifest
    records — `11.2 FL. OUNCES` is 331.22 against a recorded 331, and that gap
    is the reason the tolerance exists.

    A manifest entry recording no millilitres — the keg collar stating four
    volumes with one struck through — must parse to nothing, so the rule sends
    it to a reviewer instead of comparing a number nobody can justify.
    """
    parsed = _form(net_contents=typed).net_contents.amount
    if millilitres is None:
        assert parsed is None, f"{typed!r} names no single quantity; the manifest records none"
        return
    assert parsed is not None, f"{typed!r} declares {millilitres} mL and parsed to nothing"
    assert abs(parsed - millilitres) <= millilitres * _rule_tolerance()


def test_the_answer_key_is_the_whole_fixture_set():
    """A guard on the case above: if the manifest stops carrying application
    net contents, that test would pass by running on nothing."""
    key = _application_net_contents()
    assert len(key) == 20
    assert sum(1 for _, ml in key if ml is None) == 1


def test_source_of_product_is_lowercased():
    assert _form(source_of_product="Imported", origin="France").source_of_product == "imported"
    assert _form(source_of_product="domestic").source_of_product == "domestic"


def test_an_unknown_source_of_product_is_refused():
    with pytest.raises(ApplicationFormError):
        _form(source_of_product="somewhere")


def test_an_undeclared_source_of_product_stays_undeclared():
    """The origin check needs the application to say domestic or imported. A
    reviewer who says neither gets no origin comparison, not a wrong one."""
    record = _form(origin="France")
    assert record.source_of_product is None
