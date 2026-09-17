# Accessibility: the WCAG 2.0 A and AA criteria this app must meet

Sources: WCAG 2.0, W3C Recommendation 11 December 2008, <https://www.w3.org/TR/WCAG20/>; WCAG 2.2,
W3C Recommendation 12 December 2024, <https://www.w3.org/TR/WCAG22/>; the Section 508 standards,
36 CFR part 1194 appendix A, <https://www.ecfr.gov/current/title-36/part-1194> (eCFR, current as of
2026-09-11). Read 2026-09-15; the target was corrected on 2026-09-16. Criterion text is verbatim from
WCAG 2.2, which restates the earlier criteria unchanged; exceptions are cut where marked "…".

## Why WCAG 2.0 A and AA

Section 508 requires WCAG **2.0** Level A and AA: "Electronic content shall conform to Level A and
Level AA Success Criteria and Conformance Requirements in WCAG 2.0" (E205.4), and for software and
web applications, "User interface components, as well as the content of platforms and applications,
shall conform to Level A and Level AA Success Criteria and Conformance Requirements in WCAG 2.0"
(E207.2). That is the level this app commits to, and it is the level the automated gate scans:
`tests/test_a11y_axe.py` runs axe-core with the tags `wcag2a` and `wcag2aa`. It covers two of the
three screens `app/api/ui/shells.py` serves — `/` and `/batch/{batch_id}`. `/batches` is not scanned
yet, so on that screen the requirement rests on review alone.

WCAG 2.2 AA was the stated target until 2026-09-16, on the grounds that it adds 2.5.8 Target Size and
2.4.11 Focus Not Obscured, which help the many users over 50. It is not adopted. Read against the
installed axe-core 4.11.4, the `wcag22aa` tag turns on exactly one rule, `target-size`, and **no rule
exists for 2.4.11 at any tag** — so a green run at 2.2 would have asserted a criterion it never
examined. [Decision 0031](../decisions.md#0031) records the choice, what it gives up, and the two
alternatives rejected.

Five criteria below arrived after WCAG 2.0, and they are design guidance here, not a conformance
claim. The three from WCAG 2.1 are built — 1.4.10 Reflow has its own test,
`tests/test_reflow_320px.py`. The two from WCAG 2.2 are **not verified**: nothing here has measured
2.5.8 Target Size, and no automated rule exists for 2.4.11 at all. Nothing the product promises
rests on any of the five.

WCAG 2.2 marks 4.1.1 Parsing "Obsolete and removed"; Section 508 still names WCAG 2.0, which includes
it.

## The criteria that bear on this app

"From" is the WCAG version the criterion first appeared in. The 2.0 rows are the promise. The 2.1
rows are built above it and not claimed; the 2.2 rows are guidance only and neither is verified.

| Criterion | From | Text | Where it bites here |
|---|---|---|---|
| 1.1.1 Non-text Content (A) | 2.0 | "All non-text content that is presented to the user has a text alternative that serves the equivalent purpose, …" | The uploaded label image; pass/fail icons |
| 1.3.1 Info and Relationships (A) | 2.0 | "Information, structure, and relationships conveyed through presentation can be programmatically determined or are available in text." | Result tables; form fields tied to labels |
| 1.4.3 Contrast (Minimum) (AA) | 2.0 | "The visual presentation of text and images of text has a contrast ratio of at least 4.5:1, …" (3:1 for large text) | All text, including status colours |
| 1.4.4 Resize Text (AA) | 2.0 | "Except for captions and images of text, text can be resized without assistive technology up to 200 percent without loss of content or functionality." | Layout at 200% zoom |
| 1.4.10 Reflow (AA) | 2.1 | "Content can be presented without loss of information or functionality, and without requiring scrolling in two dimensions for: Vertical scrolling content at a width equivalent to 320 CSS pixels; …" | Side-by-side label and results view. Held by `tests/test_reflow_320px.py` |
| 1.4.11 Non-text Contrast (AA) | 2.1 | "The visual presentation of the following have a contrast ratio of at least 3:1 against adjacent color(s): User Interface Components … Graphical Objects …" | Buttons, inputs, pass/fail badges |
| 2.1.1 Keyboard (A) | 2.0 | "All functionality of the content is operable through a keyboard interface without requiring specific timings for individual keystrokes, …" | Upload, batch list, result review |
| 2.4.7 Focus Visible (AA) | 2.0 | "Any keyboard operable user interface has a mode of operation where the keyboard focus indicator is visible." | Every control |
| 2.4.11 Focus Not Obscured (Minimum) (AA) | 2.2 | "When a user interface component receives keyboard focus, the component is not entirely hidden due to author-created content." | Sticky headers over batch lists. **No automated rule exists in axe-core 4.11.4 at any tag**, so this can only be caught by a person looking |
| 2.5.8 Target Size (Minimum) (AA) | 2.2 | "The size of the target for pointer inputs is at least 24 by 24 CSS pixels, except when: …" | All buttons and links. Never measured here — the `target-size` rule has not been run against this UI |
| 3.3.1 Error Identification (A) | 2.0 | "If an input error is automatically detected, the item that is in error is identified and the error is described to the user in text." | Bad file type, missing field |
| 3.3.2 Labels or Instructions (A) | 2.0 | "Labels or instructions are provided when content requires user input." | The application-data form |
| 3.3.3 Error Suggestion (AA) | 2.0 | "If an input error is automatically detected and suggestions for correction are known, then the suggestions are provided to the user, …" | Rejected uploads |
| 4.1.3 Status Messages (AA) | 2.1 | "In content implemented using markup languages, status messages can be programmatically determined through role or properties such that they can be presented to the user by assistive technologies without receiving focus." | "Checking…", batch progress, results ready |

Colour alone must not carry a pass or fail (1.4.1 Use of Color, WCAG 2.0 Level A, not quoted here).
Held by `tests/test_disposition_pill_wcag_141.py`.
