"""YamlRuleEngine — the only concrete RuleEngine implementation. The per-rule
timeout is 250 ms, and a validator exception is caught and turned into an error
result so the remaining rules still run.

**Timeout semantics — DECISION DEADLINE, NOT EXECUTION STOP.**
``asyncio.wait_for`` cancels the awaited coroutine, but ``asyncio.to_thread``
runs synchronous code in a thread that cannot be cancelled by the event
loop. A runaway sync validator continues to consume CPU and a thread slot
in the default executor until it returns on its own. The 250 ms budget is
therefore a contract on **the result the engine returns to the caller**
(after which a TIMEOUT result is emitted and rule evaluation continues),
not a hard stop on the validator's CPU time. Implications:

  - Validators MUST be CPU-bounded by construction (every loop must have a
    finite bound; no unbounded retries; no subprocess.call without a
    timeout). The validator-registry test does not enforce this; it
    is a per-validator code-review responsibility.
  - Under load, an unbounded number of stuck threads can accumulate in the
    asyncio default executor. The request-cancellation path SHOULD bound the
    executor and surface saturation as a circuit-breaker state.
  - True hard-stop semantics would require ``concurrent.futures.ProcessPoolExecutor``
    or signal-based interruption. Both add deployment complexity out of all
    proportion to the risk, where the rules are YAML data and no validator does
    anything long-running.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Sequence

from app.rules._validators import VALIDATOR_REGISTRY, ValidatorContext
from app.rules.engine import RuleEngine
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.schemas.rules import RuleSet


PER_RULE_TIMEOUT_S = 0.25

# The two outcomes that assert something about the label, and so are the two
# the rule's confidence floor guards. The rest already say that no comparison
# was reached.
_ASSERTS_A_VERDICT = frozenset({Outcome.PASS, Outcome.FAIL})

# What a rule reports when its reading scored below the rule's own floor.
BELOW_CONFIDENCE_FLOOR = "ENGINE.EVIDENCE.BELOW_CONFIDENCE_FLOOR"

# Three vocabularies name the same label element, and the engine sits between
# all three. The reader emits physical field ids (`brand_name`, `abv`,
# `gov_warning`). The rule pack asks for evidence by semantic name (`brand`,
# `alc_text`, `warning_block`). The applicant fills in the form's own names
# (`alcohol_content`, `government_warning`). Reconciling them is the engine's
# job; keeping them in two separate maps keeps it clear which side each name
# belongs to, because a name in the wrong map fails silently — the rule still
# runs, against nothing.

# Reader field id -> the evidence names the rule pack may ask for.
_RULE_PACK_ALIASES: dict[str, tuple[str, ...]] = {
    "brand_name": ("brand",),
    "abv": ("alc_text",),
    "gov_warning": ("warning_block",),
    "name_address": ("bottler",),
}

# Reader field id -> the names the application declares the same element under.
# Without this, a rule comparing the label against the application compares it
# against an empty default and fails a label that complies.
_APPLICATION_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "abv": ("alcohol_content", "alc_text"),
    "gov_warning": ("government_warning", "warning_block"),
    "name_address": ("name_and_address", "bottler"),
    "country_origin": ("country_of_origin",),
}


def _matches_evidence_required(obs_field_id: str, required: tuple[str, ...]) -> bool:
    """`obs.field_id` directly OR any of its rule-pack aliases satisfies the
    rule's `evidence_required`."""
    if obs_field_id in required:
        return True
    aliases = _RULE_PACK_ALIASES.get(obs_field_id, ())
    return any(a in required for a in aliases)


_log = logging.getLogger(__name__)


