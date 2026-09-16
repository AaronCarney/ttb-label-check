"""verbatim_hash validator: sha256 of canonicalized observed text vs. asset hash.

Canonicalization ops are taken from ``rule.asset or {}`` (a list of
op names, applied in order). When the rule declares no asset block (e.g.,
unit tests using ``make_rule``), the default op list applies. The loader
(``_load_assets``) imports ``canonicalize_text`` from this module and
runs the SAME op pipeline before hashing the asset bytes, so loader and
validator produce identical hashes, which the loader cross-checks.

Supported ops: ``nfkc``, ``ascii_quotes``, ``collapse_whitespace``,
``strip_outer_ws``.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Sequence

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf, project_reading
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.rules import RuleDefinition


DEFAULT_NORMALIZATION_OPS: tuple[str, ...] = (
    "nfkc", "ascii_quotes", "collapse_whitespace", "strip_outer_ws",
)


def canonicalize_text(s: str, ops: Sequence[str] = DEFAULT_NORMALIZATION_OPS) -> str:
    """Apply normalization ops in declaration order. Loader and validator MUST
    use this same helper so verbatim hashes match.
    Raises ValueError on an unknown op name (fail-closed).
    """
    for op in ops:
        if op == "nfkc":
            s = unicodedata.normalize("NFKC", s)
        elif op == "ascii_quotes":
            s = (s.replace("“", '"').replace("”", '"')
                  .replace("‘", "'").replace("’", "'"))
        elif op == "collapse_whitespace":
            s = re.sub(r"\s+", " ", s)
        elif op == "strip_outer_ws":
            s = s.strip()
        else:
            raise ValueError(f"unknown normalization op: {op!r}")
    return s


@register("verbatim_hash")
def verbatim_hash(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    key = rule.parameters.get("asset_key")
    asset = ctx.assets.get(key) if key else None
    ops = (rule.asset or {}).get("normalization", DEFAULT_NORMALIZATION_OPS)
    # The warning body, not the repr of the payload that carries it:
    # `str(obs.observed_value)` on the reader's dict hashes "{'text': …}" and
    # can never equal the hash of the asset text.
    observed = canonicalize_text(project_reading(obs), ops=ops)
    matched = (
        asset is not None
        and hashlib.sha256(observed.encode("utf-8")).hexdigest() == asset.sha256
    )
    return ValidationResult(
        rule_id=rule.rule_id,
        cfr_citation=rule.cfr_citation,
        beverage_class=obs.beverage_class,
        outcome=Outcome.PASS if matched else Outcome.FAIL,
        severity=rule.severity,
        reason_code=None if matched else rule.reason_code,
        aggregated_confidence=_conf(obs),
        evidence=obs.evidence,
        expected=exp,
        observed=obs,
        engine_meta=_build_meta(rule, ctx),
    )
