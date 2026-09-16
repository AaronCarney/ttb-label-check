# Requirements: label verification

Built against `docs/PRD.md` while it reads `Status: draft`. Every entry below is provisional until the
PRD is approved.

## Brief coverage

Every ask in the brief (`PRD.md` in this folder) and its email (`brief-email.md`), and the PRD entry
that answers it. Complete as of 2026-09-15, read from both documents.

| Brief item | Source in the brief | Answered by |
|---|---|---|
| Label fields match the application: brand, class/type, alcohol content, net contents, name and address, country of origin | Additional Context; Sarah Chen | FR-1, FR-2 |
| Requirements vary by beverage type | Additional Context | FR-1, FR-3 |
| The warning is word for word | Jenny Park | FR-4 |
| "GOVERNMENT WARNING:" in capitals | Jenny Park | FR-5 |
| "GOVERNMENT WARNING:" in bold | Jenny Park | FR-6 |
| Judgement on trivial differences ("STONE'S THROW" against "Stone's Throw") | Dave Morrison | FR-7 |
| Results in about 5 seconds | Sarah Chen | NFR-1 |
| Batch uploads of 200-300 applications | Sarah Chen | FR-12, NFR-2 |
| Usable by a 73-year-old; "no hunting for buttons" | Sarah Chen | NFR-3, NFR-4, FR-8 |
| Imperfect photos: angle, lighting, glare | Jenny Park | FR-9, FR-10 |
| The agent keeps the judgement | Dave Morrison | SC-1 |
| Firewall blocks outbound traffic | Marcus Williams | C-4 |
| Standalone, no COLA integration | Marcus Williams | C-1 |
| Nothing sensitive stored | Marcus Williams | C-2 |
| User experience and error handling | Evaluation Criteria | FR-9, FR-13, NFR-4 |
| A working prototype Treasury can access and test | Deliverables; email | FR-14; the deployed URL (a deliverable, not a requirement) |
| README with setup and run instructions | Deliverables; email | S-3 |
| Approach, tools and assumptions documented; trade-offs and limitations documented | Deliverables; Evaluation Criteria | README (a deliverable) |
| Create or source test labels | Sample Label | S-1, S-2 |
| Azure after a FedRAMP migration; COLA built on .NET | Marcus Williams | No requirement. The README says how the prototype would move onto that ground |

## Checking a submission

### R1: Per-check results
**Implements**: FR-1
**Description**: A submitted application gets one result for every check that applies to its
beverage type.
**Acceptance criteria**:
- Given a distilled-spirits test submission, when it is checked, then a result is shown for each
  check that applies to distilled spirits and for no other check.
- Given a wine submission whose application states no alcohol content and whose label says "table
  wine", when it is checked, then no alcohol-content mismatch is reported for its absence.
- Given a malt-beverage submission whose application states no alcohol content, when it is checked,
  then no alcohol-content mismatch is reported for its absence.
**Priority**: P0

### R2: Label elements compared
**Implements**: FR-2
**Description**: Brand name, class/type designation, alcohol content, net contents, name and address,
and country of origin are each compared with the application where the application states them.
**Acceptance criteria**:
- Given each test submission, when it is checked, then every element its application states has a
  result, and the result agrees with the expected result in the test set.
- Given a submission whose application alcohol content differs from the label's, when it is checked,
  then alcohol content is reported as a mismatch.
**Priority**: P0

### R3: Missing mandatory element
**Implements**: FR-3
**Description**: A mandatory element absent from the label is reported.
**Acceptance criteria**:
- Given a submission whose label images lack an element mandatory for its beverage type, when it is
  checked, then that element is reported as a mismatch.
**Priority**: P1

## The warning

### R4: Warning wording
**Implements**: FR-4
**Description**: The label's warning is compared word for word with 27 CFR 16.21.
**Acceptance criteria**:
- Given a test submission with the exact warning, when it is checked, then the warning is a match.
- Given the variant with altered warning wording, when it is checked, then the warning is a mismatch.
- Given a label with no warning, when it is checked, then the warning is a mismatch.
**Priority**: P0

### R5: Warning heading in capitals
**Implements**: FR-5
**Description**: "GOVERNMENT WARNING" must appear entirely in capital letters.
**Acceptance criteria**:
- Given the variant with the heading in title case, when it is checked, then the heading is a
  mismatch.
**Priority**: P0

### R6: Warning heading in bold
**Implements**: FR-6
**Description**: The heading's bold type is reported, or needs review where it cannot be judged.
**Acceptance criteria**:
- Given a test submission with a bold heading, when it is checked, then the result is match or needs
  review, never mismatch.
**Priority**: P1

## Judgement and uncertainty

### R7: Equivalent values
**Implements**: FR-7
**Description**: Differences the matching rules treat as the same value are reported as a match.
**Acceptance criteria**:
- Given the variant whose application brand differs from the label only in case and punctuation
  ("STONE'S THROW" against "Stone's Throw"), when it is checked, then the brand is a match.
