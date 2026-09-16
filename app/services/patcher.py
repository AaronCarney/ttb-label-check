"""ValidationResult patcher: how an orchestrator note reaches a rule result
without the model getting to change the outcome.

Touches ONLY ``message`` (annotation), ``aggregated_confidence`` (downward-only),
``evidence`` (additive). NEVER touches ``outcome``, ``severity``, ``reason_code``.

The patcher tests assert this even when the orchestrator disagrees with a
rule-engine FAIL.
"""
from __future__ import annotations

from typing import Iterable

from app.schemas.refined import Refined
from app.schemas.rejection import ValidationResult


def patch_validation_results(
    results: Iterable[ValidationResult], refined: Refined,
) -> tuple[ValidationResult, ...]:
    slices_by_rule = {s.rule_id: s for s in refined.tasks if s.rule_id is not None}
    patched: list[ValidationResult] = []
    for vr in results:
        slice_ = slices_by_rule.get(vr.rule_id)
        if slice_ is None:
            patched.append(vr)
            continue
        annotation = (
            f"orchestrator/{slice_.task} note: "
            + (str(slice_.payload) if slice_.payload else f"qualifier={slice_.qualifier}")
        )
        new_message = (vr.message + " | " + annotation) if vr.message else annotation
        # outcome / severity / reason_code untouched — the model does not decide.
        patched.append(vr.model_copy(update={"message": new_message}))
    return tuple(patched)
