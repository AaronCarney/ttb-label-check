# UX Design for Federal & Senior Users

**Project:** AI-powered TTB Alcohol Label Verification Prototype
**Decisions referenced:** The deterministic core (manual review always available; safe-failure = needs-review), per-field match policies (per-field evidence + CFR citation), the spirits ABV tolerance of ±0.3 pp, rejection reasoning (rule engine vs. LLM separation; reason_code grammar `BIN.SUB.SPECIFIC[.QUALIFIER]`)
**Upstream outputs consumed:** [T2](./2026-09-15-cola-operational-context.md) (workflow), [T3](./2026-09-15-rule-engine-architecture.md) (RejectionReason data model), [T4](./2026-09-15-ocr-vision-architecture.md) (vision layer + needs_better_photo taxonomy), [T5](./2026-09-15-llm-orchestration-architecture.md) (orchestrator), [T6](./2026-09-15-batch-processing-architecture.md) (operational shape), [T7](./2026-09-15-federal-deployment-compliance.md) (accessibility legal floor)
**Out of scope (deferred):** X-6 (cross-topic stakeholder demo synthesis) — Q8.8 covers only the T8-side demo path.

**Revisions:** corrected ABV tolerance worked example (±0.3 pp); standardized hover-reveal citation to WCAG 1.4.13 throughout; replaced verbatim USWDS principle list with general citation to the *Design Principles* page; consolidated keyboard model table to include `S`, `P`, `Shift+?`, `0`; resolved C-BboxOverlay ARIA role to a single `region`+`list`+`button` pattern (removed `role="application"` waffle); aligned demo Stage 5 narration with [T6](./2026-09-15-batch-processing-architecture.md) lookahead k=2–3.

**Primary sources cited throughout (canonical anchors):**
- Pernice, Estes & Nielsen, *UX Design for Seniors* (NN/g, 3rd ed.), nngroup.com
- USWDS *Design Principles* page (designsystem.digital.gov, USWDS 3.x)
- GDS Service Manual (gov.uk/service-manual); GOV.UK Design System (design-system.service.gov.uk); Home Office Accessibility "Dos and Don'ts" posters (Pun et al., 2016, accessibility.blog.gov.uk; UKHomeOffice/posters on GitHub)
- W3C WCAG 2.0/2.1/2.2 (w3.org/WAI/WCAG22); WAI-ARIA Authoring Practices Guide (w3.org/WAI/ARIA/apg)
- 36 CFR 1194 (Revised 508 Standards); section508.gov (ART tool, DHS Trusted Tester)
- Amershi et al., "Guidelines for Human-AI Interaction," CHI 2019 (microsoft.com/haxtoolkit)
- Bansal et al., "Does the Whole Exceed Its Parts?" CHI 2021
- Buçinca, Malaya & Gajos, "To Trust or to Think," CSCW 2021
- Bainbridge, "Ironies of Automation," *Automatica* 19(6), 1983
- Zerilli, Knott, Maclaurin & Gavaghan, "Transparency in Algorithmic and Human Decision-Making," *Philosophy & Technology* 32, 2019; Zerilli, Bhatt & Weller, "How Transparency Modulates Trust in AI," *Patterns* 3(4), 2022
- Fitts, "The Information Capacity of the Human Motor System," *J. Exp. Psychol.* 47(6), 1954; Hick, "On the Rate of Gain of Information," *QJEP* 4(1), 1952
- Sweller, *Cognitive Load Theory* (multiple)
- Owsley, Sekuler & Siemsen, "Contrast Sensitivity Throughout Adulthood," *Vision Research* 23, 1983
- Pirolli & Card, "Information Foraging," *Psychological Review* 106(4), 1999
- Federal Plain Language Guidelines (PLAIN, March 2011, Rev. 1 May 2011); Plain Writing Act of 2010; plainlanguage.gov
- NIST AI RMF 1.0 (Jan 2023) + AI 600-1 GenAI Profile (July 2024); ISO/IEC 42001:2023
- UK Algorithmic Transparency Recording Standard (ATRS, GDS/DSIT, 2021–2025); GSA *AI Guide for Government* (coe.gsa.gov)

---

## TL;DR

- **Build for Sarah's mother and Dave first; Jenny gets it for free.** A senior-comfortable, keyboard-first, high-contrast, low-motion UI is faster for the digital native too. The 73-year-old benchmark is a *ruling-out heuristic* — if the design fails for her it's wrong; if it passes, that's necessary, not sufficient.
- **The rule engine decides; the LLM disambiguates.** Every screen visibly distinguishes "rule says" from "AI suggested." Citations come from rule data, never from the model. This is the single trust lever Dave will judge us by.
- **Show the work, never auto-reject.** Three-state disposition (pass / fail / needs-review) with per-field evidence, CFR citation, four-channel confidence (number + band + color + shape), and a one-keystroke override path. On any orchestrator failure → needs-review, never fail.
- **One-at-a-time review with k=2–3 invisible lookahead.** Keyboard model with documented shortcuts and a calmed progress indicator. No modal interruptions; no hover-only reveals; no spinners without progress.
- **"Needs better photo" is a first-class outcome, not an error.** A calibrated "I don't know" is more trustworthy than a confident guess (Buçinca et al. 2021), and a templated applicant message saves Dave keystrokes back into COLAs Online.
- **Section 508 floor; WCAG 2.2 AA as best-practice ceiling.** Image-region viewer is fully keyboard-operable with ARIA-described regions; bbox color is *never* the only signal (shape + icon + numeric label); reflow to 320 CSS px without 2-D scroll; live regions `aria-live="polite"` for batch progress.
- **Three levels stay distinct.** Principles (DP*) explain *why*; patterns (IP*) explain *how we recur*; components (C*) are the *specific UI elements*. The cross-reference table below makes navigation explicit.

---

## Cross-reference table — Principles ↔ Patterns ↔ Components

| Principle (DP) | Patterns that instantiate it (IP) | Components used (C) |
|---|---|---|
| **DP1** Senior-comfort floor | IP-Density, IP-Keyboard, IP-Calm | C-DispositionPill, C-FieldCard, C-EvidencePanel |
| **DP2** Rule-first, LLM-secondary | IP-DualLayer, IP-AISuggestion | C-RuleVerdict, C-AISuggestionBlock, C-CitationChip |
| **DP3** Visible uncertainty | IP-Confidence, IP-NeedsReview | C-ConfidenceIndicator, C-DispositionPill |
| **DP4** Effortless override | IP-Override, IP-CalibrationView | C-OverrideDrawer, C-ReasonCodePicker |
| **DP5** Show the work, audit-trail by default | IP-Evidence, IP-RawReveal, IP-Provenance | C-BboxOverlay, C-EvidencePanel, C-RawJSONDrawer |
| **DP6** Honest failure modes | IP-NeedsBetterPhoto, IP-ErrorMessage | C-NeedsBetterPhotoCard, C-Alert, C-Toast |
| **DP7** Don't pace the user | IP-Calm, IP-ResumeState, IP-LiveRegion | C-QueuePosition, C-LiveRegion |

Reading guide: *"How is confidence shown?"* → IP-Confidence → C-ConfidenceIndicator → DP3 *Visible uncertainty*.

---

# Q8.1 — Design principles for an age-diverse, mixed-comfort user base

We translate research into seven concrete principles. Each is durable (does not change if a button changes), broad (applies across screens), and tested by both the Sarah's-mother and Jenny ends of the distribution.

The empirical floor: NN/g's *UX Design for Seniors* (3rd ed.) reports 87 guidelines from three rounds of usability research with 65–89-year-olds spanning ~19 years; that body of work plus middle-aged-user data shows a **0.8% per-year decline in web-task ability between ages 25 and 60** (NN/g, "Usability for Senior Citizens: Improved, But Still Lacking"). Owsley, Sekuler & Siemsen (1983) document contrast sensitivity loss starting between 40 and 50 at high spatial frequencies, broadening to all frequencies after 60 — a non-trivial fraction of ALFD's ~47 agents are inside that window. Fitts (1954) gives us movement time as a logarithmic function of distance and inverse target width; Hick (1952) gives us choice reaction time as a logarithmic function of equiprobable alternatives; Sweller's Cognitive Load Theory tells us that working-memory bandwidth, not screen real estate, is the binding constraint. USWDS publishes a small, durable set of design principles on its *Design Principles* page (designsystem.digital.gov/design-principles/) which our principles below are explicitly compatible with.

### DP1 — Senior-comfort floor (Sarah's-mother heuristic)

**Statement.** Every screen passes a "could a tech-cautious 73-year-old complete the primary action without help" test before any other refinement.
**Rationale.** This is a ruling-out heuristic, not a validation criterion. Half of ALFD is over 50; Owsley contrast-sensitivity data and NN/g motor-decline data both kick in in that range. Concretely: 16 px body text minimum (per [T7](./2026-09-15-federal-deployment-compliance.md)'s TTB-specific senior benchmark and NN/g's senior recommendations), 4.5:1 contrast for normal text (WCAG 1.4.3 / Revised 508 502), 24×24 CSS px target floor (WCAG 2.5.8 AA) and 44×44 enhanced (WCAG 2.5.5 AAA) for any primary action, and *no hover-only reveal* (WCAG 1.4.13 Content on Hover or Focus; Home Office Pun motor-disabilities poster).
**Implies.** Persistent navigation, generous tap targets, plain-language labels, no acronyms-without-gloss (NN/g, "Define Techy Words for Old Users"), reduced reliance on the mouse.
**Forecloses.** Hover menus; tooltip-only help; iconography without text labels; tightly-packed action clusters; thin 1-pixel borders; gray-on-gray typography.

### DP2 — Rule-first, LLM-secondary

