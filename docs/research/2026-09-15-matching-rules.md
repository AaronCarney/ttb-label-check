# Which label-vs-application differences count as the same value

**Answer.** Only the health warning must match exactly, word for word and punctuation for
punctuation, with "GOVERNMENT WARNING" in capitals; line breaks are layout, so they are the only
difference it forgives. For the other fields the regulations themselves allow variation in how a value is
written: for distilled spirits and malt beverages mandatory information "may appear in all capital
letters, in all lower case letters, or in mixed-case" (27 CFR 5.52(d), 7.52(d)), and there are
permitted abbreviations for alcohol content, net contents units and State names. So brand name,
class/type, name and address, and country of origin are compared after normalising case, spacing
and quote style; alcohol content and net contents are parsed into numbers and units and compared as
numbers. Anything the normaliser cannot settle goes to a person as "needs review", never to an
automatic fail, because the brief's agents want judgement kept with them. TTB's own guidance points
the same way: an approved label may change "letters from upper case to lower case and vice versa",
punctuation and abbreviations without a new approval, provided "changes in spelling must not change
the meaning" (Form TTB F 5100.31, allowable revisions, item 3). But TTB also says the application's
brand name "must appear exactly as indicated on the label", so a case-only brand difference passes
and is still shown to the agent. The alcohol tolerances in
the regulations (±0.3 points and so on) do not apply here: they compare the label with the liquid,
while the app compares two declared values, which should be equal.

Sources read 2026-09-15: 27 CFR parts 4, 5, 7 and 16 and 19 CFR 134.45 on eCFR (current as of
2026-09-11), <https://www.ecfr.gov/current/title-27/part-5> and siblings, text in
[label-elements.md](../reference/label-elements.md) and [health-warning.md](../reference/health-warning.md);
the TTB guidance pages linked in the next section; the brief, <https://github.com/treasurytakehome-rgb/instructions> (copied in
`specs/0001-label-verification/PRD.md`).

## What the brief asks

- Dave Morrison: "the brand name was 'STONE'S THROW' on the label but 'Stone's Throw' in the
  application. Technically a mismatch? Sure. But it's obviously the same thing. You need judgment."
- Jenny Park: the warning "has to be **exact**. Like, word-for-word, and the 'GOVERNMENT WARNING:'
  part has to be in all caps and bold." She rejected one "where they used 'Government Warning' in
  title case instead of all caps."
- Sarah Chen: much of the work is "making sure the number on the form is the same as the number on
  the label."

## What the regulations say about variation

| Difference | Rule | Source |
|---|---|---|
| Letter case | Spirits and malt: any case allowed for mandatory information (aspartame statement excepted). Wine: part 4 is silent | 5.52(d), 7.52(d) |
| Warning case | "GOVERNMENT WARNING" must be capitals and bold; the rest not bold | 16.22(a)(2) |
| Alcohol wording | Three fixed formats, "must appear as shown" except "alc", "%", "/" for "by", "vol"; parentheses and periods optional (spirits, malt). Wine: "or similar appropriate phrase", "alc."/"vol." | 5.65(b), 7.65(b), 4.36(b) |
| Proof | Twice the ABV; optional; with the ABV in the same field of vision | 5.1, 5.65(b)(1)(i) |
| Net contents units | "liter", "litre", "L"; "ml.," "mL.," "ML."; centiliters and U.S. units only as an added equivalent (spirits). Malt: U.S. units required, metric optional | 5.70(a), 7.70 |
| Whisky spelling | "whisky" or "whiskey" | 5.143(b) |
| Extra words in class/type | Brief optional phrases such as "premium vodka" allowed; all words of the designation together | 5.52(b)(1), 5.141(d) |
| State names | Postal abbreviation allowed, e.g. "CA" | 5.66(d)(1), 5.68(b)(2), 7.66(c) |
| Address detail | Street, county, ZIP, phone, website optional | 5.66(d)(1), 7.66(c); wine street optional, 4.35(c) |
| Trade name | "identical with a name appearing on the basic permit" | 4.35(d); 5.66(g), 7.66(h) |
| Country name | Full English name; unmistakable abbreviations ("Gt. Britain") and variant spellings ("Brasil", "Italie") accepted | 19 CFR 134.45(a)–(b) |

## What TTB's guidance adds

- **Allowable revisions**, Form TTB F 5100.31 (04/2023), page 3, <https://ttb.gov/media/70320/download?inline=>;
  index page <https://www.ttb.gov/regulated-commodities/labeling/allowable-revisions>. "Once a label
  receives TTB approval, you are permitted to make certain changes to that label without submitting
  it to TTB." Item 3.b: "Change the type size and font, and make appropriate changes to the spelling
  (including punctuation marks, changing letters from upper case to lower case and vice versa, and
  abbreviations) of words, in". The published form's sentence stops at "in", both in its text and
  as printed. Item 3 comment: "All changes must comply with applicable regulations, and changes in
  spelling must not change the meaning of the previously approved information." Items 1 and 2 allow
  deleting non-mandatory information and repositioning any information, within placement rules.
  Item 19: a change of brand name needs a new application.