class YamlRuleEngine(RuleEngine):
    def __init__(self, ruleset: RuleSet) -> None:
        self._ruleset = ruleset

    def build_validator_context(self, *, started_at_ms: int) -> ValidatorContext:
        rs = self._ruleset
        return ValidatorContext(
            assets=rs.assets,
            decision_tables=rs.decision_tables,
            started_at_ms=started_at_ms,
            engine_version=rs.version,
        )

    async def evaluate(
        self,
        observations: Sequence[FieldObservation],
        expected: Sequence[ExpectedValue],
        context: ValidatorContext,
    ) -> tuple[ValidationResult, ...]:
        results: list[ValidationResult] = []
        exp_by_field: dict[str, ExpectedValue] = {}
        for e in expected:
            # An application value is reachable by its own field name and by
            # any alias the envelope declared for it. First entry wins, so a
            # declared field is never shadowed by another field's alias.
            for key in (e.field_id, *e.aliases):
                exp_by_field.setdefault(key, e)
        for rule in self._ruleset.rules:
            if rule.disabled:
                continue
            applicable_obs = [
                obs for obs in observations
                if obs.beverage_class in rule.applies_to_classes
                and (
                    not rule.evidence_required
                    or _matches_evidence_required(obs.field_id, rule.evidence_required)
                )
            ]
            if not applicable_obs:
                continue
            for obs in applicable_obs:
                exp = self._expected_for(obs.field_id, exp_by_field)
                results.append(await self._run_one(rule, obs, exp, context))
        return tuple(sorted(results, key=lambda r: (r.rule_id, r.observed.field_id if r.observed else "")))

    @staticmethod
    def _expected_for(
        field_id: str, exp_by_field: dict[str, ExpectedValue]
    ) -> ExpectedValue:
        """The application's declared value for a reader field, under whichever
        name the application used. An empty value when the application declared
        nothing for that element."""
        exp = exp_by_field.get(field_id)
        if exp is not None:
            return exp
        for alias in _APPLICATION_FIELD_ALIASES.get(field_id, ()):
            exp = exp_by_field.get(alias)
            if exp is not None:
                return exp
        return ExpectedValue(field_id=field_id)

    def _finish(self, rule, result: ValidationResult, meta: EngineMeta) -> ValidationResult:
        """Every result leaves the engine through here, carrying its timing,
        the rule's confidence floor and the sentence a reviewer reads."""
        result = self._apply_confidence_floor(rule, result)
        return result.model_copy(
            update={"engine_meta": meta, "message": self._explain(result)}
        )

    @staticmethod
    def _apply_confidence_floor(rule, result: ValidationResult) -> ValidationResult:
        """A verdict is only as good as the reading it was measured from.

        Each rule declares the confidence its reading must reach before the
        answer can be relied on (`confidence_floor`). Below it, the rule
        reports that it could not be settled instead of passing or rejecting,
        so a reading the reader is unsure of goes to a reviewer rather than
        rejecting the label as a confident one would.

        The floor applies only where there was a reading to score. A result
        with no evidence — a required statement that is simply absent — scores
        zero because nothing was read, not because the reading was poor, and
        the rule that found it missing is entitled to say so.
        """
        if result.outcome not in _ASSERTS_A_VERDICT or not result.evidence:
            return result
        if result.aggregated_confidence >= rule.confidence_floor:
            return result
        return result.model_copy(update={
            "outcome": Outcome.INSUFFICIENT_EVIDENCE,
            "severity": Severity.WARN,
            "reason_code": BELOW_CONFIDENCE_FLOOR,
        })

    def _explain(self, result: ValidationResult) -> str | None:
        """The finding's explanation, in the rule pack's own words.

        `rules/reason_codes.yaml` gives every reason code a description
        written for a reviewer; this is where it reaches one. A validator that
        wrote its own message keeps it, and a finding with no reason code — a
        plain pass — has nothing to explain.
        """
        if result.message:
            return result.message
        if not result.reason_code:
            return None
        entry = self._ruleset.reason_codes.get(result.reason_code)
        return entry.description if entry is not None else None

    async def _run_one(self, rule, obs, exp, ctx) -> ValidationResult:
        validator = VALIDATOR_REGISTRY.get(rule.validator)
        started_at_ms = int(time.monotonic() * 1000)
        t0 = time.monotonic()

        def _meta(elapsed_ms: int) -> EngineMeta:
            return EngineMeta(
                engine_version=ctx.engine_version,
                rule_pack=rule.rule_pack or "unknown",
                rule_pack_version=rule.rule_pack_version or "0.0.0",
                started_at_ms=started_at_ms,
                elapsed_ms=elapsed_ms,
            )

        if validator is None:
            return self._finish(rule, ValidationResult(
                rule_id=rule.rule_id, cfr_citation=rule.cfr_citation,
                beverage_class=obs.beverage_class, outcome=Outcome.ERROR,
                severity=Severity.REJECT, reason_code="ENGINE.VALIDATOR.NOT_FOUND",
                aggregated_confidence=0.0, evidence=obs.evidence,
                expected=exp, observed=obs, engine_meta=_meta(0),
            ), _meta(0))
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(validator, obs, exp, rule, ctx),
                timeout=PER_RULE_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return self._finish(rule, ValidationResult(
                rule_id=rule.rule_id, cfr_citation=rule.cfr_citation,
                beverage_class=obs.beverage_class, outcome=Outcome.TIMEOUT,
                severity=Severity.WARN, reason_code="ENGINE.VALIDATOR.TIMEOUT",
                aggregated_confidence=0.0, evidence=obs.evidence,
                expected=exp, observed=obs, engine_meta=_meta(elapsed_ms),
            ), _meta(elapsed_ms))
        except Exception:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            _log.exception("validator %r raised", rule.rule_id)
            return self._finish(rule, ValidationResult(
                rule_id=rule.rule_id, cfr_citation=rule.cfr_citation,
                beverage_class=obs.beverage_class, outcome=Outcome.ERROR,
                severity=Severity.REJECT, reason_code="ENGINE.VALIDATOR.EXCEPTION",
                aggregated_confidence=0.0, evidence=obs.evidence,
                expected=exp, observed=obs, engine_meta=_meta(elapsed_ms),
            ), _meta(elapsed_ms))
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return self._finish(rule, result, _meta(elapsed_ms))
