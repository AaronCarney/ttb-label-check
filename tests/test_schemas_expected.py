"""Round-trip tests for app.schemas.expected."""

from __future__ import annotations


def test_expected_value_round_trip() -> None:
    from decimal import Decimal

    from app.schemas.expected import BeverageClass, ExpectedValue

    ev = ExpectedValue(
        field_id="alcohol_content",
        value=None,
        aliases=(),
        abv_labeled_pct=Decimal("36.0"),
        container_volume_ml=Decimal("750"),
        parameters={"is_import": False},
        source_cola="cola-001",
    )
    ev2 = ExpectedValue.model_validate_json(ev.model_dump_json())
    assert ev2 == ev
    assert BeverageClass("spirits") is BeverageClass.SPIRITS
