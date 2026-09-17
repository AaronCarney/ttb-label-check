"""CLI: python -m app.rules.loader <rules_dir>

Loads the rule pack and prints a one-line manifest. Exits non-zero with the
violation list on any cross-check failure.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m app.rules.loader <rules_dir>", file=sys.stderr)
        return 2
    # Force-import every validator so the registry is populated.
    import importlib
    import pkgutil

    pkg = importlib.import_module("app.rules._validators")
    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"app.rules._validators.{mod.name}")

    from app.rules.loader import RuleLoaderError, YamlRuleLoader

    try:
        rs = YamlRuleLoader().load(Path(sys.argv[1]))
    except RuleLoaderError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(
        f"OK: {len(rs.rules)} rules; {len(rs.reason_codes)} reason codes; {len(rs.assets)} assets"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
