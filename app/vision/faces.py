"""Reading a label that has more than one face.

A label is a document and its faces are its pages, so the reader reads every
face and the rules are run over one reading of the whole label. This module
holds the two pieces that are the same for both readers: what a face's reading
means when the quality gate refused it, and how several faces' readings become
one.

Why the readings are merged rather than concatenated: the rule engine runs
every applicable rule against every observation it is handed
(`app/rules/yaml_engine.py`), and the envelope builder keys its fields by
`field_id` and keeps one (`app/services/envelope_builder.py`). Hand it both
faces' readings unmerged and a bourbon whose brand is on the front fails the
brand rule on the strength of the back, which does not show a brand and was
never meant to. Merging first is what makes a two-face label one document
instead of two labels sharing an id.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.extracted import FieldObservation

# The field_id both readers use for the observation that is not a reading at
# all but the quality gate's refusal to read. Named here because the readers
# and this module have to agree on it.
QUALITY_FIELD_ID = "quality"


def is_unreadable(reading: Sequence[FieldObservation]) -> bool:
    """Whether a face's reading is a refusal to read rather than a reading.

    Both readers answer an unusable face with exactly one observation under
    `quality`, carrying the reason the gate gave. Nothing was read, so there is
    nothing to merge and the label stops here.
    """
    return len(reading) == 1 and reading[0].field_id == QUALITY_FIELD_ID


def _confidence(observation: FieldObservation) -> float:
    """How strongly this reading claims the field is on this face.

    Both readers set an absent field to a payload with `confidence: 0.0` and
    carry that onto the evidence, so zero means "this face does not show it"
    and anything above zero means "this face does".
    """
    return max((e.confidence for e in observation.evidence), default=0.0)


def merge_readings(readings: Sequence[Sequence[FieldObservation]]) -> list[FieldObservation]:
    """Every face's reading, reduced to one reading of the label.

    One observation per field, taken from the face that actually found it —
    the highest-confidence reading of that field, with ties going to the
    earlier face, which is the order the faces were submitted in. A field no
    face found survives as the absent reading it is, so a government warning
    printed on none of the submitted faces still reaches the rules as missing
    and still fails.

    Field order follows first appearance across the faces, so a field only the
    back shows sorts after the ones the front does.
    """
    best: dict[str, FieldObservation] = {}
    for reading in readings:
        for observation in reading:
            incumbent = best.get(observation.field_id)
            if incumbent is None or _confidence(observation) > _confidence(incumbent):
                best[observation.field_id] = observation
    return list(best.values())
