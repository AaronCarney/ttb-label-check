# 0012. A class-and-type designation the app cannot place goes to a reviewer, not to a rejection

Date: 2026-09-16

## Choice

**No rule rejects a label because its class-and-type designation is absent from a list.** Four
changes carry that:

| Rule | Before | Now |
|---|---|---|
| `wine.class_type.present` | `enumerated_match` against a five-entry list | `presence_check` on the `class_type` field |
| `spirits.class_type.present` | `enumerated_match` against a ten-entry list | `presence_check` on the `class_type` field |
| `malt.class_type.present` | `enumerated_match` against an eight-entry list | `presence_check` on the `class_type` field |
| `spirits.class_type.matches_soi` | `severity: reject` | `severity: warn`, on a list completed to Part 5 Subpart I's own classes and named types |

The `*.class_type.matches_application` rules are unchanged in shape: `designation_match` already
returns needs-review at warn severity where neither side names a recognised class. Two facts about
the regulations that those rules need move into decision tables, which is where a fact about the law
belongs rather than inside a rule's parameters:

- **`rules/tables/wine_designations.yaml`** (new) pairs `Champagne` with `Sparkling Wine` in both
  directions.
- **`rules/tables/malt_designations.yaml`** now places thirteen styles within the class `Beer`, and
  `malt.class_type.matches_application`'s `recognised_classes` carries all thirteen plus `Beer`
  itself, so no table entry is unreachable. The validator works out which class each side names from
  `recognised_classes` before it consults the table, so a designation only the table knows would
  never fire.

`Rose Wine` comes off wine's recognised list.

## Why

**An allow-list is the wrong instrument for the question `present` asks.** The three citations those
rules carry — §4.32(a)(2), §5.63(a), §7.63(a)(2) — each require a designation to appear on the label.
They do not require it to be one of a short set. Checking presence against a list answers a different
and harder question, and gets the easy one wrong whenever the list is short.

**The list can never be complete, and every gap in it was a hard rejection of a compliant label.**

- §4.34(b) lets a wine be designated by a grape variety name, a semi-generic geographic name or a
  geographic distinctive name **in lieu of** a class and type. The prime grape names in §4.91 alone
  run to several hundred.
- Part 5 Subpart I lets a distilled spirit with no standard of identity be designated by a fanciful
  name alongside a truthful statement of composition, so no list of standards can cover what may
  lawfully appear.

Driving the engine over the transcribed readings in `tests/fixtures/labels/manifest.json` — all real,
all TTB-approved — produced thirteen failing verdicts on approved labels before these changes, every
one of them at reject severity:

| Designation on the label | Rule reporting it | Cause |
|---|---|---|
| `Cognac XO / Cognac Petite Champagne` | `spirits.class_type.present`, `.matches_soi` | Cognac on neither list |
| `CRÈME DE CASSIS LIQUEUR` | `spirits.class_type.present`, `.matches_soi` | Liqueur on neither list |
| `PEATED OREGON AMERICAN SINGLE MALT WHISKEY` | `spirits.class_type.matches_soi` | Qualified whiskey designation |
| `SANGIOVESE`, `CHARDONNAY`, `GEWURZTRAMINER`, `PINOT NOIR` | `wine.class_type.present` | §4.34(b) varietal designations |
| `ROSE WINE`, `WHITE RHONE WINE / CHATEAUNEUF-DU-PAPE` | `wine.class_type.present` | Colour and geographic designations |

After the changes the same run reports none of them, and no verdict anywhere off the outcome the
manifest records.

**Where the app genuinely cannot place a designation, "a reviewer should look" is the true answer and
the engine already has a shape for it.** `designation_match` returns `INSUFFICIENT_EVIDENCE` at warn
severity on that branch, and the country-of-origin comparison was settled the same way.
`spirits.class_type.matches_soi` now says the same thing: it passes what Subpart I names, and sends
what it does not recognise to a human rather than rejecting the label.

**Champagne and Rose Wine, measured against the CFR text.** Both were on
`wine.class_type.matches_application`'s recognised list, and whether either belonged there is a
measurement, not a judgement.

- **Champagne belongs, and listing it alone was not enough.** §4.21(b)(2) makes champagne a type of
  sparkling light wine, and §4.34(a) says the type designation "champagne" "may appear in lieu of the
  class designation 'sparkling wine'". §4.24(b)(2) additionally lists it among the semi-generic
  names. So a label reading CHAMPAGNE and an application reading SPARKLING WINE name the same wine.
  With Champagne merely listed and nothing recording the equivalence, `designation_match` saw two
  recognised classes that differ and returned a rejection — turning a substitution the regulation
  expressly permits into a rejected label. The decision table records the equivalence, both ways,
  because the regulation offers the two designations as alternatives rather than as a general and a
  specific term.
- **Rose Wine does not belong, and is removed.** §4.21(a)(4) puts "pink (or rose) wine" beside "red
  wine", "amber wine" and "white wine" as ways of designating the colour of a Class 1 grape wine. It
  is a colour inside a class, not a class. Removing it changes no verdict, because every designation
  carrying "rose wine" also carries "wine", which is listed, so both sides already agree at that
  class.

## Alternatives rejected

- **Extend the `present` allow-lists until they agree with each other.** This is the smallest change
  and it fixes the two spirits labels above. It leaves the cause in place — the next lawful
  designation nobody listed is still a rejection — and it cannot fix wine at all, where the lawful
  set is several hundred grape names plus the semi-generic and geographic lists.
- **Carry every lawful designation.** The list would run to thousands of entries, would need
  maintaining against §4.91 and Subpart I, and would still be a rejection engine for whatever it
  missed. `docs/decisions/0007` rejected the same idea for the qualifiers around a standard of
  identity.
- **Keep `matches_soi` at reject severity and grow its list.** Same defect in a rule whose subject
  makes it worse: Subpart I's fanciful-name route means an unlisted designation is not evidence of
  anything wrong.
- **Put the Champagne equivalence in the rule's parameters rather than a decision table.** The
  equivalence is a fact about §4.34(a), not about how this rule is configured, and a reader checking
  the rule against the regulation should find it in one place with its citation. The malt pack
  already carries its class-and-style equivalences this way.
- **Drop the `present` rules altogether, since `matches_application` also looks at the
  designation.** They answer different questions. `present` is the §4.32(a)(2) requirement that the
  label carry a designation at all, and it is the only rule that catches a label carrying none. An
  application that declares no class makes `matches_application` inapplicable, and with `present`
  gone a label with no designation would pass.

## Constraint that decided it

A wrong rejection of a real, approved label is the one failure this product cannot have. Where the
app cannot place what a label says, the honest verdict is that a reviewer should look — never that
the label is wrong.