**Statement.** The deterministic rule engine is the system's voice; the LLM is a labeled assistant whose output is visibly subordinate.
**Rationale.** Per rejection reasoning, rule citations are copied from rule data — never LLM-generated — and the LLM only disambiguates borderline brand-name matches, paraphrases reasoning text from templates, and chooses among multiple plausible OCR readings. Dave has watched modernization fail before; presenting the LLM as the primary decider reverses the trust gradient he uses. Zerilli, Bhatt & Weller (*Patterns*, 2022) show that perceived AI competence is repaired faster when the system distinguishes its mechanical from its inferential contributions.
**Implies.** Two-layer evidence display: a "Rule says" verdict block above an "AI suggested" block (only when the LLM contributed). Citations are first-class, not footnotes.
**Forecloses.** Unattributed model "explanations"; chat-style natural-language verdicts that conflate rule and inference; LLM-generated CFR references.

### DP3 — Visible uncertainty (the AI never auto-rejects)

**Statement.** Every fail/needs-review surfaces calibrated confidence in *four* parallel channels (number, band, color, shape), and the safe-failure mode is always "needs review."
**Rationale.** Bansal et al. (CHI 2021) show that team accuracy improves only when humans can read AI confidence and explanations together — confidence alone or explanations alone don't reliably produce complementarity. WCAG 1.4.1 forbids color-only conveyance. The deterministic core forbids automatic rejection: orchestrator failure → needs-review, with a reason.
**Implies.** Confidence must reconcile a numeric score (e.g., 0.87), a band (high/medium/low), a color band (within an accessible palette), and a shape/pattern (filled / striped / outlined). On any orchestrator path failure, fall through to needs-review with a code, never to "fail."
**Forecloses.** Probability bars rendered in red-yellow-green only; "AI is X% sure" without a band-level summary; auto-reject decisions of any kind.

### DP4 — Effortless override

**Statement.** The cost of overriding the system approaches zero, and the act of overriding feels empowered, not adversarial.
**Rationale.** Bainbridge ("Ironies of Automation," 1983) shows that when humans become passive monitors, they get worse, not better, at the override moment. Buçinca et al. (CSCW 2021) confirm that without cognitive forcing, users develop "follow-the-AI" heuristics. The fix is to make disagreement structurally cheap and to capture it as data. The HAX guidelines (Amershi et al. CHI 2019) — specifically G8 ("efficient dismissal"), G15 ("encourage granular feedback"), G17 ("provide global controls") — point in the same direction.
**Implies.** Per-field, per-label, and batch-level override surfaces; structured reason code (controlled vocabulary aligned to the [T3](./2026-09-15-rule-engine-architecture.md) reason_code grammar); a single keystroke (`O`) opens the override drawer and pre-selects the most likely reason. Override is logged with agent identity and timestamp; in production, it feeds a "training-data candidate" flag.
**Forecloses.** Multi-step override modals; required free-text justification on every disagreement; "are you sure?" interstitials.

### DP5 — Show the work; audit-trail by default

**Statement.** Every disposition exposes what was checked, what passed, what failed, and what was *not* checked, with single-click access to raw evidence.
**Rationale.** ALFD agents are regulators; audit-trail expectation is structural, not preferential. Pirolli & Card (1999) on information foraging tells us that information scent — proximal cues to the value of an information patch — drives forager efficiency; agents need the scent of evidence, not the evidence dumped on them. Sweller's CLT says: layer it. The HAX guideline G11 ("Make clear why the system did what it did") is the operational form.
**Implies.** Default-visible per finding: human_message, severity icon, CFR citation (clickable to full text), confidence band, bbox link. Behind one click: reason_code, rule_id, rule_set_version, model_version, timestamp. Behind a "raw" toggle: full RejectionReason JSON, the orchestrator prompt and output (when LLM contributed), full vision-response envelope.
**Forecloses.** Black-box AI verdicts; a single confidence number with no provenance; "trust us" UI.

### DP6 — Honest failure modes

**Statement.** When the system can't decide, it says "I can't decide, here's why" — never "I decided, sort of."
**Rationale.** Buçinca et al. (CSCW 2021) and the broader AI-abstention literature show that calibrated incompetence builds trust faster than confident error. [T4](./2026-09-15-ocr-vision-architecture.md)'s first-class `needs_better_photo` disposition (with reason taxonomy: low_resolution, blurred, glare_obscures_content, orientation_not_recoverable, label_partially_occluded, multiple_labels_in_one_image) is the right pattern; Q8.6 develops it.
**Implies.** Needs-review and needs-better-photo cards have their own visual treatment, distinct from fail. Error messages obey Nielsen's heuristic #9 (recognize, diagnose, recover) and the Federal Plain Language Guidelines (PLAIN 2011): plain language, precise problem identification, suggested recovery.
**Forecloses.** Auto-rejection of ambiguous cases; error codes without text ("Error 4017"); "Something went wrong, please try again."

### DP7 — Don't pace the user

**Statement.** Progress indicators *inform*; they don't shame.
**Rationale.** GDS Service Manual ("Making your service more inclusive") explicitly cautions against time pressure; Home Office Pun posters warn against rushing users. NN/g progress-indicator guidance is that pacing creates abandonment in low-confidence users. Dave's bar — "don't make my life harder" — fails the moment the UI starts a countdown.
**Implies.** "Label 47 of 312" surfaces position, not pace. Estimated-remaining-time uses a calmed phrasing ("at your current pace, ~4 hours" rather than "you must finish in 4 hours"). No flashing banners, no visual countdown timers. Animations respect `prefers-reduced-motion` (WCAG 2.3.3).
**Forecloses.** Countdown timers on per-label review; "your queue is overdue" red banners; auto-advance after N seconds without explicit agent confirmation.

---

# Q8.2 — Trust-establishment patterns for AI-assisted workflows

The user we are designing trust *for* is Dave, the 28-year senior agent who watched the 2008 phone tree fail and the scanning vendor pilot fail. Trust here is not "the AI is right"; it is "the system tells me when it can't be sure, makes my override costless, and does the rote work without surprising me." Five trust patterns operationalize this.

### IP-DualLayer — The "Rule says / AI suggested" split (instantiates DP2, DP5)

**Composing principles:** DP2, DP5.
**Components:** C-RuleVerdict, C-AISuggestionBlock, C-CitationChip.
**The pattern.** Every finding has a primary verdict block headed "Rule says" with the deterministic rule outcome and CFR citation, copied verbatim from rule data. Where the LLM contributed (borderline brand-name disambiguation; paraphrased reasoning text; chosen-among-OCR-candidates), a visually subordinate "AI suggested" block sits *below* the rule block, labeled with the model identifier and a "why this is here" link.
**Worked example.** STONE'S THROW Bourbon (application) vs. "Stone's Throw" (label OCR). The rule engine fires `BRAND_NAME.MISMATCH.NEEDS_REVIEW` (Jaro-Winkler 0.94, deterministic threshold 0.92–0.97 = borderline). The C-RuleVerdict block reads: *"Borderline brand-name match (Jaro-Winkler 0.94). 27 CFR §5.65(a)(1). Disposition: needs review."* Below, the C-AISuggestionBlock reads: *"AI suggested: STONE'S THROW and Stone's Throw differ only in capitalization and apostrophe positioning, which are routine typographic variants for this brand class. Recommend pass. (Model: gpt-4o-mini, prompt v3.1, view raw)."* The agent reads the rule first, the AI second, and one keystroke on `A` accepts the AI suggestion or `O` opens the override drawer.
**Citation.** HAX G1, G2, G11; Zerilli, Bhatt & Weller (*Patterns*, 2022) on transparency modulating trust; Bansal et al. CHI 2021 on the necessity of *both* confidence and explanation for complementary performance.

### IP-Confidence — Four-channel calibrated confidence (instantiates DP3)

**Composing principles:** DP3, DP1.
**Components:** C-ConfidenceIndicator, C-DispositionPill.
**The pattern.** Confidence renders simultaneously as a numeric score (0–1), a band label ("high"/"medium"/"low"), an accessible color, and a shape/pattern (solid / striped / outlined bar). The numeric is shown by default at one decimal precision (e.g., "0.87 — medium"). Click or keyboard focus on the indicator reveals the per-component confidences (OCR, rule-match, LLM-disambiguation if any) — but hover is never the *only* path; per WCAG 1.4.13 the same content is reachable via click and persistent focus.
**Worked example.** A government-warning-line OCR finding shows `0.78 — medium` next to a striped amber band with a `?` icon; tab-focusing it expands to "OCR confidence 0.91; rule-pattern match 0.78 (the word 'warning' is title-cased rather than upper-case)."
**Citation.** WCAG 1.4.1 (use of color), 1.4.3 (contrast), 1.4.13 (content on hover or focus); HAX G2 ("Make clear how well the system can do what it can do"); Bansal et al. CHI 2021; NN/g, "Designing AI Products and Features."

### IP-Override — Costless disagreement (instantiates DP4)

**Composing principles:** DP4, DP5.
**Components:** C-OverrideDrawer, C-ReasonCodePicker, C-RawJSONDrawer.
**The pattern.** `O` opens an override drawer keyed to the currently focused finding. The drawer pre-selects the inverse disposition (e.g., if rule said "fail," it offers "pass" and "needs-review"); the agent confirms with `Enter`. A controlled-vocabulary reason-code picker (aligned to the [T3](./2026-09-15-rule-engine-architecture.md) reason_code grammar) is required; free-text note and attachment are optional. The override is stamped with agent identity and timestamp. In the prototype, no persistent storage; in production, an override is flagged as a training-data candidate (per Q8.4).
**Worked example.** Rule fires `ABV.SPIRITS.OUT_OF_TOLERANCE` because the label says **40.5% ABV** and the application says **39.8% ABV** (delta 0.7 pp, exceeds the spirits tolerance of ±0.3 pp). The agent recognizes this submitter's history of late re-blending bringing actual ABV up before bottling, with paperwork already filed. `O` → drawer opens with the inverse disposition options ("pass" and "needs-review") → agent picks reason code `ABV.SPIRITS.OUT_OF_TOLERANCE.OVERRIDE_DOCUMENTED_REBLEND` and disposition "needs-review" (not pass — the override sends it for supervisor confirmation, not auto-approval) → `Enter`. Total cost: three keystrokes.
**Citation.** Bainbridge (1983); HAX G8 (efficient dismissal), G15 (granular feedback), G17 (global controls); Buçinca et al. CSCW 2021 (cognitive forcing) — note we deliberately *don't* add forcing friction to the override path; the forcing friction is in the *initial AI agreement* path (see IP-DualLayer). The spirits ABV tolerance of ±0.3 pp.

