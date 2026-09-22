"""The held-out registry labels become cases the corpus check can run.

`eval/fetch_registry_corpus.py` writes one `record.json` per TTB ID beside
that record's label images. `eval/corpus_check.py --registry` turns each one
into the same `LabelCase` the corpus labels use, so the held-out set goes
through the same production path. These tests build small records in a
temporary directory: the fetched records themselves are not in the repository.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.corpus_check import freeze_missing, registry_cases, registry_record


def _record(**overrides: object) -> dict:
    record = {
        "ttbid": "13231001000240",
        "beverage_type": "spirits",
        "source": "domestic",
        "brand": "COTTON HOLLOW",
        "fanciful_name": None,
        "class_type_description": "BOURBON WHISKY",
        "applicant_name_address": [
            "STRONG SPIRITS, INC",
            "999 WITHROW CT",
            "BARDSTOWN KY 40004",
            "COTTON HOLLOW DISTILLING (Used on label)",
        ],
        "images": [
            {"type": "Brand (front) or keg collar", "file": "brand-front-or-keg-collar.jpg"},
            {"type": "Other", "file": "other.jpg"},
            {"type": "Back", "file": "back.jpg"},
        ],
    }
    record.update(overrides)
    return record


def _write(root: Path, record: dict) -> None:
    folder = root / record["ttbid"]
    folder.mkdir(parents=True)
    (folder / "record.json").write_text(json.dumps(record))
    for image in record["images"]:
        (folder / image["file"]).write_bytes(f"pixels of {image['file']}".encode())


def test_the_form_fields_become_the_application() -> None:
    declared = {
        "alcohol_content": {"text": "45% ALC/VOL", "percent": 45.0},
        "net_contents": {"text": "750 ML", "ml": 750},
    }
    record = registry_record(_record(), declared)

    assert record.beverage_type == "distilled_spirits"
    assert record.brand_name == "COTTON HOLLOW"
    assert record.class_type == "BOURBON WHISKY"
    assert record.source_of_product == "domestic"
    assert record.alcohol_content is not None and record.alcohol_content.amount == 45.0
    assert record.net_contents is not None and record.net_contents.text == "750 ML"
    # The block is joined in the registry's order, so the trade name the
    # applicant marked as used on the label is still found after the ZIP.
    assert record.trade_names_used_on_label == ("COTTON HOLLOW DISTILLING",)


def test_a_value_nobody_read_off_the_image_is_left_empty() -> None:
    record = registry_record(_record(), None)

    assert record.alcohol_content is None
    assert record.net_contents is None


def test_a_case_carries_the_front_and_the_back_only(tmp_path: Path) -> None:
    _write(tmp_path / "registry", _record())

    [case] = registry_cases(tmp_path / "registry", tmp_path / "readings", tmp_path / "none.json")

    assert case.label_id == "ttb-13231001000240"
    assert [(tag, image.name) for tag, image, _r in case.faces] == [
        ("front", "brand-front-or-keg-collar.jpg"),
        ("back", "back.jpg"),
    ]
    assert case.faces[0][2] == tmp_path / "readings/13231001000240/brand-front-or-keg-collar.json"


def test_the_first_brand_image_is_the_front(tmp_path: Path) -> None:
    images = [
        {"type": "Brand (front) or keg collar", "file": "brand-front-or-keg-collar.jpg"},
        {"type": "Brand (front) or keg collar", "file": "brand-front-or-keg-collar-2.jpg"},
    ]
    _write(tmp_path / "registry", _record(images=images))

    [case] = registry_cases(tmp_path / "registry", tmp_path / "readings", tmp_path / "none.json")

    assert [image.name for _t, image, _r in case.faces] == ["brand-front-or-keg-collar.jpg"]


def test_declared_values_are_taken_by_ttb_id(tmp_path: Path) -> None:
    _write(tmp_path / "registry", _record())
    declared = tmp_path / "declared.json"
    declared.write_text(
        json.dumps({"13231001000240": {"alcohol_content": {"text": "40%", "percent": 40.0}}})
    )

    [case] = registry_cases(tmp_path / "registry", tmp_path / "readings", declared)

    assert case.record.alcohol_content is not None
    assert case.record.alcohol_content.amount == 40.0
    assert case.record.net_contents is None


def test_a_record_that_is_not_spirits_or_domestic_is_refused(tmp_path: Path) -> None:
    _write(tmp_path / "registry", _record(source="imported"))

    with pytest.raises(ValueError, match="imported"):
        registry_cases(tmp_path / "registry", tmp_path / "readings", tmp_path / "none.json")


class _CountingReader:
    def __init__(self) -> None:
        self.seen: list[bytes] = []

    def look(self, image_bytes: bytes) -> object:
        self.seen.append(image_bytes)
        return image_bytes


def test_freezing_reads_only_the_images_with_no_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "registry", _record())
    readings = tmp_path / "readings"
    [case] = registry_cases(tmp_path / "registry", readings, tmp_path / "none.json")
    front_reading = case.faces[0][2]
    front_reading.parent.mkdir(parents=True)
    front_reading.write_text("{}")
    monkeypatch.setattr("eval.corpus_check.freeze_reading", lambda r: {"boxes": r.decode()})
    reader = _CountingReader()

    read = freeze_missing([case], reader, pause=0.0)

    assert read == 1
    assert reader.seen == [b"pixels of back.jpg"]
    assert json.loads(case.faces[1][2].read_text()) == {
        "image": str(case.faces[1][1]),
        "boxes": "pixels of back.jpg",
    }
    assert front_reading.read_text() == "{}"
