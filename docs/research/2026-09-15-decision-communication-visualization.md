# Decision Communication & Visualization

Filed 2026-09-15.

**Project:** TTB AI-powered alcohol-label verification prototype
**Status:** Re-grounded in [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) (CEA, 50/80/90 percentile convention, FY 2026 constant dollars, A‑94 Appendix C revised 6 March 2026 / M‑26‑09)
**Scope:** Project-specific decisions and pattern library — not a viz-theory survey. Cross-topic synthesis (X‑6, X‑7) deferred.

**Revision note.** Two arithmetic corrections, surgical: (a) Q12.5 `P‑StageWaterfall` step deltas now match [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s stated cumulative values ($2.82M → $0.705M after 75% haircut → $0.68M after A‑94 discount → −$1.72M after subtracting $2.4M TCO). v3's intermediate deltas were wrong; final number was right by coincidence. (b) Q12.9 V4 break-even data table and headline annotation rebuilt from [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) anchors — at 50th-time / GS‑12 DC / Option A, break-even on direct savings alone is ~89% realization, far outside [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s 15–40% modeled range; previous "~52%" was fabricated. The honest result reinforces [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s CEA framing rather than weakens it.

---

## TL;DR

- **The headline chart is a three-option 5‑yr TCO band chart (Option A vs C vs G at 50th/80th/90th percentiles) with a least-cost-delivery title and a single annotated line for "central-case realized labor savings ($141K/yr · 50th)."** It frames the analysis as CEA — *cheapest credible delivery of a mandated review function* — so the negative direct NPV (−$1.7M at 50th) becomes the *expected* result of a mandated-benefit program, not a project failure. The waterfall (gross → realization haircut → vs cost) is the second slot, used to *explain the gap honestly* once the framing is set.
- **Uncertainty is communicated using the 50th/80th/90th percentile convention throughout (never P20/P50/P80, never "low/mid/high"), with an asymmetric notation that respects [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s directional convention** — the 90th percentile is the *reserve / pessimistic-side* bound (higher cost, worse savings realization). The pattern library standardizes on **P‑PercentileNotch** (a notched range bar with a 50th tick, 80th notch, 90th tail), with quantile dotplots reserved for the take-home reviewer and HOPs reserved for the interactive notebook only. Fan charts are explicitly *rejected* for this CEA because they imply continuous time and symmetric tails neither of which [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) has.
- **"We don't know X" is shown explicitly via a P‑KnowledgeRegister overlay** — a small "★" glyph on every chart that surfaces the relevant [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §XI gap (10 named items: empirical review-time distribution, seasonality, importer/domestic split, small/large producer share, forward-volume CAGR, inter-agent variance, TTB ATO timeline, realized-vs-claimed savings precedent, headcount-ceiling decisions, future FedRAMP-High status of Claude/Opus). This is GAO Step 6 ("identify ground rules and assumptions") and Spiegelhalter (2017) "humility about uncertainty" made operational. It also keeps [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s risk register (R‑01..R‑12, GAO Step 8) visually distinct from sensitivity (Step 9) — they answer different questions and must not be merged into one tornado.

---

## Q12.1 Audience Map

Six audiences, each with a distinct decision they need to make and a distinct cost of misreading the chart. Drawn from [T10](./2026-09-15-stakeholder-frameworks.md) (Sarah, take-home reviewer, Dave/Jenny scoping) plus [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s federal-economic-analysis surface area.

| # | Audience | Primary decision | Reading time | Tolerance for negative NPV | Numeracy | Preferred surface |
|---|---|---|---|---|---|---|
| A1 | **Take-home reviewer** (anonymous senior reviewer of the prototype) | Is this work credible? | 5–10 min skim | Low without framing | Mixed | Static PDF; one-page README with one headline chart + two supporting |
| A2 | **Sarah** (TTB program lead / SME, [T10](./2026-09-15-stakeholder-frameworks.md)) | Does this fit TTB ops; is the realization rate plausible? | 20–40 min | Medium; she's seen mandated-benefit framing | High domain, mid stats | README + walkthrough deck; will challenge realization rate |
| A3 | **Marcus / IT** (TTB IT POC) | Can we deploy this in our environment in our ATO window? | 15 min | High (this is procurement) | High technical, mid economic | Architecture diagram + TCO band; cares about Option A vs C vs G |
| A4 | **Federal procurement officer** (acquisition / contracting) | Does the cost estimate satisfy GAO‑20‑195G four characteristics; is the WBS aligned to A‑11? | 30–60 min | High; expects negative direct NPV in mandated-benefit CEA | High formal | GAO 12-step compliance map + WBS + tornado + sensitivity table |
| A5 | **CIO** (TTB CIO or peer-agency CIO) | Is the lock-in / Azure-incumbency posture defensible; is the 12–36 mo / $250K–$500K federal lock-in cost in scope? | 5 min | Medium | Mid stats, high portfolio | One slide: decision matrix (option × policy/cost/lock-in/deployability) + headline TCO band |
| A6 | **Ourselves** (the analyst team; pre-mortem and demo-path owner) | What do we still not know; what flip-points should we test next? | Continuous | n/a | High | Interactive notebook (Jupyter/Quarto) with HOPs, two-way heat maps, full register |

**Decision rule:** every chart in [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s deliverable is built for *exactly one* of A1–A5 (A6 lives only in the notebook). Charts that try to serve three audiences simultaneously fail all three (Knaflic 2015, ch. 1; Munzner 2014, "what / why / how"). When a chart must do double duty, layer it: keep the figure simple for A1/A5, place A2/A4 detail in caption + companion table.

---

## Q12.2 Audience-Specific Framing of the Same [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) Analysis

Same numbers, six different lead sentences. [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s −$1.7M 5‑yr NPV (50th, Option A) is the *same fact* in each, but what it *means* differs.

- **A1 (take-home reviewer)** — *"This is a cost-effectiveness analysis (CEA) of how to deliver a mandated COLA review function at lowest 5‑year TCO, using FY 2026 constant dollars and OMB A‑94 Appendix C real Treasury rates (1.3% at 5 yr). On directly-monetized labor savings alone, no option produces a positive 5‑yr NPV at the 50th percentile. That is the expected and correct CEA result for a mandated-benefit program; the question is least-cost delivery, not net value."* (Paraphrased verbatim from [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §V framing — re-using [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s own language is intentional; a reviewer should see the analyst has read their own framing.)

- **A2 (Sarah)** — Lead on the **realization rate** (the variable Sarah actually controls): *"The 50th-percentile estimate assumes 25% of the per-application 2-minute saving is recaptured as throughput or backlog reduction. Even at the top of [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s modeled range (40%), direct-savings break-even is unreachable in 5 yr at GS‑12 DC labor — break-even on direct savings alone requires ~89% realization, well outside any plausible posture. What is your honest read on TTB's realization posture, and which non-monetary benefits should we be valuing alongside?"* — drives a conversation, not a defense.

- **A3 (Marcus)** — Lead on **deployability and ATO**: *"Option A (Azure Gov + AOAI Gov + Azure DI) costs $2.4M / $3.9M / $5.8M (50th/80th/90th) over 5 yr. Option C (AWS GovCloud + Bedrock + Textract) is +$0.7–1.4M and adds a second authority boundary. Inference/cloud costs are noise (±$60K over 5 yr, [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §V Stage 5 items 8–9). Decision driver is ATO cycle length and Azure incumbency, not unit price."*

- **A4 (procurement officer)** — Lead on **conformance**: GAO‑20‑195G 12-step compliance map first, WBS reference second, monetized savings third. The framing is *"this estimate meets characteristics 1–4 (comprehensive, well-documented, accurate, credible) for steps 1‑6, 8‑10; ICE [step 7], step 11 update, and step 12 are explicitly deferred."* The negative NPV is presented as a **Cost-Effectiveness ratio** ($/application reviewed), not as net value.

- **A5 (CIO)** — Lead on **lock-in posture**: a 2×2 decision matrix (cost × switching cost) with Option A in the "low cost, federal-lock-in 12–36 mo / $250K–$500K" quadrant. The negative NPV is *footnoted*; the decision is portfolio fit and exit cost.

- **A6 (ourselves)** — Lead on **what we don't know**. The notebook opens with the §XI register overlay (10 items) and the §X risk register (R‑01..R‑12) before any number is shown.

---

## Q12.3 Federal / Policy Audience Conventions

Synthesizing GAO‑20‑195G, OMB A‑94 (rev. Nov 2023) + Appendix C (rev. 6 March 2026, M‑26‑09), CBO *Budget and Economic Outlook 2026‑2036* graphics, USWDS data‑viz guidance, and Section 508 / WCAG 2.0 AA (the legal floor per [T7](./2026-09-15-federal-deployment-compliance.md) Q7.16 and [T8](./2026-09-15-federal-ux-for-senior-users.md) Q8.10).

**What federal audiences expect:**

1. **Percentile naming:** spelled out — *"50th-percentile (most-likely)", "80th-percentile (should-cost)", "90th-percentile (reserve)"*. Never P50/P80/P90; never "low/mid/high"; never "best/worst case." This matches [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)/R0 federal naming convention and the GAO‑20‑195G chapter on risk and sensitivity.
2. **Constant-dollar labelling:** every chart titled or sub-titled "FY 2026 constant $; A‑94 App. C real rate 1.3% (5‑yr)." A‑94 Appendix C real Treasury rates for CY 2026 are 1.1% (3‑yr), 1.3% (5‑yr), 1.4% (7‑yr) per M‑26‑09; [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) uses 1.3% for 5‑yr NPV.
3. **Citation-in-visual:** every figure carries a one-line source footer. Federal style is to cite the *guide section* not the URL — e.g., "Source: [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) Stage 4; OMB A‑94 App. C (2026); GAO‑20‑195G ch. 14." CBO and GAO both do this.
4. **Color discipline:** USWDS-aligned palette; never red/green alone for increase/decrease (Section 508). For waterfalls, use blue for increases and orange for decreases ([T8](./2026-09-15-federal-ux-for-senior-users.md) Q8.10 4-channel encoding) plus a hatch pattern; for the percentile range, three monotonic blues sequenced light→dark = 50th/80th/90th. Same hue, varying lightness, always paired with a text label and a shape redundancy (Munzner 2014 channel separability; [T8](./2026-09-15-federal-ux-for-senior-users.md) 4-channel rule).
5. **Density and chart count:** GAO and CBO publications are *table-heavy*; charts are used sparingly and are usually black-and-white-readable. Federal readers tolerate a dense table over a flashy chart — for A4, a CEA cost table can replace a chart entirely. (Tufte: "a good summary table *is* a visualization" — Spiegelhalter 2017 cites this approvingly.)
6. **Fan charts:** *commonly understood by federal economists* (Britton, Fisher & Whitley 1998 BoE Quarterly Bulletin; CBO's *Long-Term Budget Outlook* uses fan-style probabilistic projections). However, for this project the fan chart is **not used** — see Q12.4 — because [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s uncertainty is *not* a forward-time density; it is a *cross-sectional percentile range over an option choice*. Using a fan chart would mis-cue the reader.
7. **Accessibility:** WCAG 2.0 AA contrast ratio ≥ 4.5:1 for text, ≥ 3:1 for non-text/graphical info; per USWDS data-viz guidance, every chart has a screen-reader-only data table; line charts start at zero unless explicitly noted; bar charts use textured fill or distinct hues redundant with shape.

---

## Q12.4 Uncertainty Visualization (HIGHEST LEVERAGE)

**The problem.** [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) is loud about uncertainty: realization rate spans 15–40% ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §VI item 1), per-application time saved spans 1–3 min (item 2), and these dominate sensitivity. Naïve error bars systematically *under-represent* uncertainty for non-statisticians (Hullman, Resnick & Adar 2015; Kale, Nguyen, Kay & Hullman 2019); they also imply symmetric tails, which [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) does not have (90th-percentile is intentionally pessimistic-side).

### Decisions

**D‑U1. Percentile direction is *not* symmetric and must be visually marked.**
[T11](./2026-09-15-economic-cost-effectiveness-analysis.md) uses 50th = most-likely, 80th = should-cost, 90th = reserve. For *cost*: the 90th sits to the *right* (higher). For *savings*: the 90th sits to the *left* (worse realization). On a single chart this can look like the 90th has flipped sides between two adjacent bars. **Solution:** every chart with percentile ranges carries the **P‑PercentileNotch** glyph and a one-line legend "▷50th ◇80th ▌90th (reserve / pessimistic side)". The legend explicitly states which direction is "worse" for that metric.

**D‑U2. Pick the right uncertainty idiom for the audience and task** (Spiegelhalter 2017 Table 4 + Kale 2019):

| Idiom | When used in this deliverable | Why |
|---|---|---|
| **P‑PercentileNotch range bar** (50th tick + 80th notch + 90th tail; static) | All A1/A2/A4/A5 figures | Static, prints in B&W, respects asymmetry, encodes 3 named percentiles directly. Default. |
| **Density strip / gradient bar** | Never in the headline; appendix only | Gradient implies continuous density, which we don't have — we have three named quantiles. Misleading. |
| **Quantile dotplot** (Kay, Kola, Hullman & Munson 2016; Fernandes et al. 2018) | Take-home reviewer (A1) supplemental figure for the realization-rate break-even | Frequency framing; 20-dot plot conveys "1 in 5 plausible worlds" intuitively for a non-economist reviewer |
| **HOPs (animated, Hullman 2015 / Kale 2019)** | Notebook only (A6) | Excellent for analysts; fails on PDF and is not 508-conformant in static form |
| **Fan chart** (BoE; Britton, Fisher, Whitley 1998) | **Rejected** | Implies continuous time-axis density and symmetric central probability. [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) has neither. Audience will mis-cue if shown one. |
| **Box / violin** | Rejected for headline | Violins have known density-misreading issues (Correll & Gleicher 2014, cited in Kale 2019); box plots compress the named percentiles into invisible quartiles. |
| **Tornado for sensitivity** (per Q12.6) | Yes, but only for *driver ranking*, not for *uncertainty about the result* | Eschenbach 1992 — tornado answers "which input matters" not "what is the range of the output." |

**D‑U3. Don't compress the three percentiles to "low / mid / high."**
This is an explicit [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)-derived anti-pattern (Q12.15 AP‑1). The 50th is the *most-likely* point estimate, not a "mid"; the 90th is the *reserve*, not a "worst." The English labels mis-cue federal readers who know the distinction.

**D‑U4. Show the don't-knows beside the knowns.**
Every range bar carries an optional "★" glyph keyed to the relevant [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §XI item. Hovering (in the interactive) or footnoting (in print) reveals: *"Range assumes the 25%-realization figure transferred from CMS / IRS prior precedents — TTB-specific realized savings precedent is unknown ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §XI item 8)."* This is Spiegelhalter (2017) "humility about uncertainty" and the GAO‑20‑195G *"data sufficient to estimate"* convention operationalized — see Q12.7.

**D‑U5. Audience effects on uncertainty viz.**
Kale 2019 finds HOPs work for *untrained* observers on *trend* tasks. [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s tasks are *option-comparison* (A vs C vs G) and *break-even* (where does the realization rate flip the sign?). For option-comparison the literature favors static intervals with explicit endpoints (Hullman 2015 §6 — "for ordering judgments, HOPs > error bars"; for *quantitative readout*, static intervals win). For break-even, a flip-point chart is correct (Q12.6). Therefore HOPs are not the right idiom for the headline; they live in the notebook.

### Specification — `P‑PercentileNotch`

```
DATA STRUCTURE
  metric:     string (e.g., "5-yr TCO Option A")
  p50:        number (most-likely)
  p80:        number (should-cost)
  p90:        number (reserve / pessimistic-side bound)
  direction:  enum {cost, savings}    # cost: p90 > p80 > p50; savings: p90 < p80 < p50
  unit:       string (e.g., "$M FY26")
  unknown_id: optional pointer into T11 §XI register {A-3, R-08, ...}

ENCODING
  horizontal axis: numeric, linear, zero-anchored unless explicitly broken
  bar:    thin (height ≤ 8 px) baseline rule from p50 to p90
  glyph at p50:  filled triangle ▷ (most-likely)        — 4-channel encoding: position + shape + label + lightness
  glyph at p80:  open diamond  ◇ (should-cost)
  glyph at p90:  short tick     ▌ (reserve)
  color:  single hue; lightness sequenced 50th(darkest)→90th(lightest); never red/green
  redundant text: numeric label at p50 (always); at p90 (if reserve > 1.5× p50)
  star ★: only rendered if unknown_id ≠ null; click/hover reveals §XI text

ACCESSIBILITY
  alt-text auto-generated:
    "{metric}: most-likely {p50}{unit}; should-cost {p80}{unit}; reserve {p90}{unit}.
     {direction == 'cost' ? 'Higher = worse.' : 'Lower = worse realization.'}
     Knowledge gap: {§XI ref}."
```

Render in matplotlib / Vega-Lite / Plotly all support this with one custom layer. Reference implementation lives in `notebooks/t11_charts.ipynb`.

---

## Q12.5 Staged Analysis Visualization

[T11](./2026-09-15-economic-cost-effectiveness-analysis.md) propagates uncertainty across five stages. Each stage's percentile range is the input to the next. Communicating this honestly — without either (a) hiding the propagation in a single net-NPV bar, or (b) burying the audience in five separate range bars they have to mentally compose — is the central challenge.

### The five stages (from [T11](./2026-09-15-economic-cost-effectiveness-analysis.md))

1. **Stage 1 — per-application time saved**: 50th 2.0 min / 80th 3.0 min / 90th 1.0 min
2. **Stage 2 — aggregate annual gross savings** (volume × time × $89.05/hr GS‑12 Step 5 DC): 50th $564K / 80th $935K / 90th $252K
3. **Stage 3 — 5‑yr TCO** (Option A central): 50th $2.4M / 80th $3.9M / 90th $5.8M
4. **Stage 4 — net 5‑yr NPV** (realized benefit − cost): 50th −$1.72M / 80th −$2.81M / 90th −$5.39M
5. **Stage 5 — sensitivity** (tornado), ranked by NPV swing across the 9 levers

### Pattern: `P‑StageWaterfall` (for README and presentation)

A horizontal waterfall reading **Gross savings (Stage 2) → realization haircut (1 − 0.25 = 0.75 reduction at 50th) → realized savings → A‑94 5‑yr discount → vs 5‑yr TCO (Stage 3) → net 5‑yr NPV**. This is the second-priority chart in the deliverable (after the headline TCO band; see Q12.8) and answers the question every audience asks: *"Why is the NPV negative — where does the money go?"*

Specification (50th-percentile / Option A central case; arithmetic verified against [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)):

```
STEP                                            DELTA       CUMULATIVE
1. Gross annual labor savings                   +$564K       $564K       (Stage 2, undiscounted, 1 yr)
2. × 5 years (undiscounted)                     +$2.256M     $2.820M     ($564K × 5)
3. × 25% realization (75% haircut)              −$2.115M     $0.705M     (T11 default; 5-yr undiscounted realized)
4. A-94 disc 1.3% real (5-yr NPV of stream)     −$0.025M     $0.680M     (NPV of $141K/yr × 5 yr at 1.3%)
5. − 5-yr TCO Option A                          −$2.400M    −$1.720M     (T7 50th-percentile)
```

Encoding:

- Increase (savings): **blue**, hatch ↗
- Decrease (haircut, discount, cost): **orange**, hatch ↘
- Subtotal: **gray**, no hatch
- Each bar carries a small `P‑PercentileNotch` *above* it showing the 80th and 90th alternatives — this is what makes the waterfall *propagated*, not point-only.
- Title: *"Why the 5-yr NPV is negative: from gross labor savings to net cost (50th-percentile, Option A; FY26 $; A-94 1.3% real)."*
- Footer: *"Realization-rate haircut is the largest single negative step (−$2.1M of $2.8M gross). The A-94 discount on the residual stream is small (−$25K) because the discount rate is low (1.3% real). Range bars above each step show 80th and 90th alternatives."*

### Pattern: `P‑StageSmallMultiples` (for the appendix and the analyst notebook)

Five panels in a row, one per stage, each rendered as a `P‑PercentileNotch` on a shared horizontal scale where possible (Stages 1 and 5 use different units so they get a separator). This is Tufte's small-multiples pattern (*Envisioning Information* 1990, §4) and it rewards careful viewers; it loses casual viewers. Use only for A2/A4/A6.

```
[ Stage 1: time/app ▷2.0 ◇3.0 ▌1.0 min ]    [ Stage 2: gross/yr ▷$564K ◇$935K ▌$252K ]
[ Stage 3: 5-yr TCO ▷$2.4M ◇$3.9M ▌$5.8M ]  [ Stage 4: net NPV ▷−$1.72M ◇−$2.81M ▌−$5.39M ]
[ Stage 5: sensitivity → see tornado, Q12.6 ]
```

### Different surface, different idiom

| Surface | Stage-propagation idiom | Why |
|---|---|---|
| README (markdown, GitHub-rendered) | `P‑StageWaterfall` only | One chart, narrative reading order |
| 8-slide presentation | `P‑StageWaterfall` slide 2; `P‑StageSmallMultiples` as backup slide; tornado as slide 4 | Pacing per [T8](./2026-09-15-federal-ux-for-senior-users.md) Q8.8 demo path |
| Interactive notebook (A6) | All of the above + a Sankey from input quantiles → output NPV (Stage 5 sensitivity as flow) | Analyst can drag realization rate and watch Stage 4 update |
| Procurement memo (A4) | Tabular WBS waterfall, no chart | Federal preference for tables in formal deliverables |

---

## Q12.6 Sensitivity Analysis (Stage 5)

[T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s tornado has 9 levers, ranked by NPV swing. From [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §VI:

| # | Lever | NPV swing |
|---|---|---|
| 1 | Realization rate (15–40%) | ±$0.7M |
| 2 | Time saved per app (1–3 min) | ±$0.6M |
| 3 | ATO/build cost (PM+SysDev+ATO+3PAO, 50th–90th) | ±$1.4M (cost-side) |
| 4 | Lock-in reserve ($0–$500K) | ±$0.5M (cost-side) |
| 5 | Volume (170–210K apps) | ±$0.15M |
| 6 | Labor rate (GS‑11→GS‑13 DC, $73–$106/hr) | ±$0.13M |
| 7 | Ops labor (0.5–1.0 FTE) | ±$0.4M (cost-side) |
| 8 | Cloud OCR cost over 5 yr | ±$50K — **negligible** |
| 9 | Cloud LLM cost over 5 yr | ±$10K — **negligible** |

### Specification — `P‑Tornado`

Standard deterministic-sensitivity tornado per Eschenbach (1992) and GAO‑20‑195G ch. 14:

```
ROW ORDER     largest swing at top, smallest at bottom (sorted by |swing|)
AXIS          centered on 50th-percentile NPV (here −$1.72M, vertical 0-line)
BAR           one bar per lever, extending left (favorable) and right (unfavorable)
              direction is per T11 percentile convention — 90th is right (worse)
ENDPOINT LABELS  numeric value of the swing endpoint
ANNOTATIONS  items 8-9 rendered in light gray with text "negligible" — visible
              but not competing for attention; this is honest about what doesn't matter
TITLE         "Drivers of 5-yr NPV (Option A, 50th-percentile baseline = −$1.72M, FY26 $)"
FOOTER        "Cloud OCR/LLM cost combined ≈ $60K over 5 yr (T11 §V Stage 5 items 8-9)
              — confirms T5 conclusion that inference cost is not the decision driver."
```

### Spider plot — *rejected*

Eschenbach (1992) himself argued tornado and spider are *complementary*: tornado for many-input ranking, spider for *non-linearity* in a small number of inputs. [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s drivers are predominantly linear over the percentile range (realization rate × volume × time-saved is multiplicative but locally linear); the audience benefit of a spider plot is low and the cost (radial axes are widely misread) is high. **Decision: tornado only.** The Howard / Eschenbach flip-point chart (`P‑BreakEven` below) covers the non-linearity question for the one lever that matters (realization rate).

### Two-way heat map — *yes, in the notebook*

For (realization rate × time-saved-per-app), a 5×5 heat map of net 5‑yr NPV with the sign-flip contour drawn. This belongs in A6 (notebook) and as a backup slide for A2 (Sarah). Cells colored by NPV magnitude (sequential blue→orange diverging at zero, redundantly labeled with $ value). The contour line answers Sarah's question directly: *"What combination of (realization, time-saved) flips this to break-even?"*

### Flip-point chart — `P‑BreakEven`

Per Howard's decision-analysis tradition (also Eschenbach 1992 §3): a 1‑D plot of net 5‑yr NPV (Option A) as a function of realization rate, with three curves (50th / 80th / 90th time-saved) plus a vertical band marking the [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) default 25% realization. **Specification updated in v4 with corrected arithmetic (see Q12.9 V4).** This chart is non-optional for A2 and A4.

### When tabular beats visual

For A4 (procurement officer): a 9-row table of (lever, range, NPV swing, % of total swing, direction) outperforms the tornado. Tables let A4 cite specific rows in their memo. Provide both; lead with the table in the procurement deliverable.

---

## Q12.7 Showing "We Don't Know X" Credibly

This is where most economic analyses fail. The temptation is to push uncertainty into a wider range bar; the discipline is to label what is *unknown in kind*, not just *unknown in magnitude*.

### Three orthogonal "don't know" categories (Spiegelhalter 2017 §6 + GAO‑20‑195G "data sufficient to estimate")

1. **Aleatory** — known random variation (e.g., per-application time will always vary across labels). Communicate with the percentile range bar.
2. **Epistemic, characterized** — we have a literature precedent or analog but no TTB-specific data (e.g., realization rate transferred from CMS/IRS analogs). Communicate with a `★` glyph + footnote citing the analog.
3. **Epistemic, uncharacterized** — we have neither TTB data nor a defensible analog (e.g., "future FedRAMP-High status of Claude 4.5/4.6/Opus 4.x"). **Refuse to put a number on this.** Communicate with text only and a Spiegelhalter-style verbal probability ("not knowable from available evidence").

### [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §XI ten-item register — verbatim mapping

| # | Unknown ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §XI) | Category | T12 treatment |
|---|---|---|---|
| 1 | Empirical review-time distribution at TTB | Epist. characterized (we have CMS/USDA analog) | ★ on Stage 1 chart; footnote *"Range derived from [T9](./2026-09-15-verification-targets-research.md) ABV-correction analog (±0.3 pp) and CMS analog; TTB empirical distribution unknown — see 04‑research‑topics A‑3"* |
| 2 | Seasonality (intra-year COLA volume swings) | Epist. characterized | Footnote on volume axis |
| 3 | Importer / domestic split | Epist. uncharacterized | Text-only note in §V; not in any chart |
| 4 | Small / large producer share | Epist. uncharacterized | Text-only |
| 5 | Forward volume CAGR | Epist. uncharacterized | Volume held flat 190K in all 5 yrs; flagged in title |
| 6 | Inter-agent reviewer variance | Epist. characterized ([T9](./2026-09-15-verification-targets-research.md) Krippendorff α gap) | ★ on Stage 1 |
| 7 | TTB-specific ATO timeline | Epist. uncharacterized | Drives the 12–36 mo / $250K–$500K lock-in reserve range; ★ on cost-side tornado bar |
| 8 | Realized vs claimed savings precedent | Epist. characterized | ★ on realization-rate axis; footnote *"25% default per CMS/IRS analog; TTB precedent unknown"* |
| 9 | Headcount-ceiling decisions | Epist. uncharacterized | Text-only in §V |
| 10 | Future FedRAMP-High status of Claude 4.5/4.6/Opus 4.x | Epist. uncharacterized | Text-only in §X risk register R‑11 (links to §IX) |

### CBO band conventions, applied here

CBO uses *fan-style* probabilistic bands for forward economic projections (current 2026 *Long-Term Budget Outlook* and *Budget and Economic Outlook 2026‑2036*). They label the *central* projection as "current law" and surround it with shaded fan deciles. **We deliberately do not adopt the CBO fan idiom for [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)** because [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s percentiles are over an *option-design choice* (which cloud, which model), not over a *forward-time density*. Adopting the CBO idiom would import a temporal-density misreading. Where we *do* borrow from CBO: the *labelled* percentile narrative ("In CBO's projections, …") becomes *"In our 50th-percentile case, …"* — a verbal anchor before any chart.

### Pattern: `P‑KnowledgeRegister`

A standalone half-page artifact at the *front* of the economic analysis (not the back), inspired by Gebru et al. (2021) *Datasheets for Datasets* and Bender & Friedman (2018) *Data Statements for NLP*. Ten rows × five columns: unknown / category / why it matters / how the analysis handles it / what would resolve it.

This is GAO Step 6 ("ground rules and assumptions") rendered as a transparency artifact rather than a buried section. It is the single most credibility-building element for A4 (procurement officer).

---

## Q12.8 Headline Chart — Resolving the CEA / Negative-NPV Tension

### The tension

[T11](./2026-09-15-economic-cost-effectiveness-analysis.md) is a CEA, not a BCA. At the 50th percentile, every option produces a *negative* 5‑yr NPV on monetized labor savings alone. Three failure modes if mishandled:

- **Failure A — lead with net NPV.** A range bar showing options A/C/G all negative invites the reviewer to conclude "this project doesn't pay for itself; recommend kill." This is *out-of-context misreading*: the project delivers a *mandated* review function, so direct NPV is not the decision criterion. ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §V is explicit about this.)
- **Failure B — hide the negative number.** Lead with cost only, or savings only, and the reviewer rightly concludes the analyst is selling. Loses A1, A2, and A4 instantly.
- **Failure C — overload.** Try to show CEA framing + cost + savings + percentile + option in one chart. No one reads it.

### The resolution: `P‑CEABand` headline

A **three-option 5‑yr TCO band chart** (Option A vs C vs G, each with `P‑PercentileNotch`) on a horizontal cost axis, **with a single annotated horizontal line** at the 50th-percentile *realized* annual labor savings × A‑94 5‑yr NPV ≈ $0.68M. Title and subtitle do the framing work:

```
TITLE:    "Least-cost delivery of mandated COLA review (5-yr TCO, FY26 $; A-94 1.3% real)"
SUBTITLE: "Cost-effectiveness analysis: review function is mandated; question is cheapest credible delivery."
SUBTITLE-2: "Direct labor savings (50th-percentile, 5-yr NPV) cover ~$0.68M of 5-yr cost — this is expected for a mandated-benefit program."

Y-axis (categorical, top to bottom):
  Option A  (Azure Gov + AOAI Gov + Azure DI)
  Option C  (AWS GovCloud + Bedrock + Textract)
  Option G  (self-hosted Llama/Granite, Azure Gov)

X-axis: $ millions, FY26 constant
  Each row: P-PercentileNotch with ▷50th ◇80th ▌90th
  Option A: ▷$2.4M ◇$3.9M ▌$5.8M
  Option C: ▷$3.1M ◇$4.9M ▌$7.2M
  Option G: ▷$3.5M ◇$5.5M ▌$7.5M

OVERLAY:
  vertical dashed line at $0.68M labelled "50th-pctile realized labor savings, 5-yr NPV"
  small footnote arrow: "≈ $141K/yr × 5 yr × A-94 1.3% real disc."

FOOTER:
  "Negative direct NPV is the expected CEA result for a mandated-benefit program (T11 §V).
   Decision drivers: ATO/build cost (T7), realization rate (T11 §VI), lock-in posture (12-36 mo / $250K-$500K).
   Source: T11 §V Stage 3-4; T7 WBS; OMB A-94 App. C (M-26-09)."
```

### Why this resolves the tension

1. **Framing is in the title** — "least-cost delivery of mandated review" — so the reader's first cognitive frame is CEA, not BCA. Knaflic (2015) ch. 3: title carries the message.
2. **Costs are the bars; savings are a single reference line.** The visual hierarchy makes cost the comparison and savings the *context*, which is correct for CEA.
3. **The negative number is not on the chart but is *not hidden*** — the subtitle and footer state plainly that direct savings cover only ~$0.68M of cost. A reader who wants the −$1.72M can derive it ($2.4M − $0.68M ≈ $1.72M); the waterfall (Q12.5) shows it explicitly as the second chart.
4. **Three options on one axis** lets A5 (CIO) make the option choice in 5 seconds; A becomes "low-cost lane," C and G are visibly more expensive.
5. **80th and 90th percentiles are present** so A4 (procurement officer) can read should-cost and reserve directly without a second chart.

### What was rejected and why

- **Net-value range bars (A vs C vs G with negative NPVs)** — Failure A.
- **Decision matrix as headline** — too text-heavy for A1/A5; works as slide 7, not slide 1.
- **Waterfall as headline** — answers "why" before the audience has heard "what." Waterfall is slide 2.
- **Tornado as headline** — answers "which lever" before the audience has heard the result. Slide 4.

### The tension is genuine

There is no chart that simultaneously (a) shows the −$1.72M directly, (b) doesn't lead with bad news, and (c) is read in 5 seconds by a CIO. The resolution is *sequence*, not *single chart*: headline = `P‑CEABand` (least-cost framing); slide 2 = `P‑StageWaterfall` (where the gap comes from); slide 3 = `P‑BreakEven` (what would close it); slide 4 = `P‑Tornado` (which lever to push). The negative number appears on slide 2, in context.

---

## Q12.9 Per-Stage Charts — The Six [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §XII Visualizations, Specified

[T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §XII names six visualizations as T12-pointers. Concrete specs implementable from [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s CSV data follow. All use `P‑PercentileNotch` glyphs and 50th/80th/90th naming.

### V1. Tornado (from [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) Q11.18 / Stage 5)

Already specified in Q12.6 above as `P‑Tornado`. Data: `t11_sensitivity.csv` (lever, p50_value, p90_value, swing_dollars, direction). Render: 9 horizontal bars centered on −$1.72M baseline; cloud cost rows in light gray; sort by |swing| desc.

### V2. Waterfall — Stage 1 → Stage 2 → Stage 4

Already specified in Q12.5 above as `P‑StageWaterfall` with corrected arithmetic. Data: 5-row sequence with per-row 80th/90th overlays drawn from [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) Stages 2, 3, 4. Render order: gross savings → 5× → realization haircut (75% reduction at 25% realization) → A‑94 5-yr NPV discount → minus TCO → net NPV.

### V3. Three-option TCO band (A vs C vs G at 50/80/90)

Already specified in Q12.8 above as `P‑CEABand`. Data: 9 cells (3 options × 3 percentiles) from [T7](./2026-09-15-federal-deployment-compliance.md) + [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) Stage 3. This is the headline.

### V4. Realization-rate break-even curve — `P‑BreakEven` (CORRECTED in v4)

A 1-D plot of net 5-yr NPV (Option A) as a function of realization rate, with three curves (50th / 80th / 90th time-saved) plus a vertical band marking [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s modeled realization range (15–40%) and the 25% default.

**Underlying arithmetic (verified):**
- 5-yr annuity factor at 1.3% real (A-94) = (1 − 1.013⁻⁵) / 0.013 ≈ **4.799**
- 50th-time gross/yr ($564K) → 5-yr NPV gross at 100% realization: $2.707M
- 80th-time gross/yr ($935K, [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) 80th-volume × 80th-time) → 5-yr NPV gross: $4.487M
- 90th-time gross/yr ($252K, [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) 90th-volume × 90th-time) → 5-yr NPV gross: $1.209M
- Net 5-yr NPV = realization × gross_5yr_NPV − $2.4M (Option A 50th-percentile TCO)

**Data table (corrected):**

```
realization,  net_npv_50th_time,  net_npv_80th_time,  net_npv_90th_time
0.10,         −$2.13M,            −$1.95M,            −$2.28M
0.15,         −$1.99M,            −$1.73M,            −$2.22M
0.20,         −$1.86M,            −$1.50M,            −$2.16M
0.25 (T11),   −$1.72M,            −$1.28M,            −$2.10M  ← T11 default
0.30,         −$1.59M,            −$1.05M,            −$2.04M
0.35,         −$1.45M,            −$0.83M,            −$1.98M
0.40,         −$1.32M,            −$0.60M,            −$1.92M  ← T11 80th realization
0.55,          —,                 +$0.07M,             —       ← break-even on 80th-time
0.89,         +$0.01M,             —,                  —       ← break-even on 50th-time
```

**Encoding:**
- Three curves on one axis. Vertical shaded band from 0.15 to 0.40 = [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s modeled realization range. Vertical line at 0.25 = [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) default.
- Horizontal zero-line.
- Annotations at break-even crossings:
  - "50th-time × Option A: break-even ≈ 89% realization (outside modeled range)"
  - "80th-time × Option A: break-even ≈ 55% realization (outside modeled range)"
  - "90th-time × Option A: never reaches break-even (max realized = $1.21M < $2.4M cost)"

**Title:** *"Realization rate is the largest NPV driver. Break-even on direct labor savings alone is unreachable within [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s modeled realization range (15–40%) at GS‑12 DC labor — the expected and correct CEA result for a mandated-benefit program."*

**Footer:** *"Even at 80th-percentile time-saved (3 min) and the top of the modeled realization range (40%), net 5-yr NPV is −$0.60M. Break-even requires realization ~55%, well outside any plausible posture. [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §VII Q11.19 notes that GS-13 DC labor + >40% realization 'approaches break-even'; our chart confirms it does not cross zero. Implication: this CEA's recommendation cannot rest on direct monetized savings; non-monetary benefits and least-cost-delivery framing carry the decision."*

This is the **most analytically important chart in the deliverable** for A2 (Sarah) and A4 (procurement officer). It demonstrates the analyst understands the program is a CEA, not a BCA, and is honest about what the numbers say.

### V5. OPM grade × locality matrix

Tabular heat map. Rows = OPM grades (GS‑11, GS‑12, GS‑13). Columns = locality (DC, RUS, ATL, SF, etc.). Cells = hourly fully-loaded $/hr (FY26). [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) uses GS‑12 Step 5 DC = $89.05/hr as the central case. Highlight that cell with a heavy border. Color scale sequential blue, but the *purpose* of the chart is to show that NPV-swing of the labor-rate lever ($73–$106/hr) is small ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md) Stage 5 item 6, ±$0.13M). Title: *"Labor rate ranges across OPM grade × locality — small NPV impact (±$0.13M, [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §VI item 6)."*

This is a *de-emphasis* chart — its purpose is to *show* something doesn't matter much, and to head off the procurement officer's question about which step / locality.

### V6. GAO 12-step compliance map

Twelve cells in a 3×4 grid, one per GAO‑20‑195G step. Each cell colored by [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s coverage status:

```
1 Define purpose          ✓  T11 §I
2 Develop estimating plan  ✓  T11 §II
3 Define program           ✓  T7 + T11 §III
4 Determine WBS            ✓  T7
5 Identify ground rules    ✓  T11 §VI + §XI
6 Obtain data              ✓  T11 §IV
7 Develop point estimate   ⚠  ICE deferred (T11 §VIII note)
8 Conduct risk/uncert.     ✓  T11 §X (R-01..R-12)
9 Conduct sensitivity      ✓  T11 §VI
10 Document                ✓  T11 §IX
11 Present to mgmt         ⚠  deferred to TTB review
12 Update with actuals     ⚠  deferred to deployment
```

Render: 3×4 grid, each cell is a labeled box; ✓ in green-equivalent (USWDS green-50 plus check-mark glyph for 508 redundancy) and ⚠ in amber/orange. Title: *"GAO‑20‑195G coverage: 9 of 12 steps complete; 3 explicitly deferred."*

This is the single most useful chart for A4 (procurement officer) and should be slide 1 of the procurement memo.

---

## Q12.10 Interactive vs Static — Hybrid

**Decision: hybrid, with a static-first default.**

- **Static (PDF / Markdown / printed deck)** is the deliverable for A1, A4, and A5. Federal review processes expect PDFs that print B&W-readable. Every chart in the deliverable is rendered first as static SVG/PNG using `P‑PercentileNotch` and renders correctly without color.
- **Interactive (Quarto/Jupyter notebook + a single Plotly-Dash mini-app)** is the supplemental for A2 (Sarah) and A6 (ourselves). The interactive surfaces:
  - Realization-rate slider on `P‑BreakEven`
  - Time-saved-per-app slider
  - Option toggle (A/C/G)
  - Percentile toggle (which of 50/80/90 is the central reference)
- HOPs (animated, Hullman 2015) live *only* in the notebook, not in any deliverable artifact.

**Anti-pattern flagged:** an interactive chart shown in a live demo to A4 without a static fallback. Federal reviewers will ask for "the figure" and "the figure" must be a single static SVG with a stable filename.

---

## Q12.11 Architecture Diagrams (lighter)

C4 model (Brown 2006–2018; *The C4 Model*, O'Reilly 2026). For [T7](./2026-09-15-federal-deployment-compliance.md)'s 6-component option, ASCII is sufficient and preferred — the deliverable should print on one page.

**Decision rules:**

- **≤ 6 nodes → ASCII box-and-arrow** in the markdown source. Renders identically across GitHub, VS Code, and PDF.
- **7–15 nodes → C4 Container diagram** (single PNG, exported from Structurizr or PlantUML).
- **> 15 nodes → C4 Component diagram** plus a Container diagram; never a single all-in-one.
- Always include a *boundary* showing the FedRAMP/ATO authorization boundary. This is what A4 looks for.

Reference ASCII pattern (Option A, 6 nodes, fits the rule):

```
  +-------------+    +---------------+    +-----------------+
  | COLA submit | -> | Azure Doc Int | -> | Azure OpenAI Gov|
  | (PDF/JPG)   |    | (OCR)         |    | (LLM)           |
  +-------------+    +---------------+    +-----------------+
                              |                    |
                              v                    v
                     +-------------------------------+
                     | Reviewer queue (Sarah, T10)   |
                     +-------------------------------+
                     [ FedRAMP-High Azure Gov boundary ]
```

Lighter than the C4-Container diagram [T7](./2026-09-15-federal-deployment-compliance.md) produced; fine for the README.

---

## Q12.12 Stakeholder Maps (lighter)

Per [T10](./2026-09-15-stakeholder-frameworks.md). Two artifacts:

1. **Snapshot** (date-stamped, per [T10](./2026-09-15-stakeholder-frameworks.md) cadence): Mendelow salience grid (power × interest), 2×2, with current names placed. Single PNG; updated at each milestone.
2. **Log** (cumulative, per [T10](./2026-09-15-stakeholder-frameworks.md) §3.1 and 05‑gaps §3.1): chronological list of stakeholder engagements with date, channel, and what was learned. Markdown table, not a chart.

The snapshot is the chart; the log is the table. Don't try to combine them.

A simple RACI table is sufficient for the demo team and demo path (Q12.14); not chart-worthy.

---

## Q12.13 Evaluation Scorecards (lighter)

Per [T9](./2026-09-15-verification-targets-research.md). Three artifacts:

1. **Krippendorff α scorecard** (single bullet graph, Few 2013): α target ≥ 0.80, current α value, 95% CI as range. Bullet graph qualitative bands per Krippendorff (2019): <0.667 unreliable / 0.667–0.79 tentative / ≥0.80 reliable. Rendered with USWDS palette; reads B&W.
2. **Datasheet** (Gebru et al. 2021, CACM 64(12):86–92): a 7-section markdown document for the COLA labels training set — Motivation / Composition / Collection / Preprocessing / Uses / Distribution / Maintenance.
3. **Data Statement** (Bender & Friedman 2018, TACL): for any text-extraction NLP dataset (e.g., the OCR-text training/eval corpus). A six-section markdown document — Curation rationale / Language variety / Speaker demographic / Annotator demographic / Speech situation / Text characteristics.

The ABV ±0.3 pp correction ([T9](./2026-09-15-verification-targets-research.md)) is rendered as a single annotated dot plot of (predicted ABV − ground-truth ABV) with the ±0.3 pp tolerance band shaded. Bullet-graph variant works equally well.

---

## Q12.14 Demo Path Visualization (lighter)

Per [T8](./2026-09-15-federal-ux-for-senior-users.md) Q8.8 and 05‑gaps §3.4. Two artifacts:

1. **Demo flow** (linear): a 6-station ASCII sequence with per-station time budget and "what we show / what we say / what we hide." Renders in markdown.
2. **Pacing chart** (timeline): horizontal bar with 6 segments scaled to time budget; annotations at expected handoff points. Use [T8](./2026-09-15-federal-ux-for-senior-users.md)'s reconciliation between live demo and recorded fallback.

Anti-pattern: showing the architecture diagram during the demo. A3 (Marcus) wants it; A1/A2/A5 don't. Architecture diagram lives in the supplementary deck.

---

## Q12.15 Anti-Patterns (project-specific)

**AP‑1 — Compress 50th/80th/90th to "low / mid / high."** Loses the federal naming convention and the directional asymmetry. Always spell out *"50th-percentile (most-likely) / 80th-percentile (should-cost) / 90th-percentile (reserve)."*

**AP‑2 — Lead with the −$1.72M net 5‑yr NPV out of context.** The number is correct but is meaningless without the CEA framing. If quoted in isolation it reads as "project fails." Always pair with the CEA-framing sentence from [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §V.

**AP‑3 — Hide the realization rate.** The realization rate is the largest single driver of NPV ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §VI item 1, ±$0.7M swing). Charts that show net NPV without exposing the realization-rate assumption are misleading. Every NPV chart cites the realization-rate assumption in the footer; the `P‑BreakEven` chart is non-optional.

**AP‑4 — Use a fan chart.** [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s percentiles are not a forward-time density. Fan charts mis-cue federal economists into expecting CBO/BoE-style temporal probability bands.

**AP‑5 — Overlay a tornado on a probabilistic NPV distribution.** GAO‑20‑195G separates Step 8 (risk register, uncertainty) from Step 9 (sensitivity). [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) keeps R‑01..R‑12 (risk) distinct from the 9-lever tornado (sensitivity); T12 must too. *Two charts, not one.*

**AP‑6 — Use red/green for waterfall increase/decrease.** Section 508 / WCAG 2.0 AA fails. Use blue/orange + hatch + text label ([T8](./2026-09-15-federal-ux-for-senior-users.md) 4-channel rule).

**AP‑7 — Tile six different percentile naming systems.** Standardize on 50th/80th/90th throughout. Don't drift to P50/P80/P90 in code variable names while the charts say "50th-percentile" — A4 will catch the inconsistency.

**AP‑8 — Hide the §XI register at the back.** It belongs at the front, as `P‑KnowledgeRegister`. Federal reviewers reward humility about uncertainty; they punish it appearing late.

**AP‑9 — Show negative NPV without a CEA-framing title.** Failure A in Q12.8.

**AP‑10 — Quote 5‑yr NPV at a discount rate other than A‑94 App. C (M‑26‑09) 1.3% real.** [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) is constant-dollar at 1.3% real (5‑yr); any other rate makes it look like the analyst doesn't know A‑94. If anyone asks for nominal rates, flag the requirement and re-discount; do not silently swap.

**AP‑11 — Use a CBO-style fan band for the option choice.** AP‑4 + AP‑1 combined. CBO bands are over time; [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)'s bands are over option-design.

**AP‑12 — Treat HOPs as a presentation chart.** HOPs are an *analyst* idiom. They fail in PDFs and are not 508-conformant in static form.

**AP‑13 — Conflate snapshot stakeholder map with cumulative log.** Per [T10](./2026-09-15-stakeholder-frameworks.md) / 05‑gaps §3.1. Snapshot answers "who right now"; log answers "what was learned over time." Different artifacts.

**AP‑14 — Skip the alt-text.** USWDS data-viz guidance and Section 508 require it. Auto-generate from the `P‑PercentileNotch` data structure; never ship a chart without it.

**AP‑15 — Use Knaflic's "spotlight one number" pattern on the negative NPV.** Knaflic's preattentive-attribute spotlight works *for a positive lead*. Spotlighting −$1.72M is just AP‑2 with bold type.

**AP‑16 (NEW v4) — Mis-state intermediate arithmetic in the waterfall.** A federal reviewer will recompute a waterfall step-by-step. If the cumulative values don't match the stated final NPV, the entire credibility of the deliverable collapses (GAO‑20‑195G four-pillar "accurate"). The `P‑StageWaterfall` spec in Q12.5 must show: gross/yr × 5 × (1 − realization_rate) × A‑94 disc factor − TCO = net NPV, with *every* intermediate value computable from the previous one. v3's waterfall had wrong intermediate deltas while showing the correct final number; this would have failed an A4 review. Always derive the waterfall directly from [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) Stage 2/3/4 anchor numbers, not by working backwards from the answer.

---

## Pattern Library — named patterns

| Pattern | Where used | One-line definition |
|---|---|---|
| `P‑PercentileNotch` | every percentile range bar | ▷50th tick + ◇80th notch + ▌90th tail; direction-aware; alt-text auto |
| `P‑CEABand` | headline (Q12.8) | 3-option TCO band with single labor-savings reference line and CEA-framing title |
| `P‑StageWaterfall` | slide 2 / README #2 (Q12.5) | 5-step waterfall gross→haircut→discount→cost→net, with per-step `P‑PercentileNotch` overlays; arithmetic verified |
| `P‑StageSmallMultiples` | appendix / notebook | 5-panel small multiples, one per [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) stage |
| `P‑Tornado` | Q12.6 / V1 | 9-lever horizontal tornado on 50th-percentile baseline; "negligible" rows in light gray |
| `P‑BreakEven` | Q12.6 / V4 | 1-D NPV vs realization-rate plot with three time-saved curves + zero-line + [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) default band; honest about unreachable break-even |
| `P‑KnowledgeRegister` | front of analysis (Q12.7) | 10-row table of [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) §XI unknowns; category × treatment × resolution-pathway |
| `P‑CEAFraming` | every chart title that touches NPV | First line: "least-cost delivery of mandated …"; second line: "FY26 $; A‑94 App. C 1.3% real" |
| `P‑GAO12Map` | procurement memo slide 1 (V6) | 3×4 grid of GAO‑20‑195G steps with ✓/⚠ status |
| `P‑BulletScorecard` | [T9](./2026-09-15-verification-targets-research.md) evaluation (Q12.13) | Few (2013) bullet graph for Krippendorff α and ABV ±0.3 pp |
| `P‑508Hatch` | every diverging-color chart | Blue/orange + hatch + text label = 4-channel encoding ([T8](./2026-09-15-federal-ux-for-senior-users.md) Q8.10 floor) |

---

## Sources and References

**Primary project documents (cited verbatim):**

- [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) (CEA Stages 1–5; §V framing; §VI sensitivity; §X risk register R‑01..R‑12; §XI 10-item knowledge register; §XII visualization pointers).
- [T7](./2026-09-15-federal-deployment-compliance.md) (5-yr WBS; Option A/C/G/I TCO ranges; PM+SysDev+ATO+3PAO cost-side ranges).
- [T8](./2026-09-15-federal-ux-for-senior-users.md) (Q8.8 demo path; Q8.10 4-channel encoding; Section 508 / WCAG 2.0 AA color floor).
- [T9](./2026-09-15-verification-targets-research.md) (Krippendorff α ≥ 0.80; Datasheets / Data Statements; ABV ±0.3 pp tolerance).
- [T10](./2026-09-15-stakeholder-frameworks.md) (Sarah, take-home reviewer, Dave/Jenny scoping; snapshot vs log cadence).
- R0 federal cost conventions (50th/80th/90th naming; constant FY26 $; A‑94 / GAO‑20‑195G alignment).
- 04-research-topics A‑3 (review-time benchmark gap) and D‑1 (on-prem inference signal).
- 05-gaps-and-limitations §3.1 (stakeholder log cadence), §3.3 (pre-mortem), §3.4 (demo design checklist).

**Federal / policy:**

- OMB Circular A‑94 (revised Nov 2023); Appendix C revised 6 March 2026 (M‑26‑09): real Treasury rates CY 2026 = 1.1% (3‑yr), 1.3% (5‑yr), 1.4% (7‑yr).
- OMB Circular A‑11 / Exhibit 300.
- GAO‑20‑195G *Cost Estimating and Assessment Guide* (March 2020), 12-step process, ch. 14 risk/uncertainty/sensitivity.
- CBO *The Budget and Economic Outlook: 2026 to 2036* (11 Feb 2026); CBO *Long-Term Budget Outlook 2026* (data release, 3 Mar 2026); CBO Waterfall Model for Discretionary Spending.
- USWDS Data Visualizations component guidance (designsystem.digital.gov).
- Section 508 / WCAG 2.0 Level AA.

**Visualization theory and primary literature:**

- Tufte, E. R. (1983/2001) *The Visual Display of Quantitative Information*; (1990) *Envisioning Information* (small multiples); (2006) *Beautiful Evidence* (sparklines).
- Knaflic, C. N. (2015) *Storytelling with Data*. Wiley.
- Few, S. (2013) *Information Dashboard Design* (2nd ed.); bullet-graph spec (Perceptual Edge, 2013).
- Munzner, T. (2014) *Visualization Analysis and Design*. CRC Press / AK Peters.
- Spiegelhalter, D., Pearson, M., & Short, I. (2011) "Visualizing Uncertainty About the Future." *Science* 333(6048): 1393–1400.
- Spiegelhalter, D. (2017) "Risk and Uncertainty Communication." *Annual Review of Statistics and Its Application* 4: 31–60.
- Hullman, J., Resnick, P., & Adar, E. (2015) "Hypothetical Outcome Plots Outperform Error Bars and Violin Plots." *PLOS ONE* 10(11): e0142444.
- Kale, A., Nguyen, F., Kay, M., & Hullman, J. (2019) "Hypothetical Outcome Plots Help Untrained Observers Judge Trends in Ambiguous Data." *IEEE TVCG* 25(1): 892–902.
- Kay, M., Kola, T., Hullman, J., & Munson, S. A. (2016) "When (ish) is My Bus?" *CHI '16*; Fernandes, M., Walls, L., Munson, S., Hullman, J., & Kay, M. (2018) "Uncertainty Displays Using Quantile Dotplots or CDFs." *CHI '18* (Best Paper Honorable Mention).
- Britton, E., Fisher, P., & Whitley, J. (1998) "The Inflation Report projections: understanding the fan chart." *Bank of England Quarterly Bulletin* 38: 30–37.
- Eschenbach, T. G. (1992) "Spiderplots versus Tornado Diagrams for Sensitivity Analysis." *Interfaces* 22(6): 40–46.
- Howard, R. A. (decision-analysis tradition; flip-point / threshold reasoning) — invoked via Eschenbach (1992) §3.

**Documentation / data artifacts:**

- Gebru, T., Morgenstern, J., Vecchione, B., Vaughan, J. W., Wallach, H., Daumé III, H., & Crawford, K. (2021) "Datasheets for Datasets." *Communications of the ACM* 64(12): 86–92.
- Bender, E. M., & Friedman, B. (2018) "Data Statements for Natural Language Processing." *TACL* 6: 587–604.
- Krippendorff, K. (2019) *Content Analysis: An Introduction to Its Methodology* (4th ed.); Hayes, A. F., & Krippendorff, K. (2007) "Answering the Call for a Standard Reliability Measure." *Communication Methods and Measures*.

**Architecture diagram convention:**

- Brown, S. (2018; book ed. O'Reilly 2026) *The C4 Model: Visualizing Software Architecture*.

---

*End.*