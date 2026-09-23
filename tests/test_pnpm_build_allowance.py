"""The allowance that lets a clean checkout install the front end is written
where the pnpm we run actually reads it.

pnpm 10 refuses to run a dependency's install script unless the repository names
that dependency, and in CI that refusal is an error rather than a warning. So
without the allowance a clean checkout cannot build the island, and every
browser test errors at setup — which is what pipeline #1 and #3 did.

The allowance was first written as a `pnpm` field in `frontend/package.json`.
pnpm 11 does not read that field at all; it logs *"The 'pnpm' field in
package.json is no longer read by pnpm"* and fails the install anyway. The
setting's home is `pnpm-workspace.yaml`, which pnpm 10.19 and later read too, so
one file serves both. This test exists because the mistake is invisible: the
ignored field looks exactly like a working one, and a machine with a warm
`node_modules` never notices.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


def test_build_allowance_lives_in_pnpm_workspace_yaml() -> None:
    settings = yaml.safe_load((FRONTEND / "pnpm-workspace.yaml").read_text(encoding="utf-8"))
    assert "esbuild" in (settings or {}).get("onlyBuiltDependencies", []), (
        "esbuild's install script is not allowed in frontend/pnpm-workspace.yaml, so a clean "
        "checkout cannot install the front end"
    )


def test_package_json_does_not_hold_settings_pnpm_ignores() -> None:
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    assert "pnpm" not in package, (
        "frontend/package.json carries a `pnpm` settings field, which pnpm 11 ignores silently "
        "— the settings belong in frontend/pnpm-workspace.yaml"
    )


def test_the_pnpm_version_is_pinned() -> None:
    """An unpinned pnpm is whatever is newest on the day it is installed. That
    is how a major version that changed where settings live arrived without
    anyone choosing it. The version is declared once, here, and `scripts/ci.sh`
    refuses to run under any other."""
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    declared = package.get("packageManager", "")
    assert declared.startswith("pnpm@"), (
        "frontend/package.json declares no `packageManager`, so nothing pins pnpm"
    )
    ci = (FRONTEND.parent / "scripts/ci.sh").read_text(encoding="utf-8")
    assert '"packageManager"' in ci and "pnpm --version" in ci, (
        "scripts/ci.sh does not hold pnpm to the declared package manager, so the version "
        "the checks run can drift away from the version this repository was built against"
    )
