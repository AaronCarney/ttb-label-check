"""Every corpus label through the production evaluator, from frozen readings.

What it answers: on labels TTB approved, what does the product report — match,
mismatch or needs review, per check and per label — and why?

    uv run python -m eval.corpus_check              # the 30 real corpus labels
    uv run python -m eval.corpus_check --json out.json

The path is the running app's. Each label's faces go through
`LocalVisionExtractor.extract`, the quality gate, the face merge, the rule pack
and the disposition, inside `Evaluator.evaluate`, against an `Application`
built the way the upload form builds one (`app/api/ui/_submission.py`). One
step is stood in for: `LocalVisionExtractor.look`, which turns pixels into
boxes, returns the frozen reading of that image instead of running the OCR.
Everything after the boxes is the product's own code. A frozen reading is the
reader's own output, taken by `eval/read_accuracy.py --freeze`.

Every corpus label was approved, so a mismatch here is either a genuine
difference the label carries or the product reading the label wrong. The
scoreboard says how many of each outcome there were, why each review was
sent to a person, and how many checks the product settled without one — the
figure that shows whether a change cut mismatches by sending everything to
review.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from app.config import Settings
from app.rules import build_rule_engine
from app.schemas.application import Application
from app.schemas.application_record import ApplicationRecord, DeclaredQuantity
from app.schemas.label import Face, FaceTag, Label
from app.services.application_mapper import expected_values_from
from app.services.evaluator import Evaluator
from app.vision.local import LocalVisionExtractor, _Reading, thaw_reading

LABELS_ROOT = Path("tests/fixtures/labels")
RECORDINGS_ROOT = Path("tests/recordings/reader")

# The order the upload puts a label's faces in (`app/api/ui/_faces.py`).
_FACE_ORDER = ("front", "back", "neck", "side")


@dataclass(frozen=True)
class LabelCase:
    """One label to check: its faces, the reading of each, and its application."""

    label_id: str
    faces: tuple[tuple[FaceTag, Path, Path], ...]  # (face tag, image, frozen reading)
    record: ApplicationRecord


@dataclass(frozen=True)
class RuleOutcome:
    disposition: str
    reason_code: str


@dataclass(frozen=True)
class LabelOutcome:
    label_id: str
    disposition: str
    rules: dict[str, RuleOutcome] = field(default_factory=dict)


def application_record(entry: dict[str, Any]) -> ApplicationRecord:
    """The application a corpus manifest entry was filed under."""
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


def corpus_cases(
    labels_root: Path = LABELS_ROOT, recordings_root: Path = RECORDINGS_ROOT
) -> list[LabelCase]:
    """The corpus's real labels, in manifest order."""
    manifest = json.loads((labels_root / "manifest.json").read_text())
    cases = []
    for entry in manifest["labels"]:
        if entry["kind"] != "real":
            continue
        tags = sorted(entry["images"], key=_FACE_ORDER.index)
        faces = tuple(
            (
                cast(FaceTag, tag),
                labels_root / entry["images"][tag],
                (recordings_root / entry["images"][tag]).with_suffix(".json"),
            )
            for tag in tags
        )
        cases.append(LabelCase(entry["id"], faces, application_record(entry)))
    return cases


def frozen_reader(readings: dict[bytes, Path]) -> LocalVisionExtractor:
    """The production reader, with each image's frozen reading as its OCR.

    `readings` maps an image's bytes to its frozen reading. An image with no
    reading raises, so a run can never quietly OCR a label or skip one.
    """
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=deque(maxlen=500))

    def look(image_bytes: bytes) -> _Reading:
        return thaw_reading(json.loads(readings[image_bytes].read_text()))

    async def loaded() -> None:
        return None

    # Instance attributes, so no other reader in the process is touched.
    reader.look = look  # type: ignore[method-assign]
    reader.ensure_loaded = loaded  # type: ignore[method-assign]
    return reader


