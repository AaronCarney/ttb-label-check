r"""Reason-code grammar enforcement:

  Pattern: ^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*){2,3}$

Every code in reason_codes.yaml matches; representative malformed strings do not.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

GRAMMAR = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*){2,3}$")
REGISTRY = Path("rules/reason_codes.yaml")


def test_every_registry_code_obeys_grammar() -> None:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    for code in data["codes"]:
        assert GRAMMAR.match(code), code


def test_grammar_rejects_lowercase_bin() -> None:
    assert GRAMMAR.match("brand.name.missing") is None


def test_grammar_rejects_too_few_parts() -> None:
    assert GRAMMAR.match("BRAND.MISSING") is None


def test_grammar_rejects_too_many_parts() -> None:
    assert GRAMMAR.match("BRAND.NAME.MISSING.QUAL.EXTRA") is None


def test_grammar_accepts_qualified_form() -> None:
    assert GRAMMAR.match("BRAND.NAME.NEEDS_REVIEW.LLM") is not None
