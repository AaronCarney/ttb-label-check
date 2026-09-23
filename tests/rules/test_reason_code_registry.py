"""The reason-code registry and the things that name reason codes hold together.

`rules/reason_codes.yaml` is the vocabulary every finding is written in. It has
been edited by hand, one bin at a time, by whichever lane owned the element, and
until this file nothing stated either half of the contract:

1. **Everything that names a code names a real one.** A rule's `reason_code`, a
   rule parameter ending `reason_code`, and a reason code written into
   application Python. The first two are enforced at load time by the loader's
   cross-check 7 (`app/rules/loader.py:213-223`), which refuses to start a pack
   naming an unregistered code — so every test that loads the real `rules/` tree
   has been enforcing it silently. Nothing said so, and the one test that came
   close (`tests/rules/test_warning_rules.py`) covered four codes out of sixty.
   The third had no check at all, and it was wrong: `ENGINE.OVERRIDE.NOT_FOUND`
   at `app/api/overrides.py:115` reached the log without a registry entry.
2. **Every registered code is either emitted or declared unemitted.** This half
   does not hold on its own and a naive orphan check would fail on purpose: the
   registry ships codes no rule and no code path produces, because
   `app/api/overrides.py` accepts any registered code, so each is a sentence a
   reviewer can apply by hand. Those are listed in the registry's
   `reviewer_vocabulary:` block with the reason each stays. The block is checked
   from both sides — an entry naming no registered code fails, and an entry
   naming a code something does emit fails — so it cannot drift out of date
   without this file going red.

A code counts as written into application Python when it appears as a quoted
string whose first segment is a key of the registry's own `bins:`. Anchoring on
the declared bins is what keeps an unrelated dotted uppercase literal from
reading as a reason code; `tests/rules/test_reason_codes_yaml.py` checks the
other side of that, that every registered code sits in a declared bin.

Every check below is a plain function over data, and each has a case underneath
it that feeds it a planted defect and asserts it is caught. A guard that has only
ever seen a passing file is not known to work.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace

import yaml

from app.rules.loader import YamlRuleLoader
from app.rules.yaml_engine import read_uncertain_code
from app.schemas.rejection import Severity
from tests.rules.fixtures import load_all_validators

# The loader refuses a pack naming a validator the registry has not got, and a
# validator registers on import. Register them all here, as the running app
# does, so this file loads the real pack whether it runs alone or in a suite.
load_all_validators()

REGISTRY = Path("rules/reason_codes.yaml")
RULES_ROOT = Path("rules")
SOURCE_ROOTS = ("app", "eval")

# A quoted reason code in Python source: "ENGINE.OVERRIDE.NOT_FOUND".
LITERAL = re.compile(r'"([A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*){2,3})"')


# --------------------------------------------------------------------------
# Reading the tree
# --------------------------------------------------------------------------


def _registry() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}


def _ruleset():
    return YamlRuleLoader().load(RULES_ROOT)


def _source_files() -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files", *SOURCE_ROOTS], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return [Path(p) for p in listing if p.endswith(".py")]


# --------------------------------------------------------------------------
# Who names what — each returns code -> the places that name it
# --------------------------------------------------------------------------


def rule_reason_codes(ruleset) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for rule in ruleset.rules:
        out.setdefault(rule.reason_code, []).append(rule.rule_id)
    return out


def rule_parameter_reason_codes(ruleset) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for rule in ruleset.rules:
        for key, value in rule.parameters.items():
            if key.endswith("reason_code") and isinstance(value, str):
                out.setdefault(value, []).append(f"{rule.rule_id}.{key}")
    return out


def source_reason_codes(bins: Iterable[str], files: Iterable[Path]) -> dict[str, list[str]]:
    declared_bins = set(bins)
    out: dict[str, list[str]] = {}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for code in LITERAL.findall(text):
            if code.split(".")[0] in declared_bins:
                out.setdefault(code, []).append(str(path))
    return out


# --------------------------------------------------------------------------
# The checks
# --------------------------------------------------------------------------


def unregistered(named: dict[str, list[str]], registered: Iterable[str]) -> dict[str, list[str]]:
    """Codes something names that the registry does not carry."""
    known = set(registered)
    return {code: where for code, where in named.items() if code not in known}


def undescribed(named: Iterable[str], codes: dict[str, dict]) -> list[str]:
    """Registered codes with no description — a finding with no sentence in it."""
    return sorted(
        code
        for code in named
        if code in codes and not str(codes[code].get("description", "")).strip()
    )


def unreachable(
    registered: Iterable[str], emitted: Iterable[str], declared: Iterable[str]
) -> list[str]:
    """Registered codes nothing emits and `reviewer_vocabulary` does not claim."""
    return sorted(set(registered) - set(emitted) - set(declared))


def stale_declarations(declared: Iterable[str], registered: Iterable[str]) -> list[str]:
    """`reviewer_vocabulary` entries naming a code the registry has not got."""
    return sorted(set(declared) - set(registered))


def redundant_declarations(declared: Iterable[str], emitted: Iterable[str]) -> list[str]:
    """`reviewer_vocabulary` entries for codes something does emit."""
    return sorted(set(declared) & set(emitted))


def reasonless_declarations(vocabulary: dict[str, object]) -> list[str]:
    return sorted(
        code
        for code, reason in vocabulary.items()
        if not isinstance(reason, str) or not reason.strip()
    )


# --------------------------------------------------------------------------
# Against the tree as it stands
# --------------------------------------------------------------------------


def test_the_registry_carries_the_three_blocks_this_file_checks() -> None:
    data = _registry()
    assert data.get("bins"), "no bins block — the source scan has nothing to anchor on"
    assert data.get("codes"), "no codes block"
    assert isinstance(data.get("reviewer_vocabulary"), dict), (
        "no reviewer_vocabulary block; a registry with no unemitted codes should "
        "carry an empty mapping rather than omit the key, so its absence is a change "
        "somebody made rather than a file that never had one"
    )


def test_every_rule_reason_code_is_registered() -> None:
    """Generalises tests/rules/test_warning_rules.py's four-code check over the pack."""
    codes = _registry()["codes"]
    missing = unregistered(rule_reason_codes(_ruleset()), codes)
    assert not missing, f"rules naming unregistered reason codes: {missing}"