### IP-NeedsReview — Honest abstention as default failure (instantiates DP3, DP6)

**Composing principles:** DP3, DP6.
**Components:** C-DispositionPill (needs-review variant), C-NeedsBetterPhotoCard.
**The pattern.** Three-state per-label disposition (pass / fail / needs-review) is the legal floor; on *any* orchestrator failure the safe-failure mode is needs-review with a structured reason code (`ORCHESTRATOR.TIMEOUT`, `ORCHESTRATOR.LLM_API_FAILURE`, `VISION.NEEDS_BETTER_PHOTO.GLARE`, etc.). The needs-review pill is amber, outlined, with a `?` icon and the text "Needs review" — never auto-converted to fail, never silently dropped to pass.
**Worked example.** Orchestrator times out after 5s on label 47. The system surfaces a needs-review card with the reason `ORCHESTRATOR.TIMEOUT` and a "retry" affordance, plus the human-message "We couldn't finish checking this label in time. Try again, or review manually." The agent has full manual control.
**Citation.** The deterministic core; [T4](./2026-09-15-ocr-vision-architecture.md) needs-better-photo taxonomy; Buçinca et al. CSCW 2021 on AI abstention building trust; HAX G10 ("Scope services when in doubt").

### IP-Provenance — Audit-trail by default (instantiates DP5)

**Composing principles:** DP5, DP2.
**Components:** C-CitationChip, C-RawJSONDrawer, "More detail" disclosure.
**The pattern.** Every finding's CFR citation is a clickable chip that opens the relevant rule text inline (cached) — never a popup, never a new tab unless the agent middle-clicks. The "more detail" disclosure (Q8.11) reveals reason_code, rule_id, rule_set_version, model_version, timestamp. A "raw" toggle reveals the full structured RejectionReason and, where the LLM contributed, the orchestrator prompt + output and full vision-response envelope. This mirrors the UK ATRS template's tier-1/tier-2 structure (gov.uk/algorithmic-transparency-recording-standard) — public-facing summary on top, technical detail below — applied to a per-finding level.
**Worked example.** A government-warning fail has the citation chip "27 CFR §16.22(a)(2)"; clicking expands the regulation text in a side panel. "More detail" reveals reason_code `GOVERNMENT_WARNING.FORMAT.CAPS_REQUIRED`, rule_id `gw-fmt-caps-001`, rule_set_version `2026-Q1.3`, OCR raw confidence 0.91. "Raw" reveals the JSON.
**Citation.** Per-field match policies; UK ATRS (gov.uk, 2024-mandatory); NIST AI RMF GOVERN-1.4 (transparent policies); HAX G11.

---

# Q8.3 — Evidence display patterns

For each label the UI must surface: pass/fail/needs-review disposition; per-field evidence (extracted text, image region/bbox, expected value); rule citation; confidence. Four candidate patterns are evaluated.

### Comparison

**1. Card-per-field layouts (Stripe-style, Atlassian Compass).**
*Where it shines.* Discrete findings; each card carries its own context; easy to add/remove findings without disrupting the rest.
*Where seniors struggle.* If cards stack densely below the fold, scrolling becomes a navigational tax (NN/g senior-research finding: scrolling fatigue + "where am I?"). Cards-only loses spatial grounding to the underlying image.
*Cognitive load (Sweller).* Low intrinsic load per card; high extraneous load if cards lack a stable order or if findings are duplicated across cards.

**2. Annotated-image overlays (bboxes drawn on the image, linked to side-panel cards).**
*Where it shines.* Spatial grounding — "this region of this label" is the agent's actual mental model. Maps directly to [T4](./2026-09-15-ocr-vision-architecture.md)'s bbox + region taxonomy.
*Where seniors struggle.* If overlays use color alone (red bbox) or hover-only reveal, fails WCAG 1.4.1 / 1.4.13 and Pun's motor-disability poster. Image zoom on a small bbox requires fine-motor mouse precision (NN/g touch-target / mouse-precision findings).
*Cognitive load.* Low if overlays are clearly numbered and linked to side cards; high if overlays multiply without an index.

**3. Side-by-side diffs (form data left, OCR-extracted right).**
*Where it shines.* When the application form and the label disagree, a textual diff is the most precise representation. Especially good for ABV-mismatch and brand-name-mismatch.
*Where seniors struggle.* Diff coloring is often the only signal (red/green); reading two narrow columns side-by-side is hostile to presbyopic vision (Owsley et al. 1983 on contrast sensitivity at high spatial frequencies). Reflow on a small viewport (WCAG 1.4.10) is hard.
*Cognitive load.* Moderate — but it concentrates load at the moment the agent most needs to think (the disagreement).

**4. Progressive disclosure (summary → details → raw).**
*Where it shines.* Scales gracefully across simple and complex cases; respects information foraging (Pirolli & Card 1999) by surfacing high-scent cues first.
*Where seniors struggle.* NN/g progressive-disclosure guidance specifically warns: hidden content can be missed, especially when the cue to expand is low-contrast or dependent on hover. Multi-level accordions amplify the problem.
*Cognitive load.* Low at default, low under load, but each extra level of disclosure is a navigational cost (Hick-Hyman: choice complexity grows logarithmically with options).

### Recommendation — composite hierarchy

We **adopt all four**, layered:

1. **Top-of-page summary ribbon** (always visible). Overall disposition pill + counts: "1 fail, 3 needs-review, 12 pass." Implements C-DispositionPill at label-level and a `<output role="status">` summary.
2. **Left pane: image with annotated overlays** (the C-BboxOverlay component). Bboxes are *numbered* (1, 2, 3…) in CFR-citation order, with shape + color + icon as triple-redundant signals.
3. **Right pane: per-field cards in CFR-citation order** (the C-FieldCard component). Each card's number matches its bbox's number; the card carries C-RuleVerdict + C-AISuggestionBlock + C-ConfidenceIndicator + C-CitationChip.
4. **Within each card, "more detail" disclosure** for reason_code, rule_id, rule_set_version, model_version, timestamp.
5. **A single "Raw evidence" toggle** at the bottom of the right pane that reveals full structured RejectionReason JSON, orchestrator I/O, vision envelope.
6. **Side-by-side diff** is reserved for the *one* finding type where it dominates: brand-name-mismatch and ABV-mismatch. In those cards the textual diff is *inside* the card, not its own pane.

**Justification.** This hierarchy passes Sarah's "no hunting for buttons" criterion (the summary ribbon is the first thing the agent sees; the right-pane cards are in CFR order, not in some priority-by-LLM order) and Dave's "don't fight the system" criterion (image and text co-located; one keystroke from anywhere to override; raw evidence one click away when needed). Pirolli & Card's information-scent argument is satisfied by surfacing the highest-value cues at default visibility, and Sweller's CLT is respected by deferring intrinsic-load-heavy artifacts (raw JSON, full prompts) to opt-in disclosure.

### Bbox overlay design specifics

These specs are non-negotiable; they are the most-likely accessibility regression points.

- **Triple-redundant disposition signal.** Color is *not* enough (WCAG 1.4.1 / Revised 508 410). Bboxes encode disposition four ways: stroke style (**solid for fail, dashed for needs-review, dotted-or-thin for pass**), an adjacent icon (✗ / ? / ✓), a numeric label, and color (red/amber/green within an accessible 4.5:1 contrast palette).
- **No hover-only reveal.** WCAG 1.4.13 (Content on Hover or Focus) requires that any content triggered by hover also be triggerable by keyboard focus and remain dismissible without moving pointer/focus, and Pun's motor-disability poster reinforces this. The interaction model is **click-to-pin**: clicking a bbox highlights both the bbox and its corresponding right-pane card; clicking again unpins. Keyboard-tabbable: Tab enters the image region, arrow keys cycle bboxes, Enter pins, Esc exits.
- **Image zoom is keyboard-operable.** `+` and `−` zoom; arrow keys pan when zoomed; `0` resets. Each step announces via `aria-live="polite"`: "Page zoom 200%, focus on government warning region (bbox 3 of 7)."
- **Reflow.** On viewports < 768 px CSS, the image+evidence pair collapses to stacked (image top, cards below) — WCAG 1.4.10 reflow at 320 CSS px without two-dimensional scrolling.
- **Multi-bbox indexing.** When more than ~6 bboxes are present, bboxes outside the current viewport zoom show as "off-screen" indicators in a strip (per the NN/g view-tap asymmetry findings — visible cues at full size).

---

# Q8.4 — Manual override interaction design

The deterministic core makes manual review path always available. The override pattern operationalizes that.

### Override surfaces (three levels)

- **Per-field override.** Override a single finding without changing the overall label-level disposition. Use case: rule fires `ABV.SPIRITS.OUT_OF_TOLERANCE` for a documented re-blend, but the rest of the label is correct. Keystroke: `O` while a field card is focused.
- **Per-label override.** Change the overall pass/fail/needs-review disposition. Use case: agent disagrees with an aggregated label-level decision. Keystroke: `Shift+O` from the label-level disposition pill.
- **Batch-level action (not a per-finding override).** "Send all needs-review back to the applicant," "request better photos for all flagged labels," "ask supervisor on all needs-review." This is a workflow shortcut, not a verdict override.

### Metadata captured on every override