- **Brand name**, malt beverage label tool, <https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling/anatomy-of-a-malt-beverage-label-tool>
  (last updated November 12, 2025): "The brand name entered on the application must appear exactly
  as indicated on the label." No TTB rule on case or stylisation in brand matching was found.
- **Health warning**: "continuous", and other text may share the last sentence's line if separate
  and apart; see [health-warning.md](../reference/health-warning.md).
- **Beverage Alcohol Manual**: TTB marks both the spirits and malt volumes as "not been updated to
  be consistent with the current … labeling regulations", <https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/beverage-alcohol-manual>
  (last updated January 8, 2026), <https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/beverage-alcohol-manual>
  (last updated January 6, 2026). These rules therefore rest on the CFR, not the BAM.

## Normalisation used below

"Normalised" means, in this order: Unicode NFKC; curly quotes and apostrophes (’ ‘ “ ”) to straight
ones; case-fold; line breaks and runs of spaces to one space; trim; drop ™, ® and ©. Nothing else.
Punctuation other than quote style is kept, because dropping it can change a name.

## Proposed rule per field

| Field | Rule | Result | Reason |
|---|---|---|---|
| Government warning | **Exact.** Compare word sequence with the 16.21 text after collapsing line breaks and spaces only. "GOVERNMENT WARNING:" compared case-sensitively. Text after the last sentence on the same line is not part of the warning. Bold is reported as seen, or "needs review" if the image cannot show it | Any word, number or punctuation difference, a non-capital heading, or other text inside the statement: **fail** | 16.21 fixes the words; 16.22(a)(2) fixes the capitals; TTB says "continuous"; the brief says "exact" |
| Brand name | **Normalised equality** | Equal: pass, showing the difference if case differs. Differs only by punctuation or a likely misread: needs review. Otherwise: fail | 5.52(d) allows any case; allowable revision 3.b; the brief's "STONE'S THROW" example; TTB's "exactly as indicated" is why the difference stays visible |
| Class/type | **Normalised**, plus the listed equivalents (whisky/whiskey). If the application's words appear together inside a longer label designation ("premium vodka"), pass with a note | Other wording: needs review | 5.143(b), 5.52(b)(1), 5.141(d). Standards of identity are too many to encode as equivalents |
| Alcohol content | **Numeric equality** of ABV parsed from both; 45 = 45.0. If proof is shown, it must equal 2 × ABV. The label statement must fit a permitted format for its beverage type | ABV differs: fail. Proof ≠ 2 × ABV: fail. Format not recognised (for example "45% ABV" on spirits): needs review | 5.65, 7.65, 4.36, 5.1. Tolerances apply to the liquid, not this comparison |
| Net contents | **Numeric equality in one unit**: parse number and unit, accept the unit spellings in 5.70(a) and "ml", convert L, mL and cl by powers of ten | Same volume: pass ("750 mL", "750ml", "75 cl"; "75 cl" noted as an equivalent that needs the metric statement alongside on spirits). U.S. against metric units: pass only where the 4.37(b) table pairs them (750 mL = 25.4 fl. oz.), else needs review | 5.70(a), 4.37(b), 7.70 |
| Name and address | **Normalised**, ignoring the function phrase ("Bottled by"), optional detail (street, ZIP, phone, website) and State name vs postal code | Name differs after normalising: fail. Address differs only in detail: pass. Anything else: needs review | 5.66(d), 7.66(c), 4.35(c)–(d) |
| Country of origin (imports) | **Normalised against a list** of English names plus accepted abbreviations and variants | Not recognised: needs review | 19 CFR 134.45 |
| Required presence | Per beverage type (see [label-elements.md](../reference/label-elements.md)) | Required field absent: fail; optional field absent: pass | 4.32, 4.36(a), 5.63, 7.63 |

## Cases worked through

- "STONE'S THROW" vs "Stone's Throw": equal after case-folding. Pass, with the case difference shown.
- "Stone’s Throw" (curly) vs "Stone's Throw": equal after quote mapping. Pass.
- "Stones Throw" vs "Stone's Throw": punctuation differs. Needs review.
- "45% Alc./Vol. (90 Proof)" vs application "45%": ABV 45 = 45; proof 90 = 2 × 45; format uses "%",
  "alc", "/" and "vol" with periods, all permitted. Pass.
- "Alc. 45% by Vol." vs "45% Alc./Vol.": both 45. Pass.
- "750 mL" vs "750ml" vs "75 cl": all 750 mL. Pass.
- "Kentucky Straight Bourbon Whiskey" vs "Kentucky Straight Bourbon Whisky": listed equivalent. Pass.
- "Government Warning:" in title case: heading case differs. Fail, as in the brief.

## Open points

- Wine case: part 4 has no clause like 5.52(d). Applying the same case rule to wine is a judgement,
  supported by the brief's example; it is not stated in part 4.
- The warning's remainder in all capitals: 16.22 only rules the heading's case. Proposed: needs
  review, not fail.
- A fuzzy threshold for "likely misread" belongs in one place and should be set by measuring the
  extraction on real labels, not chosen here.
