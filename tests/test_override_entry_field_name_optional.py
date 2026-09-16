"""OverrideEntry.field_name accepts None, for an override that applies to the
whole submission rather than to one named field."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.audit import OverrideEntry


def _now() -> datetime:
    return datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc)


def test_override_entry_accepts_none_field_name_for_whole_envelope_override():
    entry = OverrideEntry(
        field_name=None,
        original_disposition="needs_review",
        applied_disposition="pass",
        reason_code="BRAND.NAME.NEEDS_REVIEW",
        justification_text="Reviewed and approved.",
        reviewer_id="session-test1234",
        timestamp=_now(),
    )
    assert entry.field_name is None


def test_override_entry_field_name_default_is_none_when_omitted():
    entry = OverrideEntry(
        original_disposition="needs_review",
        applied_disposition="pass",
        reason_code="BRAND.NAME.NEEDS_REVIEW",
        reviewer_id="session-test1234",
        timestamp=_now(),
    )
    assert entry.field_name is None
    assert entry.justification_text is None


def test_override_entry_still_accepts_string_field_name_backwards_compat():
    """Callers that pass a string keep working; only None is newly allowed."""
    entry = OverrideEntry(
        field_name="brand_name",
        original_disposition="fail",
        applied_disposition="needs_review",
        reason_code="BRAND.NAME.MISMATCH",
        justification_text="Borderline — flag for human re-review.",
        reviewer_id="session-test1234",
        timestamp=_now(),
    )
    assert entry.field_name == "brand_name"


def test_override_entry_rejects_non_string_non_none_field_name():
    """Type discipline preserved — only str | None accepted."""
    with pytest.raises(ValidationError):
        OverrideEntry(
            field_name=42,  # type: ignore[arg-type]
            original_disposition="pass",
            applied_disposition="pass",
            reason_code="BRAND.NAME.NEEDS_REVIEW",
            reviewer_id="session-test1234",
            timestamp=_now(),
        )
