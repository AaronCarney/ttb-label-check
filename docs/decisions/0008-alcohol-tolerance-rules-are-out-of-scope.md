# 0008. The alcohol-content tolerance rules are out of scope

Date: 2026-09-16

## Choice

Five rules are removed from the pack, with the validators and the reason codes that served only
them:

| Rule | Citation |
|---|---|
| `spirits.alcohol.tolerance_band` | 27 CFR §5.65(c) |
| `wine.alcohol.tolerance_band` | 27 CFR §4.36(b)(1) |
| `wine.alcohol.no_class_boundary_cross` | 27 CFR §4.36(c) |
| `malt.alcohol.tolerance_band` | 27 CFR §7.65(c) |
| `malt.alcohol.floor_05` | 27 CFR §7.65(c) |

Gone with them: the `abv_band`, `abv_class_boundary_check` and `abv_hard_floor` validators, the
`abv_actual_pct` field on `ExpectedValue`, and the `CROSSES_CLASS_BOUNDARY` and `BELOW_HARD_FLOOR`
reason codes.

`ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND` **stays in the registry as reviewer vocabulary**, and no
rule emits it. The reviewer console offers it in the override picker, and `app/api/overrides.py`
refuses any code the registry does not list, so removing it would make that override fail. A
reviewer holding a laboratory figure the application does not carry is exactly the person who
should be able to record this, which the automatic check could never do.

What stays is every check this product can actually make about alcohol content: that the label
states one where the application declares one, that the statement is in a permitted format, and
that the number on the label is the number the application declared.

## Why

Each of those five rules compares the alcohol content **printed on the label** against the alcohol
content **in the bottle**. That second number comes from laboratory analysis of the product. This
application is given an image of a label and a copy of the application form. It never sees the
liquid, so the figure the rules need does not exist anywhere in its inputs and cannot be obtained
from them.

The regulations are real and the tolerances are stated correctly. The rules are simply not
answerable from what a label checker is given.

Keeping them was not neutral. `ExpectedValue.abv_actual_pct` was declared and never written, so all
three validators took their "no value" branch and returned a failure on every label. All five rules
were `severity: reject`, and `compute_disposition` turns any non-warn failure into `fail`. Both
readers emit an alcohol observation even when they find none, so the rules ran every time. The
result was that **no label of any beverage type could be reported as a match** — the exact outcome
this product exists to avoid.

The unit tests did not catch it, because each supplied `abv_actual_pct` itself through a test
helper. They were checking arithmetic the product could never reach.

## Alternatives rejected

- **Populate `abv_actual_pct` from the application.** The application declares the labeled value,
  which is the other side of the same comparison. Comparing a number against itself makes the rule
  pass on every label, which is as wrong as failing on every label and harder to notice.
- **Lower the severity to `warn`.** That routes every label to a human reviewer with a reason code
  that names a discrepancy nobody measured. It converts a false rejection into a false alarm.
- **Leave the rules in and mark them disabled.** A disabled rule still reads as a capability in the
  pack. A reviewer would reasonably believe the tolerance is checked.
- **Accept a laboratory figure as an optional input.** No such field exists on the TTB Public COLA
  Registry record the application form is modelled on, and the brief supplies a label image and an
  application, not an analysis.

## Consequence

A label whose stated alcohol content differs from the product's true alcohol content is not detected
here, and this is named in the README as a limitation. Detecting it needs an input this product is
not given.
