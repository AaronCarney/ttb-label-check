# Economic Analysis (Cost-Effectiveness) for the AI-Powered TTB COLA Label Verification Prototype

**Sources consumed:** R0 / [T2](./2026-09-15-cola-operational-context.md) / [T4](./2026-09-15-ocr-vision-architecture.md) / [T5](./2026-09-15-llm-orchestration-architecture.md) / [T7](./2026-09-15-federal-deployment-compliance.md) / 01–05 project knowledge
**Status:** Draft for internal review; numbers anchored to verified primary sources as of 30 April 2026
**Author:** TTB COLA AI Prototype Working Group
**Distribution:** Internal — paired with [T7](./2026-09-15-federal-deployment-compliance.md) (policy/compliance overlay) and [T12](./2026-09-15-decision-communication-visualization.md) (visualization deck)

---

## I. Preamble / Front Matter

### Linked prerequisite outputs
| Doc | Role in this analysis |
|---|---|
| **R0** federal-cost-conventions | Binding methodology layer; sets A-94 § 5 framing, GAO-20-195G four-pillar / 12-step structure, percentile-naming convention, real-dollar default |
| **[T2](./2026-09-15-cola-operational-context.md)** volumes / processing times | Source for label volume tiers and current TTB processing-time snapshot |
| **[T4](./2026-09-15-ocr-vision-architecture.md)** OCR & vision pricing | Verified cloud-OCR list prices and Azure DI on-prem container parity finding |
| **[T5](./2026-09-15-llm-orchestration-architecture.md)** LLM orchestration costs | Per-call cost table; "cost is not the driver at TTB scale" conclusion |
| **[T7](./2026-09-15-federal-deployment-compliance.md)** policy / compliance cost overlay | 5-yr WBS for Options A / C / G; ATO, ConMon, 3PAO, M-25-21 § 4 line items |
| **`docs/PRD.md` / `ARCHITECTURE.md` / `docs/decisions/`** | Hard and strong constraints; the settled build decisions; the open review-time research item |

### Methodology statement

This analysis is structured as a **Cost-Effectiveness Analysis (CEA)** under **OMB Circular A-94 § 5** ("Cost-Effectiveness analysis is appropriate … where the benefits from competing alternatives are the same or where a policy decision has been made that the benefits must be provided"; A-94, 9 Nov 2023). CEA — not Benefit-Cost Analysis (BCA) — is the correct frame here because the *benefit* (label-application review against 27 CFR parts 4/5/7) is statutorily mandated by the FAA Act; the policy question is which delivery alternative provides the mandated review at lowest life-cycle cost while honoring the binding constraints in `docs/PRD.md` and the production-parity substitutability design rule.

All figures default to **constant FY 2026 dollars** per A-94 § 6.b. NPV is computed using the **real Treasury rates from the current Appendix C (Revised 6 March 2026, transmitted as OMB M-26-09; valid through Dec 2026)**: 3-yr **1.1 %**, 5-yr **1.3 %**, 7-yr **1.4 %**. (Note: R0 cited the prior Nov 2024 Appendix C; this document uses the current 2026 update verified at whitehouse.gov/wp-content/uploads/2026/03/.)

The analysis is organized to map directly to the **GAO-20-195G four pillars** (comprehensive, well-documented, accurate, credible) and follows the **GAO 12-step process**, with explicit pointers to each step. Per R0, percentile estimates use the federal-audience naming convention **50th-percentile (most likely) / 80th-percentile (should-cost) / 90th-percentile (reserve)** — *not* P10/P50/P90.

### A-94 required-component checklist (R0 §3.1)

| A-94 § 5 component | Where addressed |
|---|---|
| 1. Statement of objectives | Preamble + § II GR&A |
| 2. Identification of alternatives (incl. no-action) | § VII (Stage 3) — Options A / C / G + No-Action |
| 3. Time horizon | § II GR&A — 3-yr primary, 5-yr secondary |
| 4. Costs and benefits | § V (labor savings) + § VII (cost) + § VIII (net) |
| 5. Treatment of uncertainty | § IX Sensitivity + § X Risk register |
| 6. Sensitivity analysis | § IX (separate from risk per GAO Step 8) |
| 7. Distributional / equity considerations | § VIII Q11.17 + § X register entry |
| 8. Recommendation | § IX Q11.20 + § XII (deferred to [T12](./2026-09-15-decision-communication-visualization.md) cross-topic synthesis) |

---

## II. Ground Rules and Assumptions (GR&A) — GAO Step 5

