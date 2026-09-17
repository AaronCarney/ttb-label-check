"""The result of a single-label check: where it is kept, so it can be amended.

A batch keeps its results in memory for as long as the batch is in flight, and
that is what the override endpoint searches. A single label had nowhere at all:
the result page rendered the envelope into the template and dropped it, so an
override against a single label could only ever answer "not found".

The envelopes are kept the way the label images are — one JSON file per
evaluation, under the machine's temporary directory, swept on the same window.
The reasoning in `docs/decisions.md#0018` for the images applies unchanged: a
page opened now is still whole when it is looked at again, every worker on the
host reads what every other one wrote, and a restart loses nothing.

**What is kept is not the whole envelope.** An override amends the audit trail
and needs the evaluation id and the disposition to do it; it never reads a
field's values. So every part of the envelope that carries what the applicant
wrote or what the label said is blanked before the file is written — see
`_forget_applicant_material`. C-2 asks the product to keep none of it, and
keeping the whole envelope for seven days was a wider bargain than the override
needed (`docs/decisions.md#0033`).
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
import uuid
from pathlib import Path

from app.schemas.wire.disposition import DispositionEnvelope

_logger = logging.getLogger("app.api.ui.results")

# Same guard as the image store: an evaluation id reaches this from a URL path,
# so no id can name a file outside the store whatever a caller sends.
_EVALUATION_ID = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")

# The window the image store uses, for the same reason and so the two do not
# drift into disagreeing about how long a result page stays whole.
_RETENTION_SECONDS = 7 * 24 * 60 * 60


class SingleResultStore:
    """The envelopes from single-label checks, as files in one directory."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def put(self, envelope: DispositionEnvelope) -> None:
        """Keep one result under the id an override will ask for, carrying
        nothing of the applicant's into the file."""
        envelope = _forget_applicant_material(envelope)
        evaluation_id = envelope.evaluation_id
        if not _EVALUATION_ID.match(evaluation_id):
            raise ValueError(f"refusing to store under evaluation id {evaluation_id!r}")

        self._root.mkdir(parents=True, exist_ok=True)
        final = self._root / f"{evaluation_id}.json"
        # Written beside the final name and moved onto it, so a concurrent
        # reader never sees half a document.
        staging = self._root / f".{evaluation_id}.{uuid.uuid4().hex}.part"
        staging.write_text(envelope.model_dump_json())
        os.replace(staging, final)
        self._forget_what_has_expired()

    def get(self, evaluation_id: str) -> DispositionEnvelope | None:
        """The result kept for one evaluation, or nothing.

        Nothing is the honest answer for an id that was never stored, for one
        that is not an id at all, for one the sweep has dropped, and for a file
        that cannot be read or parsed. Every one of those is a 404 to a caller.
        """
        if not _EVALUATION_ID.match(evaluation_id):
            return None
        path = self._root / f"{evaluation_id}.json"
        try:
            raw = path.read_text()
        except OSError:
            return None
        try:
            return DispositionEnvelope.model_validate(json.loads(raw))
        except Exception:
            _logger.warning(
                "single_result_unreadable",
                extra={"evaluation_id": evaluation_id, "reason_code": "ENGINE.OK.NONE"},
            )
            return None

    def _forget_what_has_expired(self) -> None:
        """Drop results older than the retention window, on a write, as the
        image store does and for the same reason."""
        cutoff = time.time() - _RETENTION_SECONDS
        try:
            entries = list(self._root.iterdir())
        except OSError:  # pragma: no cover — the directory was just written to
            return
        for path in entries:
            try:
                if path.stat().st_mtime >= cutoff:
                    continue
                path.unlink()
            except OSError:
                continue


def _forget_applicant_material(envelope: DispositionEnvelope) -> DispositionEnvelope:
    """A copy of `envelope` with every value-bearing string emptied.

    What survives is what an override needs and what a later reader could not
    misuse: the evaluation id, the dispositions and confidences, the rule ids,
    the CFR citations, the reason codes, the evidence geometry, the audit trail
    and the metrics. What goes is everything that could name a person or quote
    a label: the value read off the artwork, the value the application
    declared, the sentence explaining a finding, any model-written prose, and
    the label reference, which is built from the name of the uploaded file.

    Returns a new object. The caller's envelope is the one rendered to the
    page, and it must keep its values.
    """
    fields = tuple(
        field.model_copy(
            update={
                "extracted_value": "",
                "expected_value": "",
                "rule_findings": tuple(
                    rf.model_copy(update={"plain_language_explanation": ""})
                    for rf in field.rule_findings
                ),
                "ai_suggestion": field.ai_suggestion.model_copy(update={"text": None}),
            }
        )
        for field in envelope.fields
    )
    return envelope.model_copy(update={"fields": fields, "label_ref": ""})


def _default_store_root() -> Path:
    """Where single-label results live when nothing overrides it."""
    return Path(tempfile.gettempdir()) / "ttb-label-check" / "label-results"


_store = SingleResultStore(_default_store_root())


def _get_result_store() -> SingleResultStore:
    """The store this request reads or writes, as a dependency so a test can
    point the app at a directory of its own."""
    return _store
