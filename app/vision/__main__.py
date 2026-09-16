"""CLI smoke entry — `python -m app.vision --label <path> --mode <cloud|local>`.

This module exercises the cloud impl against committed recordings, so CI needs
no network. The recording-replay mechanism uses respx to mount
each recording file as a route keyed on the OpenAI request body's
`response_format.json_schema.name` field — which the cloud impl populates
deterministically for each per-field call.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import deque
from pathlib import Path

from app.config import Settings


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.vision")
    p.add_argument("--label", required=True, type=Path)
    p.add_argument("--use-recordings", action="store_true",
                   help="Mount tests/recordings/openai/<snapshot>/<prompt-version>/<fixture>/* via respx.")
    return p


async def _run(args: argparse.Namespace) -> int:
    from app.schemas.label import Dimensions, Label
    from app.vision.cloud import CloudVisionExtractor

    if not args.label.exists():
        print(f"label not found: {args.label}", file=sys.stderr)
        return 2

    settings = Settings()
    ring = deque(maxlen=200)

    label = Label(
        label_id=args.label.stem,
        batch_id="cli-smoke",
        image_bytes=args.label.read_bytes(),
        content_type=("image/png" if args.label.suffix.lower() == ".png" else "image/jpeg"),
        face_tag="front",
        dimensions=Dimensions(width_px=200, height_px=200, dpi=300),
    )

    extractor = CloudVisionExtractor(settings=settings, ring_buffer=ring,
                                     api_key=settings.openai_api_key or "sk-test")

    if args.use_recordings:
        import respx  # dev-only — guarded by flag
        from httpx import Response

        rec_root = Path("tests/recordings/openai") / settings.llm_model_snapshot \
            / settings.prompt_version / args.label.parent.name
        if not rec_root.exists():
            print(f"recordings not found: {rec_root}", file=sys.stderr)
            return 2

        # respx 0.23.1 deduplicates same-URL/method routes (only the last mount
        # survives). Equivalent: one dispatcher handler keyed on the request
        # body's `response_format.json_schema.name`, which the cloud impl sets
        # per call. Mirrors tests/test_vision_cloud_extraction.py.
        recordings = {p.stem: json.loads(p.read_text()) for p in rec_root.glob("*.json")}

        with respx.mock(base_url="https://api.openai.com") as router:
            def _dispatch(request):
                body = json.loads(request.content)
                name = body.get("response_format", {}).get("json_schema", {}).get("name")
                payload = recordings.get(name)
                if payload is None:
                    return Response(404, json={"error": f"no recording for {name!r}"})
                return Response(200, json=payload)

            router.post("/v1/chat/completions").mock(side_effect=_dispatch)

            observations = await extractor.extract(label)
    else:
        observations = await extractor.extract(label)

    print(f"field_count: {len(observations)}")
    print(f"first_three: {[o.field_id for o in observations[:3]]}")
    return 0


def main() -> None:
    args = _build_argparser().parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
