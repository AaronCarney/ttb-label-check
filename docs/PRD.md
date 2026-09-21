# ttb-label-check — Product Requirements

Status: draft

## 1. Purpose

TTB's compliance agents review about 150,000 label applications a year, and much of each review is
matching. By eye, an agent checks that the brand name, alcohol content and other fields printed on
the label artwork are the ones stated in the application, and that the Government Health Warning
Statement is present and exact. A simple application takes five to ten minutes. In peak season,
importers file hundreds at once, which are still reviewed one at a time. An automated pilot that
took 30 to 40 seconds per label was abandoned, because agents were faster by eye. The product is a
standalone prototype that checks a label against its application and tells the agent which fields
match, which do not, and which need a human look (brief, `specs/0001-label-verification/PRD.md`).

## 2. Glossary

- **Agent** — a TTB label-compliance specialist reviewing applications; the product's user.
- **Application data** — the values the applicant stated in the label application, which the label
  must match.
- **COLA** — Certificate of Label Approval: TTB's approval of a label, and the online system
  applications are filed through.
- **Label image** — a picture of label artwork submitted with an application. One application may
  have several, such as front and back.
- **Submission** — one application's data together with its label images.
- **Beverage type** — distilled spirits, wine, or malt beverage. It decides which label elements are
  mandatory.
- **Class/type designation** — the statement of what the beverage is, such as "Kentucky Straight
  Bourbon Whiskey".
- **Alcohol content** — the alcohol-by-volume statement on the label. Proof, where shown, is twice
  the alcohol by volume.
- **Net contents** — the statement of the volume in the container, such as "750 mL".
- **Name and address** — the statement of the bottler, producer or importer responsible for the
  product.
- **Warning** — the Government Health Warning Statement that 27 CFR 16.21 requires on every alcohol
  beverage container, word for word, with "GOVERNMENT WARNING" in capital letters and bold type
  (27 CFR 16.22).
- **Check** — one comparison: a label element against its application value, or the warning against
  the regulation.
- **Result** — the outcome of a check: match, mismatch, or needs review.
- **Batch** — several submissions checked in one upload.

## 3. Scope

**SC-1** — The product checks the label images of a submission against that submission's application
data, and against the federal labeling rules for the label elements the brief lists, and reports the
results to the agent. The decision to approve or reject stays with the agent.
`Because` — label review has nuance a matcher can miss, and the agents are the ones accountable for
the decision; the product exists to take the routine matching off them.

## 4. Constraints

**C-1** — The product exchanges no data with COLA or any other TTB system.
`Because` — COLA integration carries its own authorization requirements, and the prototype is meant
to inform a procurement decision before any integration is attempted.

**C-2** — The product writes no application data to disk. It keeps a batch's results in memory
until the next batch starts, and writes two things to disk, each swept at the first upload after
it is seven days old: the uploaded label
image, so a result page can show the label it describes, and each result stripped of every value
read from the label or declared in the application, so a reviewer's override has something to
amend (`docs/decisions.md#0018`).
`Because` — production use brings PII and document-retention obligations that a prototype is not
built to meet, and the exercise holds nothing sensitive; keeping only what a result page and an
override need, for a bounded time, keeps it clear of both.

**C-3** — The product is used through a web browser, with nothing to install on the agent's computer.
`Because` — agents' comfort with technology varies widely, and a tool that needs installing is one
more thing to fight with.

**C-4** — The product checks labels with no outbound network connection. Any external service it can
optionally use is named in its documentation, and none is required for it to work.
`Because` — the agency's firewall blocks outbound traffic to many domains, and an earlier pilot lost
half its features to blocked endpoints; IT can allow only what it knows about, and a product that
cannot run without an outbound call cannot run in the environment it is for.

## 5. Functional requirements

**FR-1** — When an agent submits one submission, the product reports a result for each check that
applies to the submission's beverage type.

**FR-2** — The product checks each of these label elements that the application states against the
label: brand name, class/type designation, alcohol content, net contents, name and address, and
country of origin. These are the common elements the brief's Additional Context lists; which of them
a label must carry is set by the regulations for its beverage type (FR-3).

**FR-3** — If a label element that is mandatory for the submission's beverage type is not found on
its label images, the product reports it. A missing warning is reported as a mismatch where the
product read the label's faces and found neither the heading "GOVERNMENT WARNING" nor the
statement's own wording; 27 CFR 16.30 bars approval of a label without it. Any other mandatory
element, including country of origin on an import, is reported as needs review, because the reader
not finding an element does not show that the label lacks it. For country of origin this is also
because the product reads only the English name, and cannot tell a label with no origin statement
from one that states it in another form 19 CFR 134.45 accepts. For every beverage type, brand
name, class/type designation, name and address, net contents and the warning are mandatory, and
country of origin is mandatory on imports. Alcohol content is mandatory on distilled spirits, and on
wine unless the wine is 14% alcohol by volume or less and its label says "table wine" or "light
wine". On malt beverages it is mandatory only when alcohol comes from added flavors or other
nonbeverage ingredients, which the application data does not record, so the product does not report
its absence as a mismatch.

