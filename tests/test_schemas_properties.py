"""Generated inputs against the reason-code grammar and the wire envelopes.

Two things the rest of the suite checks only by example.

**The reason-code grammar.** `app/schemas/rejection.py` and `app/rules/loader.py`
each compile their own copy of the same pattern, and the loader's copy is the
gate every shipped rule pack passes through. `tests/test_schemas_round_trip.py`
checks four spellings someone thought of. A property says the thing that has to
be true: *a value the grammar accepts is three or four dot-separated segments and
nothing else* — so a value carrying anything the grammar was never meant to allow
is found by the search rather than by a reader.

**The wire envelopes.** Two properties, and the second is the one with teeth.
Parsing what we serialised must give back an equal model; and serialising *that*
must give back the same bytes. The second matters because `audit_trail.input_hash`
and `output_hash`, and the result cache's key, are digests over serialised JSON
(`app/services/evaluator.py`). If a value survives the round trip as an equal
object but not as identical bytes, the same answer hashes two ways.

Strategies here generate what the system can really carry — UTC and whole-minute
offsets for timestamps, because that is what a clock and a client produce — not
every value the annotation technically permits. A property that fails only on an
input the system cannot receive reports a defect that does not exist.
"""

from __future__ import annotations

import string
from datetime import UTC, datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from app.rules.loader import _REASON_CODE_RE, _SEMVER_RE
from app.schemas.audit import AuditRecord
from app.schemas.metrics import Metrics
from app.schemas.rejection import REASON_CODE_GRAMMAR, ReasonCode
from app.schemas.wire.application import (
    Address,
    Applicant,
    ApplicationEnvelope,
    Formula,
    LabelDimensions,
    LabelRef,
    TypeOfApplication,
)
from app.schemas.wire.batch import BatchEnvelope, BatchItemRef
from app.schemas.wire.disposition import (
    AISuggestionWire,
    ConfidenceBand,
    DispositionEnvelope,
    FieldEvidenceWire,
    FieldFindingWire,
    RuleFindingWire,
)
from app.schemas.wire.error import ErrorEnvelope

# ---------------------------------------------------------------------------
# The reason-code grammar: BIN.SUB.SPECIFIC[.QUALIFIER]
# ---------------------------------------------------------------------------

_SEGMENT = st.from_regex(r"[A-Z][A-Z0-9_]{0,10}", fullmatch=True)

# A well-formed code, built from the grammar's own definition rather than from a
# list written here: three segments, or four with the optional qualifier.
_well_formed = st.lists(_SEGMENT, min_size=3, max_size=4).map(".".join)

# Characters a reason code may not contain. Each is something a hand-edited YAML
# registry, a copied constant or a trimmed-wrong string really carries: the
# whitespace a text editor leaves behind, and the punctuation next to the dot on
# a keyboard. Sampling from a named set rather than from free text means every
# one of them is tried, instead of turning up in roughly one run in five.
_NOT_IN_A_CODE = st.sampled_from(
    ["\n", "\r", "\t", " ", "\x0b", "\x0c", "\u00a0", ".", "-", "/", "a", "#", "\u200b"]
)

_JUNK = st.text(alphabet="\n\r\t .-_0az\x0b\x0c\u00a0", max_size=4)

# A code with one thing wrong with it, and the ways it goes wrong kept apart so
# each is searched on its own.
_perturbed = st.one_of(
    _well_formed,
    st.builds(lambda c, ch: c + ch, _well_formed, _NOT_IN_A_CODE),  # one character after
    st.builds(lambda ch, c: ch + c, _NOT_IN_A_CODE, _well_formed),  # one character before
    st.builds(lambda a, c, b: a + c + b, _JUNK, _well_formed, _JUNK),  # junk at both ends
    st.lists(_SEGMENT, min_size=0, max_size=6).map(".".join),  # the wrong number of segments
)


def _is_three_or_four_clean_segments(value: str) -> bool:
    """The grammar in prose: three or four segments, each a capital letter
    followed by capitals, digits or underscores, joined by dots, and nothing
    before or after."""
    segments = value.split(".")
    if not 3 <= len(segments) <= 4:
        return False
    allowed = set(string.ascii_uppercase + string.digits + "_")
    return all(seg and seg[0] in string.ascii_uppercase and set(seg) <= allowed for seg in segments)


@given(_perturbed)
@settings(max_examples=500)
def test_grammar_accepts_only_three_or_four_clean_segments(value: str) -> None:
    """Soundness. Whatever the grammar lets through is a reason code and nothing
    more — no leading or trailing character rides along on it.

    This is not pedantry about whitespace. An accepted code is used as a
    dictionary key against `rules/reason_codes.yaml`
    (`app/rules/yaml_engine.py`), and it is written into the envelope and into
    the audit hash. A code that passes the gate carrying an extra character is
    not the code anyone looks it up by.
    """
    if REASON_CODE_GRAMMAR.match(value):
        assert _is_three_or_four_clean_segments(value), (
            f"the grammar accepted {value!r}, which is not three or four clean segments"
        )


