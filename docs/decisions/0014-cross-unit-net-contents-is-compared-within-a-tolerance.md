# 0014. Cross-unit net contents is compared within the rounding the standards of fill carry

Date: 2026-09-16

## Choice

When the net contents on the label and the net contents on the application are in **different**
units, the two agree if they are within **1% of the figure the application declared**. When they
are in the **same** unit, they must be equal, as before.

The 1% is data in the rule pack, not a constant in the validator. It sits in the `tolerance:` block
of each `*.net_contents.matches_application` rule, as `cross_unit_relative: 0.01`, in all three
beverage packs. A rule that carries no tolerance compares exactly in both cases.

## Why a tolerance at all

The container sizes the regulations authorize are metric, and the customary figure a label prints
for one of them is that size converted and rounded to a tenth of a fluid ounce. 375 mL is 12.6803
fluid ounces, and the label prints `12.7 FL. OZ.`. Converting 12.7 back gives 375.58 mL, not 375.

So a comparison that demands equality rejects a compliant label **by construction**: the rounding
is already in the figure the label prints, and no reader or parser can undo it. Four of the nine
failures the answer key uncovered are this shape.

## Why 1%, and not some other number

The tolerance has to be wide enough to absorb that rounding and narrow enough that one authorized
size cannot pass as another. Both bounds come from the authorized standards of fill — 27 CFR §4.72
for wine and §5.203 for distilled spirits, as amended by T.D. TTB-200, effective 2025-01-10, listed
in `docs/research/2026-09-15-ttb-regulatory-framework.md`.

**The floor: 0.633%.** Converting every authorized size to fluid ounces and rounding to a tenth —
the precision the labels in `tests/fixtures/labels/manifest.json` actually print, which gives 50 mL
as 1.7 FL OZ and 375 mL as 12.7 FL OZ — the worst case is 0.550%, at 50, 100, 200 and 250 mL. A
label may also print the tenth *below* the true figure so the customary statement does not
overstate the contents: a 250 mL can
prints `8.4 FL OZ`, which is 0.633% low. That is the widest gap a printed customary figure opens on
an authorized size, so the tolerance must be at least 0.633%.

**The ceiling: 1.216%.** Take each authorized size and the customary figure printed for the nearest
size that prints a different one. The closest such pair is in the spirits list: 710 mL against the
`24.3 FL OZ` printed for 720 mL, which converts to 718.64 mL — 1.216% away from 710. A tolerance at
or above that would let a 720 mL label pass against a 710 mL application. So the tolerance must stay
below 1.216%.

1% sits between the two, and is the round number in that gap.

**Where the tenth comes from.** It is observed, not cited. Every customary figure in the fixture
corpus is printed to a tenth of a fluid ounce — `12.7 FL. OZ.` on a 375 mL label,
`11.2 FL. OUNCES` on a 331 mL one, `1 PT. 0.9 FL. OZ. (500 mL)` on a 500 mL one — and each matches
its metric size converted and rounded to a tenth.
`docs/research/2026-09-15-ttb-regulatory-framework.md` records that equivalent customary units are
*permitted* alongside metric (§5.70(a), §7.70(a),
§4.37) but prescribes no precision for them and publishes no equivalents table; its only rounding
note, "Liters use decimals to nearest hundredth," is about metric liters. If the regulation does
fix a precision and it is coarser than a tenth, the floor below rises and 1% may no longer clear
it — that is the one thing worth re-checking against the regulation itself.

`tests/rules/_validators/test_quantity_match.py` recomputes both bounds from the two size lists and
asserts the shipped tolerance sits between them, so an edit that loosens it fails with the reason
attached rather than passing quietly.

## What this cannot do

Authorized sizes closer together than the rounding itself — 330 against 331 mL, 473 against 475,
568 against 570 — print the **same** customary figure. No tolerance of any width can tell them
apart, because the label genuinely does not say which one it is. That is a limit of a customary
declaration, not of this rule.

Malt beverages have **no** federal standards of fill at all (§7.70). The bounds above are derived
from the wine and spirits lists and applied to malt as well, because a malt label prints its
customary figure with the same rounding even though the size it rounds is unconstrained.

## Why the number lives in the rule pack

Determinism is a first-class criterion for this product: the same input gives the same answer, and
a reviewer can read the reason a verdict went the way it did. A tolerance held in the pack is a
number a reviewer can look up beside the rule that used it, and a number a rule pack version pins.
A constant in `quantity_match.py` would be neither. `app/schemas/rules.py` already declares the
`tolerance` field and `tests/test_rules_yaml_round_trip.py` already covers it; nothing else in the
pack used it until now.

## Rejected

**Comparing at the label's printed precision.** Convert the application's figure into the label's
unit, round it to the number of decimal places the label printed, and demand equality. It is
deterministic and it closes the three cross-unit failures, and it has two holes. It still rejects
the compliant 250 mL can: it computes 8.4535, rounds to 8.5, and fails against the printed 8.4. And
it stops being a check at coarse precision — a label printing `1 PINT` has a last printed digit of
one whole pint, so the rule admits anything within half a pint, and an application declaring 700 mL
passes against a pint label. `ttb-26240001000563` is exactly that shape.

**A table of admissible equivalents** — every authorized size listed with the customary figures a
label may print for it, and a pair admissible only if it appears. The most explainable design, and
it cannot be completed: malt beverages have no standards of fill, so any lawful malt size outside
the list would be reported as a disagreement. All four of the failures this decision closes are
malt labels.

**27 CFR §7.71's net-contents tolerances** as the source of the number. Those cover the difference
between the liquid in the container and the declaration on it — a filling-line tolerance. This app
compares two *declarations* about the same container and never sees the liquid, which is the same
reason `docs/decisions/0008` removed the carried-over alcohol tolerance.

**A middle band** — pass inside 1%, needs-review between 1% and the next authorized size, fail
beyond. The band would be 1% to 1.216% wide, too thin to carry a third outcome, and its second
boundary would need a derivation of its own.