Required (controlled vocabulary):
- `override_action` — one of `pass`, `fail`, `needs_review`.
- `reason_code` — selected from the [T3](./2026-09-15-rule-engine-architecture.md) grammar (`BIN.SUB.SPECIFIC[.QUALIFIER]`), filtered by current finding's bin. The picker pre-suggests the most common 2–3 codes for the bin; type-ahead reveals the full vocabulary.
- `agent_id` and `timestamp` — stamped automatically.
- `original_disposition` and `original_reason_code` — preserved for audit.

Optional:
- `note` — free-text, plain-language. The picker hint says "Why are you overriding? (optional)" — never required.
- `attachment` — file upload (a screenshot of an internal regulatory note, etc.).

### Does override feed back?

In the **prototype**: no persistent storage (per gaps doc). Overrides are session-local; surface this honestly to the agent as "Overrides in this session won't be saved." This is part of trust — the prototype doesn't pretend.

In **production**: every override carries a `training_data_candidate: bool` flag, defaulted by reason_code (e.g., `BRAND_NAME.MISMATCH.NEEDS_REVIEW.OVERRIDDEN_TO_PASS` is a candidate; `ABV.SPIRITS.OUT_OF_TOLERANCE.OVERRIDE_DOCUMENTED_REBLEND` is a curated rule-tuning signal, not training data). Supervisors curate.

### Supervisor calibration view

A separate supervisor screen shows where agents disagree with the system most, broken down by:
- `reason_code` (which rules are most-overridden)
- `confidence_band` (does the system over-trust at "high"? under-flag at "low"?)
- `agent` (cross-agent consistency — does Dave override `BRAND_NAME.MISMATCH.NEEDS_REVIEW` 3× more than Jenny?)
- `time-bucket` (week-over-week drift)

This view directly serves NIST AI RMF 1.0 GOVERN-1.5 (ongoing monitoring and periodic review of the risk management process and outcomes), GOVERN-1.7 (decommissioning), and the AI 600-1 GenAI Profile MEASURE-2 actions on bias and reliability evaluation. ISO/IEC 42001:2023's continual-improvement clause is the management-system equivalent. The calibration view is the artifact the rule-tuning team and Sarah use jointly.

### Avoiding both over-reliance and under-reliance

Bansal et al. (CHI 2021) and Buçinca et al. (CSCW 2021) converge on the same finding: simply showing AI confidence and explanations does *not* reliably reduce over-reliance. We address it three ways:

1. **Cognitive forcing on initial AI agreement, not on override.** When the AI agrees with the rule, the agent reviews the evidence anyway because the four-channel confidence and citation chip put it on the page; the AI's answer is not the loud part. When the AI disagrees with the rule (the borderline brand-name case), the AI's reasoning sits visibly *below* the rule's verdict, so the agent has to read both before pressing `A` or `O`.
2. **Override is structurally cheap, not free.** Three keystrokes (O → reason → Enter) is cheap; "free" would be one keystroke and would invite rubber-stamping in the *other* direction.
3. **Calibration view as the org-level check.** If an agent overrides at 95% the same way the AI suggests, the calibration view flags it for the supervisor.

---

# Q8.5 — Batch review interaction design

[T6](./2026-09-15-batch-processing-architecture.md) establishes ~150,000 COLAs/year, ~5–10 minutes per simple application, 5-second SLA per single-label review, and peak batches of 200–500 labels. Throughput is human-bound (P/R << 1); lookahead k=2–3 keeps the agent saturated. ALFD work is queued by beverage class (wine office vs. spirits/malt office); "Needs Correction" resubmissions take priority.

### One-at-a-time as primary, batch dashboard as secondary

**Recommendation: one-at-a-time review** with k=2–3 invisible lookahead, plus a secondary "batch dashboard" for triage and skip-ahead. Rationale: at 5–10 minutes per simple application and a 5-second SLA on initial classification, the cognitive bottleneck is the *current* label, not the queue. Parallel-grid review forces working-memory thrashing across labels (Sweller); one-at-a-time lets the agent commit to a single mental context. The batch dashboard is for triage decisions ("which labels in this batch are needs-review?"), skip-ahead, and bulk actions — not the primary review surface. This pattern matches Snorkel Flow's and Prodigy's labeling-tool UX (single-item primary view, dataset overview secondary).

### Queue-position display — calmed

The default reads: **"Label 47 of 312 — paced view: ~4 hours remaining."** "Paced view" is an opt-in preference, off by default for new agents. Don't pace the user (DP7; GDS Service Manual; NN/g progress-indicator guidance). Alternatives the agent can switch to:

- **Position only.** "47 / 312" — no time projection.
- **Batch progress bar without time.** A simple bar with current position.
- **Off.** Some agents (Dave) prefer no pacing at all; honor that.

Color cues are calming, not urgent (cool blue/green progress, not red/amber). Reduced motion is honored (`prefers-reduced-motion` → static bar, no animation).

### Keyboard model (complete)

The agent will live on the keyboard. Single-letter mnemonics that don't conflict with screen-reader virtual keystrokes (per WAI-ARIA Authoring Practices "Developing a Keyboard Interface" guidance on shortcut conflicts):

| Key | Action | Mnemonic source |
|---|---|---|
| `J` | Next label | Gmail/Vim convention |
| `K` | Previous label | Gmail/Vim convention |
| `A` | Approve / pass | Approve |
| `R` | Reject / fail | Reject |
| `N` | Send to needs-review | Needs-review |
| `O` | Override (current finding) | Override |
| `Shift+O` | Override label-level disposition | — |
| `S` | Skip this label (push to end of batch) | Skip |
| `P` | Request better photo (templated message) | Photo |
| `Shift+?` | Ask supervisor on this label | — |
| `E` | Open evidence panel | Evidence |
| `?` | Show keyboard shortcut sheet | de facto convention |
| `+` / `−` | Zoom image | — |
| `0` | Reset zoom | — |
| `Tab` / `Shift+Tab` | Move between findings | — |
| `Esc` | Close any drawer / unpin | — |

**WAI-ARIA conflict avoidance.** All single-letter shortcuts are scoped to the review surface (a `<main>` with an explicit focus boundary); they don't fire when focus is in a text input or when a screen reader's virtual cursor mode is active (we listen for `keydown` only on the review-surface root and check `event.target` is not editable). The `?` sheet shows the shortcuts plus a "press any modifier-key combo to disable" option for users whose AT conflicts.

**First-five-minutes learnability.** The first-time-user state shows a non-modal, dismissible coachmark (left-pane border with "Press `?` for shortcuts; `J`/`K` to move; `A`/`R`/`N` for verdict") that auto-dismisses after the agent uses any shortcut once. No mandatory onboarding tour. Jenny's printed checklist is the signal — agents will keep their own scaffolds; we don't add one.

### Tag-out mid-batch ("resume where you left off")

The pattern: any time the agent leaves a batch, the current state (label index, current verdicts in the session, override drafts) is preserved in the session. On return, the UI offers a "Resume at label 47" affordance.

**Prototype constraint disclosed honestly.** Because there is no persistent storage, "tag out" lasts only as long as the browser session/tab. The first-time-user state surfaces this: *"Your session is in-memory only. If you close this tab, your in-progress reviews will be lost. (Production deployment will persist.)"* This is an honest-failure-mode application of DP6.

### Skip-ahead and batch-level actions

- **Skip this label** (`S`): pushes the current label to the end of the batch; logs `agent_id` and reason.
- **Request better photo for this label** (`P`): generates the templated applicant message (Q8.6) and stamps the agent's identity on the request.
- **Ask supervisor** (`Shift+?`): tags the label for supervisor review with a free-text note.
- **Bulk needs-review return** (from batch dashboard): "Send all needs-review labels back to applicant" — modal confirms count and the templated message; agent confirms with `Enter`.

Every batch-level action carries the agent's identity into the action log; this is non-optional.

### Citation

WAI-ARIA Authoring Practices (Developing a Keyboard Interface, Assigning and Revealing Keyboard Shortcuts); Snorkel Flow user guide (auto-advance, keyboard shortcuts for label classes); Prodigy `audio.manual` / `ner.manual` recipes; the CHI Workshop on User Interfaces for Crowdsourcing literature on labeling-tool UX (one-at-a-time primary, dataset overview secondary).

---

# Q8.6 — "Needs better photo" disposition UX

[T4](./2026-09-15-ocr-vision-architecture.md) makes `needs_better_photo` a first-class vision-layer disposition with the reason taxonomy: low_resolution, blurred, glare_obscures_content, orientation_not_recoverable, label_partially_occluded, multiple_labels_in_one_image. The UX must (a) tell the agent *which* image and *which* region is unreadable, (b) surface the reason in plain language, (c) offer two paths: request a new image, or proceed with manual review using what's visible.

### Agent-facing card (C-NeedsBetterPhotoCard)

Layout:
- **Header.** Disposition pill: "Needs better photo" (amber, outlined, camera icon — *not* the same as needs-review).
- **Image identifier.** "Image 2 of 3 (`label-back.jpg`, uploaded 2026-09-12)." Clicking the identifier scrolls/zooms to that image.
- **Region.** If a bbox is known, the bbox is rendered with a striped amber stroke and a camera icon; the card says "Region: government warning area (bbox 4)." If the bbox is unknown, the card says "Region: entire image."
- **Reason in plain language** (rendered from the [T4](./2026-09-15-ocr-vision-architecture.md) reason taxonomy). Example: "The image is too blurry to read. We tried to extract the government warning text but the OCR confidence was too low (0.42)."
- **Suggested fix**, in plain language. Example: "Re-take the photo at higher resolution (at least 1500 × 1500 pixels) with even lighting and no glare on the warning text."
- **Two action buttons.**
  1. **Request new image.** Opens a templated message to the applicant (below).
  2. **Proceed with manual review.** Closes the card; agent makes a manual disposition based on what's visible.

### Templated "request new image" message

