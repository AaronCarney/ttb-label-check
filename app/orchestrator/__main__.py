"""CLI smoke: python -m app.orchestrator --task <name> --fixture <id> --backend <openai|anthropic>.

Exercises the orchestrator against recorded responses, so CI needs no network.

NOTE on path resolution: recording paths are anchored to the **repo root**, not
to CWD. The CLI smoke test invokes `python -m app.orchestrator` via
`subprocess.run` from pytest's CWD which equals the repo root, so this works
in CI; running the CLI from any other directory also works because we resolve
the anchor from this module's own filesystem location.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import deque
from pathlib import Path

from app.config import Settings


_VALID_TASKS = ("brand_disambig", "reasoning_enrich", "ocr_reconcile")
# Resolve the repo root from this module's location so recordings are found
# regardless of the user's CWD. `__file__` is `<repo>/app/orchestrator/__main__.py`,
# so parents[2] is `<repo>`.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.orchestrator")
    p.add_argument("--task", required=True, choices=_VALID_TASKS)
    p.add_argument("--fixture", required=True)
    p.add_argument("--backend", choices=("openai", "anthropic"), default="openai")
    p.add_argument("--use-recordings", action="store_true")
    return p


async def _run_openai(args, settings: Settings) -> int:
    from app.orchestrator.openai_strict import OpenAIStrictOrchestrator
    from app.schemas.application import Application
    rec_root = _REPO_ROOT / "tests" / "recordings" / "openai" / settings.llm_model_snapshot \
        / settings.prompt_version / "orchestrator" / args.task
    rec_path = rec_root / f"{args.fixture}.json"
    if not rec_path.exists():
        print(f"recording not found: {rec_path}", file=sys.stderr)
        return 2

    ring: deque = deque(maxlen=200)
    orch = OpenAIStrictOrchestrator(settings=settings, ring_buffer=ring, api_key=settings.openai_api_key or "sk-test")
    payload = json.loads(rec_path.read_text())

    if args.use_recordings:
        import respx
        from httpx import Response

        with respx.mock(base_url="https://api.openai.com") as router:
            def _handler(request):
                body = json.loads(request.content)
                # Always return the same recorded payload regardless of task name —
                # the smoke runs only the requested task, so the payload matches.
                return Response(200, json=payload)
            router.post("/v1/chat/completions").mock(side_effect=_handler)
            # Run the requested task in isolation by calling _call_task directly.
            slice_ = await orch._call_task(args.task, _stub_app(), [], [])
    else:
        slice_ = await orch._call_task(args.task, _stub_app(), [], [])

    print(f"task: {slice_.task}")
    if slice_.payload:
        for k, v in slice_.payload.items():
            print(f"{k}: {v}")
    if slice_.qualifier:
        print(f"qualifier: {slice_.qualifier}")
    return 0


def _stub_app():
    from app.schemas.application import Application
    return Application(application_id="A-001", evaluation_id="EV-cli-smoke")


async def _run(args) -> int:
    settings = Settings()
    if args.backend == "openai":
        return await _run_openai(args, settings)
    if args.backend == "anthropic":
        # Symmetric impl path; call Anthropic orchestrator's _call_task with recordings.
        from app.orchestrator.anthropic_strict import AnthropicStrictOrchestrator
        rec_root = _REPO_ROOT / "tests" / "recordings" / "anthropic" / "claude-3-5-sonnet-20241022" \
            / settings.prompt_version / "orchestrator" / args.task
        rec_path = rec_root / f"{args.fixture}.json"
        if not rec_path.exists():
            print(f"recording not found: {rec_path}", file=sys.stderr)
            return 2
        ring: deque = deque(maxlen=200)
        orch = AnthropicStrictOrchestrator(
            settings=settings, ring_buffer=ring, api_key=settings.anthropic_api_key or "sk-ant-test",
            model_snapshot="claude-3-5-sonnet-20241022",
        )
        payload = json.loads(rec_path.read_text())
        if args.use_recordings:
            import respx
            from httpx import Response
            with respx.mock(base_url="https://api.anthropic.com") as router:
                router.post("/v1/messages").mock(return_value=Response(200, json=payload))
                slice_ = await orch._call_task(args.task)
        else:
            slice_ = await orch._call_task(args.task)
        print(f"task: {slice_.task}")
        if slice_.payload:
            for k, v in slice_.payload.items():
                print(f"{k}: {v}")
        if slice_.qualifier:
            print(f"qualifier: {slice_.qualifier}")
        return 0
    print(f"unknown backend: {args.backend}", file=sys.stderr)
    return 2


def main() -> None:
    try:
        args = _build_argparser().parse_args()
    except SystemExit as e:
        # argparse exits 2 on bad args; keep that.
        raise
    try:
        sys.exit(asyncio.run(_run(args)))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
