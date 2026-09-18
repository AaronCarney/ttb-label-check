# PRD amendment record

One entry per change to the text of `PRD.md`: what moved, and what made it necessary. The commit
that made the change records when.

## FR-7, equivalent values

**What moved.** FR-7 was one paragraph listing what each comparison ignores. It is now four, and three
statements in it changed rather than being reworded:

1. **Punctuation.** The old text listed what brand, class/type, name and address and country of origin
   ignore — case, spacing, line breaks, quote style, the ™ ® © marks — and punctuation was not on the
   list, which made a punctuation-only difference a "needs review" under the paragraph's closing
   sentence. The new text says class/type, name and address and country of origin ignore punctuation,
   and that brand keeps it and **scores** the difference: "Stones Throw" against an application's
   "Stone's Throw" scores 0.9846 where a match needs 0.92, and reports a match. Accents were added to
   the ignored list in the same sentence; the product folds them everywhere and FR-7 never said so.
2. **Country of origin.** The old text promised the comparison "also accepts the abbreviations and
   variant spellings 19 CFR 134.45 allows". It does not, and no such table was built. The new text says
   the check reads the English name the application declares and sends any other form to a reviewer
   rather than rejecting it.
3. **Brand's admissible set.** FR-7 now says brand is compared against every name the application says
   the label may carry — the declared brand, the fanciful name, and each trade name marked "(Used on
   label)" — not against the brand-name field alone.

**What made it necessary.** All three were the PRD describing a product different from the one built,
and in each case the product was built against a primary source the PRD's own text did not follow.

- Punctuation: Form TTB F 5100.31's allowable revisions, item 3.b, permits a label to change punctuation
  without a new approval. `docs/research/2026-09-15-matching-rules.md` cites that item in its opening
  paragraph and then contradicts it in its worked cases; FR-7 inherited the contradiction. Settled in
  [decision 0017](decisions.md#0017), which also corrects
  `specs/0001-label-verification/requirements.md` R7 and both halves of the research document.
- Country of origin: 19 CFR 134.45(b)–(c) gives the acceptable forms by example and by the test
  "unmistakably indicates", not as a list, so there is no table to load and building one means a
  judgement call per country. [Decision 0016](decisions.md#0016) records that it is not built, and why an
  unread form goes to a reviewer instead of being rejected.
- Brand's admissible set: three TTB-approved labels in the 38-label corpus carry a brand the application
  records somewhere other than its brand-name field, and the old comparison rejected all three.
  [Decision 0015](decisions.md#0015) records the change.

## NFR-3, the accessibility conformance level

**What moved.** NFR-3 said *"Every screen meets WCAG 2.2 level AA, read by a conformance review before
each release."* It now names **WCAG 2.0 level A and AA**, says that this is the level Section 508
requires, and names the automated scan alongside the conformance review as the way it is read.
`specs/0001-label-verification/requirements.md` R17 is corrected to match, and gains an acceptance
criterion for the automated scan it always had but never mentioned.

**What made it necessary.** The requirement promised a level nothing in the repository was built to
reach or could test. `tests/test_a11y_axe.py` requests the axe tags `wcag2a` and `wcag2aa` — WCAG 2.0
Level A and AA — so no run of the gate could ever fail against a 2.2 requirement, and R17 was a P1 that
nothing could hold. Section 508, 36 CFR part 1194 appendix A at E205.4 and E207.2, incorporates WCAG
**2.0** Level A and AA by reference, so the level now named is both what the gate scans and what the
regulation binds.

The stated reason for 2.2 also failed on inspection. `docs/reference/accessibility.md` gave 2.5.8
Target Size and 2.4.11 Focus Not Obscured as the criteria that justified the level; read against the
installed axe-core 4.11.4, the `wcag22aa` tag turns on one rule, `target-size`, and **no rule exists for
2.4.11 at any tag**. Settled in [decision 0031](decisions.md#0031), which also corrects
`docs/reference/accessibility.md` and `docs/approach.md` and records what the change gives up.

## FR-7, the result an unread country of origin gets

**What moved.** FR-7 said a label stating its origin in a form the product does not read "goes to a
reviewer rather than being rejected". It now says the label "is reported as needs review rather than
as a mismatch".

**What made it necessary.** The product rejects nothing and every label reaches the agent: SC-1 says
"The decision to approve or reject stays with the agent", and FR-11 names the three results the
product reports. The old wording described a product that decides.