Composed automatically from the reason taxonomy and label metadata. Federal Plain Language Guidelines (PLAIN 2011) compliant: short sentences, "you" + "we," active voice, no jargon. Agent reviews and edits before sending; agent's identity is on the sent message.

> **Subject:** Request for an updated image of label *Brand Name — Spirits — 750 mL*
>
> Dear *Applicant*,
>
> We need a clearer image of one of the labels you submitted on *2026-09-12*. The current image (`label-back.jpg`) is too blurry to confirm the government-warning statement.
>
> Please take a new photo of the back of this label, with these conditions:
> - Resolution at least 1500 × 1500 pixels
> - Even lighting, with no glare on the warning text
> - The whole label visible in one image, oriented upright
>
> Upload the new image at *[link to COLAs Online application]*. Reply to this email if you have questions.
>
> Thank you,
> *Agent Name, ALFD*

### Calibrated incompetence

Buçinca et al. (CSCW 2021) and the AI-abstention literature converge on the finding that a system that says "I don't know" cleanly is more trustworthy than one that always answers. The needs-better-photo disposition is our flagship abstention pattern. It is *not* a failure of the system; it is the system doing its job. The card's tone reflects this: no apology, no "the system encountered an error," just "this image isn't usable for X — here's what to do."

### Citation

[T4](./2026-09-15-ocr-vision-architecture.md) (vision-layer reason taxonomy); Nielsen heuristic #9 (recognize, diagnose, recover); Federal Plain Language Guidelines (March 2011, Rev. 1 May 2011); Plain Writing Act of 2010; Buçinca et al. CSCW 2021; HAX G10 ("Scope services when in doubt").

---

# Q8.7 — Error and exception messaging

Government tools are notorious for cryptic error messages. The patterns that produce clear, actionable messages without being condescending are well-established: **GDS error-message pattern** (error summary at top of page in a `role="alert"` region; field-level errors inline with `aria-describedby`; explicit instruction to fix; "Error:" prefix on `<title>` when error is present), **NN/g heuristic #9** (recognize, diagnose, recover), and **Federal Plain Language Guidelines** (PLAIN 2011).

### The "didn't make my life harder" test

Every error message answers four questions:
1. **What happened?** (in plain language; no error codes alone)
2. **Why?** (proximate cause, not architectural)
3. **What should I do next?** (one explicit action)
4. **Where can I get help?** (a link, a contact, or "save and try again later")

If a message doesn't answer all four, it fails the test.

### Worked examples

Each "before" is a cryptic government-style error; each "after" is our system's version. Specific failure modes are tied to upstream [T3](./2026-09-15-rule-engine-architecture.md)/[T4](./2026-09-15-ocr-vision-architecture.md)/[T5](./2026-09-15-llm-orchestration-architecture.md) outputs.

**1. Orchestrator timeout ([T5](./2026-09-15-llm-orchestration-architecture.md): orchestrator path).**
- **Before:** *"Error 4017: Submission rejected."*
- **After:** *"We couldn't finish checking this label in time. The check exceeded our 5-second budget. Try again, or review this label manually using the panel on the right. (Reason: `ORCHESTRATOR.TIMEOUT`. If this keeps happening, contact ALFD-tech@ttb.gov.)"*

**2. Vision-layer engine failure ([T4](./2026-09-15-ocr-vision-architecture.md)).**
- **Before:** *"Vision API call failed (500)."*
- **After:** *"We can't read this image right now. The image-processing service didn't respond. The label has been moved to needs-review so you can decide how to handle it. Retry the check, or proceed with manual review. (Reason: `VISION.ENGINE.UNAVAILABLE`.)"*

**3. Rule-set version mismatch ([T5](./2026-09-15-llm-orchestration-architecture.md)).**
- **Before:** *"Rule set version mismatch: expected 2026-Q1.3, got 2026-Q1.2."*
- **After:** *"This label was checked against an older set of rules (rule-set version 2026-Q1.2; the current version is 2026-Q1.3). The findings are still valid for the older rule set. Re-run the check to use the current rules, or proceed with the older findings if appropriate. (Reason: `RULESET.VERSION_MISMATCH`.)"*

**4. Malformed application input ([T3](./2026-09-15-rule-engine-architecture.md)).**
- **Before:** *"JSON parse error at line 47, column 12."*
- **After:** *"We couldn't read part of the application data — the ABV field is missing for this label. The label has been moved to needs-review. Open the application in COLAs Online to check the ABV, then come back here to record your decision. (Reason: `APPLICATION.MISSING_FIELD.ABV`.)"*

