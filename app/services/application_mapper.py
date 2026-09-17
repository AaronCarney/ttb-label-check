"""Turn one application record into the reference values the rules compare against.

The rule engine asks for `ExpectedValue`s, one per label element, keyed by the
name the application uses for that element. Nothing else in the product builds
them, so without this step every comparison rule runs against an empty default
and reports that it has nothing to compare — which is not a check.

Field names here are the application's own (`alcohol_content`, not `abv`;
`name_and_address`, not `bottler`). Reconciling them with the names the reader
and the rule pack use is the engine's job, in `app.rules.yaml_engine`.

An element the application says nothing about produces no reference value, and
the check against it reports that it does not apply. The one exception is
country of origin: a domestic application is a positive statement that no
country-of-origin check applies, so it produces a reference value that says so
rather than no value at all.
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas.application_record import ApplicationRecord
from app.schemas.expected import ExpectedValue


def _decimal(amount: float | None) -> Decimal | None:
    return None if amount is None else Decimal(str(amount))


def expected_values_from(record: ApplicationRecord) -> tuple[ExpectedValue, ...]:
    """The reference values one application gives the rules."""
    values: list[ExpectedValue] = []

    if record.brand_name:
        # The brand field is not the only name the application says the label
        # may show. A fanciful name is the second name an applicant may put on
        # the label beside the brand, and a trade name marked "(Used on label)"
        # is a name the applicant told TTB it prints there. A label carrying
        # one of those instead of the brand field's wording is a match the
        # reviewer should see, not a miss, so both travel with the brand
        # reference value and `fuzzy_brand` compares against all of them.
        brand_parameters: dict[str, object] = {}
        if record.fanciful_name:
            brand_parameters["fanciful_name"] = record.fanciful_name
        trade_names = record.trade_names_used_on_label
        if trade_names:
            brand_parameters["trade_names_used_on_label"] = trade_names
        values.append(
            ExpectedValue(
                field_id="brand_name",
                value=record.brand_name,
                parameters=brand_parameters,
            )
        )

    if record.class_type:
        values.append(ExpectedValue(field_id="class_type", value=record.class_type))

    alcohol = record.alcohol_content
    values.append(
        ExpectedValue(
            field_id="alcohol_content",
            value=alcohol.text if alcohol else None,
            abv_labeled_pct=_decimal(alcohol.amount) if alcohol else None,
            # The label must state an alcohol content when the application
            # declares one. Where it declares none, the presence check has no
            # ground to stand on and reports that it does not apply.
            parameters={"abv_required": bool(alcohol and alcohol.text)},
        )
    )

    net = record.net_contents
    if net and (net.text or net.amount is not None):
        values.append(
            ExpectedValue(
                field_id="net_contents",
                value=net.text,
                container_volume_ml=_decimal(net.amount),
            )
        )

    if record.applicant_name_address:
        values.append(
            ExpectedValue(
                field_id="name_and_address",
                value=record.applicant_name_address,
            )
        )

    if record.source_of_product is not None:
        imported = record.source_of_product == "imported"
        values.append(
            ExpectedValue(
                field_id="country_of_origin",
                value=record.origin if imported else None,
                parameters={"source_of_product": record.source_of_product},
            )
        )

    if record.wine_appellation:
        values.append(ExpectedValue(field_id="wine_appellation", value=record.wine_appellation))

    return tuple(values)