**FR-4** — If the label's warning differs in wording from the text of 27 CFR 16.21, the product
reports a mismatch for the warning.

**FR-5** — If "GOVERNMENT WARNING" on the label is not entirely in capital letters, the product
reports a mismatch for the warning heading.

**FR-6** — The product reports whether "GOVERNMENT WARNING" on the label is in bold type, and reports
needs review where it cannot tell.

**FR-7** — If a label value differs from its application value only in a way the matching rules treat
as the same value, the product reports a match. Brand name, class/type designation, name and address
and country of origin are compared ignoring letter case, runs of spaces and line breaks, curly
against straight quotes, the ™, ® and © marks, and accents. Class/type, name and address and country
of origin also ignore punctuation. Class/type also treats "whisky" and "whiskey" as the same. Name
and address also ignores a "Bottled by"-style phrase, street, ZIP code, phone and website, and a
State name against its postal code.

Brand name is the exception: it does not ignore punctuation silently. Where the label's brand differs
from a name the application allows only in punctuation or spacing — "Os" against "O'S", "Stones Throw"
against "Stone's Throw", "Firestone" against "Fire Stone" — the product reports a match at any length,
and the finding names the difference. Form TTB F 5100.31, allowable revisions item 3.b, lets an
approved label change the punctuation of its words without a new approval; the form adds that the
change must not alter the meaning, which the product does not judge. A mark that stands for a word or
a thing — "&", "#", "@", "%" — is part of the name, and so is a mark between two digits. Any other
difference is scored, and a match needs 0.92. Brand is also compared against every name the
application says the label may carry, not its brand-name field alone. The product looks for those
names on the label; where it does not find one, it reports needs review and shows the text it
takes to be the brand. It does not report a brand mismatch, because nothing printed on a label marks
which text is its brand, so the product cannot be confident it compared the right text (FR-9).
See `docs/decisions.md#0017` and `docs/decisions.md#0015`.

Country of origin is read only as the English name the application declares, appearing as whole
words inside the label's wording. The abbreviations, adjectival forms, other-language names and
variant spellings 19 CFR 134.45 allows are not read; a label stating its origin in one of those
forms is reported as needs review rather than as a mismatch. See `docs/decisions.md#0016`.

Alcohol content and net contents are compared as numbers, net contents after converting units, and a
stated proof must equal twice the alcohol by volume. Where these rules cannot settle a difference,
the product reports needs review.

**FR-8** — For every check, the product shows the value it read from the label beside the application
value.

**FR-9** — For every check, the product establishes two things: that it read the text correctly, and
that the text it read is the element being checked. It reports a mismatch only where it is confident
of both. Where either falls short, it reports needs review, and the result says which of the two fell
short and for which element. A match may rest on the value itself: finding the application's value
on the label shows both. This is the three-way split of record linkage, where only a confident
comparison is decided and the rest goes to clerical review (Fellegi and Sunter, "A Theory for Record
Linkage", 1969); a reading's OCR score measures only the first of the two.

**FR-10** — If a label image is too low in resolution or too blurred by camera movement to read,
the product checks nothing on that label, names which of the two problems it found, and says in
plain words what a better photograph needs.

**FR-11** — The product gives each submission an overall result: match when every check matches,
mismatch when any check mismatches, and needs review otherwise.

**FR-12** — When an agent submits a batch, the product checks every submission in it and lists each
submission's overall result, with that submission's check results one step away.

**FR-13** — If a file is not a readable image, or a submission's application data is incomplete, the
product names the file or field at fault and says in plain words what to do, and checks the rest of
the batch.

**FR-14** — The start page offers a sample pack to download — label images together with the
applications filed for them — that anyone can check through the same form as their own labels,
with no account.

## 6. Non-functional requirements

**NFR-1** — 95% of single-submission checks show their results within 5 seconds of the agent
starting the check, read on the deployed product with the project's test submissions, whose correct
results are known.

**NFR-2** — A batch of 300 submissions shows all its results within 10 minutes, read on the deployed
product.

**NFR-3** — Every screen meets WCAG 2.0 level A and AA, the level Section 508 requires, read by
an automated scan on every screen and by a conformance review before each release.

**NFR-4** — Every control a single-submission check needs is on the start page and labelled in words,
read by a walkthrough before each release.

## 7. Success criteria

**S-1** — On the test submissions in `tests/fixtures/labels/`, the product's result agrees with the
expected result for at least 90% of checks, read by the evaluation run before each release.

**S-2** — No deliberately flawed test submission gets an overall result of match, read by the same
evaluation run.

**S-3** — Someone new to the project builds, tests and runs it from the README alone on a clean
clone, read by a clean-clone run before each release.
