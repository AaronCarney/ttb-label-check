# PRD amendment record

One entry per change to the text of `PRD.md`: what moved, when, and what made it necessary.

## 2026-09-16 — FR-7, equivalent values

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