def test_every_rule_reason_code_carries_a_description() -> None:
    codes = _registry()["codes"]
    blank = undescribed(rule_reason_codes(_ruleset()), codes)
    assert not blank, f"rules emitting codes with no description: {blank}"


def test_every_rule_parameter_reason_code_is_registered() -> None:
    """A rule's parameters name the codes it emits on its other branches."""
    codes = _registry()["codes"]
    named = rule_parameter_reason_codes(_ruleset())
    assert named, "no parameter reason codes found — the parameter shape changed"
    missing = unregistered(named, codes)
    assert not missing, f"rule parameters naming unregistered reason codes: {missing}"


def test_every_reason_code_in_application_source_is_registered() -> None:
    data = _registry()
    named = source_reason_codes(data["bins"], _source_files())
    assert len(named) >= 15, (
        f"only {len(named)} reason codes found in {SOURCE_ROOTS} — the scan is not "
        "reading the source it thinks it is"
    )
    missing = unregistered(named, data["codes"])
    assert not missing, f"application source naming unregistered reason codes: {missing}"


def test_every_registered_code_is_emitted_or_declared() -> None:
    data = _registry()
    ruleset = _ruleset()
    emitted = (
        set(rule_reason_codes(ruleset))
        | set(rule_parameter_reason_codes(ruleset))
        | set(source_reason_codes(data["bins"], _source_files()))
        # The engine builds the confidence floor's code from each rejecting
        # rule's own, so none is written out as a literal.
        | {read_uncertain_code(r) for r in ruleset.rules if r.severity is Severity.REJECT}
    )
    orphans = unreachable(data["codes"], emitted, data["reviewer_vocabulary"])
    assert not orphans, (
        "registered reason codes that nothing emits and reviewer_vocabulary does "
        f"not declare: {orphans} — either something should emit them, or they belong "
        "in reviewer_vocabulary with the reason they stay"
    )


def test_reviewer_vocabulary_names_only_registered_codes() -> None:
    data = _registry()
    stale = stale_declarations(data["reviewer_vocabulary"], data["codes"])
    assert not stale, f"reviewer_vocabulary names codes the registry has not got: {stale}"


def test_reviewer_vocabulary_declares_no_emitted_code() -> None:
    data = _registry()
    ruleset = _ruleset()
    emitted = (
        set(rule_reason_codes(ruleset))
        | set(rule_parameter_reason_codes(ruleset))
        | set(source_reason_codes(data["bins"], _source_files()))
    )
    redundant = redundant_declarations(data["reviewer_vocabulary"], emitted)
    assert not redundant, (
        f"reviewer_vocabulary claims nothing emits these, but something does: {redundant}"
    )