| GR&A | Value | Source / rationale |
|---|---|---|
| **Discount rate (real)** | 1.1 % (3-yr) / 1.3 % (5-yr) | OMB Circular A-94 Appendix C, Revised 6 Mar 2026, transmitted as M-26-09; valid CY 2026. |
| **Base year** | FY 2026 (constant $) | A-94 § 6.b real-dollar default |
| **Currency convention** | Real / constant FY 2026 USD throughout | A-94; avoids R0 anti-pattern of mixed real / nominal |
| **Time horizon — primary** | 3 years (CEA window) | Aligned with prototype-to-production decision cadence and TMF reporting horizons |
| **Time horizon — secondary** | 5 years (TCO sensitivity) | Aligned with [T7](./2026-09-15-federal-deployment-compliance.md)'s 5-yr WBS in Options A / C / G |
| **Application-volume baseline** | ~180,000–200,000 / yr; central case **190 K** | [T2](./2026-09-15-cola-operational-context.md)-verified: TTB NPRM (Notice 176) cites *"approximately 200,000 label applications that TTB receives each year"* (87 FR 8266, finalized as T.D. TTB-176, 9 Feb 2022); FY2020 Annual Report ~190K; About-TTB page "nearly 180K"; CY2026 YTD 55,528 through 28 Apr 2026 → annualized ~180–185K. |
| **Volume growth rate** | Historical **~4 % CAGR (2010–2020)**; **forward growth: "we don't know"** | Computed from 134K (2010) → 146K (2011) → 153K+ (FY2015) → 190K (FY2020). FY2025 Budget-in-Brief notes malt-beverage submissions *declined ~15 % over 5 years*. Forward growth modeled as flat in 50th-percentile case; ±25 % swing in sensitivity. |
| **Seasonality** | Modeled as flat | **TTB does not publish seasonality data for COLA volumes.** Sarah's "200–300 batches in peak season" is an interview anecdote, not a published TTB metric. Industry-blog seasonality narratives are not authoritative. Per R0, do-not-invent. |
| **Submission distribution** (importer vs domestic; small vs large) | Not modeled | Not publicly published by TTB. |
| **ALFD specialist headcount denominator** | **47 agents** | Marcus interview; down from "over 100" in the 1980s. This is the relevant FTE pool for time-savings ÷ realization analysis. |
| **Per-application review-time anchor** | **5–10 min for a "simple" application; longer with issues** | Sarah interview anchor. **This is interview anecdote, not benchmarked empirical data, and remains an open research item** and listed in the §XI "we don't know" register. |
| **Federal labor — anchor grade** | GS-12 Step 5; range GS-9 → GS-13 modeled | OPM 2026 base table, salary range FY2026: GS-9 base $49,960 – GS-13 base $118,204. ALFD specialists are line-level federal reviewers; GS-11 to GS-13 is the realistic band. |
| **Locality** | DC (HQ) and Cincinnati (NRC); RUS as floor | OPM 2026 — DCB locality **33.94 %**, CIN locality **21.93 %**, RUS **17.06 %**. GS-12 Step 5 ≈ $86,659 base → **$116,065 DC** / **$105,659 Cincinnati** / **$101,440 RUS**. GS-13 Step 5 DC = **$138,024**. |
| **Fringe / overhead loading** | **36.25 %** of base salary | OMB M-08-13 (2008) civilian-position full-fringe-benefit factor (26.1 % retirement + 7.0 % FEHB/FEGLI + 1.45 % Medicare + 1.7 % misc). Cited under OMB Circular A-76 Attachment C methodology. [T7](./2026-09-15-federal-deployment-compliance.md) uses 30–35 %; we use the OMB-published 36.25 % point. |
| **Loaded labor cost (anchor, GS-12 Step 5 DC)** | ≈ $158,150 / yr fully loaded | $116,065 × 1.3625 |
| **Productive hours / yr** | 1,776 (≈ 2,087 less leave / training / admin overhead) | OPM uses 2,087 for hourly-rate divisor; net productive hours ≈ 85 % per common federal capacity-planning practice |
| **Realization rate (savings → budget)** | Range **15 % – 40 %** modeled; central **25 %** | Q11.8 deep dive — anchored to GSA OIG 2021 RPA finding (claimed 240,000 hrs "inaccurate and unreliable"); GAO TMF reporting (8 of 37 projects produced documented savings; $14.8 M realized vs $738.6 M anticipated → ≈2 %); federal civilian attrition ~5.9–7.6 %. |
| **Scope inclusions** | Prototype dev, ATO, ConMon (5 yr), cloud OCR/LLM/compute, 508, M-25-21 § 4 minimum practices, re-auth Yr3 | Per [T7](./2026-09-15-federal-deployment-compliance.md) WBS |
| **Scope exclusions** | Production COLA-system integration, persistent storage / audit trail beyond session, PIV/SAML federation, externalized rule engine, training of regulated industry on new flow | Per `docs/PRD.md` scope and constraints |
| **Independent Cost Estimate (ICE)** | **Not produced** | GAO Step 7 calls for an ICE; for a prototype-stage internal CEA we did not commission one. **What would change with an ICE:** (a) tighter 80th/90th-percentile bounds on PM, SysDev, and ATO cost; (b) independent realization-rate haircut; (c) third-party challenge of LLM and compute estimates. [T7](./2026-09-15-federal-deployment-compliance.md)'s three-option WBS serves as a partial in-house cross-check but is not an independent estimate. |

---

## III. Four-Pillar Self-Assessment (GAO-20-195G)

| Pillar | Self-rating | Why |
|---|---|---|
| **Comprehensive** | Partial | WBS aligned to [T7](./2026-09-15-federal-deployment-compliance.md)'s 8-line structure; covers labor + cloud + compliance + lock-in. Gaps: no PIV/SAML, no production integration, no industry-side compliance cost (out of scope per `docs/PRD.md`). |
| **Well-documented** | Adequate | Every assumption traced to a primary source (OPM, OMB, GAO, TTB, T-document). No black-box numbers. |
| **Accurate** | Partial | Driver decomposition (Q11.1) anchored to interview anecdote (A-3 open). Volume central case verified against TTB NPRM. ATO / ConMon cost ranges from [T7](./2026-09-15-federal-deployment-compliance.md) (themselves modeled, not actuals). |
| **Credible** | Partial | Cross-checks to [T5](./2026-09-15-llm-orchestration-architecture.md) (LLM cost), [T4](./2026-09-15-ocr-vision-architecture.md) (OCR cost), [T7](./2026-09-15-federal-deployment-compliance.md) (policy WBS) and OMB / GAO primary docs. **No ICE produced (gap).** Sensitivity and risk treated as separate sections per Steps 8 and 9. |

---

## IV. Work Breakdown Structure (GAO Step 4) — aligned with [T7](./2026-09-15-federal-deployment-compliance.md)

