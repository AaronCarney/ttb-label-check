"""verbatim_hash compares the canonicalized observed text against the sha256
recorded in ctx.assets[<key>]. The asset key comes from rule.parameters['asset_key'].
Used by the rule that pins the health warning's wording word for word.
"""
from __future__ import annotations

import hashlib

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.verbatim_hash import verbatim_hash  # noqa: F401
from app.schemas.rejection import Outcome
from app.schemas.rules import AssetRef, MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule


CANONICAL = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects. (2) "
    "Consumption of alcoholic beverages impairs your ability to drive a car or operate "
    "machinery, and may cause health problems."
)
SHA = hashlib.sha256(CANONICAL.encode("utf-8")).hexdigest()


def _rule():
    return make_rule(
        rule_id="common.warning.verbatim",
        cfr_citation="27 CFR §16.21",
        validator="verbatim_hash",
        reason_code="WARNING.VERBATIM.MISMATCH",
        match_policy=MatchPolicy.VERBATIM_HASH,
        parameters={"asset_key": "govt_warning_16_21"},
    )


def _ctx():
    return make_context(
        assets={"govt_warning_16_21": AssetRef(path="assets/warnings/govt_warning_16_21.txt", sha256=SHA)},
    )


def test_verbatim_hash_pass_when_match() -> None:
    obs = make_obs(field_id="warning_block", value=CANONICAL)
    res = verbatim_hash(obs, make_expected(field_id="warning_block"), _rule(), _ctx())
    assert res.outcome is Outcome.PASS


def test_verbatim_hash_fail_when_paraphrase() -> None:
    obs = make_obs(field_id="warning_block", value=CANONICAL.replace("birth defects", "birth complications"))
    res = verbatim_hash(obs, make_expected(field_id="warning_block"), _rule(), _ctx())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.VERBATIM.MISMATCH"


def test_verbatim_hash_registered() -> None:
    assert "verbatim_hash" in VALIDATOR_REGISTRY
