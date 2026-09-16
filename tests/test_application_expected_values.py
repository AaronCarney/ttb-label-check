"""Application.expected_values — additive optional field (defaults to ())."""
from decimal import Decimal

from app.schemas.application import Application
from app.schemas.expected import ExpectedValue


def test_application_default_expected_values_is_empty_tuple():
    app = Application(application_id="A-001", evaluation_id="EV-001")
    assert app.expected_values == ()


def test_application_accepts_expected_values_tuple():
    ev = ExpectedValue(field_id="brand_name", value="Crown Royal", aliases=())
    app = Application(application_id="A-001", evaluation_id="EV-001",
                      expected_values=(ev,))
    assert app.expected_values == (ev,)
    assert app.expected_values[0].field_id == "brand_name"


def test_application_expected_values_round_trips_via_model_dump():
    ev = ExpectedValue(field_id="alcohol_content",
                       abv_labeled_pct=Decimal("40.0"),
                       abv_actual_pct=Decimal("40.1"))
    app = Application(application_id="A-001", evaluation_id="EV-001",
                      expected_values=(ev,))
    dumped = app.model_dump(mode="json")
    rebuilt = Application(**dumped)
    assert rebuilt.expected_values[0].field_id == "alcohol_content"
