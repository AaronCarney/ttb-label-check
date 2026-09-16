"""GET /batches/{batch_id}/labels/{label_id}/calls — DEV_MODE-gated."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import Settings


router = APIRouter(tags=["dev"])


def _dev_mode_on() -> bool:
    return Settings().dev_mode


@router.get("/batches/{batch_id}/labels/{label_id}/calls")
async def get_calls(batch_id: str, label_id: str) -> list[dict]:
    if not _dev_mode_on():
        raise HTTPException(status_code=404, detail="not found")
    # Returns an empty list: the ring buffer is populated on the
    # Evaluator → orchestrator path; tests can populate app.state.calls[label_id].
    return []