@given(_well_formed)
@settings(max_examples=300)
def test_grammar_accepts_every_well_formed_code(value: str) -> None:
    """Completeness. Anything built to the grammar is accepted by it, so a rule
    pack cannot be refused for a code that is in fact well formed."""
    assert ReasonCode.validate_grammar(value) == value


@given(_perturbed)
@settings(max_examples=500)
def test_both_copies_of_the_grammar_agree(value: str) -> None:
    """The rule pack's gate (`_REASON_CODE_RE` in `app/rules/loader.py`) and the
    construction-site gate (`app/schemas/rejection.py`) are one gate. They were
    two separately compiled copies of the same pattern, which is one edit away
    from a code the loader admits and the schema layer refuses. They answer the
    same way here, and the identity check below says why: there is only one of
    them to answer.
    """
    assert bool(REASON_CODE_GRAMMAR.match(value)) == bool(_REASON_CODE_RE.match(value)), (
        f"the two copies of the reason-code grammar disagree about {value!r}"
    )
    assert _REASON_CODE_RE is REASON_CODE_GRAMMAR, (
        "the loader has gone back to compiling its own copy of the reason-code grammar"
    )


# ---------------------------------------------------------------------------
# Wire envelopes: model -> JSON -> model
# ---------------------------------------------------------------------------

_text = st.text(max_size=40)
_unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Real clocks and real clients: UTC, and whole-minute offsets either side of it.
_tz = st.one_of(
    st.just(UTC),
    st.integers(min_value=-12 * 60, max_value=14 * 60).map(
        lambda m: timezone(timedelta(minutes=m))
    ),
)
_datetimes = st.datetimes(
    min_value=datetime(1970, 1, 1),
    max_value=datetime(2999, 12, 31),
    timezones=_tz,
)

_confidence = st.builds(
    ConfidenceBand, band=st.sampled_from(["high", "medium", "low"]), numeric=_unit
)

_rule_finding = st.builds(
    RuleFindingWire,
    rule_id=_text,
    cfr_citation=_text,
    disposition=st.sampled_from(["pass", "fail", "needs_review"]),
    reason_code=_well_formed,
    plain_language_explanation=_text,
)

_field_finding = st.builds(
    FieldFindingWire,
    field_name=st.sampled_from(
        [
            "brand_name",
            "class_type",
            "alcohol_content",
            "net_contents",
            "warning",
            "name_address",
            "country_of_origin",
        ]
    ),
    extracted_value=_text,
    expected_value=_text,
    evidence=st.builds(
        FieldEvidenceWire,
        bbox=st.tuples(*[st.integers(min_value=0, max_value=10_000)] * 4),
        crop_ref=_text,
        extraction_confidence=_unit,
    ),
    rule_findings=st.lists(_rule_finding, max_size=3).map(tuple),
    ai_suggestion=st.builds(
        AISuggestionWire,
        present=st.booleans(),
        task=st.none()
        | st.sampled_from(["brand_borderline", "reasoning_enrichment", "ocr_reconciliation"]),
        text=st.none() | _text,
        model_disposition=st.none() | st.sampled_from(["pass", "needs_review"]),
    ),
    field_confidence=_confidence,
)

_address = st.builds(Address, street=_text, city=_text, state=_text, zip=_text, country=_text)

_application = st.builds(
    ApplicationEnvelope,
    rep_id=st.none() | _text,
    permit_number=_text,
    source_of_product=st.sampled_from(["domestic", "imported"]),
    serial_number=st.text(max_size=6),
    type_of_product=st.sampled_from(["wine", "distilled_spirits", "malt_beverages"]),
    brand_name=_text,
    fanciful_name=st.none() | _text,
    applicant=st.builds(
        Applicant, name=_text, address=_address, mailing_address=st.none() | _address
    ),
    formula=st.none() | st.builds(Formula, ttb_formula_id=_text, approval_date=st.dates()),
    grape_varietals=st.none() | st.lists(_text, max_size=3).map(tuple),
    wine_appellation=st.none() | _text,
    phone=_text,
    email=st.none() | _text,
    type_of_application=st.builds(
        TypeOfApplication,
        cola=st.booleans(),
        exemption=st.booleans(),
        exemption_state=st.none() | _text,
        distinctive_bottle=st.booleans(),
        bottle_capacity=st.none() | _text,
        resubmission=st.booleans(),
        prior_ttb_id=st.none() | _text,
    ),
    blown_branded_embossed_text=st.none() | _text,
    date_of_application=st.dates(),
    applicant_signature=st.none() | _text,
    applicant_print_name=_text,
    perjury_attested=st.just(True),
    labels=st.lists(
        st.builds(
            LabelRef,
            image_ref=_text,
            face_tag=st.sampled_from(["front", "back", "neck", "side"]),
            dimensions=st.builds(
                LabelDimensions,
                width_px=st.integers(min_value=0, max_value=100_000),
                height_px=st.integers(min_value=0, max_value=100_000),
                dpi=st.integers(min_value=0, max_value=10_000),
            ),
        ),
        max_size=2,
    ).map(tuple),
)

