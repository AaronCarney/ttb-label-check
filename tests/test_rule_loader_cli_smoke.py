"""CLI smoke test: `python -m app.rules.loader rules/` exits 0
on the real tree. Mutating the verbatim asset file (write-then-restore) breaks
the loader (exit ≠ 0) — the asset hash drift cross-check fires.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def test_loader_cli_smoke_passes_on_real_tree() -> None:
    code, _, err = _run([sys.executable, "-m", "app.rules.loader", "rules/"])
    assert code == 0, err


def test_loader_cli_smoke_breaks_on_asset_mutation(tmp_path: Path) -> None:
    """Mutating the §16.21 asset breaks the loader (asset hash drift cross-check).

    Mutate a tmp_path COPY of rules/ + assets/, NEVER the tracked working-tree
    file — a killed test (Ctrl-C, OOM, pytest --collect-only abort) would
    otherwise leave the repo with a corrupt asset and the loader broken.
    The loader resolves asset paths relative to ``rules_root.parent``; copying
    both trees under tmp_path preserves that relationship.
    """
    rules_copy = tmp_path / "rules"
    assets_copy = tmp_path / "assets"
    shutil.copytree("rules", rules_copy)
    shutil.copytree("assets", assets_copy)
    asset = assets_copy / "warnings" / "govt_warning_16_21.txt"
    asset.write_text(asset.read_text(encoding="utf-8") + " EXTRA", encoding="utf-8")
    code, _, err = _run([sys.executable, "-m", "app.rules.loader", str(rules_copy)])
    assert code != 0
    assert "asset hash drift" in err.lower()