| WBS line | Description | Source |
|---|---|---|
| 1.0 Program management | TTB PM, governance, vendor mgmt | [T7](./2026-09-15-federal-deployment-compliance.md) |
| 2.0 System development | App build, UI, batch orchestrator, rules engine | [T7](./2026-09-15-federal-deployment-compliance.md) + `ARCHITECTURE.md` |
| 3.0 Authorization (initial ATO) | Treasury bureau ATO; FedRAMP package reuse where possible | [T7](./2026-09-15-federal-deployment-compliance.md) |
| 3.1 3PAO (initial) | Independent assessor | [T7](./2026-09-15-federal-deployment-compliance.md) |
| 4.0 Continuous monitoring (5 yr) | ConMon tooling + POA&M FTE | [T7](./2026-09-15-federal-deployment-compliance.md) |
| 5.0 Cloud compute / hosting (5 yr) | VMs, storage, networking, log/SIEM | [T7](./2026-09-15-federal-deployment-compliance.md) |
| 5.1 OCR / Document Intelligence | Per-page OCR | [T4](./2026-09-15-ocr-vision-architecture.md) |
| 5.2 LLM / inference | Per-call orchestration | [T5](./2026-09-15-llm-orchestration-architecture.md) |
| 6.0 M-25-21 § 4 minimum practices | Pre-deployment testing, AI impact assessment, ongoing monitoring, training, human-oversight, appeals, end-user feedback | [T7](./2026-09-15-federal-deployment-compliance.md) + OMB M-25-21 (3 Apr 2025) |
| 7.0 Section 508 conformance | Senior-friendly UI per `docs/PRD.md` NFR-3 and NFR-4 | [T7](./2026-09-15-federal-deployment-compliance.md) |
| 8.0 Re-authorization (Yr 3) | ATO re-issue / 20x transition | [T7](./2026-09-15-federal-deployment-compliance.md) |
| 9.0 Lock-in / switching reserve | Modeled separately in §VII Q11.14 | This doc |

---

## V. Stage 1 — Labor Time Saved per Application

### Q11.1 Driver decomposition (anchored to Sarah's 5–10 min anecdote, *not* benchmarked)

A benchmarked empirical review-time study has *not* been done. We decompose Sarah's 5–10 min "simple application" anecdote into plausible drivers and label each with confidence:

