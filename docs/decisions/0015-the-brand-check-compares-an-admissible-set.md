# 0015. The brand check compares an admissible set, not one string

Date: 2026-09-16

## Choice

The brand comparison no longer asks whether the label's mark equals the application's `brand_name`.
It asks whether the mark is **one of the names the application says the label may carry**:

- the brand the application declares;
- the fanciful name, where the application declares one;
- every trade name the application marks `(Used on label)` inside its free-text applicant block.

Four routes run against every one of those values, in order, and the finding names which value
matched and how:

| Route | What it establishes | Verdict it can reach |
|---|---|---|
| Exact | The two are the same once normalised | match |
| Whole words | One value's words sit inside the other's as a consecutive run | match |
| Score | Jaro-Winkler similarity of the two normalised strings | match, review, or mismatch by threshold |
| First letter | The score the two reach with a disagreeing first character dropped from both | **review only, never a match** |

Normalisation is what `docs/research/2026-09-15-matching-rules.md` specifies — NFKC, curly quotes
straightened, ™ ® © dropped, whitespace collapsed, trimmed, case-folded — plus one addition and
minus two subtractions:

- **Added: accents fold away.** The research says "nothing else", and this is the deliberate
  exception. A label printing `ŠVYTURYS` against an application's `SVYTURYS` scored 0.9167 and went
  to a reviewer, while the same two spellings were equal for the class-and-type check, which folds
  accents through shared normalisation. One engine gave two answers about one pair of strings.
- **Removed: the punctuation strip.** Punctuation is kept, because dropping it can change a name
  and, worse, hides the change: the check reported an *exact* match on a pair that differed, and the
  envelope told the reviewer the brand matched the application exactly.
- **Removed: the legal-suffix strip.** It cut `TACONIC DISTILLERY` to `taconic` and
  `SALTIRE RARE MALT WHISKY COMPANY` to `saltire rare malt whisky`. Those words are part of the
  name. The whole-words route covers the case the strip existed for — `Stone's Throw` against
  `Stone's Throw Distilling Co.` — without deciding in advance which words are disposable.

A name-and-address side effect of the same principle: a State written out and its two-letter postal
code are folded together in `name_address_match`, so "California" corroborates "CA" (PRD FR-7).

## Why

Three approved labels in the 38-label corpus carry a brand the application records somewhere other
than its `brand_name` field, and the old comparison rejected all three:

| Label | Label mark | Application `brand_name` | Where the application does say it |
|---|---|---|---|
| `ttb-26239001000079`, `ttb-26239001000081` | `BONEFISH` | `TACONIC DISTILLERY` | the applicant block ends `… 12581 BONEFISH (Used on label)` |
| `ttb-26233001000566` | `THE UGLY` | `UGLY SWEATER` | the declared brand itself, of which the mark is a run of whole words |

These are not near misses to be rescued with a looser threshold. In each, the application states in
writing that the label carries that name. The honest comparison is against the set of names the
application states, and the finding says which one matched — which is what a reviewer needs when
the mark on the bottle is not the brand field's wording.

The whole-words route is the same test `docs/decisions/0007` settled for class-and-type
designations, on the same helper, for the same reason: whole words rather than substrings, so "gin"
cannot match inside "Virginia". A leading definite article is dropped before the run is compared,
because an article is not part of a mark.

The first-letter route answers a different failure. `ttb-26238001000795` prints its brand as a
script logo reading `Gallo`; the registry record spells it `QALIO`. Jaro-Winkler scores that 0.7333
against a 0.85 review floor, so the check hard-rejected a label TTB approved. The prefix bonus that
makes Jaro-Winkler good at near-matches is zero whenever the first characters differ — exactly
backwards for this product, where a stylised first letter is the single most likely reading error.

## Alternatives rejected

- **Fold the first-letter variant into one score and take the maximum.** Measured: it makes `Gin`
  against `Din` a 1.0 — a clean match on a three-letter brand whose only distinguishing letter is
  wrong. Keeping the variant as a separate route that can only reach a reviewer says the true
  thing: these two spellings agree except at the character a stylised mark most often loses, so a
  person compares them.

  | Pair | Score | First-letter variant | Reported as |
  |---|---|---|---|
  | `Gallo` / `QALIO` | 0.7333 | 0.8667 | needs review |
  | `Gin` / `Din` | 0.7778 | 1.0000 | needs review, **not** a match |
  | `Zebra` / `Cobra` | 0.7333 | 0.8333 | mismatch |
  | `Acme` / `Bizmark` | 0.4643 | 0.5000 | mismatch |

- **Lower the review threshold instead.** A floor low enough to admit 0.7333 also admits `Zebra`
  against `Cobra`. The fix for a label whose name the application states elsewhere is to read where
  the application states it, not to make every comparison in the product blurrier.
- **Reverse both strings and take the better score, or add a common-affix bonus.** Both were
  measured at 0.76 for `Gallo` / `QALIO`, still below the floor. Jaro is invariant when both strings
  are reversed, so all either buys is the Winkler bonus on a one-character common suffix.
- **Resolve `ttb-26233001000566` through the trade-name list alone.** Its trade name is `UGLY
  WINES`; the label mark is `THE UGLY`. The best score against the whole admissible set is 0.88,
  short of the 0.92 a match needs. Whole-word containment is what settles it.
- **Put the State-name table in `rules/tables/` as a decision table.** The equivalence is lexical
  and belongs to one element, not a regulatory list, and it would need a `decision_table_ref` on
  three rules across three pack files.

## The costs, stated

- **A one-word mark that happens to be a word of a different brand passes.** `BOURBON` on a label
  against a declared `ACME BOURBON` is a match under the whole-words route. Nothing in the 38-label
  corpus does this.
- **A punctuation-only difference reports a match.** `Lucky Lucy's` against an application's
  `Lucky Lucys` scores 0.9833 and passes. Two of this project's own documents say it should report
  needs review — `specs/0001-label-verification/requirements.md` R7 and `docs/PRD.md` FR-7 — and the
  corpus answer key, `tests/fixtures/labels/manifest.json`, says it passes with no other outcome
  acceptable. The deciding source is TTB's own: Form 5100.31's allowable revisions, item 3.b,
  permits a label to change "the spelling (including punctuation marks, changing letters from upper
  case to lower case and vice versa, and abbreviations) of words" without a new approval, provided
  the change does not alter the meaning. A dropped apostrophe is that change. The two documents need
  their wording corrected to match; until they are, this record is the account of what the product
  does.

  What makes the disagreement smaller than it reads: the research's worry was that dropping
  punctuation can change a name, and the answer to that worry is to stop dropping it. Once
  punctuation is kept, a punctuation difference no longer produces a silent exact match — it
  produces a measured score, graded by how much of the name the difference is, and a message the
  reviewer sees. A short name losing a character falls into the review band on its own.
- **A city name can corroborate a State.** The State fold is applied to both sides, so an over-fold
  is symmetric — a city called Washington becomes "wa" in the label reading and in the application
  block alike. What remains is that a label naming a city could corroborate an application naming
  the same word as a State. The check it feeds never rejects, so the cost is a match a reviewer
  would have been asked about, not a wrong rejection.

## Constraint that decided it

Determinism first: the product should give the same answer for the same input and be able to show a
reviewer why. Every route above is an exact statement about two strings — they are equal, one
contains the other's words, they score this much, they agree after the first character — and every
one of them is named in the finding. A single blurrier threshold would have cleared the same three
labels while making the answer harder to defend and admitting pairs that are genuinely different
names.
