"""Drift guard: every code that stops a label for its photo has an applicant message.

`app/vision/quality.py` decides a photo cannot be read and names why, and
`app/vision/local.py` names a photo it found no text on. The
browser card that tells the applicant what to do about it carries one message
per code, in `frontend/src/lib/needsBetterPhoto.ts`. Adding a gate outcome
there and not here would leave the reviewer looking at a card with nothing in
it, or at no card at all, which is the failure this pair of files was written
to end.

Deliberately one-directional: the TypeScript file may carry a code the gate
does not emit (a code retired from the gate keeps its message until someone
removes it), but the gate may not emit a code the TypeScript file lacks.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_QUALITY = _ROOT / "app" / "vision" / "quality.py"
_READER = _ROOT / "app" / "vision" / "local.py"
_MESSAGES = _ROOT / "frontend" / "src" / "lib" / "needsBetterPhoto.ts"

_PY_CODE = re.compile(r'reason_code="([A-Z0-9_.]+)"')
_READER_CODE = re.compile(r'^_NO_TEXT = "([A-Z0-9_.]+)"$', re.M)
_TS_CODE = re.compile(r'"((?:WARNING\.LEGIBILITY|LEGIBILITY\.PHOTO)\.[A-Z0-9_]+)":')


def test_every_quality_gate_code_has_an_applicant_message() -> None:
    emitted = set(_PY_CODE.findall(_QUALITY.read_text()))
    assert emitted, f"no reason codes found in {_QUALITY} — the pattern has drifted"
    from_reader = set(_READER_CODE.findall(_READER.read_text()))
    assert from_reader, f"no no-text code found in {_READER} — the pattern has drifted"
    emitted |= from_reader

    messaged = set(_TS_CODE.findall(_MESSAGES.read_text()))
    assert messaged, f"no reason codes found in {_MESSAGES} — the pattern has drifted"

    missing = emitted - messaged
    assert not missing, (
        "app/vision/ emits reason codes that "
        "frontend/src/lib/needsBetterPhoto.ts has no applicant message for, so the "
        f"Needs-better-photo card cannot explain them: {sorted(missing)}"
    )
