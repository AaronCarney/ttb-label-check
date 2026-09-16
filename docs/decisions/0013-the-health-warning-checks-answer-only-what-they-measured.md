# 0013. The health-warning checks answer only what they measured

Date: 2026-09-16

Extends `docs/decisions/0006`, which put four of these checks out of scope. That record said which
checks are not made. This one says what they answer instead, and settles three further questions the
warning rules raised: what "the same words" means when a printer's spacing differs, what a boldness
nobody could measure is worth, and what happens to a rule that duplicates another.

## Choice

**1. The four checks this product cannot make answer `insufficient_evidence` at warn severity, under
a reason code that names the missing measurement.** They no longer have implementations of their own.
All four now name one validator, `unmeasurable`:

| Rule | What it checks | Citation | Reason code |
|---|---|---|---|
| `common.warning.contrasting_bg` | The warning sits on a contrasting background | §16.22(a)(1) | `WARNING.LEGIBILITY.CONTRAST_NOT_MEASURED` |
| `common.warning.cpi_max` | Characters per inch, against the §16.22(a)(4) table | §16.22(a)(4) | `WARNING.TYPE_SIZE.CPI_NOT_MEASURED` |
| `common.warning.type_size_min` | Minimum type height | §16.22(b) | `WARNING.TYPE_SIZE.HEIGHT_NOT_MEASURED` |
| `common.warning.separate_apart` | The warning is separate and apart from other information | §16.21 | `WARNING.PLACEMENT.ISOLATION_NOT_MEASURED` |

Each rule stays in the pack with its citation and its `notes`, and each stays `disabled: true`, so
none of them adds a finding to a label today. What changed is what they say the moment anyone
switches one on. The four bodies that used to back them — `contrast_ratio_check.py`, `cpi_lookup.py`
and `type_size_check.py`, plus the `layout_isolation_check` half of `layout_check.py` — are deleted.
Each of them compared against a payload key no reader emits, so each returned a rejection on every
label, compliant ones included.

**2. `type_size_check` is deleted rather than left switched off.** It compared a point value against
a fixed 2.0. §16.22(b) sets the minimum in millimetres and keys it to container size — 1 mm at 237 mL
or under, 2 mm up to 3 L, 3 mm above — so a pass from that comparison did not mean what its own
citation says. Code whose answer is wrong in a way its citation hides is worse than no code: a later
reader trusts it. The §16.22(a)(4) decision table stays, at `decision_table_ref` on the CPI rule,
because it is the regulation's own three rows rather than an implementation of anything.

**3. The verbatim comparison ignores letter case, spacing and a line break that splits a word. It
does not ignore punctuation.** `common.warning.verbatim` keeps reject severity: once case and spacing
are out of the comparison, a mismatch means the words differ, and §16.21 fixes the words. The
canonical form both the loader and the validator use is, in order:

    nfkc → ascii_quotes → join_line_break_hyphens → collapse_whitespace →
    tighten_punctuation_spacing → casefold → strip_outer_ws

**4. `common.warning.heading_phrase` is deleted, not switched off.** It asked for evidence named
`warning_heading` that no reader produces, and `common.warning.heading_caps_bold` already checks the
same two words together with the capitals §16.22(a)(2) requires. `equality_match`, the validator it
was the only user of, is deleted with it.

**5. A boldness the reader could not measure is not a rejection.** `heading_style_check` decides the
heading's words and capitals first, from the heading's own text, and still rejects when either is
wrong. Where the payload reports `heading_bold_measured_confident: false`, the rule answers
`insufficient_evidence` at warn severity under `WARNING.STYLE.BOLD_NOT_MEASURED`, which the rule
declares in its own `parameters`. `app/vision/heading_measure.py` no longer falls back to measuring
the lower half of the whole image when it has no heading box: a measurement taken somewhere else is
not a measurement of the heading.

## Why

**On the four unmeasurable checks.** A check that cannot be made has three possible answers and only
one of them is honest. Passing claims a requirement was met that nobody looked at. Failing rejects a
compliant label for the product's own blindness — which is exactly what the deleted implementations
did. Insufficient evidence says what happened: the label goes to a reviewer on that point, with a
sentence naming the measurement nobody could take, and is never rejected on it. Decision 0006
established that these are out of scope; leaving four separate bodies of unreachable code switched
off left four traps, because switching one on produced a wrong verdict rather than a missing one.

