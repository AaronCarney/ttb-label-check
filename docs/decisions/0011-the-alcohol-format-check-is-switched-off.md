# 0011. The alcohol-content format check is switched off until the reader returns the label's wording

Date: 2026-09-16

## Choice

Three rules are switched off, each carrying the reason in its own `notes` field:

| Rule | What it checks | Citation |
|---|---|---|
| `spirits.alcohol.format` | The alcohol statement is in a permitted form | §5.65(b) |
| `wine.alcohol.format` | The alcohol statement is in a permitted form | §4.36(b)(1) |
| `malt.alcohol.format` | The alcohol statement is in a permitted form | §7.65(b) |

The rules stay in their packs with their citations and their regex, and the validator
`app/rules/_validators/format_check.py` stays registered as `regex_match`. Nothing is deleted. The
README states the gap as a limitation.

What still runs on alcohol content is every check this app can make from what it is given: that a
label carries a statement where one is required — `spirits.alcohol.present`,
`wine.alcohol.present_or_table`, `malt.alcohol.conditional_required` — and that the number on the
label is the number the application declared, `*.alcohol.matches_application`.

## Why

The rule never sees the label's wording, so it cannot judge the label's wording.

`format_check.py:17-36` takes the reader's alcohol observation — a percentage and a unit — and
builds the sentence `f"alcohol {pct}{unit} by volume"` from it. Line 49 hands that construction to
the regex, and line 61 matches it. The string being tested is one the validator wrote itself, in the
canonical form the pattern is designed to accept. Both readers supply the number and not the text:
`app/vision/local.py:597-605` parses `_ABV_RE` down to `{"abv_pct": float, "unit": "%"}` and discards
the matched characters.

Two consequences follow, and both are wrong verdicts:

- **A number read means a pass, whatever the label printed.** `_ABV_RE` matches a bare percentage,
  so a label whose only alcohol statement is `12.5%` — with none of the wording §5.65(b) requires —
  yields `12.5` to the reader, which the validator renders as `alcohol 12.5% by volume`, which
  matches. The check reports the format as verified when it examined nothing. Across the 38 labels in
  the fixture manifest the rule passed every one.
- **No number read means a rejection, at `severity: reject`.** When the reader places no alcohol
  figure, the projection returns the empty string and line 61 short-circuits to `FAIL`. For spirits
  the statement is mandatory (§5.63(a)(3)), so the rejection is at least aimed at a real
  requirement — but it is aimed at a formatting question the rule never asked, and it fires whenever
  the reader could not place a statement the label carries. For wine and malt the statement is often
  not required at all: §4.36(a) makes it optional at or below 14% alcohol where "table wine" or
  "light wine" appears on the brand label, and §7.63(a)(3) requires it for a malt beverage only where
  the alcohol comes from added nonbeverage ingredients. On those labels a lawful silence is a hard
  reject.

A check that passes whatever it is shown, and rejects when it is shown nothing, carries no
information about the label either way.

## Alternatives rejected

- **Leave the rules enabled.** They return a verdict they have not earned in both directions. A
  wrong rejection on a compliant label is the one failure this product cannot have, and a pass that
  reports an unmade check is the failure `docs/decisions/0006` already refused.
- **Repair the projection here.** The repair needs the reader to return the label's alcohol statement
  as printed, which is a change to `app/vision/local.py` and `app/vision/cloud.py`. Those files are
  the reader's, their work is gathered in one pass against frozen OCR output, and neither the change
  nor its proof can be made without an OCR run. The switch-off is what can be landed honestly now;
  the repair is written down where the reader work is planned.
- **Delete the rules, as `docs/decisions/0008` deleted the tolerance rules.** The two cases differ.
  A tolerance rule compares the label against the liquid, and the liquid's alcohol content exists
  nowhere in this app's inputs, so that check can never be made here. The format check compares the
  label against a regex, and the label's own text is in the image the app is already given. This
  check is unbuilt, not unbuildable, and deleting it would throw away a correct rule and its
  citation.
- **Lower the severity to `warn`.** That sends every label whose alcohol statement the reader could
  not place to a human, with a reason code naming a formatting defect nobody examined. It converts a
  false rejection into a false alarm, which `docs/decisions/0008` rejected for the same reason.
- **Pass when nothing was read.** This reports the format as checked and correct on a label the app
  never looked at. It is the same claim of an unmade check that `docs/decisions/0006` refused for
  contrast and type size.
- **Delete `format_check.py` along with the rules.** `app/rules/loader.py:211` refuses startup when
  any rule names a validator the registry does not carry, and it makes that check for disabled rules
  too. A switched-off rule still names `regex_match`, so the validator stays.

## Constraint that decided it

A check that cannot be made must not be reported as made. Between a rule that passes everything and
a rule that rejects compliant labels, the honest option is to not run it and to say so in the README.

## Consequence

The app does not check the form of words a label uses to state its alcohol content, and this is named
in the README as a limitation. The check returns when the reader returns the alcohol statement as the
label prints it — verbatim, as a string, alongside the parsed percentage rather than instead of it.
Until then `format_check.py`'s projection is what it has always been: a restatement of the reader's
numbers, not a reading of the label.
