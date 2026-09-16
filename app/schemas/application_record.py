"""The application fields a label is checked against.

The full application form is `app.schemas.wire.application.ApplicationEnvelope`
(TTB Form 5100.31, items 1-18 plus the label images). Only some of it names a
value that has to appear on the label, and that subset is what this module
models: brand, class and type, alcohol content, net contents, the applicant's
name and address, where the product comes from, and a wine's appellation.

The shape follows the TTB Public COLA Registry record, because that is where a
real application's values are read from: `alcohol_content` and `net_contents`
each carry the text as declared together with the number it means, so a check
can compare either the words or the quantity.

Two of these — alcohol content and net contents — are not fields on the current
registry record. Where an application has no value for them, the field is left
empty and every check against it reports that it does not apply, rather than
inventing a comparison.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.expected import BeverageClass


BeverageType = Literal["distilled_spirits", "wine", "malt_beverage"]
SourceOfProduct = Literal["domestic", "imported"]

_BEVERAGE_CLASS_BY_TYPE: dict[str, BeverageClass] = {
    "distilled_spirits": BeverageClass.SPIRITS,
    "wine": BeverageClass.WINE,
    "malt_beverage": BeverageClass.MALT,
}


class DeclaredQuantity(BaseModel):
    """A declared value and the number it means.

    `text` is what the application says, word for word. `amount` is that same
    value as a number in the unit the field is measured in — a percentage for
    alcohol content, millilitres for net contents — or empty where the
    declared text names no single quantity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str | None = None
    amount: float | None = None


class ApplicationRecord(BaseModel):
    """What one application declares about one product.

    Every field is optional. An empty field means the application declared
    nothing for that element, and the check against it reports that it does
    not apply — which is not the same as the label failing it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    beverage_type: BeverageType
    brand_name: str | None = None
    fanciful_name: str | None = None
    class_type: str | None = None
    alcohol_content: DeclaredQuantity | None = None
    net_contents: DeclaredQuantity | None = None
    applicant_name_address: str | None = None
    source_of_product: SourceOfProduct | None = None
    origin: str | None = None
    wine_appellation: str | None = None

    @property
    def beverage_class(self) -> BeverageClass:
        """Which rule pack applies. The application declares the product type,
        so the product never has to guess it from the label image."""
        return _BEVERAGE_CLASS_BY_TYPE[self.beverage_type]