_batch = st.builds(
    BatchEnvelope,
    batch_id=_text,
    agent_id=_text,
    submitted_at=_datetimes,
    items=st.lists(st.builds(BatchItemRef, label_ref=_text, application_ref=_text), max_size=3).map(
        tuple
    ),
)

_error = st.builds(
    ErrorEnvelope,
    error_kind=st.sampled_from(["rejected_input", "engine_failure", "partial_completion"]),
    reason_code=_well_formed,
    message=_text,
    details=st.dictionaries(_text, st.none() | st.booleans() | st.integers() | _text, max_size=3),
)

_envelopes = st.one_of(_application, _batch, _error)


@given(_envelopes)
@settings(max_examples=300)
def test_wire_envelope_round_trip_is_identity(envelope) -> None:
    """model -> JSON -> model gives back an equal model, for every envelope an
    agent submits or the boundary returns."""
    parsed = type(envelope).model_validate_json(envelope.model_dump_json())
    assert parsed == envelope


@given(_envelopes)
@settings(max_examples=300)
def test_wire_envelope_serialisation_is_byte_stable(envelope) -> None:
    """Serialising, parsing and serialising again gives the same bytes.

    Equality is not enough for this codebase. `audit_trail.input_hash` and
    `output_hash` are digests over serialised JSON, and the result cache keys on
    a digest of the canonical application JSON (`app/services/evaluator.py`). A
    value that round-trips equal but re-serialises differently hashes two ways,
    so the same submission can miss its own cache entry and the same answer can
    carry two audit hashes.
    """
    once = envelope.model_dump_json()
    twice = type(envelope).model_validate_json(once).model_dump_json()
    assert once == twice


@given(
    st.builds(
        DispositionEnvelope,
        evaluation_id=_text,
        label_ref=_text,
        disposition=st.sampled_from(["pass", "fail", "needs_review"]),
        disposition_confidence=_confidence,
        fields=st.lists(_field_finding, max_size=2).map(tuple),
        audit_trail=st.builds(
            AuditRecord,
            evaluation_id=_text,
            rule_set_version=_text,
            model_version=st.none() | _text,
            prompt_version=st.none() | _text,
            input_hash=_text,
            output_hash=_text,
            started_at=_datetimes,
            completed_at=_datetimes,
            per_rule_trace=st.tuples(),
            overrides=st.tuples(),
        ),
        metrics=st.builds(
            Metrics,
            total_duration_ms=st.integers(min_value=0, max_value=10**9),
            per_rule_durations_ms=st.tuples(),
            vision_duration_ms=st.integers(min_value=0, max_value=10**9),
            cache_hit=st.booleans(),
        ),
    )
)
@settings(max_examples=200)
def test_disposition_envelope_round_trip_is_identity_and_byte_stable(envelope) -> None:
    """The outbound envelope is the one a reviewer reads and the one the audit
    hash is taken over, so it gets both properties at once."""
    once = envelope.model_dump_json()
    parsed = DispositionEnvelope.model_validate_json(once)
    assert parsed == envelope
    assert parsed.model_dump_json() == once


# The registry's version string is read by the same loader, through a second
# pattern with the same shape, and it is not cosmetic: `rule_set_version` goes
# into `audit_trail` and into the result cache's key
# (`app/rules/yaml_engine.py`), so a version that is not the version it looks
# like is a wrong audit record and a cache that cannot be invalidated.

_semver = st.builds(
    lambda a, b, c, pre: f"{a}.{b}.{c}" + pre,
    st.integers(min_value=0, max_value=999),
    st.integers(min_value=0, max_value=999),
    st.integers(min_value=0, max_value=999),
    st.just("") | st.from_regex(r"[-+][0-9A-Za-z.-]{1,8}", fullmatch=True),
)

_perturbed_semver = st.one_of(
    _semver,
    st.builds(lambda v, ch: v + ch, _semver, _NOT_IN_A_CODE),
    st.builds(lambda ch, v: ch + v, _NOT_IN_A_CODE, _semver),
)


@given(_perturbed_semver)
@settings(max_examples=400)
def test_registry_version_gate_accepts_only_a_clean_semver(value: str) -> None:
    """Whatever the loader accepts as the rule-set version is a version and
    nothing more. The same reasoning as the reason-code grammar above: the
    accepted string is carried forward as an identifier, so a stray character
    riding along on it makes two names for one rule set."""
    if _SEMVER_RE.match(value):
        assert value == value.strip(), (
            f"the registry version gate accepted {value!r}, which carries surrounding whitespace"
        )
        assert "\n" not in value and "\r" not in value, (
            f"the registry version gate accepted {value!r}, which spans more than one line"
        )