| Driver | % of review time (modeled) | Confidence |
|---|---|---|
| Routine field-by-field matching against form vs label image | 30–45 % | Medium — automatable with OCR + rules (per [T4](./2026-09-15-ocr-vision-architecture.md)) |
| Judgment / fuzzy matching (e.g., Dave's STONE'S THROW vs Stone's Throw) | 15–25 % | Low–Medium — partially automatable; the deterministic core caps AI's role |
| Edge cases / regulatory-citation lookup (27 CFR 4.x, 5.x, 7.x; 16.22 health warning) | 10–20 % | Low — Tesseract LSTM has broken font-attribute output ([T4](./2026-09-15-ocr-vision-architecture.md)), affecting §16.22 type-size enforcement |
| Overhead (queue switching, COLAs Online navigation, communication w/ applicant) | 15–30 % | Low — *not addressed* by this prototype (no COLA-system integration per HARD constraint) |

### Q11.2 Capability ramp scenarios

| Scenario | Baseline review time | Plausible w/ tool | Notes |
|---|---|---|---|
| Dave-like (28 yrs experience, senior) | 4–6 min simple | 3–5 min | Marginal gain; he already knows the rules |
| Jenny-like (8 mo, junior) | 8–12 min simple | 5–7 min | Largest absolute gain — tool acts as on-the-job guide |
| First 90 days post-rollout | +20–40 % vs steady-state | — | Negative gain during ramp; a known anti-pattern of skipping this is in the GR&A |
| Steady-state mix (47-agent ALFD) | 5–10 min (Sarah anchor) | 4–7 min | Working assumption — interview anchor only |

### Q11.3 Unknown-overhead factors (explicit "we don't know")
- True distribution of "simple" vs "issues" applications — TTB does not publish.
- Inter-agent variance (the 47 agents are not interchangeable).
- Effect of seasonal surges on per-app time (TTB does not publish seasonality).
- Correction-cycle time (the 30-day applicant-correction window is part of total cycle but not part of agent review time per se).

### Q11.4 Net time-saved range per scenario

Modeling a **steady-state weighted-average gain of 1.5–3.0 min/application** (most likely 2.0 min). This is conservative vs naïve "5→3 min = 2 min savings" because it accounts for ramp, edge-case fall-through to human, and the 1st-90-days dip.

| Percentile | Time saved per app |
|---|---|
| 50th (most likely) | **2.0 min** |
| 80th (should-cost / aggressive) | **3.0 min** |
| 90th (reserve / pessimistic on benefit) | **1.0 min** |

---

## VI. Stage 2 — Aggregate Annual Labor Savings

### Q11.5 Application volume range
- Low: 170,000 (factoring malt-beverage 5-yr decline noted in FY2025 BiB)
- Central: **190,000** (mid-point of TTB's own NPRM 200K vs About-TTB 180K)
- High: 210,000 (modest growth from 4 % historical CAGR)
- Seasonality: **explicitly not modeled — TTB does not publish.**

### Q11.6 Federal labor-cost loading (OPM 2026, verified)

| Grade / Step | Base | Locality | Loaded (×1.3625) | Per productive hr (1,776 hrs) |
|---|---|---|---|---|
| GS-9 Step 5 RUS | $58,398 | 17.06 % | $93,118 | $52.43 |
| GS-11 Step 5 DC | $76,471 | 33.94 % | $139,532 | $78.57 |
| **GS-12 Step 5 DC (anchor)** | **$86,659** | **33.94 %** | **$158,150** | **$89.05** |
| GS-12 Step 5 Cincinnati | $86,659 | 21.93 % | $143,896 | $81.02 |
| GS-13 Step 5 DC | $103,049 | 33.94 % | $188,055 | $105.88 |

Source: OPM Salary Tables 2026-GS, 2026-DCB, 2026-CIN; January 2026 Pay Examples (opm.gov/policy-data-oversight/pay-leave/.../january-2026-pay-examples). Fringe loading 36.25 % per OMB M-08-13.

### Q11.7 Aggregate gross-time savings (before realization haircut)

At **190 K apps × 2.0 min × $89.05/hr ÷ 60 = ~$564 K/yr** gross labor-time value (50th-percentile, GS-12 Step 5 DC anchor).

| Volume × time-saved | $/hr GS-12 DC | Annual gross |
|---|---|---|
| 170 K × 1.0 min | $89.05 | $252 K |
| 190 K × 2.0 min | $89.05 | **$564 K (50th)** |
| 210 K × 3.0 min | $89.05 | $935 K (80th) |

### Q11.8 Realization Rate — DEEP DIVE

This is the most important — and most-often-skipped — input in any federal automation business case (R0 anti-pattern: "missing realization-rate discussion"). Gross hours saved ≠ budget recovered.

**Anchors:**
- **GSA OIG 2021** (CAP report): GSA's claimed RPA savings of *"more than 240,000 work hours annually was inaccurate and unreliable"* — GSA was not verifying actual hours saved with end-users. (gsaig.gov)
- **GAO-24-106575 (TMF, Dec 2023):** Of 37 TMF-funded projects, **only 8 had realized cost savings, totaling $14.8 M against $738.6 M anticipated** (~2 % realization). Of 7 completed projects with at least a full FY to realize savings, only 2 met OMB's 10 % variance threshold.
- **GAO-22-105117 / GAO-22-106054:** Most TMF cost-saving estimates were *not reliable*; documentation absent.
- **Federal civilian attrition** (Partnership for Public Service, FY2023 data): governmentwide ~**5.9 %**, peaked at **7.6 % in FY2022**. Treasury Department was among the highest-attrition cabinet departments.
- **Headcount rigidity:** 47-agent ALFD pool is set by appropriations and FAA Act statutory workload, not reduced by efficiency gains in the short term. Time saved → typically reabsorbed into queue-depth reduction, not FTE reduction.

**Structural reasons savings ≠ budget cut:**
1. ALFD's headcount is already 47 (down from 100+ in the 80s) — the headcount has *already* been cut; remaining staff are at floor.
2. Treasury / OMB control bureau ceilings; TTB cannot unilaterally reinvest hours.
3. M-25-21 § 4 *adds* human-oversight/appeals workload that partially offsets savings.
4. SLAs and the 85 %/15-day customer-service goal mean recovered hours flow to faster turnaround, not budget cut.

**Modeled realization range (50th/80th/90th naming per R0):**

| Percentile | Realization rate | Realized $/yr (190 K × 2 min anchor = $564 K gross) |
|---|---|---|
| 50th (most likely) | **25 %** | **$141 K** |
| 80th (should-cost / optimistic) | **40 %** | $226 K |
| 90th (reserve / pessimistic) | **15 %** | $85 K |

> **Note:** "90th percentile" here is the *reserve*-side bound on savings, which corresponds to the *worst* realization for the program. Direction is intentional — the high-percentile reserve in CEA is the conservative side for a budget-defense audience.

---

## VII. Stage 3 — Per-Option Cost at Scale

### Q11.9 Cost-model template

For every option we report 5-yr TCO across the WBS in §IV. Cost lines for compliance / ATO / ConMon / M-25-21 § 4 / 508 / re-auth come **directly from [T7](./2026-09-15-federal-deployment-compliance.md)** (the policy-cost overlay was the work product of [T7](./2026-09-15-federal-deployment-compliance.md) specifically; we do not re-derive them here).

### Q11.10 Cloud OCR costing — [T4](./2026-09-15-ocr-vision-architecture.md) verified prices (April 2026)

| Service | Basic OCR / 1K pp | Layout / 1K pp | Forms / Custom / 1K pp | Notable add-ons |
|---|---|---|---|---|
| Google Document AI | $1.50 | — | $30 (custom) | — |
| AWS Textract | $1.50 | — | $50 (forms) | Tables priced separately |
| **Azure Document Intelligence** | **$1.50** | **$10** | **$30 (custom extraction)** | $6 / 1 K styleFont add-on; **container = parity pricing on-prem** |
| Tesseract / PaddleOCR / EasyOCR | $0 (self-host only) | n/a | n/a | Tesseract LSTM **font-attribute output is broken** — affects 27 CFR 16.22 enforcement |

**TTB scale (190 K apps × ~2 pages each ≈ 380 K pages/yr):**
- Basic OCR: **~$570/yr**
- Layout: **~$3,800/yr**
- Custom extraction: **~$11,400/yr**

Even at the highest tier, OCR is **<<1 % of TCO** at TTB scale.

### Q11.11 Self-hosted OCR
- Tesseract / PaddleOCR / EasyOCR: $0 software; bears compute cost only (folded into self-hosted compute below). Tesseract's broken font-attribute output is a §16.22 enforcement risk that pushes toward Azure DI or PaddleOCR in production.
- **Azure DI on-prem container** ([T4](./2026-09-15-ocr-vision-architecture.md) unique finding): Microsoft confirms *"Container pricing is the same as cloud service pricing"*; disconnected containers require ≥100K pages/month + 1-yr commitment (consistent with TTB's volume floor). This is the **strongest cloud-substitutability story** because the same vendor SKU runs in cloud or on-prem at parity pricing.

### Q11.12 Cloud LLM costing — [T5](./2026-09-15-llm-orchestration-architecture.md) per-call table (verified Apr 2026)

| Path | $/call | Annual @ 380K calls (≤2 calls/label × 190K labels) |
|---|---|---|
| Claude 3.5 Haiku, Bedrock GovCloud (FedRAMP High + IL4/5) | ~$0.0021 | ~$800 |
| Claude 4.5 Haiku, Bedrock (verify IL4/5) | ~$0.0021 | ~$800 |
| GPT-4o-2024-08-06, Azure OpenAI Gov (FedRAMP High) | ~$0.0058 | ~$2,200 |
| GPT-4o-mini, Azure OpenAI Gov | ~$0.00035 | ~$133 |
| Gemini 2.5 Flash, Vertex Gov | ~$0.00050 | ~$190 |

Per [T5](./2026-09-15-llm-orchestration-architecture.md) across all paths: **cloud LLM ≈ $750–$1,800/yr** at TTB scale.

> **[T5](./2026-09-15-llm-orchestration-architecture.md) explicit conclusion (cited verbatim):** *"Cost is not the driver at TTB scale. At 150K labels/year, LLM cost (cloud or self-hosted) is negligible; choose path on policy posture and procurement vehicle ([T7](./2026-09-15-federal-deployment-compliance.md)), not unit economics."* The 5-second SLA in `docs/PRD.md` NFR-1 constrains us to single-shot orchestration, capping token budget further.

**FedRAMP authorization status (verified):**
- Anthropic Claude 3.5 Sonnet v1 + Claude 3 Haiku — **FedRAMP High + DoD IL4/5 in Bedrock GovCloud since May 2025** (anthropic.com/news/claude-in-amazon-bedrock-fedramp-high; aws.amazon.com/about-aws/whats-new/2025/05/...).
- Claude 3.7 Sonnet — added July 2025 (aws.amazon.com/about-aws/whats-new/2025/07/...).
- **Claude Sonnet 4.5 / 4.6 / Opus 4.x** — *not yet uniformly* FedRAMP High in Bedrock GovCloud as of 30 Apr 2026; verify at deployment.

### Q11.13 Self-hosted LLM costing
Per [T5](./2026-09-15-llm-orchestration-architecture.md): Llama 3.1 8B / Qwen3 / IBM Granite on a single L4 GPU on a FedRAMP-High VM ≈ **$0.00006–0.00015 / call** ⇒ ~$30–$75 / yr compute-only. Strongest production-parity story; weakest staffing story (need ML-Ops + GPU patching + monitoring loaded into ConMon FTE).

### Q11.14 Lock-In — DEEP DIVE (R0 anti-pattern: "lock-in left out")

Federal lock-in is **categorically different** from commercial lock-in. The switching cost of an LLM/OCR provider is dominated not by data egress or re-coding but by **ATO/3PAO re-issuance and FedRAMP package re-mapping**.

| Lock-in driver | Commercial magnitude | **Federal magnitude (TTB)** |
|---|---|---|
| Time to switch CSP / model SKU | 1–3 months | **12–36 months** (legacy Rev-5 ATO pathway, 12–18 mo even reusing Treasury bureau controls per [T7](./2026-09-15-federal-deployment-compliance.md); 24–36 mo with remediation) |
| ATO re-issuance cost | ~$0 | **$250 K–$500 K Moderate** ([T7](./2026-09-15-federal-deployment-compliance.md) 3PAO range: $150K–$650K; typical $250K–$500K) |
| ConMon tooling re-platform | low | $50K–$200K/yr per [T7](./2026-09-15-federal-deployment-compliance.md) |
| Negotiating leverage | retail / EA pricing | GSA Schedule + ELAs constrain pricing; agency cannot freely shop |
| FedRAMP authorization availability lag | ~weeks | **Months–years** for newest model SKUs (Claude 4.5/4.6, Opus 4.x not yet uniformly authorized) |
| Historical pricing pattern | discounts via competition | Federal cloud prices have trended *down* (GovCloud parity initiatives) but per-SKU volatility on new models is high |

**Lock-in reserve** (90th-percentile cost line in §VIII): we add a **$300 K – $500 K** reserve over the 5-yr horizon to fund a single SKU/CSP swap. This is *not* in [T7](./2026-09-15-federal-deployment-compliance.md)'s WBS and is **additive** to [T7](./2026-09-15-federal-deployment-compliance.md) totals.

### Q11.15 Hybrid options (defined against [T7](./2026-09-15-federal-deployment-compliance.md) framework)

| Code | Definition | When it wins |
|---|---|---|
| **A** ([T7](./2026-09-15-federal-deployment-compliance.md) Option A) | Azure Gov + Azure OpenAI Gov + Azure DI | TTB Azure-incumbent (Treasury already on Azure since 2019, per the Marcus interview); fastest deployable per [T7](./2026-09-15-federal-deployment-compliance.md) Q7.4 deployability hierarchy |
| **C** ([T7](./2026-09-15-federal-deployment-compliance.md) Option C) | AWS GovCloud + Bedrock + Textract | Best Claude model coverage; second-hyperscaler stand-up cost penalty at TTB |
| **G** ([T7](./2026-09-15-federal-deployment-compliance.md) Option G) | Self-hosted Llama / Granite in Azure Gov VM | Strongest substitutability story; production-parity; weakest staffing story |
| **H1 (hybrid)** | Azure DI on-prem container + Claude in Bedrock GovCloud | Pairs Azure incumbency for OCR with the strongest FedRAMP-High LLM today; cross-cloud network cost is real |
| **H2 (hybrid)** | Azure DI cloud + self-hosted Llama 8B in Azure Gov | All-Azure footprint; preserves substitutability for the LLM tier; OCR stays vendor-managed |

---

## VIII. Stage 4 — Net Value per Option

### Q11.16 Net-value calculation

**Cost side (5-yr TCO from [T7](./2026-09-15-federal-deployment-compliance.md) — used directly, *not* re-derived):**

| Option | 50th (most likely) | 80th (should-cost) | 90th (reserve) |
|---|---|---|---|
| **A** Azure Gov / AOAI / DI | **~$2.4 M** | ~$3.9 M | ~$5.8 M |
| **C** AWS GovCloud / Bedrock / Textract | ~$3.1 M | ~$4.9 M | ~$7.2 M |
| **G** Self-hosted Llama / Granite on Azure Gov | substantially higher than A ([T7](./2026-09-15-federal-deployment-compliance.md) GPU compute $500K/$900K/$1.4M; ~$3.5M / $5.5M / $7.5M est.) |

**Benefit side (Stage 2 realized savings × 5 yr, undiscounted):**

| Realization | Annual realized $ | 5-yr undiscounted | 5-yr NPV @ 1.3 % real (A-94 Mar 2026) |
|---|---|---|---|
| 50th (25 %) | $141 K | $705 K | **$680 K** |
| 80th (40 %) | $226 K | $1.13 M | $1.09 M |
| 90th (15 %) | $85 K | $425 K | $410 K |

**Net (5-yr NPV, central case, Option A):**
- Cost: $2.4 M (50th) — $3.9 M (80th) — $5.8 M (90th)
- Benefit (realized): $0.68 M — $1.09 M — $0.41 M
- **Net 5-yr NPV (50th / Option A):** **−$1.7 M** (cost exceeds realized monetized labor savings)

> **Honest framing per R0:** A *single-point ROI* would be misleading here (R0 anti-pattern). On directly-monetized labor savings alone, **no option produces a positive NPV in the 5-yr CEA window** at the 50th percentile. This is the **expected and correct CEA result for a mandated-benefit program** — the question is least-cost delivery of mandated review against `docs/PRD.md`, plus optionality / non-monetizable factors below.

### Q11.17 Non-monetizable factors (listed without forcing dollars per R0)

| Factor | Direction | Notes |
|---|---|---|
| Risk reduction (reasoning on every rejection) | + | Audit-defensible rejections; reduces FOIA / appeal risk |
| Junior-agent ramp-up (Jenny scenario) | + | Compresses 8-mo onboarding; institutional-knowledge transfer from Dave's 28 yrs |
| Public trust / consistency (the economics-and-policy test) | + | Reduces inter-agent variance in label decisions |
| Optionality (cloud-substitutable design) | + | Future-proofs against CSP / model lock-in |
| Senior-friendly UI ("73-year-old benchmark") | + | Mitigates adoption risk in 47-agent pool |
| Marcus's gatekeeper risk (firewall / FedRAMP-18-mo) | − | Production-stage friction not in the prototype budget |
| Industry-side burden | neutral | Out of scope; prototype is internal-facing |
| Equity / distributional | neutral | Reviewer workload is professional-class; no public benefit-distribution implications |

---

## IX. Stage 5 — Sensitivity (GAO Step 8) and Risk / Uncertainty (GAO Step 9)
*Treated as **separate** sections per R0.*

### Q11.18 Sensitivity tornado (Step 8)

Inputs ranked by **NPV swing (5-yr, Option A central case)**:

| Rank | Input | Low → High swing | NPV swing |
|---|---|---|---|
| 1 | **Realization rate** | 15 % → 40 % | **±$0.7 M** |
| 2 | **Time saved per app** | 1 → 3 min | ±$0.6 M |
| 3 | **ATO / build cost ([T7](./2026-09-15-federal-deployment-compliance.md) PM+SysDev+ATO+3PAO)** | 50th → 90th | ±$1.4 M (cost-side) |
| 4 | **Lock-in reserve** | $0 → $500 K | ±$0.5 M (cost-side) |
| 5 | Volume | 170 K → 210 K | ±$0.15 M |
| 6 | Labor rate (GS-11 → GS-13 DC) | $73 → $106/hr | ±$0.13 M |
| 7 | Ops labor (POA&M FTE) | 0.5 → 1.0 FTE | ±$0.4 M (cost-side) |
| 8 | **Cloud OCR cost** | basic → custom extraction | ±$50 K *over 5 yr* — **negligible** |
| 9 | **Cloud LLM cost** | cheapest path → most expensive | ±$10 K *over 5 yr* — **negligible** |

> Per [T5](./2026-09-15-llm-orchestration-architecture.md) conclusion: items 8–9 do **not** drive option choice at TTB scale. The decision turns on items 1–4.

### Q11.19 Recommendation flip points
- If **realization > 40 %** *and* labor rate ≥ GS-13 DC, central case approaches break-even on direct savings alone in 5 yr.
- If **ATO timeline runs > 24 mo** ([T7](./2026-09-15-federal-deployment-compliance.md) worst-case), Option A loses its deployability advantage; reconsider Option C only if AWS GovCloud already has a pre-existing Treasury bureau ATO for the workload class.
- If **Claude Sonnet 4.5 / Opus 4.x receives Bedrock GovCloud FedRAMP High** before deployment date, Option C's LLM-quality advantage strengthens; not enough to flip if Treasury Azure-incumbency holds.
- If TTB's headcount ceiling is **lifted** (workload growth → ALFD goes back toward 100), realization rises sharply because savings translate directly into capacity rather than budget.

### Q11.20 Headline framing — honest synthesis (R0 explicit guidance)

**At TTB scale, the cloud-vs-self-hosted choice is not decided on raw inference cost** — [T5](./2026-09-15-llm-orchestration-architecture.md) establishes that cloud LLM cost is ≈$750–1,800/yr and self-hosted compute ≈$30–75/yr; both rounding-error against the $2.4–5.8 M 5-yr TCO of any Option-A-class build ([T7](./2026-09-15-federal-deployment-compliance.md)).

The decision **turns on:**
1. **Realization rate** (Q11.8) — modeled 15–40 %; the single most-leveraged input.
2. **ATO / build cost** ([T7](./2026-09-15-federal-deployment-compliance.md) §3.0) — Moderate-impact ATO is the dominant cost line.
3. **Lock-in posture** (Q11.14) — federal switching costs are 12–36 months and $250 K–$500 K, not commercial 1–3 months.
4. **TTB's Azure incumbency** ([T7](./2026-09-15-federal-deployment-compliance.md) Q7.4) — Treasury migrated to Azure in 2019; the prior vendor was firewall-blocked; **Option A is the most deployable** and incurs no second-hyperscaler stand-up.

We do **not** force a winner on direct-monetized labor savings (R0: "Anti-pattern: single-point ROI"). The CEA conclusion is that **Option A provides mandated-benefit delivery at the lowest credible 5-yr TCO** (~$2.4 M / 50th, [T7](./2026-09-15-federal-deployment-compliance.md)), and the savings side does not change the ranking among A / C / G — it sets the ceiling on how much complexity is justifiable.

---

## X. Risk and Uncertainty Register (GAO Step 9 — distinct from Sensitivity)

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | Realization rate << 25 % (GSA-OIG-RPA / GAO-TMF pattern) | Medium-High | High | Track realized hours against that open item; do not promise FTE reductions |
| R-02 | Sarah's 5–10 min anchor not representative | Medium | Medium | Commission empirical baseline (recommended T-12 follow-on) |
| R-03 | Claude Sonnet 4.5 / Opus 4.x FedRAMP-High lag persists past deployment | Medium | Low–Medium | Default to Claude 3.7 Sonnet / 3.5 Haiku until updated |
| R-04 | ATO takes 24–36 mo ([T7](./2026-09-15-federal-deployment-compliance.md) worst case) | Medium | High | Reuse Treasury bureau controls; consider FedRAMP 20x Phase 3 path (Q3-Q4 FY26) |
| R-05 | M-25-21 § 4 minimum-practice scope grows | Medium | Medium | Reserve in WBS line 6.0 per [T7](./2026-09-15-federal-deployment-compliance.md) |
| R-06 | Lock-in event (CSP swap forced by policy) | Low–Medium | High | Lock-in reserve $300–500K (Q11.14); substitutable design |
| R-07 | Headcount cut absorbs all gains (no realization) | Medium | Critical to BCA framing | Track via OPM EHRI / Partnership for Public Service attrition data |
| R-08 | Tesseract LSTM font-attribute bug → §16.22 enforcement gap | High (if Tesseract chosen) | Medium | Use Azure DI or PaddleOCR; or hybrid H1 |
| R-09 | Industry pushback on AI-mediated rejections | Low–Medium | Medium | required rejection reasoning mitigates; appeals path required by M-25-21 § 4 |
| R-10 | Prototype-to-production handoff delay (Marcus gatekeeper, the phase-dependent stakeholder priority) | High | Medium | Plan production-parity from day 1; the economics-and-policy test requires economic + policy story for every option |
| R-11 | TTB volume drops 15 %+ (per FY2025 BiB malt-bev trend) | Medium | Low (cuts both costs and savings proportionally) | Annual volume re-assessment |
| R-12 | Government shutdown / appropriations lapse | Medium | Medium | Phasing of ATO milestones around CR cycles |

---

## XI. Explicit "We Don't Know" Register

| Item | Why we don't know |
|---|---|
| Empirical per-application review-time distribution | TTB does not publish; A-3 open research item |
| Seasonality of label-application volume | TTB does not publish; industry-blog narratives not authoritative |
| Importer vs domestic submission share | Not publicly published |
| Small vs large producer share | Not publicly published |
| Forward volume CAGR | Historical 4 % (2010–2020) but FY2025 BiB shows malt-bev decline; do not extrapolate |
| Inter-agent variance in the 47-person ALFD pool | Not measured; unknown |
| TTB's specific ATO timeline for an AI workload | [T7](./2026-09-15-federal-deployment-compliance.md) provides ranges; bureau-specific actuals unknown |
| Realized vs claimed savings from any TTB automation precedent | None published |
| Whether ALFD headcount ceiling will be lifted on workload growth | Treasury / OMB decision, not TTB unilateral |
| Future FedRAMP-High status of Claude 4.5 / 4.6 / Opus 4.x in Bedrock GovCloud | Anthropic + AWS roadmap not committed |

---

## XII. Pointers to [T12](./2026-09-15-decision-communication-visualization.md) (visualization-ready)

The following are clean, publication-ready data structures for [T12](./2026-09-15-decision-communication-visualization.md) visual deck:
1. **Tornado** — Q11.18 input ranking with NPV swings.
2. **Waterfall** — Stage 1 → Stage 2 → Stage 4 (gross savings → realization haircut → vs [T7](./2026-09-15-federal-deployment-compliance.md) cost).
3. **Three-option TCO band chart** — A vs C vs G at 50th/80th/90th, sourced from [T7](./2026-09-15-federal-deployment-compliance.md).
4. **Realization-rate curve** — break-even realization for net-zero NPV by option.
5. **OPM grade × locality matrix** — GS-9 / 11 / 12 / 13 × DC / Cincinnati / RUS loaded $/hr.
6. **GAO-12-step compliance map** — steps covered (1, 2, 3, 4, 5, 6, 8, 9, 10) vs steps deferred (7 ICE, 11 risk-monitoring runtime, 12 ongoing update).

**Cross-topic synthesis (X-7) is deferred** per task scope.

---

## XIII. Citations (primary sources used)

- **OMB Circular A-94**, "Guidelines and Discount Rates for Benefit-Cost Analysis of Federal Programs," 9 Nov 2023 — whitehouse.gov/wp-content/uploads/2023/11/CircularA-94.pdf (cited §§ 5, 6.b).
- **OMB Circular A-94 Appendix C** (Revised 6 Mar 2026), transmitted as **OMB M-26-09** — whitehouse.gov/wp-content/uploads/2026/03/M-26-09-2026-Discount-Rates-for-OMB-Circular-No.-A-94.pdf. Real rates 3-yr 1.1 %, 5-yr 1.3 %, 7-yr 1.4 %; nominal 3-yr 3.4 %, 5-yr 3.5 %, 7-yr 3.6 %; valid CY 2026.
- **GAO-20-195G**, *Cost Estimating and Assessment Guide* (Mar 2020) — gao.gov/products/gao-20-195g (four characteristics: comprehensive / well-documented / accurate / credible; 12-step process; 18 best practices).
- **OMB M-08-13** (May 2008) — Civilian-position full-fringe-benefit factor 36.25 %.
- **OMB Circular A-76**, Attachment C — performance-of-commercial-activities cost methodology.
- **OPM 2026 Salary Tables** — opm.gov/policy-data-oversight/pay-leave/salaries-wages/2026/general-schedule/ (Tables 2026-GS, 2026-DCB, 2026-CIN). 2026 base raise 1 %, locality frozen at 2025: DC 33.94 %, Cincinnati 21.93 %, RUS 17.06 %; pay cap $197,200 (Exec Sched IV).
- **OPM January 2026 Pay Examples** — opm.gov/policy-data-oversight/pay-leave/pay-administration/fact-sheets/january-2026-pay-examples/.
- **TTB Form 5100.31 (04/2023)**; **87 FR 8266** (cited as Notice No. 176 / T.D. TTB-176, *Modernization of the Labeling and Advertising Regulations for Distilled Spirits and Malt Beverages*, 9 Feb 2022) — *"approximately 200,000 label applications that TTB receives each year"*; TTB COLA Streamlining Accomplishments page (134K 2010, 146K 2011); TTB Processing Times for Label Applications (current data 04/17/2026).
- **OMB M-25-21**, *Accelerating Federal Use of AI* (3 Apr 2025) — § 4 minimum risk-management practices for high-impact AI; whitehouse.gov/wp-content/uploads/2025/02/M-25-21....
- **GSA OIG**, *GSA's Robotic Process Automation Program Lacks Evidence to Support Claimed Savings* (2021) — gsaig.gov; *"240,000 work hours annually was inaccurate and unreliable."*
- **GAO-24-106575**, *Technology Modernization Fund: Although Planned Amounts Are Substantial, Projects Have Thus Far Achieved Minimal Savings* (Dec 2023) — 8 of 37 projects with realized savings of $14.8 M; **GAO-22-105117**; **GAO-22-106054**; **GAO-20-3**.
- **Partnership for Public Service**, *Recent trends in quits and retirements in the federal workforce* — FY2023 attrition 5.9 %; FY2022 7.6 %.
- **AWS Textract** pricing — basic OCR $1.50 / 1K pp, Forms $50 / 1K pp.
- **Azure AI Document Intelligence** pricing — azure.microsoft.com/en-us/pricing/details/document-intelligence/; basic Read $1.50/1K pp, Layout $10/1K pp, Custom Extraction $30/1K pp; styleFont add-on $6/1K pp; **container = parity pricing** (learn.microsoft.com).
- **Google Document AI** pricing — basic OCR $1.50/1K pp; Custom $30/1K pp.
- **Anthropic Claude API** pricing — Sonnet 4.5 $3 in / $15 out per MTok.
- **AWS Bedrock GovCloud** — Anthropic Claude 3.5 Sonnet v1 + Claude 3 Haiku **FedRAMP High + DoD IL4/5 (May 2025)**; aws.amazon.com/about-aws/whats-new/2025/05/amazon-bedrock-models-fedramp-high-dod-il-4-5-govcloud/; anthropic.com/news/claude-in-amazon-bedrock-fedramp-high. Claude 3.7 Sonnet added July 2025.
- **FedRAMP Marketplace** — fedramp.gov; **FedRAMP 20x Phase 2** (Nov 2025–31 Mar 2026) and Phase 3 (Q3–Q4 FY26).
- **Azure OpenAI Service** in Azure Government — FedRAMP High.
- **T-document trail (project-internal):** [T2](./2026-09-15-cola-operational-context.md), [T4](./2026-09-15-ocr-vision-architecture.md), [T5](./2026-09-15-llm-orchestration-architecture.md), [T7](./2026-09-15-federal-deployment-compliance.md) (cited in §I links) — used directly per task instruction *"Re-derive LLM costs that [T5](./2026-09-15-llm-orchestration-architecture.md) already provides; cite [T5](./2026-09-15-llm-orchestration-architecture.md) directly. Re-derive ATO/build cost ranges that [T7](./2026-09-15-federal-deployment-compliance.md) already provides; cite [T7](./2026-09-15-federal-deployment-compliance.md) directly."*

---

*End of T11. Pair with [T7](./2026-09-15-federal-deployment-compliance.md) (policy/compliance overlay) and [T12](./2026-09-15-decision-communication-visualization.md) (visualization). Cross-topic synthesis question X-7 deferred per task scope.*