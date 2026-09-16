"""Equality-style validators. Two registered names:

  equality_match    — single-value exact / case-insensitive / normalized
  enumerated_match  — lookup against `rule.parameters['allowed_values']`,
                      either whole-reading (`match_mode: exact`, the default)
                      or designation-includes (`match_mode:
                      contains_designation`)

Both read through `project_reading`, because the reader returns a payload dict
per field and comparing its repr matches nothing.

This file carries no regulation citations; they live in the YAML rule pack.

Shared helpers (`_build_meta`, `_conf`) live in `_helpers.py` so every
validator file can import them without depending on this module's load
order. `_normalize` stays here because it is genuinely equality-internal.
"""
from __future__ import annotations

import unicodedata

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import _build_meta, _conf, project_reading
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, ValidationResult
from app.schemas.rules import MatchPolicy, RuleDefinition


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip().casefold()


def _contains_designation(observed: str, allowed: str) -> bool:
    """True when `allowed` appears in `observed` as a run of whole words.

    A class-and-type designation on a real label carries qualifiers the
    regulation permits around the class or type itself: "KENTUCKY STRAIGHT
    BOURBON WHISKEY" is the bourbon whisky standard of identity with a state
    of origin and "straight" in front of it. An allow-list of bare standards
    can only be checked against such a label by asking whether the label's
    designation includes one. The citation stays in the rule pack, where the
    allow-list itself lives.

    Whole words, not substrings: "gin" must not match inside "Virginia".
    """
    haystack = _normalize(observed).split()
    needle = _normalize(allowed).split()
    if not needle or len(needle) > len(haystack):
        return False
    return any(
        haystack[i:i + len(needle)] == needle
        for i in range(len(haystack) - len(needle) + 1)
    )


@register("equality_match")
def equality_match(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    observed = project_reading(obs) or None
    expected = exp.value
    matched = False
    if observed is not None and expected is not None:
        if rule.match_policy is MatchPolicy.NORMALIZED:
            matched = _normalize(str(observed)) == _normalize(str(expected))
        elif rule.match_policy is MatchPolicy.EXACT:
            matched = str(observed) == str(expected)
        else:
            matched = _normalize(str(observed)) == _normalize(str(expected))
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


@register("enumerated_match")
def enumerated_match(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    allowed: list[str] = rule.parameters.get("allowed_values", [])
    # `exact` (the default) requires the whole reading to be an allowed value.
    # `contains_designation` accepts a reading that includes one, for the
    # class-and-type rules where the label carries permitted qualifiers.
    mode = rule.parameters.get("match_mode", "exact")
    observed = project_reading(obs)
    if not observed:
        matched = False
    elif mode == "contains_designation":
        matched = any(_contains_designation(observed, str(v)) for v in allowed)
    else:
        matched = any(_normalize(observed) == _normalize(str(v)) for v in allowed)
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
