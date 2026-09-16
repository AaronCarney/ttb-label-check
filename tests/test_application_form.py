"""What a grader types into the application form becomes reference values.

The single-label page asks for the application's own fields beside the image.
This module is the contract for turning those posted strings into an
`ApplicationRecord`: which beverage types are accepted, what a blank field
means, and how a declared quantity written in words becomes the number the
comparison rules need.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.expected import BeverageClass
from app.services.application_form import ApplicationFormError, record_from_form

RULES_ROOT = Path("rules").resolve()


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
    """A grader who only picks an image declares no application. Nothing is
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
    """The application records millilitres; the grader types the unit the
    application declares. Conversions come from the rule pack's own table."""
    record = _form(net_contents=typed)
    assert record.net_contents.text == typed
    assert record.net_contents.amount == pytest.approx(millilitres)


def test_net_contents_naming_no_number_goes_to_a_reviewer():
    record = _form(net_contents="see keg collar")
    assert record.net_contents.amount is None


def test_source_of_product_is_lowercased():
    assert _form(source_of_product="Imported", origin="France").source_of_product == "imported"
    assert _form(source_of_product="domestic").source_of_product == "domestic"


def test_an_unknown_source_of_product_is_refused():
    with pytest.raises(ApplicationFormError):
        _form(source_of_product="somewhere")


def test_an_undeclared_source_of_product_stays_undeclared():
    """The origin check needs the application to say domestic or imported. A
    grader who says neither gets no origin comparison, not a wrong one."""
    record = _form(origin="France")
    assert record.source_of_product is None
