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
word a line break split with a hyphen, and takes every space out. A label that
prints "GOVERNMENT WARNING  :", one that prints "GOVERNMENT WARNING:(1)" and a
reading that runs "IMPAIRSYOUR" together all reach the same canonical string
as the regulation's own text; a label that prints a different word or letter,
or ends the statement with a quotation mark instead of a full stop, does not.

Spaces are removed rather than collapsed because label type is justified,
which closes some word gaps and opens others, and because the reader loses a
narrow gap as readily as a printer closes one. Removing them cannot make a
different statement equal the mandated one: the letters, digits and
punctuation still have to match in order.

Supported ops: ``nfkc``, ``join_line_break_hyphens``, ``drop_whitespace``,
``casefold``. There is no op for quotation marks: the mandated statement
contains none, so a label that prints one, curly or straight, differs from it
either way.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Sequence

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    not_read_result,
    project_reading,
    unlocated,
    unlocated_is_absent,
    verdict_result,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import ValidationResult
from app.schemas.rules import RuleDefinition

DEFAULT_NORMALIZATION_OPS: tuple[str, ...] = (
    "nfkc",
    "join_line_break_hyphens",
    "drop_whitespace",
    "casefold",
)

# A hyphen with whitespace after it is a word a line break split. The mandated
# statement contains no hyphen of its own, so nothing legitimate is joined here.
_LINE_BREAK_HYPHEN = re.compile(r"-\s+")


def canonicalize_text(s: str, ops: Sequence[str] = DEFAULT_NORMALIZATION_OPS) -> str:
    """Apply normalization ops in declaration order. Loader and validator MUST
    use this same helper so verbatim hashes match.
    Raises ValueError on an unknown op name (fail-closed).
    """
    for op in ops:
        if op == "nfkc":
            s = unicodedata.normalize("NFKC", s)
        elif op == "join_line_break_hyphens":
            s = _LINE_BREAK_HYPHEN.sub("", s)
        elif op == "drop_whitespace":
            s = re.sub(r"\s+", "", s)
        elif op == "casefold":
            s = s.casefold()
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
    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`.
    if unlocated(obs) and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx, element="the government warning")

    key = rule.parameters.get("asset_key")
    asset = ctx.assets.get(key) if key else None
    ops = (rule.asset or {}).get("normalization", DEFAULT_NORMALIZATION_OPS)
    # The warning body, not the repr of the payload that carries it:
    # `str(obs.observed_value)` on the reader's dict hashes "{'text': …}" and
    # can never equal the hash of the asset text.
    observed = canonicalize_text(project_reading(obs), ops=ops)
    matched = (
        asset is not None and hashlib.sha256(observed.encode("utf-8")).hexdigest() == asset.sha256
    )
    return verdict_result(obs, exp, rule, ctx, ok=matched)
