"""What a rule pack cites has to be readable by the person reading the rule.

Two guards, and both exist because `common.warning.present` is the one rule in
any pack allowed to read "the reader did not find it" as "the label does not
carry it" — and since the confidence floor was fixed, that reading reaches the
applicant as a 27 CFR §16.21 rejection rather than a reviewer's question.

The evidence licensing it is a measurement, and a reader who wants to judge the
rule has to be able to find that measurement and see what it does and does not
show.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
RULES = ROOT / "rules"

_MD_PATH = re.compile(r"[A-Za-z0-9_./-]+\.md")


def _tracked_files() -> set[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return set(out.stdout.split())


def test_every_document_a_rule_pack_cites_is_in_the_repository() -> None:
    """A citation to an excluded file is a citation to nothing.

    `plans/` is kept out of the repository, so a rule that sourced its
    justification there pointed a reviewer at a file they will never see.
    """
    tracked = _tracked_files()
    dangling: list[str] = []
    for path in sorted(RULES.rglob("*.yaml")):
        for cited in _MD_PATH.findall(path.read_text(encoding="utf-8")):
            if cited not in tracked:
                dangling.append(f"{path.relative_to(ROOT)} cites {cited}")
    assert not dangling, "rule packs cite documents a reviewer cannot read:\n  " + "\n  ".join(
        dangling
    )


def test_the_one_rule_allowed_to_reject_on_silence_says_its_evidence_is_in_sample() -> None:
    """`unlocated_is_absent` rests on a number measured on the tuning corpus.

    The reader finds the health warning on 30 of 30 labels — measured over the
    same 30 labels the reader's own heuristics were tuned against. There is no
    held-out set, so that figure is an upper bound on what the reader does with
    a label it has never seen, and the rule it licenses rejects.

    Stating that beside the rule is the whole of this guard. A reader who sees
    "30 of 30" and not "in-sample" reads a reliability the measurement does not
    establish.
    """
    text = (RULES / "common" / "health_warning.yaml").read_text(encoding="utf-8")
    granting = [
        path for path in sorted(RULES.rglob("*.yaml"))
        if "unlocated_is_absent: true" in path.read_text(encoding="utf-8")
    ]
    assert [p.name for p in granting] == ["health_warning.yaml"], (
        "another rule now reads silence as absence; it needs the same disclosure"
    )
    assert "in-sample" in text, (
        "the rule quotes its 30 of 30 without saying the figure is in-sample"
    )
    assert "held-out" in text, (
        "the rule does not say there is no held-out set behind that figure"
    )


def test_the_rule_that_rejects_on_silence_is_still_the_only_one() -> None:
    """A second rule granted this would need its own argument, on its own
    evidence. Loading every pack rather than reading the text, so a grant
    written in any spelling YAML accepts is caught."""
    granting: list[str] = []
    for path in sorted(RULES.rglob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        for rule in doc.get("rules") or ():
            params = rule.get("parameters") or {}
            if params.get("unlocated_is_absent"):
                granting.append(rule["rule_id"])
    assert granting == ["common.warning.present"], granting
