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

## FR-2, FR-3, FR-10, FR-14 and C-2, the product as built

**What moved.** Five statements that described a product other than the one built were rewritten to
describe it. `specs/0001-label-verification/requirements.md` R3, R10 and R14 follow.

1. **FR-2** said its list of six elements "is complete; it was read from the brief's Additional
   Context". The brief introduces that list as "common elements include", and the regulations for
   each beverage type decide which elements a label must carry. The new text says so and points to
   FR-3.
2. **FR-3** said any mandatory element absent from the label images is a mismatch. It now says a
   missing warning, and a missing country of origin on an import, are a mismatch, and any other
   mandatory element the reader does not find is needs review, because the reader not finding an
   element does not show that the label lacks it.
3. **FR-10** said the product names skew, poor light or glare on each check it sends to review for
   that reason. It now says a photograph too low in resolution or too blurred by camera movement is
   not checked at all, and the result names which of the two it is and says what a better photograph
   needs.
4. **FR-14** said sample submissions can be checked without supplying files. It now says the start
   page offers a sample pack to download, label images with the applications filed for them, checked
   through the same form as any other upload.
5. **C-2** said the product retains no label image or application data once it has returned the
   results. It now says what is kept: a batch's results in memory until the next batch starts, and on
   disk for seven days the uploaded image and each result stripped of every value read or declared.

**What made it necessary.** Each was the PRD describing a product the code does not build, settled
by a later decision the PRD never caught up with.

- FR-2: `docs/approach.md` already said the regulations, not the brief's list, set the checks; the
  PRD sentence contradicted it. The rule packs select by beverage type ([decision 0010](decisions.md#0010)).
- FR-3: every validator sends an element the reader did not locate to needs review
  (`app/rules/_validators/_helpers.py`, `not_read_result`), and only the warning rule sets
  `unlocated_is_absent` (`rules/common/health_warning.yaml`). An import with no origin statement was
  rejected under `ORIGIN.PRESENCE.MISSING` ([decision 0016](decisions.md#0016)) until
  [decision 0059](decisions.md#0059). A reader miss treated as absence rejected labels that carry the
  element.
- FR-10: the glare gate was removed because it turned away readable labels, and nothing measures
  skew or light ([decision 0026](decisions.md#0026)). The gates that remain, low resolution and camera
  blur (`app/vision/quality.py`), stop the whole label before any rule runs.
- FR-14: the sample buttons were retired when the batch began to carry its applications as a CSV,
  and the sample pack ships both halves ([decision 0043](decisions.md#0043)).
- C-2: the image store ([decision 0018](decisions.md#0018)), the value-stripped result store an
  override amends ([decision 0033](decisions.md#0033)) and one batch held until the next
  ([decision 0041](decisions.md#0041)). The old text was stricter than the brief asks — "We're not
  storing anything sensitive for this exercise" — and the README already stated the seven days.

## FR-7, a brand that differs only in punctuation

**What moved.** FR-7's brand paragraph said brand keeps punctuation and scores the difference, so "the
same dropped character in a short name falls into the review band". It now says a brand differing from
an allowed name only in punctuation or spacing is a match at any length and the finding names the
difference; that a mark standing for a word or a thing, or sitting between two digits, is part of the
name; and that the form's condition that a change not alter the meaning is not judged by the product.
`specs/0001-label-verification/requirements.md` R7 follows, and gains a criterion for the marks that
are part of the name. R7's first criterion also said Dave Morrison's "STONE'S THROW" against "Stone's
Throw" differs "in case and punctuation"; both keep the apostrophe, so it now says case.

**What made it necessary.** The old text described a result that depended on the name's length, and
the shipped comparison did worse than it said: "Os" against "O's" scored below the review floor and
was rejected. Form TTB F 5100.31, allowable revisions item 3.b, lets an approved label change "the
spelling (including punctuation marks …)" of its words without a new approval, with no condition on
length. It governs revisions to an approved label and is applied here by analogy, as the regulator's
own statement of which spelling differences are not a different label. The brief itself does not
decide punctuation; its example differs in case only. See [decision 0017](decisions.md#0017).