**On case and spacing.** The answer key settles it. `tests/fixtures/labels/manifest.json`'s own
`check_rules.warning_exact` reads, verbatim:

> Same words, numbers and punctuation as 27 CFR 16.21. Letter case, spacing, line breaks and hyphens
> that split a word at a line end are ignored; the heading's capitals are scored separately by
> warning_heading_caps.

Five labels in that manifest prove each half of it, and they are why the pipeline is shaped the way
it is:

- `ttb-26231001000662` prints `GOVERNMENT WARNING  :`, doubles the space after two commas, and sets
  the whole body in capitals. Approved, and the manifest marks it `warning_exact: true`.
- `ttb-26237001000107` prints `(1)ACCORDING`, with no space at all. Also `true` — so "ignore spacing"
  cannot mean "collapse runs of spaces", because there is no run to collapse. Whitespace on both
  sides of a punctuation mark is removed instead, which makes `WARNING  :`, `WARNING :` and
  `WARNING:` one string.
- `ttb-26231001000333` breaks `PREG-\nNANCY` across two printed lines. Also `true`.
- `ttb-26240001000454` ends `HEALTH PROBLEMS"` instead of `PROBLEMS.`, and the manifest marks it
  `warning_exact: false`. So punctuation stays in the comparison.
- `var-heading-title-case` prints the heading as `Government Warning:` with the body unchanged, and
  the manifest marks it `warning_exact: true` and `warning_heading_caps: false`. That one is
  decisive: the verbatim rule ignores the heading's case, and the separate capitals rule is what
  catches it.

Case in the body is regulated nowhere. §16.22(a)(2) rules the heading's case only, and
`common.warning.heading_caps_bold` scores exactly that. A comparison that sent every all-capitals
approved label to a reviewer would be reporting a difference no regulation names.

**On an unmeasured boldness.** Both readers already say whether their stroke-width measurement was
confident (`app/vision/local.py`, `app/vision/cloud.py`). Against a reject-severity rule, treating
"not measured" as "not bold" turns the product's own blindness into a rejection of a label that may
well be printed in bold. The label element that *was* read — the capitals — is still decided, so a
title-case heading is rejected whether or not anyone measured its weight.

## Alternatives rejected

- **Keep the four implementations, switched off.** They are unreachable code against a reader that
  does not exist, and each carries a wrong verdict for whoever switches it on.
  `meta-plan-decisions/0009` decided this shape directly: the four rules stay and point at one
  shared `unmeasurable` validator, the three implementation bodies go, and the fifth rule goes
  outright. The rule entry, with its citation and its notes, is the durable record; the body was
  not.
- **One shared "not measured" reason code.** Four rules ask four different questions. A reviewer
  reads the code's description as a sentence, and "a measurement was not taken" does not say which.
- **Delete the §16.22(a)(4) decision table with `cpi_lookup`.** The table is the regulation's three
  normative rows as data. It costs nothing, the loader resolves the reference, and it is what a
  characters-per-inch check reads the day a reader reports a physical scale.
- **Report a case-only difference as needs-review.** Proposed in
  `docs/research/2026-09-15-matching-rules.md`, under that document's own *Open points* heading,
  where it was never settled. The manifest settles it the other way, and `var-heading-title-case` —
  `warning_exact: true` with a title-case heading — is not compatible with any other reading.
- **Normalize punctuation out along with spacing.** `ttb-26240001000454` must still fail on
  `PROBLEMS"`, and §16.21 fixes the statement's punctuation as much as its words.
- **Rename `equality_match.py`.** It keeps `enumerated_match`, which is still equality against an
  enumerated list. Renaming the module would touch seven test files for no change in behaviour.

## Constraint that decided it

A check that cannot be made must not be reported as made, and must not be reported as failed either.
Between passing a label nobody checked and rejecting one the product could not see, the honest answer
is to say which measurement is missing and hand the label to a reviewer.