- Given a brand of "Stones Throw" against an application's "Stone's Throw", when it is checked, then
  the brand is a match, and the finding carries the similarity score the two reached (0.9846) so the
  reviewer sees the difference. The dropped apostrophe is a spelling change Form TTB F 5100.31
  item 3.b permits without a new approval; it is scored rather than ignored, so the same dropped
  character in a short name reaches the review band instead. See `docs/decisions.md#0017`.
- Given a brand mark of "BONEFISH" against an application whose brand-name field says "TACONIC
  DISTILLERY" and whose applicant block lists "BONEFISH (Used on label)", when it is checked, then
  the brand is a match and the finding names which declared value matched.
- Given a class/type of "Bourbon Whiskey" against an application's "Bourbon Whisky", when it is
  checked, then the class/type is a match.
- Given an alcohol statement of "45% Alc./Vol. (90 Proof)" against an application's "45%", when it is
  checked, then alcohol content is a match; with "(80 Proof)" instead, it is a mismatch.
- Given net contents of "75 cl" against an application's "750 mL", when it is checked, then net
  contents is a match.
- Given a name and address that differs from the application only by "Bottled by", the ZIP code and
  "California" against "CA", when it is checked, then name and address is a match.
- Given a country of origin of "Brasil" against an application's "Brazil", when it is checked, then
  country of origin is needs review, not a match and not a rejection. The check reads one form of
  the country's name — the English name the application declares — and reports that it could not
  settle anything else, because 19 CFR 134.45 gives the acceptable variants by a test
  ("unmistakably indicates") rather than as a table, and a wrong verdict on a real label is the one
  failure this product cannot have. See `docs/decisions.md#0016`.
**Priority**: P0

### R8: Values side by side
**Implements**: FR-8
**Description**: Every result shows what was read from the label beside the application value.
**Acceptance criteria**:
- Given any checked submission, when its results are shown, then each check shows both values.
**Priority**: P0

### R9: Needs review when unsure
**Implements**: FR-9
**Description**: An element that cannot be read with confidence is reported as needs review, not as
match or mismatch.
**Acceptance criteria**:
- Given a label image with an element made illegible, when it is checked, then that element is needs
  review.
**Priority**: P0

### R10: Image problems named
**Implements**: FR-10
**Description**: A needs-review result caused by glare, skew or poor light says so.
**Acceptance criteria**:
- Given the glare, skew and low-light variants, when each is checked, then any needs-review result
  names the image problem.
**Priority**: P2

### R11: Overall result
**Implements**: FR-11
**Description**: Each submission gets match, mismatch or needs review overall.
**Acceptance criteria**:
- Given a submission with one mismatch and the rest matches, when it is checked, then it is a
  mismatch overall.
- Given a submission with one needs review and the rest matches, when it is checked, then it is needs
  review overall.
**Priority**: P0

## Batches, errors and samples

### R12: Batch checking
**Implements**: FR-12
**Description**: A batch is checked in one upload and listed by overall result.
**Acceptance criteria**:
- Given a batch of the test submissions, when it is checked, then every submission is listed with
  its overall result, and opening one shows its check results.
**Priority**: P1

### R13: Plain error messages
**Implements**: FR-13
**Description**: A bad file or incomplete application data is named, with what to do, and the rest of
the batch still runs.
**Acceptance criteria**:
- Given a batch with one file that is not an image, when it is checked, then that file is named with
  an instruction and every other submission has results.
- Given a submission missing its brand name, when it is checked, then the missing field is named.
**Priority**: P0

### R14: Sample submissions
**Implements**: FR-14
**Description**: Sample submissions can be checked without supplying any file.
**Acceptance criteria**:
- Given a first visit to the start page, when a sample is chosen and checked, then its results are
  shown.
**Priority**: P0

## How well

### R15: Single-check latency
**Implements**: NFR-1
**Description**: Results within 5 seconds for 95% of single checks.
**Acceptance criteria**:
- Given the deployed product, when every test submission is checked once in sequence from a fresh
  browser session, then at least 95% show results within 5 seconds of pressing check.
**Priority**: P0

### R16: Batch time
**Implements**: NFR-2
**Description**: A 300-submission batch finishes within 10 minutes.
**Acceptance criteria**:
- Given a 300-submission batch built from the test submissions, when it is checked on the deployed
  product, then all results are shown within 10 minutes.
**Priority**: P1

### R17: Accessibility
**Implements**: NFR-3
**Description**: Every screen meets WCAG 2.2 AA.
**Acceptance criteria**:
- Given the release candidate, when a reviewer who did not build the UI runs the conformance review,
  then no level A or AA failure is recorded.
**Priority**: P1

### R18: Controls on the start page
**Implements**: NFR-4
**Description**: A single check needs no control that is off the start page or unlabelled.
**Acceptance criteria**:
- Given the start page, when a walkthrough checks one submission, then every control used is on the
  start page and labelled in words.
**Priority**: P1