async def check(cases: list[LabelCase]) -> list[LabelOutcome]:
    """Every case through one production evaluator."""
    settings = Settings()
    faces = {case.label_id: [(t, i.read_bytes(), r) for t, i, r in case.faces] for case in cases}
    readings = {data: rec for held in faces.values() for _t, data, rec in held}
    evaluator = Evaluator(
        vision=frozen_reader(readings), rules=build_rule_engine(settings), settings=settings
    )
    outcomes = []
    for case in cases:
        label = Label(
            label_id=case.label_id,
            batch_id="corpus-check",
            faces=tuple(
                Face(image_bytes=data, content_type="image/jpeg", face_tag=tag)
                for tag, data, _r in faces[case.label_id]
            ),
        )
        application = Application(
            application_id=case.label_id,
            evaluation_id=f"corpus-check-{case.label_id}",
            expected_values=expected_values_from(case.record),
            beverage_class=case.record.beverage_class,
        )
        envelope = await evaluator.evaluate(application, label)
        # The audit trail holds one entry per rule (`vr/<rule id>`) and, for
        # every rule that did not pass and carries a reason code, a second
        # entry named by that code (`reason_code/<rule id>`).
        trace = envelope.audit_trail.per_rule_trace
        codes = {
            e.evidence_ref.removeprefix("reason_code/"): e.rule_id
            for e in trace
            if e.evidence_ref.startswith("reason_code/")
        }
        rules = {
            e.rule_id: RuleOutcome(e.disposition, codes.get(e.rule_id, ""))
            for e in trace
            if e.evidence_ref.startswith("vr/")
        }
        outcomes.append(LabelOutcome(case.label_id, envelope.disposition, rules))
    return outcomes


def scoreboard(outcomes: list[LabelOutcome]) -> dict[str, Any]:
    """The figures a change to the reader or the rules is judged by.

    A check that did not apply to a label is left out of every count: it was
    not a question the product had to answer.
    """
    checks = [r for o in outcomes for r in o.rules.values() if r.disposition != "not_applicable"]
    by_check = Counter(r.disposition for r in checks)
    decided = by_check["pass"] + by_check["fail"]
    return {
        "labels": len(outcomes),
        "label_outcomes": dict(Counter(o.disposition for o in outcomes)),
        "checks": len(checks),
        "check_outcomes": dict(by_check),
        "decided_without_a_person": round(decided / len(checks), 3) if checks else 0.0,
        "review_causes": dict(
            Counter(r.reason_code for r in checks if r.disposition == "needs_review").most_common()
        ),
        "mismatch_causes": dict(
            Counter(r.reason_code for r in checks if r.disposition == "fail").most_common()
        ),
    }


def _as_json(outcomes: list[LabelOutcome]) -> dict[str, Any]:
    return {
        "scoreboard": scoreboard(outcomes),
        "labels": {
            o.label_id: {
                "disposition": o.disposition,
                "rules": {k: [v.disposition, v.reason_code] for k, v in sorted(o.rules.items())},
            }
            for o in outcomes
        },
    }


def _print(outcomes: list[LabelOutcome]) -> None:
    board = scoreboard(outcomes)
    words = {"pass": "match", "fail": "mismatch", "needs_review": "needs review"}
    print(f"{board['labels']} labels")
    for key in ("pass", "fail", "needs_review"):
        print(f"  {words[key]:<13} {board['label_outcomes'].get(key, 0)}")
    print(f"{board['checks']} checks that applied")
    for key in ("pass", "fail", "needs_review"):
        print(f"  {words[key]:<13} {board['check_outcomes'].get(key, 0)}")
    print(f"  settled without a person: {board['decided_without_a_person']:.1%}")
    for title, key in (("mismatches", "mismatch_causes"), ("sent to review", "review_causes")):
        print(f"Reason codes, {title}:")
        for code, count in board[key].items():
            print(f"  {count:>3}  {code or '(no code)'}")
    print("Mismatches, by label:")
    for o in outcomes:
        for rule_id, r in sorted(o.rules.items()):
            if r.disposition == "fail":
                print(f"  {o.label_id}  {rule_id}  {r.reason_code}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", type=Path, help="also write every outcome to this file")
    args = parser.parse_args()
    outcomes = asyncio.run(check(corpus_cases()))
    _print(outcomes)
    if args.json:
        args.json.write_text(json.dumps(_as_json(outcomes), indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
