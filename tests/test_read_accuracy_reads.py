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
from eval.read_accuracy import LABELS_ROOT, _read_faces, _read_one_face


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


def test_the_cooling_pause_follows_each_image_read_and_is_not_timed(monkeypatch) -> None:
    # The machine's budget for a reader run is a pause between images, so the
    # pause belongs after each face the reader reads, and none after a face
    # replayed from a recording. The seconds the harness reports time the
    # reading only.
    entry = next(
        e
        for e in json.loads((LABELS_ROOT / "manifest.json").read_text())["labels"]
        if len(e["images"]) == 2
    )
    pauses: list[float] = []
    clock = [100.0]

    async def fake_sleep(seconds: float) -> None:
        pauses.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr("eval.read_accuracy.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("eval.read_accuracy.time.perf_counter", lambda: clock[0])

    _, seconds, replayed = asyncio.run(_read_faces(_StandInReader(), entry, None, 2.0))

    assert (pauses, replayed) == ([2.0, 2.0], 0)
    # The stand-in reads in no time, so every second on the clock is pause.
    assert seconds == 0.0


def test_a_face_replayed_from_a_recording_is_not_followed_by_a_pause(monkeypatch) -> None:
    pauses: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        pauses.append(seconds)

    async def replayed_face(*_args):
        return {}, True

    monkeypatch.setattr("eval.read_accuracy.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("eval.read_accuracy._read_one_face", replayed_face)
    entry = json.loads((LABELS_ROOT / "manifest.json").read_text())["labels"][0]

    _, _, replayed = asyncio.run(_read_faces(_StandInReader(), entry, None, 2.0))

    assert pauses == []
    assert replayed == len(entry["images"])
