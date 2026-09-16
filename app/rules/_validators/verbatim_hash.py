"""verbatim_hash validator: sha256 of canonicalized observed text vs. asset hash.

Canonicalization ops are taken from ``rule.asset or {}`` (a list of
op names, applied in order). When the rule declares no asset block (e.g.,
unit tests using ``make_rule``), the default op list applies. The loader
(``_load_assets``) imports ``canonicalize_text`` from this module and
runs the SAME op pipeline before hashing the asset bytes, so loader and
validator produce identical hashes, which the loader cross-checks.

What the canonical form throws away, and why it throws away exactly that:
the mandated statement fixes the words, the numbers and the punctuation. It
does not fix the letter case of the statement's body — the separate heading
rule is what requires the heading's capitals — and it does not fix how the
printer spaced or broke the lines. So the canonical form folds case, joins a
word a line break split with a hyphen, and takes spacing out of the
comparison altogether. A label that prints "GOVERNMENT WARNING  :" and one
that prints "GOVERNMENT WARNING:(1)" both reach the same canonical string as
the regulation's own text; a label that prints a different word, or ends the
statement with a quotation mark instead of a full stop, does not.

Supported ops: ``nfkc``, ``ascii_quotes``, ``join_line_break_hyphens``,
``collapse_whitespace``, ``tighten_punctuation_spacing``, ``casefold``,
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
    "nfkc",
    "ascii_quotes",
    "join_line_break_hyphens",
    "collapse_whitespace",
    "tighten_punctuation_spacing",
    "casefold",
    "strip_outer_ws",
)

# A hyphen with whitespace after it is a word a line break split. The mandated
# statement contains no hyphen of its own, so nothing legitimate is joined here.
_LINE_BREAK_HYPHEN = re.compile(r"-\s+")

# Whitespace on either side of a punctuation mark. Removing it rather than
# collapsing it is what makes "WARNING  :", "WARNING :" and "WARNING:" one
# string: a label that omits the space is as common as one that doubles it,
# and neither is a difference in the words the regulation mandates.
_SPACE_AROUND_PUNCTUATION = re.compile(r"""\s*([(),.;:!?"'])\s*""")


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
        elif op == "join_line_break_hyphens":
            s = _LINE_BREAK_HYPHEN.sub("", s)
        elif op == "collapse_whitespace":
            s = re.sub(r"\s+", " ", s)
        elif op == "tighten_punctuation_spacing":
            s = _SPACE_AROUND_PUNCTUATION.sub(r"\1", s)
        elif op == "casefold":
            s = s.casefold()
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
