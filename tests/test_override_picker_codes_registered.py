"""The reviewer's override picker offers only codes the override endpoint accepts.

`frontend/src/components/LabelResult.tsx` carries its own short list of reason
codes for the override drawer, so the picker and `rules/reason_codes.yaml` can drift apart
without anything noticing: `app/api/overrides.py` refuses a code the registry
does not list, and the reviewer meets a 400 at the point of overriding.

The field correction control sends a code of its own per result, from
`frontend/src/lib/corrections.ts`, and is held to the registry the same way.

The picker is a curated shortlist, not the whole registry, so this asserts one
direction only — every code it offers is a code the endpoint will take.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PICKER_SOURCE = ROOT / "frontend" / "src" / "components" / "LabelResult.tsx"
CORRECTIONS_SOURCE = ROOT / "frontend" / "src" / "lib" / "corrections.ts"
REGISTRY = ROOT / "rules" / "reason_codes.yaml"


def _picker_codes() -> list[str]:
    source = PICKER_SOURCE.read_text(encoding="utf-8")
    _, _, after = source.partition("export const REASON_CODES: ReasonCodeEntry[] = [")
    assert after, f"override picker array not found in {PICKER_SOURCE}"
    block, _, _ = after.partition("];")
    return re.findall(r'code:\s*"([^"]+)"', block)


def test_picker_offers_at_least_one_code() -> None:
    assert _picker_codes(), "override picker is empty"


def test_every_picker_code_is_in_the_registry() -> None:
    registered = set((yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}).get("codes", {}))
    unknown = [code for code in _picker_codes() if code not in registered]
    assert not unknown, (
        "override picker offers reason codes the override endpoint will refuse: "
        + ", ".join(unknown)
    )


def _correction_codes() -> dict[str, str]:
    """The code each field correction carries, by the result it corrects to."""
    source = CORRECTIONS_SOURCE.read_text(encoding="utf-8")
    _, _, after = source.partition("export const CORRECTION_CODES: Record<Verdict, string> = {")
    assert after, f"correction code map not found in {CORRECTIONS_SOURCE}"
    block, _, _ = after.partition("};")
    return dict(re.findall(r'(\w+):\s*"([^"]+)"', block))


def test_every_field_correction_code_is_in_the_registry() -> None:
    """The result page's "this result is wrong" control sends one of these for
    each result a reviewer can correct a field to, and all three must be taken."""
    codes = _correction_codes()
    assert set(codes) == {"pass", "fail", "needs_review"}
    registered = set((yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}).get("codes", {}))
    unknown = [code for code in codes.values() if code not in registered]
    assert not unknown, "field correction sends codes the endpoint will refuse: " + ", ".join(unknown)
