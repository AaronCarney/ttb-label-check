# Accessibility: the WCAG 2.2 AA criteria this app must meet

Sources: WCAG 2.2, W3C Recommendation 12 December 2024, <https://www.w3.org/TR/WCAG22/>; the
Section 508 standards, 36 CFR part 1194 appendix A, <https://www.ecfr.gov/current/title-36/part-1194>
(eCFR, current as of 2026-09-11). Read 2026-09-15. Criterion text is verbatim; exceptions are cut
where marked "…".

## Why WCAG 2.2 AA

Section 508 requires WCAG **2.0** Level A and AA: "Electronic content shall conform to Level A and
Level AA Success Criteria and Conformance Requirements in WCAG 2.0" (E205.4), and for software and
web applications, "User interface components, as well as the content of platforms and applications,
shall conform to Level A and Level AA Success Criteria and Conformance Requirements in WCAG 2.0"
(E207.2). WCAG 2.2 AA is the target because it adds criteria, among them 2.5.8 Target Size and
2.4.11 Focus Not Obscured, that help the many users over 50. WCAG 2.2 marks 4.1.1 Parsing "Obsolete and removed"; Section 508 still names WCAG
2.0, which includes it.

## The criteria that bear on this app

| Criterion | Text | Where it bites here |
|---|---|---|
| 1.1.1 Non-text Content (A) | "All non-text content that is presented to the user has a text alternative that serves the equivalent purpose, …" | The uploaded label image; pass/fail icons |
| 1.3.1 Info and Relationships (A) | "Information, structure, and relationships conveyed through presentation can be programmatically determined or are available in text." | Result tables; form fields tied to labels |
| 1.4.3 Contrast (Minimum) (AA) | "The visual presentation of text and images of text has a contrast ratio of at least 4.5:1, …" (3:1 for large text) | All text, including status colours |
| 1.4.4 Resize Text (AA) | "Except for captions and images of text, text can be resized without assistive technology up to 200 percent without loss of content or functionality." | Layout at 200% zoom |
| 1.4.10 Reflow (AA) | "Content can be presented without loss of information or functionality, and without requiring scrolling in two dimensions for: Vertical scrolling content at a width equivalent to 320 CSS pixels; …" | Side-by-side label and results view |
| 1.4.11 Non-text Contrast (AA) | "The visual presentation of the following have a contrast ratio of at least 3:1 against adjacent color(s): User Interface Components … Graphical Objects …" | Buttons, inputs, pass/fail badges |
| 2.1.1 Keyboard (A) | "All functionality of the content is operable through a keyboard interface without requiring specific timings for individual keystrokes, …" | Upload, batch list, result review |
| 2.4.7 Focus Visible (AA) | "Any keyboard operable user interface has a mode of operation where the keyboard focus indicator is visible." | Every control |
| 2.4.11 Focus Not Obscured (Minimum) (AA) | "When a user interface component receives keyboard focus, the component is not entirely hidden due to author-created content." | Sticky headers over batch lists |
| 2.5.8 Target Size (Minimum) (AA) | "The size of the target for pointer inputs is at least 24 by 24 CSS pixels, except when: …" | All buttons and links |
| 3.3.1 Error Identification (A) | "If an input error is automatically detected, the item that is in error is identified and the error is described to the user in text." | Bad file type, missing field |
| 3.3.2 Labels or Instructions (A) | "Labels or instructions are provided when content requires user input." | The application-data form |
| 3.3.3 Error Suggestion (AA) | "If an input error is automatically detected and suggestions for correction are known, then the suggestions are provided to the user, …" | Rejected uploads |
| 4.1.3 Status Messages (AA) | "In content implemented using markup languages, status messages can be programmatically determined through role or properties such that they can be presented to the user by assistive technologies without receiving focus." | "Checking…", batch progress, results ready |

Colour alone must not carry a pass or fail (1.4.1 Use of Color, Level A, not quoted here).
