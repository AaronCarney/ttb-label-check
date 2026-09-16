"""Rule-engine package. ``build_rule_engine`` is the single construction point
used by ``app/deps.py::build_evaluator`` and the healthz warm-up.

Forces validator-decorator imports — the loader's registry cross-check reads
``VALIDATOR_REGISTRY``, which is populated by ``@register`` decorators at import
time — before loading the ruleset, so registration is guaranteed regardless of
import order at FastAPI startup.
"""
from __future__ import annotations

import importlib
import pkgutil

from app.config import Settings
from app.rules.loader import YamlRuleLoader
from app.rules.yaml_engine import YamlRuleEngine


def build_rule_engine(settings: Settings) -> YamlRuleEngine:
    """Force-import every validator module, then load the ruleset and wrap it."""
    import app.rules._validators as _v
    for _, modname, _ in pkgutil.iter_modules(_v.__path__):
        importlib.import_module(f"{_v.__name__}.{modname}")
    ruleset = YamlRuleLoader().load(settings.rules_root)
    return YamlRuleEngine(ruleset)
