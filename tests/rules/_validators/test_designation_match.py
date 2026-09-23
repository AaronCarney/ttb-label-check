"""designation_match asks whether a label's class-and-type designation names the
same class the application declared, not whether the two read the same.

The two sides never read the same. An application names a class from the
registry's own list, which carries filing shorthand no label shows — "VODKA
80-89 PROOF", "OTHER GIN FB", "COGNAC (BRANDY) FB". A label carries the class
with the qualifiers the regulations permit around it — "AMERICAN DRY GIN",
"BARREL-AGED IMPERIAL STOUT". So the validator works out which recognised
classes each side names and compares those.

Two things can be wrong here and they fail differently, so the tests come in
two parts.

The first part drives the four branches with hand-built parameters, because
that is the only way to reach each one deliberately. It says what the module
does with a given list of classes and a given table.

The second part runs the *shipped* rule packs over the whole approved corpus.
That is the part that catches a rule-pack edit, and it is the one that can be
wrong while every branch test still passes: the branches are reached from
`recognised_classes` and the decision tables, which are data in
`rules/`, and a class dropped from that list turns a pass into a reviewer
question without touching a line of Python. Every one of the 38 labels in
`tests/fixtures/labels/manifest.json` was approved by TTB, so no pairing in it
may be reported as a disagreement - a rejection there is a false rejection by
construction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from app.rules._validators.designation_match import designation_match
from app.schemas.expected import BeverageClass
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import DecisionTable
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST = _REPO / "tests" / "fixtures" / "labels" / "manifest.json"
_TABLES = _REPO / "rules" / "tables"

# beverage_type in the manifest -> the pack that carries the rule for it.
_PACK_FOR: dict[str, tuple[str, BeverageClass]] = {
    "distilled_spirits": ("spirits/spirits.yaml", BeverageClass.SPIRITS),
    "wine": ("wine/wine.yaml", BeverageClass.WINE),
    "malt_beverage": ("malt/malt.yaml", BeverageClass.MALT),
}

_DISAGREE = "CLASS_TYPE.MATCH.APPLICATION_LABEL_DISAGREE"
_NEEDS_REVIEW = "CLASS_TYPE.MATCH.NEEDS_REVIEW"


# --- part one: the four branches ---------------------------------------------


def _rule(
    *,
    recognised: tuple[str, ...] = ("Beer", "Ale", "Lager", "Gin", "Vodka"),
    table_ref: str | None = None,
    severity: Severity = Severity.REJECT,
) -> Any:
    return make_rule(
        rule_id="test.class_type.matches_application",
        cfr_citation="27 CFR §7.63(a)(2)",
        validator="designation_match",
        reason_code=_DISAGREE,
        severity=severity,
        decision_table_ref=table_ref,
        parameters={
            "recognised_classes": list(recognised),
            "disagreement_reason_code": _DISAGREE,
            "needs_review_reason_code": _NEEDS_REVIEW,
        },
    )


def _run(label: str, declared: str, *, rule: Any = None, tables: dict | None = None) -> Any:
    rule = rule if rule is not None else _rule()
    return designation_match(
        make_obs(field_id="class_type", value=label),
        make_expected(field_id="class_type", value=declared),
        rule,
        make_context(decision_tables=tables or {}),
    )


def test_a_designation_the_reader_did_not_find_is_a_reviewers_question() -> None:
    # Not a rejection: an empty reading with no box and no text is the reader
    # saying it did not find the element, which is not the claim that the label
    # lacks one. See `unlocated` in `_helpers.py`.
    result = _run("", "BEER")
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.severity is Severity.WARN
    assert result.reason_code == "LEGIBILITY.FIELD.NOT_READ"


def test_a_label_the_reader_read_but_found_no_designation_on_fails() -> None:
    # The reader located the field and read nothing in it, so the label really
    # does carry no designation. That is a finding against the label itself.
    obs = make_obs(field_id="class_type", value="")
    located = obs.model_copy(
        update={"evidence": (obs.evidence[0].model_copy(update={"bbox": (0, 0, 10, 10)}),)}
    )
    result = designation_match(
        located,
        make_expected(field_id="class_type", value="BEER"),
        _rule(),
        make_context(),
    )
    assert result.outcome is Outcome.FAIL
    assert result.reason_code == _DISAGREE


def test_an_application_declaring_no_class_leaves_nothing_to_compare() -> None:
    # Reporting agreement here would name a check that only ever had one side.
    result = _run("LAGER", "")
    assert result.outcome is Outcome.NOT_APPLICABLE
    assert result.reason_code is None


def test_1_the_declared_designation_inside_the_labels_passes() -> None:
    assert _run("BARREL-AGED IMPERIAL STOUT", "STOUT").outcome is Outcome.PASS


def test_1_the_declared_designation_must_appear_as_whole_words() -> None:
    # "gin" must not match inside "Virginia", or a Virginia wine passes a gin
    # check. Nothing else here names a class, so this is a reviewer's question.
    result = _run("VIRGINIA HIGHLANDS", "GIN")
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE


def test_1_the_registry_packs_several_classes_into_one_string() -> None:
    # The registry writes alternatives with slashes and parentheses. Each part
    # is a designation in its own right, and matching any one of them is
    # agreement: "DESSERT /PORT/SHERRY/(COOKING) WINE" declares four.
    assert _run("PORT", "DESSERT /PORT/SHERRY/(COOKING) WINE").outcome is Outcome.PASS
    assert _run("COOKING WINE", "DESSERT /PORT/SHERRY/(COOKING) WINE").outcome is Outcome.PASS


def test_2_both_naming_the_same_class_passes_whatever_order_the_words_come_in() -> None:
    # A designation interleaves its qualifiers, so class words are looked for
    # anywhere in it rather than as a run: both of these name table wine.
    rule = _rule(recognised=("Wine", "Table Wine"))
    assert _run("RED TABLE WINE", "TABLE RED WINE", rule=rule).outcome is Outcome.PASS


def test_3_a_class_the_table_places_within_the_declared_one_passes() -> None:
    # A registry application routinely declares the bare class BEER where the
    # label designates the style it sells as. Without the table those are two
    # different classes and a compliant label is rejected.
    tables = {"t": DecisionTable(entries=({"class": "Beer", "designations_within": ["Lager"]},))}
    result = _run("LAGER", "BEER", rule=_rule(table_ref="t"), tables=tables)
    assert result.outcome is Outcome.PASS


def test_3_the_table_is_read_in_the_direction_it_is_written() -> None:
    # `malt_designations` is one-way on purpose: the label may be narrower than
    # the class declared, and the reverse - filing for an ale and labelling a
    # beer - tells TTB less than it was told, so it stays a disagreement. The
    # table has to carry the reverse entry itself to permit it, which is what
    # `wine_designations` does for champagne.
    tables = {"t": DecisionTable(entries=({"class": "Beer", "designations_within": ["Lager"]},))}
    result = _run("BEER", "LAGER", rule=_rule(table_ref="t"), tables=tables)
    assert result.outcome is Outcome.FAIL


def test_3_a_missing_decision_table_leaves_the_pairing_unpermitted() -> None:
    # The rule names a table the context has not got. Reading that as agreement
    # would turn a lost file into a silent pass.
    result = _run("LAGER", "BEER", rule=_rule(table_ref="absent"))
    assert result.outcome is Outcome.FAIL


def test_4a_two_different_recognised_classes_is_a_disagreement() -> None:
    result = _run("GIN", "VODKA")
    assert result.outcome is Outcome.FAIL
    assert result.severity is Severity.REJECT
    assert result.reason_code == _DISAGREE


def test_4a_a_line_of_class_names_only_is_a_disagreement() -> None:
    rule = _rule(recognised=("Gin", "London Dry Gin", "Vodka"))
    assert _run("LONDON DRY GIN", "VODKA", rule=rule).outcome is Outcome.FAIL


def test_4a_a_line_carrying_other_words_goes_to_a_reviewer() -> None:
    """The reader's pick is the largest line that names a class, which is a
    guess at which line is the designation. ttb-26240001000454, a keg, had
    its designation misread and a line of its tapping instructions picked:
    "RETAILER OR LOCAL BEER" against an application for ale. A line that is
    nothing but class names is a designation whatever else the label says;
    one carrying other words may not be one, so a reviewer decides."""
    result = _run("RETAILER OR LOCAL BEER", "ALE")
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.severity is Severity.WARN
    assert result.reason_code == _NEEDS_REVIEW
    assert result.message is not None and '"Beer"' in result.message and '"ALE"' in result.message


def test_4a_the_disagreement_carries_the_severity_the_pack_set() -> None:
    # Every pack sets reject today, so this changes no outcome now. It says the
    # pack decides, the way it does on every other branch that reports against
    # the label, so a pack can pilot this rule as a warning.
    result = _run("GIN", "VODKA", rule=_rule(severity=Severity.WARN))
    assert result.outcome is Outcome.FAIL
    assert result.severity is Severity.WARN


def test_4b_a_designation_the_list_does_not_know_goes_to_a_reviewer() -> None:
    # A designation the list has never heard of is no evidence the label is
    # wrong, so this is a question rather than a rejection - and warn, so
    # `app/services/disposition.py` routes it to needs_review and it cannot
    # reject the submission on its own.
    result = _run("SANGIOVESE", "TABLE RED WINE", rule=_rule(recognised=("Wine",)))
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.severity is Severity.WARN
    assert result.reason_code == _NEEDS_REVIEW


def test_4b_one_side_naming_a_class_alone_is_not_a_disagreement() -> None:
    # The label names a recognised class and the application names none the
    # list knows. Nothing here says the two differ, only that one of them could
    # not be placed.
    result = _run("LAGER", "SOMETHING THE LIST HAS NEVER HEARD OF")
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.reason_code == _NEEDS_REVIEW


# --- part two: the shipped packs over the approved corpus ---------------------


def _shipped_rule(pack: str) -> dict[str, Any]:
    doc = yaml.safe_load((_REPO / "rules" / pack).read_text())
    named = [r for r in doc["rules"] if r.get("validator") == "designation_match"]
    assert len(named) == 1, f"{pack} carries {len(named)} designation_match rules"
    return named[0]


def _shipped_table(ref: str) -> DecisionTable:
    doc = yaml.safe_load((_TABLES / f"{ref}.yaml").read_text())
    return DecisionTable(interpolation=doc.get("interpolation", "none"), entries=doc["entries"])


def _corpus() -> list[dict[str, Any]]:
    doc = json.loads(_MANIFEST.read_text())
    return doc if isinstance(doc, list) else doc["labels"]


def _run_shipped(entry: dict[str, Any]) -> Any:
    pack, beverage = _PACK_FOR[entry["beverage_type"]]
    raw = _shipped_rule(pack)
    ref = raw.get("decision_table_ref")
    rule = make_rule(
        rule_id=raw["rule_id"],
        cfr_citation=raw["cfr_citation"],
        validator="designation_match",
        reason_code=raw["reason_code"],
        applies_to_classes=(beverage,),
        parameters=raw.get("parameters", {}),
        decision_table_ref=ref,
    )
    return designation_match(
        make_obs(
            field_id="class_type",
            value=(entry.get("label_observed") or {}).get("class_type") or "",
            beverage_class=beverage,
        ),
        make_expected(
            field_id="class_type",
            value=(entry.get("application") or {}).get("class_type") or "",
        ),
        rule,
        make_context(decision_tables={ref: _shipped_table(ref)} if ref else {}),
    )


def test_the_shipped_packs_reject_none_of_the_approved_corpus() -> None:
    """Every label in the corpus was approved, so a rejection here is a false one.

    This is the check a rule-pack edit has to get past. Dropping "Wine" from
    `recognised_classes`, or a designation from a decision table, turns one of
    these into a disagreement against a label TTB approved.
    """
    rejected = [
        (
            (e.get("application") or {}).get("class_type"),
            (e.get("label_observed") or {}).get("class_type"),
        )
        for e in _corpus()
        if _run_shipped(e).outcome is Outcome.FAIL
    ]
    assert rejected == [], f"approved labels reported as disagreements: {rejected}"


def test_the_corpus_labels_that_name_no_class_go_to_a_reviewer_not_a_rejection() -> None:
    """The wine labels carrying a grape variety instead of a class.

    `wine.class_type.matches_application` says so in its own comment: a label
    reading "SANGIOVESE" or "CHARDONNAY" names no class the list knows, and the
    approved labels record a reviewer's question as the correct outcome. Pinned
    by the designation itself rather than by a count, so a corpus that grows
    keeps this test meaningful.
    """
    unsettled = sorted(
        (e.get("label_observed") or {}).get("class_type") or ""
        for e in _corpus()
        if _run_shipped(e).outcome is Outcome.INSUFFICIENT_EVIDENCE
    )
    assert unsettled == [
        "CHARDONNAY",
        "CHARDONNAY",
        "GEWURZTRAMINER",
        "GEWURZTRAMINER",
        "PINOT NOIR",
        "SANGIOVESE",
    ]


def test_every_designation_a_decision_table_names_can_be_recognised_on_a_label() -> None:
    """Both table files state this, and nothing has been enforcing it.

    The validator works out which classes the label names from
    `recognised_classes` *before* it consults the table. A designation only the
    table knows is therefore never recognised, its entry never fires, and the
    pairing the table exists to permit silently stops happening.
    """
    from app.rules._validators._helpers import normalize_words

    def name(value: object) -> str:
        return " ".join(normalize_words(str(value)))

    for pack, _ in _PACK_FOR.values():
        raw = _shipped_rule(pack)
        ref = raw.get("decision_table_ref")
        if not ref:
            continue
        recognised = {name(c) for c in raw["parameters"]["recognised_classes"]}
        named = set()
        for entry in _shipped_table(ref).entries:
            named.add(name(entry.get("class", "")))
            named.update(name(v) for v in entry.get("designations_within", []))
        assert named <= recognised, (
            f"{ref} names designations {sorted(named - recognised)} that "
            f"{raw['rule_id']} cannot recognise on a label"
        )


def test_a_table_entry_naming_no_class_is_dropped_rather_than_stringified() -> None:
    # `str(None)` is "None", which normalizes to the word "none". An entry with
    # no `class:` line would otherwise enter the map under that name and pair
    # with any label designation carrying the word.
    tables = {
        "t": DecisionTable(
            entries=(
                {"designations_within": ["Lager"]},
                {"class": "Beer", "designations_within": ["Lager"]},
            )
        )
    }
    rule = _rule(recognised=("Beer", "Lager", "None"), table_ref="t")
    assert _run("LAGER", "NONE", rule=rule, tables=tables).outcome is not Outcome.PASS
    # The well-formed entry beside it still works.
    assert _run("LAGER", "BEER", rule=rule, tables=tables).outcome is Outcome.PASS


def test_a_table_entry_listing_no_designations_covers_nothing() -> None:
    # A class line added without its list. The entry covers nothing, which is
    # what it says; it must not crash the evaluation of every other rule.
    tables = {"t": DecisionTable(entries=({"class": "Beer"},))}
    result = _run("LAGER", "BEER", rule=_rule(table_ref="t"), tables=tables)
    assert result.outcome is Outcome.FAIL


def test_no_pack_names_the_same_class_twice() -> None:
    """Both sides are reduced to plain words before anything is compared.

    That fold reads whisky as whiskey, so "Bourbon Whisky" and "Bourbon
    Whiskey" are one entry written twice: the second matches nothing the first
    did not already match, while reading as though it covered a case of its
    own. Three such pairs were in the spirits pack.
    """
    from app.rules._validators._helpers import normalize_words

    for pack, _ in _PACK_FOR.values():
        raw = _shipped_rule(pack)
        listed = [str(c) for c in raw["parameters"]["recognised_classes"]]
        seen: dict[tuple[str, ...], str] = {}
        for entry in listed:
            name = normalize_words(entry)
            assert name not in seen, (
                f"{raw['rule_id']} lists {entry!r} and {seen[name]!r}, "
                f"which are the same class once both are normalized"
            )
            seen[name] = entry


# ---------------------------------------------------------------------------
# A pass says what it matched
# ---------------------------------------------------------------------------
#
# The result card shows the application's value and the label's side by side
# under one pill, and on this element the two almost never read the same: the
# application declares STOUT and the label designates BARREL-AGED IMPERIAL
# STOUT. A pass with nothing beside it leaves a reviewer reading a card that
# appears to contradict its own verdict, with no way to tell agreement from a
# rule that is simply wrong.


def test_a_pass_names_the_declared_designation_found_inside_the_labels() -> None:
    result = _run("BARREL-AGED IMPERIAL STOUT", "STOUT")
    assert result.outcome is Outcome.PASS
    assert result.message is not None
    assert "BARREL-AGED IMPERIAL STOUT" in result.message
    assert "STOUT" in result.message
    # Nothing other than the declared designation was matched, so the card has
    # no second value to show; the sentence carries it.
    assert result.matched_value is None


def test_a_pass_on_one_of_several_packed_designations_carries_that_one() -> None:
    # "DESSERT /PORT/SHERRY/(COOKING) WINE" declares four. A reviewer reading
    # the whole string beside a label saying COOKING WINE needs to be told
    # which of the four the rule matched.
    result = _run("COOKING WINE", "DESSERT /PORT/SHERRY/(COOKING) WINE")
    assert result.outcome is Outcome.PASS
    assert result.matched_value is not None
    assert "COOKING" in result.matched_value.upper()
    assert result.message is not None


def test_a_pass_on_a_shared_class_names_the_class() -> None:
    rule = _rule(recognised=("Wine", "Table Wine"))
    result = _run("RED TABLE WINE", "TABLE RED WINE", rule=rule)
    assert result.outcome is Outcome.PASS
    assert result.message is not None
    assert "TABLE WINE" in result.message.upper()


def test_a_pass_within_a_class_names_the_class_it_falls_within() -> None:
    tables = {"t": DecisionTable(entries=({"class": "Beer", "designations_within": ["Lager"]},))}
    result = _run("LAGER", "BEER", rule=_rule(table_ref="t"), tables=tables)
    assert result.outcome is Outcome.PASS
    assert result.message is not None
    assert "LAGER" in result.message.upper()
    assert "BEER" in result.message.upper()
    # The label's class is a value the application never wrote, so it goes on
    # the card as well as into the sentence.
    assert result.matched_value is not None
    assert "LAGER" in result.matched_value.upper()
