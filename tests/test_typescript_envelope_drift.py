"""The hand-mirrored TypeScript envelope types track the Pydantic field names.

This is a fast structural canary, not a full type-isomorphism check. If a
field is renamed in app/schemas/wire/*.py, this test surfaces the drift; the
fix is a one-line edit in frontend/src/types/envelopes.ts.

Two layers:
1. **Global canary** — every Pydantic field name appears somewhere in the TS
   file. Catches outright renames.
2. **Per-class canary** — every Pydantic class has a TS interface with the
   same name and the same field set. Catches "field added to class B that
   already exists in class A" drift the global set silently passes.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS_PATH = ROOT / "frontend" / "src" / "types" / "envelopes.ts"
PYDANTIC_FILES = [
    ROOT / "app" / "schemas" / "wire" / "disposition.py",
    ROOT / "app" / "schemas" / "wire" / "batch.py",
    ROOT / "app" / "schemas" / "audit.py",
    ROOT / "app" / "schemas" / "metrics.py",
]

# Fields whose names the TS file is required to contain. These are field
# IDENTIFIERS as written in Pydantic source (e.g. ``label_ref:``); the regex
# captures lines like ``    label_ref: str`` or ``    label_ref: Literal[...]``.
_FIELD_RE = re.compile(r"^\s{4}([a-z_][a-z0-9_]*):\s", re.MULTILINE)
_CLASS_RE = re.compile(r"^class\s+([A-Z][A-Za-z0-9_]*)\(BaseModel\):", re.MULTILINE)
_TS_INTERFACE_RE = re.compile(
    r"export\s+interface\s+([A-Z][A-Za-z0-9_]*)\s*\{([^}]*)\}", re.MULTILINE
)
_TS_FIELD_RE = re.compile(r"^\s+([a-z_][a-z0-9_]*)[?:]\s", re.MULTILINE)

# Pydantic class -> TS interface name (most are 1:1; explicit mappings stay
# here for the few that intentionally differ). Pydantic-only structs that
# the UI doesn't consume can be added to _SKIP_CLASSES.
_CLASS_NAME_MAP: dict[str, str] = {}
# Pydantic classes the UI does not consume (server-internal validation models,
# request/response wrappers without UI surface).
_SKIP_CLASSES: set[str] = {
    "OverrideRequest",
    "OverrideResponse",
    "BatchSubmitRequest",
    "BatchStatusResponse",
}


def _pydantic_class_fields() -> dict[str, set[str]]:
    """Return {ClassName: {field_name, ...}} across all wire files."""
    out: dict[str, set[str]] = {}
    for p in PYDANTIC_FILES:
        source = p.read_text()
        # Slice the source by class start positions and capture each block's
        # 4-space-indented field declarations.
        matches = list(_CLASS_RE.finditer(source))
        for i, m in enumerate(matches):
            cls = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
            body = source[start:end]
            out[cls] = set(_FIELD_RE.findall(body))
    return out


def _ts_interface_fields() -> dict[str, set[str]]:
    """Return {InterfaceName: {field_name, ...}} from envelopes.ts."""
    ts = TS_PATH.read_text()
    return {
        m.group(1): set(_TS_FIELD_RE.findall(m.group(2))) for m in _TS_INTERFACE_RE.finditer(ts)
    }


def _pydantic_fields() -> set[str]:
    """Flat set of every field across every Pydantic class — used by the
    global canary."""
    out: set[str] = set()
    for fields in _pydantic_class_fields().values():
        out |= fields
    return out


def test_typescript_envelopes_file_exists() -> None:
    assert TS_PATH.exists(), f"missing {TS_PATH}"


def test_typescript_envelopes_mirror_pydantic_fields() -> None:
    """Global canary — catches outright renames."""
    ts = TS_PATH.read_text()
    missing: list[str] = []
    for field in sorted(_pydantic_fields()):
        if field not in ts:
            missing.append(field)
    assert not missing, f"TypeScript envelope types missing fields: {missing}"


def test_typescript_interfaces_match_pydantic_classes_per_field() -> None:
    """Per-class canary — every consumed Pydantic class has a TS interface
    with the same name and the same field set. Catches "field added to class
    B but TS only has it on class A" drift the global canary masks."""
    py_classes = _pydantic_class_fields()
    ts_interfaces = _ts_interface_fields()
    drift: list[str] = []
    for cls, py_fields in sorted(py_classes.items()):
        if cls in _SKIP_CLASSES:
            continue
        ts_name = _CLASS_NAME_MAP.get(cls, cls)
        if ts_name not in ts_interfaces:
            drift.append(f"missing TS interface for Pydantic class {cls}")
            continue
        ts_fields = ts_interfaces[ts_name]
        only_in_py = py_fields - ts_fields
        if only_in_py:
            drift.append(f"{cls}: TS interface {ts_name} missing fields {sorted(only_in_py)}")
    assert not drift, "wire-type drift:\n  " + "\n  ".join(drift)
