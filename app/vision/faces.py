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

import re
from collections.abc import Sequence

from app.schemas.extracted import FieldObservation

# The field_id both readers use for the observation that is not a reading at
# all but the quality gate's refusal to read. Named here because the readers
# and this module have to agree on it.
QUALITY_FIELD_ID = "quality"

# The field_id both readers give the alcohol content reading.
ALCOHOL_FIELD_ID = "abv"

# The field_id both readers give the brand reading.
BRAND_FIELD_ID = "brand_name"

# The field_id both readers give the government warning.
WARNING_FIELD_ID = "gov_warning"


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


# What makes a percentage an alcohol statement rather than a bare figure: the
# words 27 CFR §5.65(b) and §7.65(b) print with it.
_ALCOHOL_WORDS_RE = re.compile(r"ALC|VOL", re.I)


def _rank(observation: FieldObservation) -> tuple[bool, bool, float]:
    """How strongly a face's reading of a field claims to be the label's.

    The confidence, except for two fields where what was read ranks first. For
    the alcohol content, a statement printed with the alcohol words: the words
    are what say the figure is the alcohol content, and a bare percentage on
    another face — a mash bill's "75% CORN" read more cleanly than "56% ALC. BY
    VOL." — says nothing of the kind. For the government warning, a statement
    read from its heading: a face where only the statement's words were read
    cannot be judged, and one that can outranks it however cleanly it was read.
    The OCR score measures how cleanly characters were read, not which text is
    the field. Where no face found the warning, a face that read some of its
    words ranks above one that read none, because those words are what keep
    the label from being rejected for a warning the reader may have missed.
    """
    value = observation.observed_value
    if not isinstance(value, dict):
        return False, False, _confidence(observation)
    seen = False
    if observation.field_id == ALCOHOL_FIELD_ID:
        first = bool(_ALCOHOL_WORDS_RE.search(str(value.get("alc_text") or "")))
    elif observation.field_id == WARNING_FIELD_ID:
        first = bool(str(value.get("text") or "").strip())
        seen = bool(value.get("wording_without_heading") or value.get("warning_words_seen"))
    else:
        first = False
    return first, seen, _confidence(observation)


def merge_readings(readings: Sequence[Sequence[FieldObservation]]) -> list[FieldObservation]:
    """Every face's reading, reduced to one reading of the label.

    One observation per field, taken from the face that actually found it —
    the highest-ranked reading of that field (`_rank`), with ties going to the
    earlier face, which is the order the faces were submitted in. A field no
    face found survives as the absent reading it is, so a government warning
    printed on none of the submitted faces still reaches the rules as missing
    and still fails.

    Field order follows first appearance across the faces, so a field only the
    back shows sorts after the ones the front does.

    One part of one field is gathered from every face instead: the proof
    figures on the alcohol reading. A label may print its proof on a face that
    does not carry the ABV statement, and taking the alcohol reading from one
    face would drop it. The proof rule compares every figure the label states.

    The other is the list of lines the local reader hands over with its brand
    pick. The brand rule searches it for the declared name, and the name may be
    printed on a face whose pick lost the merge.
    """
    best: dict[str, FieldObservation] = {}
    for reading in readings:
        for observation in reading:
            incumbent = best.get(observation.field_id)
            if incumbent is None or _rank(observation) > _rank(incumbent):
                best[observation.field_id] = observation
    alcohol = best.get(ALCOHOL_FIELD_ID)
    if alcohol is not None:
        best[ALCOHOL_FIELD_ID] = _with_every_proof(alcohol, readings)
    brand = best.get(BRAND_FIELD_ID)
    if brand is not None:
        best[BRAND_FIELD_ID] = _with_every_candidate(brand, readings)
    return list(best.values())


def _with_every_candidate(
    brand: FieldObservation, readings: Sequence[Sequence[FieldObservation]]
) -> FieldObservation:
    """The chosen brand reading, carrying every face's candidate lines in face
    order. A reader that lists none leaves the reading as it was."""
    if not isinstance(brand.observed_value, dict):
        return brand
    candidates: list[dict] = []
    listed = False
    for reading in readings:
        for observation in reading:
            value = observation.observed_value
            if observation.field_id != BRAND_FIELD_ID or not isinstance(value, dict):
                continue
            if isinstance(value.get("candidates"), list):
                listed = True
                candidates.extend(value["candidates"])
    if not listed:
        return brand
    return brand.model_copy(
        update={"observed_value": {**brand.observed_value, "candidates": candidates}}
    )


def _with_every_proof(
    alcohol: FieldObservation, readings: Sequence[Sequence[FieldObservation]]
) -> FieldObservation:
    """The chosen alcohol reading, carrying every face's proof figures once.

    A reader that returns no proof list leaves the reading as it was, so the
    proof rule still reads the figure out of the statement itself.
    """
    if not isinstance(alcohol.observed_value, dict):
        return alcohol
    proofs: list[dict] = []
    listed = False
    for reading in readings:
        for observation in reading:
            value = observation.observed_value
            if observation.field_id != ALCOHOL_FIELD_ID or not isinstance(value, dict):
                continue
            if isinstance(value.get("proof"), list):
                listed = True
                proofs.extend(p for p in value["proof"] if p not in proofs)
    if not listed:
        return alcohol
    return alcohol.model_copy(
        update={"observed_value": {**alcohol.observed_value, "proof": proofs}}
    )
