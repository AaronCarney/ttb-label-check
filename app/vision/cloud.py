"""CloudVisionExtractor — validated default. 9-call layout+per-field pipeline.

One extract pipeline: a per-instance Semaphore bounds concurrency, a per-field
call helper does the reading, and a quality short-circuit at the top of
extract() stops on an image too poor to read.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from collections import deque
from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.schemas.calls import CallRecord
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.label import Label
from app.vision import quality
from app.vision.heading_measure import measure_heading_bold

# Keys emitted on the cloud extractor's observed_value dict that are audit-only —
# internal records of the LLM-vs-measurement comparison and the per-call
# self-reported confidence. These flow through to the wire envelope's
# upstream_meta but must be stripped from the user-facing extracted_value
# projection. Add to this set whenever a new audit key is introduced below.
OBSERVED_VALUE_AUDIT_KEYS: frozenset[str] = frozenset({
    "confidence",
    "heading_bold_llm",
    "heading_bold_measured",
    "heading_bold_measured_confident",
    "heading_bold_width_height_ratio",
})

# Self-reported per-field confidence. Required on every per-field schema so
# OpenAI Structured Outputs (strict:true) forces the model to emit a number
# we can route into Evidence.confidence. Calibration is uncalibrated — this
# is the model's own read of how well it could see/identify the field — but
# it's strictly more informative than the prior 0.7 placeholder, and the
# downstream band/min-aggregation logic now operates on real signal.
_CONFIDENCE_SCHEMA = {"type": "number", "minimum": 0.0, "maximum": 1.0}

_SCHEMAS = {
    "brand_name": {
        "type": "object",
        "properties": {
            "brand_name": {"type": "string"},
            "confidence": _CONFIDENCE_SCHEMA,
        },
        "required": ["brand_name", "confidence"],
        "additionalProperties": False,
    },
    "class_type": {
        "type": "object",
        "properties": {
            "class_type": {"type": "string"},
            "confidence": _CONFIDENCE_SCHEMA,
        },
        "required": ["class_type", "confidence"],
        "additionalProperties": False,
    },
    "abv": {
        "type": "object",
        "properties": {
            "abv_pct": {"type": "number"},
            "unit": {"type": "string"},
            "confidence": _CONFIDENCE_SCHEMA,
        },
        "required": ["abv_pct", "unit", "confidence"],
        "additionalProperties": False,
    },
    "net_contents": {
        "type": "object",
        "properties": {
            "net_contents_value": {"type": "number"},
            "unit": {"type": "string"},
            "confidence": _CONFIDENCE_SCHEMA,
        },
        "required": ["net_contents_value", "unit", "confidence"],
        "additionalProperties": False,
    },
    "gov_warning": {
        # The §16.22 health-warning rule pack checks both the verbatim body
        # text AND the heading style (all-caps, bold, type-size). Folding both
        # into one observation keeps the validator on one payload and lets us
        # apply local SWT measurement to override `heading_bold` after the
        # call — see app/vision/heading_measure.py.
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "heading_text": {"type": "string"},
            "heading_all_caps": {"type": "boolean"},
            "heading_bold": {"type": "boolean"},
            "type_size_pt": {"type": "number"},
            "confidence": _CONFIDENCE_SCHEMA,
        },
        "required": [
            "text", "heading_text", "heading_all_caps",
            "heading_bold", "type_size_pt", "confidence",
        ],
        "additionalProperties": False,
    },
    "name_address": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "city": {"type": "string"},
            "state": {"type": "string"},
            "confidence": _CONFIDENCE_SCHEMA,
        },
        "required": ["name", "city", "state", "confidence"],
        "additionalProperties": False,
    },
    "country_origin": {
        "type": "object",
        "properties": {
            "country": {"type": "string"},
            "confidence": _CONFIDENCE_SCHEMA,
        },
        "required": ["country", "confidence"],
        "additionalProperties": False,
    },
    "layout": {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "bbox": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["id", "bbox"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["fields"],
        "additionalProperties": False,
    },
}

_FIELD_NAMES = (
    "brand_name",
    "class_type",
    "abv",
    "net_contents",
    "gov_warning",
    "name_address",
    "country_origin",
)


class CloudVisionExtractor:
    def __init__(
        self,
        *,
        settings: Settings,
        ring_buffer: deque,
        api_key: str,
    ) -> None:
        self._settings = settings
        self._ring = ring_buffer
        self._api_key = api_key
        self._model = settings.llm_model_snapshot
        self._prompt_version = settings.prompt_version
        self._semaphore = asyncio.Semaphore(4)

    async def ensure_loaded(self) -> None:
        return None

    async def _call_per_field(
        self, *, field_name: str, crop: bytes, label: Label
    ) -> dict:
        prompt = (
            f"Extract field: {field_name}.\n"
            "Also return a self-reported `confidence` in [0.0, 1.0]:\n"
            "  ~0.95 — text is sharp, fully visible, unambiguous;\n"
            "  ~0.80 — clearly readable but minor occlusion/blur/skew;\n"
            "  ~0.60 — readable with effort; some characters are guesses;\n"
            "  ~0.40 — partial guess; significant occlusion or blur;\n"
            "  ~0.20 — mostly invented; field may not be on the label.\n"
            "Be honest — downstream code routes <0.6 to human review."
        )
        body = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64.b64encode(crop).decode()}"
                            },
                        },
                    ],
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": field_name,
                    "strict": True,
                    "schema": _SCHEMAS[field_name],
                },
            },
        }
        call_kind = "layout" if field_name == "layout" else "field"
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
            )
            resp.raise_for_status()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        payload = resp.json()
        content = json.loads(payload["choices"][0]["message"]["content"])
        self._ring.append(
            CallRecord(
                ts=datetime.now(timezone.utc),
                batch_id=label.batch_id,
                label_id=label.label_id,
                stage="vision.gpt4o_tiebreak",
                request={
                    "field_name": field_name,
                    "call_kind": call_kind,
                    "crop_size": len(crop),
                },
                response=content,
                latency_ms=elapsed_ms,
                model=self._model,
                provider="openai",
                prompt_version=self._prompt_version,
                output_hash=hashlib.sha256(
                    json.dumps(content, sort_keys=True).encode()
                ).hexdigest()[:16],
            )
        )
        return content

    async def _gated_call(
        self, *, field_name: str, crop: bytes, label: Label
    ) -> dict:
        async with self._semaphore:
            return await self._call_per_field(
                field_name=field_name, crop=crop, label=label
            )

    async def extract(self, label: Label) -> list[FieldObservation]:
        report = quality.assess(label)
        if report.disposition != "ok":
            return [
                FieldObservation(
                    field_id="quality",
                    beverage_class=BeverageClass.SPIRITS,
                    observed_value=None,
                    evidence=(_make_evidence(
                        field_id="quality", bbox=None, text=report.reason_code
                    ),),
                    upstream_meta={
                        "disposition": report.disposition,
                        "reason_code": report.reason_code,
                    },
                )
            ]

        layout = await self._gated_call(
            field_name="layout", crop=label.image_bytes, label=label
        )
        bbox_by_id: dict[str, tuple[int, int, int, int]] = {}
        for entry in layout.get("fields", []):
            bbox = entry.get("bbox")
            if bbox and len(bbox) == 4:
                bbox_by_id[entry["id"]] = tuple(int(v) for v in bbox)

        contents = await asyncio.gather(
            *(
                self._gated_call(field_name=fname, crop=label.image_bytes, label=label)
                for fname in _FIELD_NAMES
            )
        )
        observations: list[FieldObservation] = []
        for fname, content in zip(_FIELD_NAMES, contents):
            if fname == "gov_warning" and isinstance(content, dict):
                # Override the model's self-reported bold with a deterministic
                # stroke-width measurement on the heading bbox. The LLM's
                # value is preserved as `heading_bold_llm` in upstream_meta so
                # the audit trail captures what each source claimed.
                bbox = bbox_by_id.get("gov_warning")
                measurement = measure_heading_bold(label.image_bytes, bbox)
                content = {
                    **content,
                    "heading_bold_llm": bool(content.get("heading_bold", False)),
                    "heading_bold_measured": measurement.is_bold,
                    "heading_bold_measured_confident": measurement.confident,
                    "heading_bold_width_height_ratio": measurement.width_height_ratio,
                }
                if measurement.confident:
                    content["heading_bold"] = measurement.is_bold
            text = _extract_text(content)
            observations.append(
                FieldObservation(
                    field_id=fname,
                    beverage_class=BeverageClass.SPIRITS,
                    observed_value=content,
                    evidence=(_make_evidence(
                        field_id=fname,
                        bbox=bbox_by_id.get(fname),
                        text=text,
                        confidence=_extract_confidence(content),
                    ),),
                    upstream_meta={"bbox": bbox_by_id.get(fname)},
                )
            )
        return observations


def _extract_text(content: dict) -> str | None:
    """Pull a representative string out of the per-field LLM JSON payload.
    Schemas vary by field (text/name/country/abv); pick the first present."""
    if not isinstance(content, dict):
        return str(content) if content is not None else None
    for key in ("text", "name", "country", "value"):
        v = content.get(key)
        if v is not None:
            return str(v)
    # Fall back to any non-None scalar value (e.g. abv numeric).
    for v in content.values():
        if isinstance(v, (str, int, float)):
            return str(v)
    return None


_FALLBACK_CONFIDENCE = 0.7


def _extract_confidence(content: dict | None) -> float:
    """Pull self-reported model confidence from the per-field payload, clamped
    to [0, 1]. Falls back to 0.7 only when the field is absent — old recordings
    pre-date the schema widening, and the legibility short-circuit path
    synthesizes a quality observation that has no model call."""
    if not isinstance(content, dict):
        return _FALLBACK_CONFIDENCE
    raw = content.get("confidence")
    if raw is None:
        return _FALLBACK_CONFIDENCE
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return _FALLBACK_CONFIDENCE
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _make_evidence(
    *,
    field_id: str,
    bbox: tuple[int, int, int, int] | None,
    text: str | None,
    confidence: float = _FALLBACK_CONFIDENCE,
) -> Evidence:
    """Synthesize a single Evidence from the LLM's per-field payload + the
    bbox surfaced by the layout call."""
    return Evidence(
        field_id=field_id,
        source=EvidenceSource.LAYOUT,
        bbox=bbox,
        extracted_text=text,
        match_kind=MatchKind.NONE,
        confidence=confidence,
    )
