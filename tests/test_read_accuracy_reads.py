"""The reading-accuracy harness can hand a corpus image to the reader.

`uv run python -m eval.read_accuracy` is the command the README's reading
accuracy figures come from. The replay suite exercises its scoring, but not the
step that wraps an image as a label for the reader, and that step stopped
working when a label came to carry its faces rather than one image: the command
crashed on its first label. This reads one corpus face through that step with a
stand-in reader, so no OCR model is loaded.
"""

from __future__ import annotations

import asyncio
import json

from app.schemas.extracted import FieldObservation
from app.schemas.label import Label
from eval.read_accuracy import LABELS_ROOT, _read_one_face


class _StandInReader:
    last_reading = None

    def __init__(self) -> None:
        self.seen: list[Label] = []

    async def extract(self, label: Label) -> list[FieldObservation]:
        self.seen.append(label)
        return []


def test_a_corpus_face_reaches_the_reader_as_a_one_face_label() -> None:
    entry = json.loads((LABELS_ROOT / "manifest.json").read_text())["labels"][0]
    face, relative = next(iter(entry["images"].items()))
    reader = _StandInReader()

    payloads, replayed = asyncio.run(_read_one_face(reader, entry, face, relative, None))

    assert (payloads, replayed) == ({}, False)
    (label,) = reader.seen
    (sent,) = label.faces
    assert sent.image_bytes == (LABELS_ROOT / relative).read_bytes()
    assert sent.face_tag == ("front" if face == "front" else "back")