def test_every_reviewer_vocabulary_entry_carries_a_reason() -> None:
    reasonless = reasonless_declarations(_registry()["reviewer_vocabulary"])
    assert not reasonless, f"reviewer_vocabulary entries with no reason: {reasonless}"


# --------------------------------------------------------------------------
# Against planted defects — one per check above
# --------------------------------------------------------------------------


def _rule(rule_id: str, reason_code: str, **parameters):
    """The three attributes the helpers above read off a rule."""
    return SimpleNamespace(rule_id=rule_id, reason_code=reason_code, parameters=parameters)


def _pack(*rules):
    return SimpleNamespace(rules=rules)


REGISTERED = {"BRAND.PRESENCE.MISSING": {"description": "Brand name field absent."}}


def test_catches_a_rule_naming_an_unregistered_code() -> None:
    pack = _pack(
        _rule("wine.brand.present", "BRAND.PRESENCE.MISSING"),
        _rule("wine.brand.typo", "BRAND.PRESENCE.ABSENT"),
    )
    assert unregistered(rule_reason_codes(pack), REGISTERED) == {
        "BRAND.PRESENCE.ABSENT": ["wine.brand.typo"]
    }


def test_catches_a_registered_code_with_no_description() -> None:
    codes = {"BRAND.PRESENCE.MISSING": {"description": "   "}}
    pack = _pack(_rule("wine.brand.present", "BRAND.PRESENCE.MISSING"))
    assert undescribed(rule_reason_codes(pack), codes) == ["BRAND.PRESENCE.MISSING"]


def test_catches_a_parameter_naming_an_unregistered_code() -> None:
    pack = _pack(
        _rule(
            "wine.brand.matches",
            "BRAND.PRESENCE.MISSING",
            borderline_reason_code="BRAND.NAME.UNREGISTERED",
            threshold=0.9,
        )
    )
    named = rule_parameter_reason_codes(pack)
    assert named == {"BRAND.NAME.UNREGISTERED": ["wine.brand.matches.borderline_reason_code"]}
    assert unregistered(named, REGISTERED) == named


def test_catches_an_unregistered_code_in_source(tmp_path: Path) -> None:
    planted = tmp_path / "handler.py"
    planted.write_text(
        'log.warning("nope", extra={"reason_code": "ENGINE.OVERRIDE.UNREGISTERED"})\n'
        'CONTENT = "application/json"\n',
        encoding="utf-8",
    )
    named = source_reason_codes({"ENGINE"}, [planted])
    assert named == {"ENGINE.OVERRIDE.UNREGISTERED": [str(planted)]}
    assert unregistered(named, REGISTERED) == named


def test_the_source_scan_ignores_literals_outside_a_declared_bin(tmp_path: Path) -> None:
    """Why the scan is anchored on bins: without it this is a reason code."""
    planted = tmp_path / "handler.py"
    planted.write_text('MODE = "SOME.OTHER.CONSTANT"\n', encoding="utf-8")
    assert source_reason_codes({"ENGINE", "BRAND"}, [planted]) == {}


def test_catches_a_registered_code_nothing_emits() -> None:
    registered = ["BRAND.PRESENCE.MISSING", "BRAND.NAME.UNUSED"]
    assert unreachable(registered, ["BRAND.PRESENCE.MISSING"], []) == ["BRAND.NAME.UNUSED"]
    # ...and stays quiet once it is declared.
    assert unreachable(registered, ["BRAND.PRESENCE.MISSING"], ["BRAND.NAME.UNUSED"]) == []


def test_catches_a_stale_vocabulary_entry() -> None:
    assert stale_declarations(["BRAND.NAME.DELETED"], REGISTERED) == ["BRAND.NAME.DELETED"]


def test_catches_a_redundant_vocabulary_entry() -> None:
    assert redundant_declarations(["BRAND.PRESENCE.MISSING"], ["BRAND.PRESENCE.MISSING"]) == [
        "BRAND.PRESENCE.MISSING"
    ]


def test_catches_a_vocabulary_entry_with_no_reason() -> None:
    assert reasonless_declarations({"A.B.C": "kept because", "D.E.F": "  ", "G.H.I": None}) == [
        "D.E.F",
        "G.H.I",
    ]
