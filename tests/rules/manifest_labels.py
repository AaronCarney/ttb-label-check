"""Read the real-label fixture manifest into the shapes the engine consumes.

`tests/fixtures/labels/manifest.json` pairs 30 approved labels and 8 flawed
variants with the application each was filed under, and states, per label
element, what a correct check reports. It is the specification for what
"the label matches the application" means, so the tests read it rather than
restating it.

Each entry's `label_observed` block is what the label itself shows,
transcribed from its images without reference to the application: the brand
mark it displays, its alcohol and net-contents declarations with the unit
words as printed, the name-and-address and origin statements, and the health
warning. Every reading here comes from that block, so the two sides of each
comparison are independent — which is the point. A reading taken from the
application record would make the rule engine compare a value with itself and
report a pass it had not earned.

A variant's block is its source label's, with the variant's own alteration
applied: an altered application leaves the label's readings untouched, and a
repainted warning block changes the warning reading alone.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.application_record import ApplicationRecord, DeclaredQuantity
from app.schemas.extracted import FieldObservation
from tests.rules.fixtures import make_obs

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "labels" / "manifest.json"

FIELD_CHECKS = ("brand", "class_type", "abv", "net_contents", "name_address", "origin")


@lru_cache(maxsize=1)
def manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def entries_by_id() -> dict[str, dict[str, Any]]:
    return {entry["id"]: entry for entry in manifest()["labels"]}


def application_record(entry: dict[str, Any]) -> ApplicationRecord:
    app = entry["application"]
    alcohol = app.get("alcohol_content") or {}
    net = app.get("net_contents") or {}
    source = app.get("source_of_product")
    return ApplicationRecord(
        beverage_type=entry["beverage_type"],
        brand_name=app.get("brand_name"),
        fanciful_name=app.get("fanciful_name"),
        class_type=app.get("class_type"),
        alcohol_content=DeclaredQuantity(text=alcohol.get("value"), amount=alcohol.get("percent")),
        net_contents=DeclaredQuantity(text=net.get("value"), amount=net.get("ml")),
        applicant_name_address=app.get("applicant_name_address"),
        source_of_product=source.lower() if source else None,
        origin=app.get("origin"),
        wine_appellation=app.get("wine_appellation"),
    )


def label_observations(entry: dict[str, Any]) -> tuple[FieldObservation, ...]:
    """What a reader returns for this label, in the payload shapes the
    extractor emits (`_SCHEMAS` in `app/vision/cloud.py`)."""
    observed = entry["label_observed"]
    beverage_class = application_record(entry).beverage_class
    alcohol = observed.get("abv") or {}
    net = observed.get("net_contents") or {}

    def obs(field_id: str, value: Any) -> FieldObservation:
        return make_obs(field_id=field_id, value=value, beverage_class=beverage_class)

    return (
        obs("brand_name", {"brand_name": observed.get("brand_name") or "", "confidence": 0.95}),
        obs("class_type", {"class_type": observed.get("class_type") or "", "confidence": 0.95}),
        obs("abv", {"abv_pct": alcohol.get("percent"), "unit": "%", "confidence": 0.95}),
        obs(
            "net_contents",
            {
                "net_contents_value": net.get("amount"),
                "unit": net.get("unit") or "",
                "confidence": 0.95,
            },
        ),
        obs(
            "name_address",
            {
                "name": observed.get("name_address") or "",
                "city": "",
                "state": "",
                "confidence": 0.95,
            },
        ),
        obs(
            "country_origin",
            {"country": observed.get("origin_statement") or "", "confidence": 0.95},
        ),
    )


def accepted_verdicts(entry: dict[str, Any], check: str) -> tuple[Any, ...]:
    """Every outcome the manifest counts as correct for one check on one label.

    `expected` names the outcome; `also_acceptable` names any others. Every
    check on an image-degradation variant also accepts `needs_review`, per the
    manifest's own `check_rules`.
    """
    accepted = [entry["expected"][check], *entry.get("also_acceptable", {}).get(check, [])]
    if entry.get("variant", {}).get("kind") in {"glare", "skew", "blur", "low_light"}:
        accepted.append("needs_review")
    return tuple(dict.fromkeys(accepted))
