"""The corpus figure quoted beside the sideways thresholds must be the corpus.

`_SIDEWAYS_RATIO`, `_SIDEWAYS_MIN_BOXES` and `_SIDEWAYS_LONE_RATIO` in
`app.vision.local` are set from a measurement over the label corpus, and the
comment above them is the only record of that measurement. On 2026-09-17 it
cited 72 images against a corpus of 62, so the numbers underneath it could not
be the ones anybody had taken, and nothing failed to say so.

This is the cheap half of the guard: it catches the citation drifting away from
the corpus it names, which is what happened. It cannot check that the ratios
themselves are still right -- that needs the detector, and `eval.box_ratios` is
the command that re-derives them. Growing the corpus should fail this test, and
the fix is to re-run that command and rewrite the comment from its output.
"""

from __future__ import annotations

import re
from pathlib import Path

CORPUS = Path("tests/fixtures/labels")
SOURCE = Path("app/vision/local.py")

# The sentence the comment uses to say what it was measured over.
CITED = re.compile(r"corpus's (\d+) images")


def test_the_sideways_comment_cites_the_corpus_it_was_measured_over() -> None:
    images = sorted(CORPUS.glob("*/*.jpg"))
    assert images, f"no corpus images under {CORPUS}"

    found = CITED.search(SOURCE.read_text(encoding="utf-8"))
    assert found is not None, (
        f"{SOURCE} no longer says how many images the sideways thresholds were "
        f"measured over. The figure is the only provenance those constants have."
    )

    cited = int(found.group(1))
    assert cited == len(images), (
        f"{SOURCE} says the sideways thresholds were measured over {cited} images; "
        f"the corpus holds {len(images)}. Re-run `uv run python -m eval.box_ratios` "
        f"under the CPU budget and rewrite the comment from what it reports."
    )


def test_the_measurement_command_the_comment_names_exists() -> None:
    """A comment that names a reproducer people cannot run is not provenance."""
    assert Path("eval/box_ratios.py").exists(), (
        "eval/box_ratios.py is gone, so the sideways thresholds have no reproducer"
    )
