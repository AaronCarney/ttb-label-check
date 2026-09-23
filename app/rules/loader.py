"""YamlRuleLoader — fail-closed startup loader for the YAML rule pack.

Walks ``rules_root`` recursively. On any of the 10 cross-check violations,
collects the violation list and raises ``RuleLoaderError`` with a single
formatted message containing every violation. The engine startup hook
re-raises so ``uv run task demo`` exits non-zero with the violation list.

Cross-checks:
  1. YAML parse error.
  2. Top-level mapping with rule_pack / rule_pack_version / rules keys.
  3. rule_pack_version is semver and inside engine-supported range.
  4. Each rule entry parses against RuleDefinition.
  5. rule_id is globally unique.
  6. validator name is in VALIDATOR_REGISTRY.
  7. reason_code matches grammar AND is in reason_codes.yaml.
  8. asset.path exists and sha256 matches asset.sha256_pin.
  9. test_fixtures non-empty.
 10. decision_table_ref points at an existing decision-table YAML.

**Every caller must force-import the validators first.** The cross-check #6
registry gate refuses to start unless every ``RuleDefinition.validator`` name is
in ``VALIDATOR_REGISTRY``, which is populated only on validator-module import.
``app/rules/__init__.py`` and the ``python -m app.rules`` CLI both walk
``app.rules._validators`` with ``pkgutil.iter_modules`` to force-import every
module before ``YamlRuleLoader().load()`` runs, and the FastAPI startup path
goes through the same construction point. Explicit per-module imports are
brittle when a new validator lands; without the walk, startup fail-closes with
N "unknown validator" violations even though the unit tests pass.

**Versioning semantics.** ``RuleSet.version`` is sourced from
``rules/reason_codes.yaml``: the registry is the rule pack's manifest, and there
is no separate manifest file. Per-pack semver lives on
``EngineMeta.rule_pack_version`` for each emitted ``ValidationResult``. If a
wine-only pack bump (e.g. ``wine.yaml`` 0.1.0 → 0.2.0) ever needs to surface at
the RuleSet level without bumping the registry, introduce a separate
``rules/manifest.yaml`` and source ``RuleSet.version`` from it. ``version`` is
semver, pinned to the engine-supported range; registry version and pack
aggregate are not distinguished, and the difference is operationally
insignificant.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.rules._validators import VALIDATOR_REGISTRY
from app.schemas.rejection import REASON_CODE_GRAMMAR
from app.schemas.rules import (
    AssetRef,
    DecisionTable,
    ReasonCodeEntry,
    RuleDefinition,
    RuleSet,
)

# The rule pack's gate and the schema layer's constructor gate are one gate, so
# they are one pattern. They were two identical copies, and two copies of a rule
# is one drift away from a code the loader admits and the schema layer refuses.
_REASON_CODE_RE = REASON_CODE_GRAMMAR

# `\Z` rather than `$`, for the reason given beside REASON_CODE_GRAMMAR. This one
# guards `rules/reason_codes.yaml`'s `version:`, which becomes
# `RuleSet.version` and so `audit_trail.rule_set_version` and part of the result
# cache's key — a version string with an invisible character in it is a second
# name for one rule set.
_SEMVER_RE = re.compile(r"\A\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")


class RuleLoaderError(RuntimeError):
    """Fatal: engine must not start."""


@dataclass
class _LoadAccumulator:
    rules: list[RuleDefinition] = field(default_factory=list)
    seen_ids: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)
    decision_tables: dict[str, DecisionTable] = field(default_factory=dict)


@dataclass
class YamlRuleLoader:
    engine_supported_pack_range: tuple[str, str] = ("0.1.0", "0.2.0")
    rules_root_for_assets: Path | None = (
        None  # asset paths resolve relative to this; defaults to rules_root.parent
    )

    def load(self, rules_root: Path) -> RuleSet:
        acc = _LoadAccumulator()
        registry_version, registry = self._load_registry(rules_root, acc)
        self._load_decision_tables(rules_root, acc)
        rule_files = sorted(
            p
            for p in rules_root.rglob("*.yaml")
            if p.name != "reason_codes.yaml" and "tables" not in p.relative_to(rules_root).parts
        )
        for path in rule_files:
            self._load_rule_file(path, registry, acc)
        if acc.errors:
            raise RuleLoaderError(
                f"RuleLoader refused to start: {len(acc.errors)} violation(s):\n  - "
                + "\n  - ".join(acc.errors)
            )
        assets = self._load_assets(acc.rules, rules_root, acc)
        if acc.errors:
            raise RuleLoaderError(
                f"RuleLoader refused to start (asset stage): {len(acc.errors)} violation(s):\n  - "
                + "\n  - ".join(acc.errors)
            )
        # RuleSet.version comes from rules/reason_codes.yaml (the registry IS
        # the rule pack's manifest — there is no separate manifest.yaml). Effective
        # date is the latest among loaded rules so the RuleSet reports a date
        # consistent with what's actually shipped.
        effective_date = max(
            (rd.effective_date for rd in acc.rules),
            default="2026-09-09",
        )
        return RuleSet(
            version=registry_version,
            effective_date=effective_date,
            rules=tuple(sorted(acc.rules, key=lambda r: r.rule_id)),
            reason_codes=registry,
            assets=assets,
            decision_tables=acc.decision_tables,
        )

    # ------------------------------------------------------------------

    def _load_registry(
        self, root: Path, acc: _LoadAccumulator
    ) -> tuple[str, dict[str, ReasonCodeEntry]]:
        path = root / "reason_codes.yaml"
        if not path.exists():
            acc.errors.append(f"{path}: reason_codes.yaml not found")
            return "0.0.0", {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            acc.errors.append(f"{path}: YAML parse error: {e}")
            return "0.0.0", {}
        data = data or {}
        version = str(data.get("version", "0.0.0"))
        if not _SEMVER_RE.match(version):
            acc.errors.append(f"{path}: registry version {version!r} is not semver")
        codes = data.get("codes", {})
        out: dict[str, ReasonCodeEntry] = {}
        for code, entry in codes.items():
            if not _REASON_CODE_RE.match(code):
                acc.errors.append(f"{path}: reason_code {code!r} fails grammar")
                continue
            try:
                out[code] = ReasonCodeEntry(
                    description=entry["description"],
                    cfr_anchors=tuple(entry.get("cfr_anchors", [])),
                    severity=entry["severity"],
                    lean=entry.get("lean", "fail"),
                )
            except (KeyError, ValidationError) as e:
                acc.errors.append(f"{path}/{code}: invalid registry entry: {e}")
        return version, out

    def _load_decision_tables(self, root: Path, acc: _LoadAccumulator) -> None:
        tables_dir = root / "tables"
        if not tables_dir.exists():
            return
        for tpath in sorted(tables_dir.rglob("*.yaml")):
            try:
                data = yaml.safe_load(tpath.read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                acc.errors.append(f"{tpath}: YAML parse error: {e}")
                continue
            try:
                dt = DecisionTable(
                    interpolation=data.get("interpolation", "none"),
                    entries=tuple(data.get("entries", [])),
                )
            except ValidationError as e:
                acc.errors.append(f"{tpath}: invalid decision table: {e}")
                continue
            acc.decision_tables[tpath.stem] = dt

    def _load_rule_file(
        self, path: Path, registry: dict[str, ReasonCodeEntry], acc: _LoadAccumulator
    ) -> None:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            acc.errors.append(f"{path}: YAML parse error: {e}")
            return
        if not isinstance(raw, dict):
            acc.errors.append(f"{path}: top level must be a mapping")
            return
        pack = raw.get("rule_pack")
        pack_ver = raw.get("rule_pack_version")
        rules = raw.get("rules")
        if not isinstance(pack, str) or not pack:
            acc.errors.append(f"{path}: missing or empty rule_pack")
        if not isinstance(pack_ver, str) or not _SEMVER_RE.match(pack_ver or ""):
            acc.errors.append(f"{path}: rule_pack_version must be semver, got {pack_ver!r}")
            return
        lo, hi = self.engine_supported_pack_range
        if not (lo <= pack_ver < hi):
            acc.errors.append(
                f"{path}: rule_pack_version {pack_ver!r} outside engine-supported range [{lo}, "
                f"{hi})"
            )
            return
        if not isinstance(rules, list):
            acc.errors.append(f"{path}: rules must be a list")
            return
        for entry in rules:
            if not isinstance(entry, dict):
                acc.errors.append(f"{path}: rule entry not a mapping: {entry!r}")
                continue
            entry = {**entry, "rule_pack": pack, "rule_pack_version": pack_ver}
            try:
                rd = RuleDefinition.model_validate(entry)
            except ValidationError as e:
                acc.errors.append(f"{path}/{entry.get('rule_id', '?')}: schema invalid: {e}")
                continue
            if rd.rule_id in acc.seen_ids:
                acc.errors.append(f"{path}: duplicate rule_id {rd.rule_id!r}")
            acc.seen_ids.add(rd.rule_id)
            if rd.validator not in VALIDATOR_REGISTRY:
                acc.errors.append(f"{path}/{rd.rule_id}: unknown validator {rd.validator!r}")
            if rd.reason_code not in registry:
                acc.errors.append(
                    f"{path}/{rd.rule_id}: reason_code {rd.reason_code!r} not in registry"
                )
            # A rule's parameters name the codes it emits on its other
            # branches — the borderline brand match, the quantity with no
            # number to compare. Those codes carry the sentence the reviewer
            # reads, so one that is absent from the registry ships a finding
            # with no explanation. Fail at startup instead.
            for key, value in rd.parameters.items():
                if key.endswith("reason_code") and isinstance(value, str) and value not in registry:
                    acc.errors.append(
                        f"{path}/{rd.rule_id}: parameter {key} {value!r} not in registry"
                    )
            if not rd.test_fixtures:
                acc.errors.append(f"{path}/{rd.rule_id}: test_fixtures must be non-empty")
            if rd.decision_table_ref:
                key = rd.decision_table_ref
                if "/" in key:
                    key = key.rsplit("/", 1)[1].rsplit(".", 1)[0]
                if key not in acc.decision_tables:
                    acc.errors.append(
                        f"{path}/{rd.rule_id}: decision_table_ref {rd.decision_table_ref!r} not "
                        f"found"
                    )
            acc.rules.append(rd)

    def _load_assets(
        self,
        rules: Iterable[RuleDefinition],
        rules_root: Path,
        acc: _LoadAccumulator,
    ) -> dict[str, AssetRef]:
        # Lazy-imported to avoid a top-level loader→_validators coupling. The
        # registry itself is populated by the caller — the CLI, a test, or the
        # FastAPI startup path — before load() runs at all; see this module's
        # docstring. By the time _load_assets fires, every rule
        # has already passed cross-check #6, so verbatim_hash is guaranteed
        # to be importable.
        from app.rules._validators.verbatim_hash import (
            DEFAULT_NORMALIZATION_OPS,
            canonicalize_text,
        )

        anchor = self.rules_root_for_assets or rules_root.parent
        out: dict[str, AssetRef] = {}
        for rd in rules:
            if not rd.asset:
                continue
            ap = rd.asset.get("path")
            pin = rd.asset.get("sha256_pin")
            ops = rd.asset.get("normalization", None)
            if not ap or not pin:
                acc.errors.append(f"{rd.rule_id}: asset must declare path + sha256_pin")
                continue
            full = (anchor / ap).resolve()
            if not full.exists():
                acc.errors.append(f"{rd.rule_id}: asset file not found: {full}")
                continue
            # When the asset declares a normalization op list, hash the
            # CANONICALIZED form — that is what the asset-hash cross-check
            # compares. An empty list ([]) explicitly opts out and hashes raw
            # bytes (used by tmp_path fixtures in the fail-closed loader tests).
            # Omitted (None) defaults to the standard pipeline, so a shipped
            # asset is never silently broken by a stray trailing newline.
            if ops is None:
                ops = list(DEFAULT_NORMALIZATION_OPS)
            if ops:
                try:
                    text = full.read_text(encoding="utf-8")
                except UnicodeDecodeError as e:
                    acc.errors.append(f"{rd.rule_id}: asset is not utf-8: {e}")
                    continue
                try:
                    normalized = canonicalize_text(text, ops=ops)
                except ValueError as e:
                    acc.errors.append(f"{rd.rule_id}: {e}")
                    continue
                actual = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            else:
                actual = hashlib.sha256(full.read_bytes()).hexdigest()
            if actual != pin:
                acc.errors.append(f"{rd.rule_id}: asset hash drift; pinned={pin} actual={actual}")
                continue
            key = ap.split("/")[-1].rsplit(".", 1)[0]
            out[key] = AssetRef(path=ap, sha256=pin)
        return out


def _cli_entry() -> int:
    from app.rules.__main__ import main

    return main()


if __name__ == "__main__":
    import sys

    sys.exit(_cli_entry())
