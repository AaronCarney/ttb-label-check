"""POST /labels/{evaluation_id}/overrides — a reviewer's override of a check result."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.api.ui.results import SingleResultStore, _get_result_store
from app.schemas.audit import OverrideEntry

router = APIRouter()
_logger = logging.getLogger("app.api.overrides")


def _load_accepted_reason_codes() -> frozenset[str]:
    """Load the canonical reason-code registry from rules/reason_codes.yaml.

    As in the rule-pack loader, any code not in the registry is refused.
    Raises ``FileNotFoundError`` if the registry is missing; loud failure
    is preferable to silently rejecting every override request with 400."""
    from pathlib import Path

    import yaml

    yaml_path = Path("rules/reason_codes.yaml")
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"reason-code registry not found at {yaml_path.resolve()} — "
            "the override endpoint cannot validate codes without it"
        )
    raw = yaml.safe_load(yaml_path.read_text())
    return frozenset((raw or {}).get("codes", {}).keys())


_ACCEPTED_REASON_CODES_CACHE: frozenset[str] | None = None


def _accepted_reason_codes() -> frozenset[str]:
    """Lazy accessor — load on first call, cache for the process. Lazy
    initialization avoids a module-import side effect that would fail
    opaquely if any test imports this module before the cwd is repo-root.
    Tests can reset the cache via ``app.api.overrides._ACCEPTED_REASON_CODES_CACHE = None``."""
    global _ACCEPTED_REASON_CODES_CACHE
    if _ACCEPTED_REASON_CODES_CACHE is None:
        _ACCEPTED_REASON_CODES_CACHE = _load_accepted_reason_codes()
        _logger.info(
            f"override_registry_loaded codes={len(_ACCEPTED_REASON_CODES_CACHE)} path=rules/reason_codes.yaml",
            extra={"reason_code": "ENGINE.OK.NONE"},
        )
    return _ACCEPTED_REASON_CODES_CACHE


class OverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str | None = None
    applied_disposition: Literal["pass", "fail", "needs_review"]
    reason_code: str
    justification_text: str | None = None


def _new_reviewer_id() -> str:
    return "session-" + uuid.uuid4().hex[:12]


def _find_label_in_batches(state_batches, evaluation_id: str):
    """Locate the (batch_id, InFlightBatch, label_id, env) for an evaluation
    that has a recorded ``result``. O(N*M) — acceptable for prototype scale.

    Contract: a label that is queued but not yet evaluated has no entry in
    ``in_flight.results`` and is therefore NOT findable. Callers MUST treat
    that case as 404 (the override is rejected because the disposition the
    reviewer is overriding does not yet exist). The UI guards by enabling
    the override button only after the SSE ``label-result`` event lands."""
    for batch_id, in_flight in state_batches.items():
        for label_id, env in in_flight.results.items():
            if env.evaluation_id == evaluation_id:
                return batch_id, in_flight, label_id, env
    return None, None, None, None


@router.post("/labels/{evaluation_id}/overrides")
async def post_override(
    evaluation_id: str,
    payload: OverrideRequest,
    request: Request,
    results: SingleResultStore = Depends(_get_result_store),
) -> dict:
    if payload.reason_code not in _accepted_reason_codes():
        _logger.warning(
            f"override_rejected_unknown_code evaluation_id={evaluation_id} reason_code={payload.reason_code} applied={payload.applied_disposition}",
            extra={
                "evaluation_id": evaluation_id,
                "reason_code": payload.reason_code,
            },
        )
        raise HTTPException(
            status_code=400,
            detail=f"reason_code '{payload.reason_code}' is not in the loaded registry",
        )

    batch_id, in_flight, label_id, env = _find_label_in_batches(
        request.app.state.batches, evaluation_id
    )
    if env is None:
        # Not in a batch, so it may be a single label. Those are kept by
        # `app/api/ui/results.py` precisely so this call has something to
        # amend (`docs/decisions.md#0033`).
        env = results.get(evaluation_id)
    if env is None:
        # Three cases collapse to 404: (a) evaluation_id never existed;
        # (b) the label is queued but the evaluator has not emitted a result;
        # (c) the single-label result has passed its retention window. Per the
        # contract above, the UI prevents (b) by gating the override button on
        # the SSE label-result event.
        _logger.warning(
            f"override_rejected_not_found evaluation_id={evaluation_id} reason_code={payload.reason_code}",
            extra={
                "evaluation_id": evaluation_id,
                "reason_code": "ENGINE.OVERRIDE.NOT_FOUND",
            },
        )
        raise HTTPException(
            status_code=404,
            detail=(
                f"evaluation_id {evaluation_id} has no result to override: it is in "
                "no in-flight batch and no single-label result is kept for it"
            ),
        )

    entry = OverrideEntry(
        field_name=payload.field_name,
        original_disposition=env.disposition,
        applied_disposition=payload.applied_disposition,
        reason_code=payload.reason_code,
        justification_text=payload.justification_text,
        reviewer_id=_new_reviewer_id(),
        timestamp=datetime.now(UTC),
    )

    new_audit = env.audit_trail.model_copy(
        update={
            "overrides": (*env.audit_trail.overrides, entry),
        }
    )
    new_env = env.model_copy(update={"audit_trail": new_audit})
    if in_flight is not None:
        in_flight.results[label_id] = new_env
    else:
        # A single label: the store is where its record lives, so the amended
        # envelope is written back there.
        results.put(new_env)

    # Surface on the SSE stream so the UI updates the timeline. Bus may be
    # absent if the lifespan registry has been torn down concurrently; treat
    # the broadcast as best-effort — the audit-trail mutation is the
    # source-of-truth contract.
    # A single label has no batch and so no stream to announce on.
    bus = request.app.state.buses.get(batch_id) if batch_id is not None else None
    bus_present = bus is not None
    if bus is not None:
        bus.broadcast(
            {
                "event": "override-applied",
                "data": {
                    "batch_id": batch_id,
                    "evaluation_id": evaluation_id,
                    "entry": entry.model_dump(mode="json"),
                },
            }
        )

    _logger.info(
        f"override_applied batch_id={batch_id or 'single'} evaluation_id={evaluation_id} field={payload.field_name} {env.disposition}->{payload.applied_disposition} bus={bus_present}",
        extra={
            "batch_id": batch_id or "single",
            "evaluation_id": evaluation_id,
            "reason_code": payload.reason_code,
        },
    )

    return entry.model_dump(mode="json")