**5. Network / firewall failure (the pilot vendor's pattern — explicitly not repeated).**
- **Before:** *"Failed to connect to upstream service (timeout 30s)."*
- **After:** *"We can't reach the rule service from this network. This may be a firewall block — the prior pilot ran into the same issue. Try refreshing in a minute. If it keeps failing, contact ALFD-tech@ttb.gov; in the meantime, all labels in this batch are paused, not lost. (Reason: `NETWORK.UPSTREAM_UNREACHABLE`.)"*

**6. LLM API transient failure ([T5](./2026-09-15-llm-orchestration-architecture.md); relevant in needs-better-photo and brand-name disambiguation).**
- **Before:** *"OpenAI request failed: 429 Too Many Requests."*
- **After:** *"The AI assistant is briefly unavailable. The rule check finished, but we couldn't get the AI's suggestion on the borderline brand-name match. The rule says 'borderline.' Decide manually, or retry in a moment. (Reason: `LLM_API.RATE_LIMITED`.)"*

**7. Image upload too large ([T4](./2026-09-15-ocr-vision-architecture.md) + application input).**
- **Before:** *"413 Payload Too Large."*
- **After:** *"This image is too large to process (it's 28 MB; we can handle up to 20 MB). Ask the applicant to re-save the image at a lower file size — JPEG at quality 85 is usually enough — or scale the longest dimension to 3000 pixels. (Reason: `IMAGE.UPLOAD.TOO_LARGE`.)"*

**8. Multiple-labels-in-one-image ([T4](./2026-09-15-ocr-vision-architecture.md) vision reason taxonomy).**
- **Before:** *"Vision detected 3 labels in 1 image."*
- **After:** *"This image has more than one label in it. We can't reliably check each one separately. Ask the applicant to upload one image per label, or proceed with manual review of the whole image. (Reason: `VISION.NEEDS_BETTER_PHOTO.MULTIPLE_LABELS_IN_ONE_IMAGE`.)"*

### Visual treatment

All error messages render through the C-Alert component (USWDS `usa-alert` adapted with our verbiage), with `role="alert"` for assertive errors and `role="status"` (`aria-live="polite"`) for non-blocking ones, per the USWDS alert component accessibility guidance.

### Citation

GOV.UK Design System "Error summary" and "Error message" components; Home Office UCD Manual on error messages; Nielsen heuristic #9; Federal Plain Language Guidelines (PLAIN 2011); Plain Writing Act of 2010; USWDS alert component accessibility guidance.

---

# Q8.8 — Demo path design

The demo runs 5–10 minutes. The path below hits Sarah's, Dave's, and Jenny's signals in sequence without feeling scripted. (Note: this is the T8-side path. Cross-topic demo synthesis spanning T8+[T9](./2026-09-15-verification-targets-research.md)+[T10](./2026-09-15-stakeholder-frameworks.md) is X-6 and deferred.)

### Stakeholder signals

- **Sarah (sponsor, Deputy Director).** Speed (sub-5-second response visible to the audience), batch processing visible, simplicity.
- **Dave (28-year senior agent).** Nuance handling — STONE'S THROW vs. Stone's Throw; "AI thinks vs rule says" visible; override <3 keystrokes.
- **Jenny (junior agent).** Warning-statement strictness — title-case "Government Warning" caught with `GOVERNMENT_WARNING.FORMAT.CAPS_REQUIRED` tied to 27 CFR §16.22(a)(2). Plus a low-res image producing a needs-better-photo disposition.

### 7-stage demo path (timing budget ~7 minutes core + 2 minutes Q&A buffer)

| Stage | ~Time | Audience sees | Narrator says |
|---|---|---|---|
| **1. Single-label happy path** | 0:00–0:45 | Drag-drop one clean label image; result returns in <2 seconds; pass disposition + 4 fields, all green. Citation chips clickable. | "This is the simplest case. The orchestrator's 5-second SLA is the budget; here we used about 1.8 seconds. Notice every finding has a CFR citation that comes straight from rule data — never the model." (Sarah's *speed* + *simplicity*.) |
| **2. The borderline brand-name case (Dave's signal)** | 0:45–2:00 | Load STONE'S THROW Bourbon. Right pane shows `BRAND_NAME.MISMATCH.NEEDS_REVIEW` with Jaro-Winkler 0.94 in the rule verdict block. Below it, an "AI suggested:" block reads "STONE'S THROW and Stone's Throw differ only in capitalization — recommend pass." | "The rule engine made the deterministic call: borderline. The LLM only paraphrased reasoning from a template. The agent reads the rule first; the AI sits visibly below it, labeled. Pressing `O` for override opens this drawer — three keystrokes to flip the disposition with a structured reason code." Demonstrate `O → ENTER → ENTER`. (Dave's *nuance* + *override* + *trust separation*.) |
| **3. The warning-statement strictness case (Jenny's signal)** | 2:00–3:00 | A label where the warning text reads "Government Warning: According to the Surgeon General…" in title case. The system fires `GOVERNMENT_WARNING.FORMAT.CAPS_REQUIRED`, severity fail, citation 27 CFR §16.22(a)(2), confidence 0.93 high. | "27 CFR §16.22 is word-for-word strict — caps and bold. The system catches title-case as a fail with a precise reason code. The bbox on the left highlights the exact words. Confidence is high because OCR was clean and the rule is unambiguous." (Jenny's *warning strictness* + *reason-code precision*.) |
| **4. The "needs better photo" case** | 3:00–4:00 | A low-resolution / glare image. Disposition pill: "Needs better photo" (amber, camera icon). Card states reason `VISION.NEEDS_BETTER_PHOTO.GLARE_OBSCURES_CONTENT`, with the templated applicant message in the side panel. | "The system says 'I can't reliably read this' — that's a first-class outcome, not an error. The agent has two options: send this templated message to the applicant — agent identity stamped — or proceed with manual review. The applicant message is in plain language because federal forms have to be." (Jenny's *edge case* + DP6 *honest failure*.) |
| **5. Batch upload (Sarah's signal)** | 4:00–5:30 | Drag in 50 labels. Top ribbon updates: "Processing… 12 of 50 done." One-at-a-time review surface stays primary; lookahead k=2–3 keeps the next labels pre-fetched. Agent rapidly J/A/J/A/J/N through 5 labels. | "Throughput is human-bound, not compute-bound. Lookahead k=2–3 keeps the agent saturated. The keyboard model is `J/K` next/prev, `A` approve, `R` reject, `N` needs-review, `O` override, `?` for shortcuts. Press `?`." Show shortcut sheet. (Sarah's *batch* + *speed* + *simplicity*.) |
| **6. The override that becomes calibration data** | 5:30–6:15 | On an out-of-tolerance ABV finding (label 40.5%, application 39.8%, delta 0.7 pp exceeds the spirits ABV tolerance ±0.3 pp), agent overrides with reason `ABV.SPIRITS.OUT_OF_TOLERANCE.OVERRIDE_DOCUMENTED_REBLEND`. Switch briefly to the supervisor calibration view: a heat map of overrides by `reason_code` × `confidence_band`. | "In the prototype, overrides aren't persisted — we tell the agent that honestly. In production, the same override flows into the supervisor's calibration view. NIST AI RMF GOVERN-1.5 calls this 'ongoing monitoring'; ISO/IEC 42001 calls it 'continual improvement.' Same idea." (Sarah's *governance* + Dave's *empowered override*.) |
| **7. Failure-recovery demo** | 6:15–7:00 | Disable network briefly; show the C-Alert "We can't reach the rule service from this network…" with a `NETWORK.UPSTREAM_UNREACHABLE` reason. Re-enable; click retry; queue resumes. | "The prior scanning vendor pilot died on outbound firewall blocks plus 30–40-second latencies. We don't repeat either pattern: the message is plain, the queue isn't lost, and on any orchestrator failure the safe-failure mode is needs-review — never auto-rejection." (Raised as a pre-mortem risk in [T10](./2026-09-15-stakeholder-frameworks.md).) |

### Test fixtures required

(This is Q8.8's specific output; not synthesized with X-6.)

| Fixture | Purpose | Notes |
|---|---|---|
| `fixture-01-clean-spirits-pass.pdf` + label image | Stage 1 happy path | High-quality image; matches application exactly. |
| `fixture-02-stones-throw-borderline.pdf` + label | Stage 2 brand-name borderline | Application: "STONE'S THROW Bourbon"; label OCR: "Stone's Throw". |
| `fixture-03-warning-titlecase.pdf` + label | Stage 3 government-warning fail | Warning text in title case, otherwise correct. |
| `fixture-04-glare-low-res.jpg` | Stage 4 needs-better-photo | Real glare on the warning region; OCR confidence < 0.5. |
| `fixture-05-batch-50-mixed.zip` | Stage 5 batch | 50 labels, ~70% pass / 20% needs-review / 10% fail. |
| `fixture-06-abv-application-disagreement.pdf` + label | Stage 6 override + calibration | Label ABV 45%, application 40%; the two declared figures do not agree. |
| `fixture-07-network-toggle` | Stage 7 failure recovery | A scriptable network toggle (browser DevTools "Offline" mode is sufficient for the demo). |

### Demo failure-recovery patterns

If the deployed URL is slow or the LLM API has a transient failure during the demo (per pre-mortem A-1):

1. **Pre-warm the orchestrator** at minute T-5 of the demo (run fixture-01 once before the audience joins).
2. **Cache the LLM response for fixture-02** so that even if the LLM API is down, the borderline brand-name demo still shows "AI suggested:" — flag this in the narration as "cached for the demo."
3. **Have a screen-recorded fallback** for stages 1–4 in case live runs fail. The narrator continues live narration; the recording plays without audio.
4. **The needs-review fall-through is actually a feature for the demo.** If the orchestrator legitimately fails, the system's response — needs-review with a reason code — *is* the demo of DP6 honest failure modes. Lean into it.

---

# Q8.9 — Workflow integration with agent's existing process

[T2](./2026-09-15-cola-operational-context.md) documents the actual workflow. Two structural facts dominate:
- **The agent will alt-tab.** COLAs Online (internal queue UI) is open in another window. The agent moves between our tool and COLAs Online constantly.
- **Our tool is standalone.** No integration; we don't get to put a button in COLAs Online's toolbar.

### Design implications

**Don't try to be the agent's "home."** No splash screens; no "welcome back" greetings; no daily summary on load. The agent opens our tool, runs verification, and goes back to COLAs Online. The session is a tool-use, not a destination. Our tool's home page on load is the queue (or the last batch); time-to-first-action is < 2 seconds.

**Make alt-tab cheap.** Persistent navigation (DP1) means the same shortcuts work every time the agent comes back; tab focus is preserved on alt-back; no state is lost on window blur.

**Make output copy-pastable.** The agent's next step in COLAs Online is one of:
- (a) approve in COLAs Online,
- (b) reject in COLAs Online with a reason,
- (c) issue a "Needs Correction" letter.

Each of those needs structured text. Our tool exposes:

- A **"Copy CFR citation"** chip on every finding. One click → clipboard contains the citation in COLAs Online's expected format (`27 CFR §16.22(a)(2): GOVERNMENT_WARNING.FORMAT.CAPS_REQUIRED — see ALFD review`).
- A **"Copy Needs Correction comment"** action on every needs-review label. One click → clipboard contains a plain-language paragraph appropriate for COLAs Online's "Needs Correction" comment field, with all CFR citations and reason codes inlined. The text is editable in a small preview before copy.
- A **"Copy structured reason code"** chip for the rule-tuning team's internal notes.

Every copy action is logged with agent identity (so we can later audit the volume going to COLAs Online).

### Hand-off and escalation

When an agent escalates (wine specialist passing a malt-beverage-specialty case to spirits/malt office), the agent's notes must be exportable as a self-contained record. We support:

- **Markdown export.** A single `.md` file per label or per batch, containing the original application metadata, all findings (with disposition, reason_code, CFR citation, confidence band, evidence summary), all overrides with agent ID and timestamp, and any free-text notes. Designed to be readable by a regulator without our tool.
- **Structured JSON export.** The full RejectionReason model ([T3](./2026-09-15-rule-engine-architecture.md)) per finding, plus override metadata, plus session metadata. Designed for tooling (rule-tuning, training-data curation) and for ingestion by another instance of our tool.

Both formats are downloadable via a single button on the label or batch view; both stamp the exporting agent's identity and a timestamp. In the prototype, exports are local file downloads; in production, exports could feed an internal repository.

### The friction-surface goal

Our tool's job is to make the next step take *less* keystrokes than today, not more. Concretely: if today the agent reads the label, mentally checks each rule, types a free-text "Needs Correction" comment in COLAs Online — that's a multi-minute task. With our tool, the agent runs verification (5 seconds), reads the findings (30 seconds for a 4-field label), clicks "Copy Needs Correction comment" (1 second), alt-tabs to COLAs Online, pastes (2 seconds), reviews and submits. Net savings of one to several minutes per label.

### Citation

[T2](./2026-09-15-cola-operational-context.md) (workflow); USWDS button and table component guidance; GOV.UK Service Manual on serving caseworkers (gov.uk/service-manual — caseworker user category).

---

# Q8.10 — Section 508 specifications (implementation-feeding)

[T7](./2026-09-15-federal-deployment-compliance.md) establishes the legal floor (Revised 508 / 36 CFR 1194 incorporating WCAG 2.0 A and AA), and the WCAG 2.2 best-practice extensions worth adopting. This section specifies implementation requirements for the components our UI uses.

### Image-region (bbox) viewer (C-BboxOverlay)

**ARIA roles.** The image is `<img>` with `alt` describing the label. The overlay container is `role="region"` with `aria-label="Label image with annotations"` and contains a `role="list"` of bbox items (each `role="listitem"`). Each bbox is a focusable `<button type="button">` carrying `aria-label="Region 3 of 7, government warning, fail, confidence medium, click to pin"` and `aria-pressed` reflecting pin state. We deliberately avoid `role="application"` (APG cautions: it suppresses normal screen-reader keystroke handling and is appropriate only for full-canvas applications, not annotated images).

**Keyboard model.**
- `Tab` enters the image region; first bbox receives focus.
- Arrow keys (Up/Down/Left/Right) cycle bboxes spatially (left-to-right, top-to-bottom reading order is the announced order).
- `Enter` or `Space` pins the focused bbox (highlights it and its corresponding right-pane card).
- `Esc` exits the image region back to the page tab order.
- `+` / `−` zoom; `0` resets; arrow keys pan when zoomed (the keystrokes scope by whether a bbox is currently focused vs. just the image background).

**Screen-reader announcement format.**
- On region focus: "Region 3 of 7, government warning, fail, low confidence. Press Enter to pin and view evidence."
- On pin: "Pinned. Region 3, government warning, fail. Evidence panel updated."
- On zoom change: "Page zoom 200%, focus on government warning region (bbox 3 of 7)."

### Per-field evidence card (C-FieldCard)

**Semantic HTML.** The override button uses `aria-keyshortcuts="O"` to expose the keyboard shortcut to assistive technology without baking it into the visible label text:

```html
<article aria-labelledby="field-3-heading">
  <header>
    <h2 id="field-3-heading">Government warning</h2>
    <span class="disposition-pill" data-disposition="fail">…</span>
    <span class="confidence-indicator" data-band="medium">…</span>
  </header>
  <dl>
    <dt>Extracted text</dt><dd>"Government Warning: According to…"</dd>
    <dt>Expected text</dt><dd>"GOVERNMENT WARNING: According to…"</dd>
    <dt>Reason</dt><dd>The warning heading must be in all-caps.</dd>
  </dl>
  <footer>
    <a class="citation-chip" href="…">27 CFR §16.22(a)(2)</a>
    <button type="button" aria-keyshortcuts="O">Override</button>
    <details><summary>More detail</summary>…</details>
  </footer>
</article>
```

**Heading hierarchy.** `h1` for the label as a whole (e.g., "Brand Name — Spirits — 750 mL"); `h2` for each field card; `h3` for subsections within "More detail."

**ARIA-labelledby.** The `<article>` is `aria-labelledby` linked to the field heading; the corresponding bbox button has `aria-controls` referencing the article id (so screen readers announce the relationship).

### Batch queue table (C-BatchTable)

**Markup.** A real `<table>` with `<caption>` ("Batch 2026-09-12 — 312 labels — wine office"), `<thead>` with `<th scope="col">` for each column, and `<tbody>` with rows.

**Sortable columns** use `aria-sort="ascending|descending|none"` on the `<th>`. Sort interactions are keyboard-operable (Enter on a focused header).

**Row selection** uses `aria-selected` on the row and `tabindex` management so that arrow keys move row focus, Space toggles selection, Enter opens the label.

**Skim-then-dive pattern for screen-reader users.** On entering the table, the screen reader announces caption + column headers + row count. The agent uses the screen reader's table-navigation keys (e.g., NVDA's Ctrl+Alt+Arrows) to skim by row; pressing Enter on any row opens that label. The "Filter to needs-review only" checkbox above the table is the main triage shortcut for screen-reader users — it reduces the scan space directly. (The skim-then-dive pattern matches WAI-ARIA APG grid/table guidance.)

### Confidence indicator (C-ConfidenceIndicator)

Four parallel channels — text content, color, shape/pattern, and a band label — explicitly forbidding color-only conveyance.

```html
<span class="confidence" role="img" aria-label="Confidence: medium, score 0.78">
  <span class="band-text">medium</span>
  <span class="score-text">0.78</span>
  <span class="bar bar--striped bar--amber" aria-hidden="true"></span>
</span>
```

- **High** — solid bar, green (≥4.5:1 contrast against background).
- **Medium** — striped bar, amber.
- **Low** — outlined bar, blue-or-gray (low confidence is *not* alarming-red, because medium is already amber and we don't want to conflate "low confidence" with "fail").

The "color-only" pattern is explicitly prevented: no UI ever depends on the color alone.

### "Pass / fail / needs-review" disposition pill (C-DispositionPill)

Text + icon + color + non-color pattern.

| Disposition | Text | Icon | Color | Pattern |
|---|---|---|---|---|
| Pass | "Pass" | ✓ | green | filled |
| Fail | "Fail" | ✗ | red | filled |
| Needs review | "Needs review" | ? | amber | striped/outlined |
| Needs better photo | "Needs better photo" | 📷 | amber | outlined with camera icon |

`<span role="status" aria-label="Disposition: needs review">` ensures screen readers announce on update.

### Live region (C-LiveRegion)

**Polite (`aria-live="polite"`)** for batch progress, queue position changes, and non-urgent notifications. Announcements throttled to every ~2 seconds to avoid screen-reader chatter.

**Assertive (`aria-live="assertive"`)** reserved for *failures* the agent must be aware of immediately (orchestrator timeout on the current label, network failure). Used sparingly.

### Reduced motion

`@media (prefers-reduced-motion: reduce)` swaps animated progress bars for static fills, eliminates toast slide-in animations (toasts appear in place), and disables any decorative motion. Progress and state changes are *never* signaled by motion alone; text + color + shape always carry the signal too.

### Reflow (WCAG 2.1 1.4.10)

Layout reflows to 320 CSS px without two-dimensional scrolling.

- **Wide viewports (≥1024 px):** image left, evidence cards right, equal split.
- **Medium (768–1023 px):** image top (60vh), cards below (scrollable).
- **Narrow (<768 px):** stacked. Image first (collapsible to a thumbnail), then cards. The bbox-overlay viewer collapses to a "tap a bbox to expand the image" affordance.

### Conformance testing posture

- **VPAT for the prototype.** Issue a Voluntary Product Accessibility Template at the WCAG 2.0 AA / Revised 508 mapping with explicit "Supports / Partially Supports / Does Not Support" per requirement. Mark the parts where the prototype intentionally omits production features (persistent storage, COLAs Online integration) as out-of-scope, not "Does Not Support."
- **Pre-production:** plan for DHS Trusted Tester program (or equivalent) testing before any production deployment. The GSA Section 508 ART tool provides the requirement framework; section508.gov hosts the validated component check.
- **Internal automated checks:** axe-core or Pa11y on every PR; manual NVDA + JAWS + VoiceOver smoke tests on each release.

### Citation

36 CFR 1194 (Revised 508 Standards); WCAG 2.2 (W3C, October 2023) success criteria 1.4.1, 1.4.3, 1.4.10, 1.4.13, 2.1.1, 2.4.7, 2.4.11, 2.4.12, 2.5.5, 2.5.7, 2.5.8, 2.3.3, 4.1.2; W3C WAI-ARIA 1.2; W3C WAI-ARIA Authoring Practices Guide; section508.gov; USWDS alert and table component accessibility tests.

---

# Q8.11 — Information density vs. processing time tradeoff

With [T3](./2026-09-15-rule-engine-architecture.md), [T4](./2026-09-15-ocr-vision-architecture.md), [T5](./2026-09-15-llm-orchestration-architecture.md) outputs known, the question is: of the many fields in the RejectionReason model — `reason_code`, `bin`, `severity`, `disposition`, `field`, `cfr`, `evidence`, `confidence`, `confidence_band`, `human_message`, `template_id`, `rule_id`, `rule_set_version`, `model_version`, `timestamp` — which are visible at the default level, behind one click, or behind a developer-mode toggle?

### Default-visible per finding (the C-FieldCard surface)

- `human_message` — the plain-language reason.
- `severity` rendered as the C-DispositionPill icon and color.
- `cfr` rendered as the C-CitationChip (clickable to inline rule text).
- `confidence_band` + `confidence` numeric — rendered as C-ConfidenceIndicator (band primary, number secondary, both visible).
- bbox link (the corresponding number on the image overlay).

Justification: these are the highest-information-scent items per Pirolli & Card (1999). They answer the agent's questions: *what*, *how bad*, *which rule*, *how sure*, *where on the label*.

### Behind "More detail" (one click, one focus stop away)

- `reason_code` — the structured [T3](./2026-09-15-rule-engine-architecture.md) grammar string (`GOVERNMENT_WARNING.FORMAT.CAPS_REQUIRED`).
- `rule_id`, `rule_set_version` — for the rule-tuning team and audit.
- `model_version` — when the LLM contributed.
- `template_id` — which message template the human_message was rendered from.
- `timestamp` — when the finding was produced.
- `evidence_json` — the structured evidence excerpt (extracted text, expected text, OCR raw confidences).

Justification: agents need these only on disagreement or escalation. Hick-Hyman: surfacing them at default would expand the choice space to ~10 things-to-look-at per finding × 4 findings = 40+ items, which exceeds working memory bandwidth (Sweller). They are valuable when needed, costly when not. Progressive disclosure is the canonical answer (NN/g, "Progressive Disclosure").

### Behind "Raw" (developer / audit mode)

- The full structured `RejectionReason` JSON.
- The full orchestrator prompt + output (when an LLM was involved in this finding).
- The full vision response envelope (OCR per-token confidences, image preprocessing decisions, etc.).

Justification: these are for incident review, prompt-tuning, and vision-pipeline debugging — not agent review. Surfacing them at default level would (a) be an information-foraging trap (low scent, high cost) and (b) leak prompt/model details that aren't relevant to the regulatory decision.

### Latency dimension

Information that requires an additional round-trip is either pre-fetched or clearly marked as a slower action.

- **Pre-fetched** at label-load time: rule text for any cited CFR section (small, cacheable, used often).
- **Pre-fetched in the background** when the agent opens "More detail": the LLM prompt + output (so "Raw" is instant when toggled).
- **Marked as slower**: "Show original COLAs Online application" (requires a cross-system lookup; rendered as a button labeled "Open in COLAs Online (alt-tab)" with a small clock icon — sets expectation that it's not instant).

### Citation

Pirolli & Card, "Information Foraging," *Psychological Review* 106(4), 1999; NN/g "Progressive Disclosure"; Sweller's Cognitive Load Theory; Hick-Hyman law (Hick 1952; Hyman 1953); HAX G4 ("Show contextually relevant information").

---

# Anti-patterns (explicit list with attribution)

Each anti-pattern is tied to (1) a real prior pilot failure, (2) a stakeholder concern, (3) an accessibility or research finding.

1. **Modal dialogs that interrupt the agent's review flow.**
*Prior pilot:* the 2008 phone-tree's "press 1 to continue" interruptions ended up *increasing* call volume.
*Stakeholder:* Dave's "don't make my life harder."
*Research:* HAX G3 ("Time services based on context"); GDS Service Manual on caseworker tools. Modal interruptions break working memory state (Sweller).

2. **Hover-only reveal of evidence.**
*Prior pilot:* the scanning vendor's tooltip-only "click to expand" was unreachable for keyboard users and non-discoverable for older agents.
*Stakeholder:* Sarah's mother (the 73-year-old benchmark) — hover discoverability fails NN/g senior research.
*Research:* WCAG 1.4.13 Content on Hover or Focus; Home Office Pun motor-disabilities poster ("don't rely on hover").

3. **Color-only disposition signals (red text alone for "fail").**
*Prior pilot:* generic; common in legacy government tools.
*Stakeholder:* both Sarah's mother (presbyopic contrast loss — Owsley 1983) and any agent with color-vision deficiency.
*Research:* WCAG 1.4.1 Use of Color; Revised 508 §410.2; Home Office Pun low-vision poster.

4. **Spinners without progress for batch processing.**
*Prior pilot:* the scanning vendor's 30–40-second pure spinner left agents not knowing if the system was hung; they retried, doubling load.
*Stakeholder:* Sarah ("speed visible"); Dave ("don't make my life harder").
*Research:* NN/g progress-indicator guidance; GDS "Don't pace your users" — pacing is a *kind* of progress signal, but progress is mandatory; pacing is the optional, calmable layer.

5. **Cryptic error messages ("Error 4017").**
*Prior pilot:* COLAs Online itself, by Dave's reckoning. The 2008 phone tree's "your call could not be completed" produced more callbacks.
*Stakeholder:* Dave's bar, explicitly.
*Research:* Nielsen heuristic #9; Federal Plain Language Guidelines (PLAIN 2011); GOV.UK Design System error-summary pattern.

6. **Forced re-onboarding every session.**
*Prior pilot:* generic. Jenny still uses a printed checklist *because* the existing system doesn't earn placeholder trust — re-onboarding signals "we don't trust you to remember."
*Stakeholder:* Jenny (digital native who has nonetheless externalized the system to paper); Dave ("just don't make my life harder").
*Research:* HAX G12 ("Remember recent interactions"); NN/g UX Design for Seniors (3rd ed.) on session continuity.

7. **AI-first framing that puts the model's reasoning above the rule's reasoning.**
*Prior pilot:* generic across "AI-augmented" gov tools, several of which have been retracted.
*Stakeholder:* Dave. The trust gradient inverts the moment the LLM is the headline.
*Research:* Rejection reasoning (rule engine decides); Zerilli et al. (2019) on transparency double standards; HAX G2 (calibrated quality expectations).

8. **Auto-rejection on AI failure.**
*Prior pilot:* any system that converts compute failure into adverse user outcomes — the 2008 phone tree being the in-context example.
*Stakeholder:* Sarah (governance liability); Dave (regulatory risk).
*Research:* The deterministic core; NIST AI RMF MANAGE-2.3 (graceful degradation); fail-safe defaults in security and safety engineering.

9. **Animations as the primary signal for state change.**
*Prior pilot:* generic.
*Stakeholder:* Sarah's mother (vestibular disorders are common over 50); reduced-motion preferences.
*Research:* WCAG 2.3.3 Animation from Interactions; WCAG 2.3.1 Three Flashes; `prefers-reduced-motion`.

10. **Right-clicks, multi-finger gestures, drag-and-drop as the only way to do something.**
*Prior pilot:* generic.
*Stakeholder:* every agent on a keyboard-first workflow; agents with motor differences.
*Research:* WCAG 2.5.7 Dragging Movements; WCAG 2.5.8 Target Size (Minimum); Home Office Pun motor-disabilities poster.

11. **Dark patterns to nudge agents toward AI-suggested decisions.**
*Prior pilot:* not specifically TTB, but the broader literature on AI deployments where the AI's suggestion is pre-selected as the default action and agents rubber-stamp it.
*Stakeholder:* Sarah (regulatory liability); Dave (will spot it instantly).
*Research:* Bansal et al. CHI 2021 on over-reliance; Buçinca et al. CSCW 2021 on cognitive forcing — *don't* pre-select AI suggestions; require explicit affirmative action; structurally cheap, but never default-selected.

---

# Open questions / what would change with empirical data

- **Is `O` the right override key, or should it conflict-check with screen-reader keystrokes per AT?** We've scoped shortcuts to the review surface and excluded them from text inputs, but real-world testing with NVDA, JAWS, VoiceOver virtual cursor mode is needed before we ship.
- **Is the 5-second SLA tight enough for Sarah's "speed visible" demo signal, or should the orchestrator target 2 seconds at the 95th percentile?** [T6](./2026-09-15-batch-processing-architecture.md) says 5; demo experience suggests <2 is the visceral threshold. Empirical: time the audience's perception during a 200-label batch.
- **Does the calibration view's "agent" axis create chilling effects on override behavior?** If agents perceive that they're being benchmarked against the AI, they may rubber-stamp. Mitigation: aggregate-only views by default; named-agent views unlock only at supervisor request and are auditable.
- **Should the "needs better photo" message template be auto-sent or always agent-confirmed?** We chose agent-confirmed (DP1 senior-comfort: no surprises). A high-volume importer might prefer auto-send for routine reasons. Configurable per office; defaulted to confirm.
- **Reflow behavior on actual ALFD desktop sizes.** ALFD's monitors are likely 1920×1080 or larger; if so, the < 768 px reflow matters mostly for accessibility-zoom users, not for primary day-to-day. [T9](./2026-09-15-verification-targets-research.md)/[T10](./2026-09-15-stakeholder-frameworks.md) should validate.
- **What is the actual latency cost of pre-fetching the LLM prompt + output for "Raw" mode?** If it's > 200 ms it should not be pre-fetched on every label; only on labels with LLM contribution.

---

# Sources cited

- Amershi, S., Weld, D., Vorvoreanu, M., Fourney, A., Nushi, B., Collisson, P., Suh, J., Iqbal, S., Bennett, P., Inkpen, K., Teevan, J., Kikin-Gil, R., Horvitz, E. "Guidelines for Human-AI Interaction." *Proc. CHI 2019*, ACM. (Microsoft HAX Toolkit, microsoft.com/haxtoolkit)
- Bainbridge, L. "Ironies of Automation." *Automatica* 19(6), pp. 775–779, 1983.
- Bansal, G., Wu, T., Zhou, J., Fok, R., Nushi, B., Kamar, E., Ribeiro, M.T., Weld, D. "Does the Whole Exceed Its Parts? The Effect of AI Explanations on Complementary Team Performance." *Proc. CHI 2021*, ACM.
- Buçinca, Z., Malaya, M.B., Gajos, K.Z. "To Trust or to Think: Cognitive Forcing Functions Can Reduce Overreliance on AI in AI-assisted Decision-making." *Proc. ACM Hum.-Comput. Interact.* 5, CSCW1, Article 188, 2021.
- Federal Plain Language Guidelines. PLAIN (Plain Language Action and Information Network), March 2011, Rev. 1 May 2011. plainlanguage.gov.
- Fitts, P.M. "The Information Capacity of the Human Motor System in Controlling the Amplitude of Movement." *Journal of Experimental Psychology* 47(6), pp. 381–391, 1954.
- GDS / GOV.UK Design System. "Error summary," "Error message," "Validation" patterns. design-system.service.gov.uk; gov.uk/service-manual.
- GSA / GOV.UK / DSIT. UK Algorithmic Transparency Recording Standard, gov.uk/government/collections/algorithmic-transparency-recording-standard-hub (mandatory for UK central government from 2024).
- GSA Centers of Excellence. *AI Guide for Government*. coe.gsa.gov/coe/ai-guide-for-government/.
- Hick, W.E. "On the Rate of Gain of Information." *Quarterly Journal of Experimental Psychology* 4(1), pp. 11–26, 1952; Hyman, R. "Stimulus Information as a Determinant of Reaction Time." *J. Exp. Psychol.* 45(3), pp. 188–196, 1953.
- Home Office Digital. "Dos and Don'ts on Designing for Accessibility" posters (Pun, K., Ball, E., Buller, J., Cowan, N., et al., 2016). accessibility.blog.gov.uk; UKHomeOffice/posters on GitHub.
- ISO/IEC 42001:2023, *Artificial Intelligence Management System*.
- NIST. *AI Risk Management Framework 1.0* (NIST AI 100-1), January 2023; *AI 600-1: Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*, July 2024.
- Nielsen Norman Group. *UX Design for Seniors* (Pernice, K., Estes, J., Nielsen, J.; 3rd ed.). nngroup.com/reports/senior-citizens-on-the-web/.
- Nielsen Norman Group. "10 Usability Heuristics for User Interface Design"; "Error Message Guidelines"; "Progressive Disclosure"; "Information Foraging"; "Touch Targets on Touchscreens"; "Designing AI Products and Features: Study Guide"; "Define Techy Words for Old Users." nngroup.com.
- Owsley, C., Sekuler, R., Siemsen, D. "Contrast Sensitivity Throughout Adulthood." *Vision Research* 23(7), pp. 689–699, 1983.
- Pirolli, P., Card, S. "Information Foraging." *Psychological Review* 106(4), pp. 643–675, 1999.
- Plain Writing Act of 2010, Public Law 111-274.
- Section 508 of the Rehabilitation Act, as amended; Revised 508 Standards (36 CFR Part 1194), effective January 18, 2018; section508.gov.
- Sweller, J. *Cognitive Load Theory* (multiple papers, 1988–present).
- USWDS (U.S. Web Design System). *Design Principles* page and component documentation (alert, button, table, accordion), accessibility tests. designsystem.digital.gov, USWDS 3.x.
- W3C Web Accessibility Initiative. *Web Content Accessibility Guidelines (WCAG) 2.0* (2008), *2.1* (2018), *2.2* (October 2023); WAI-ARIA 1.2 (2023); WAI-ARIA Authoring Practices Guide (APG). w3.org/WAI.
- Zerilli, J., Knott, A., Maclaurin, J., Gavaghan, C. "Transparency in Algorithmic and Human Decision-Making: Is There a Double Standard?" *Philosophy & Technology* 32, pp. 661–683, 2019.
- Zerilli, J., Bhatt, U., Weller, A. "How Transparency Modulates Trust in Artificial Intelligence." *Patterns* 3(4), 100455, 2022.
- Snorkel AI Documentation (snorkel.ai/docs); Prodigy Documentation (prodi.gy/docs) — labeling-tool UX patterns referenced for keyboard-first batch review.
