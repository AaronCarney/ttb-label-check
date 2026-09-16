# Federal Deployment: Policy Gradations & Compliance Pathways

Filed 2026-09-15.

---

**Project:** TTB AI-Powered Alcohol Label Verification Prototype
**Decisions Referenced:** The deterministic core (deterministic-first; AI orchestrates, does not decide), substitutability (production parity, cloud OK for prototype but architecturally substitutable), the economics-and-policy test (every option carries economic + federal-policy story), federal cost-analysis conventions (OMB A-94 Nov 2023, GAO-20-195G, A-11/Exhibit 300)
**Upstream Outputs Consumed:** [T3](./2026-09-15-rule-engine-architecture.md) (rule engine), [T4](./2026-09-15-ocr-vision-architecture.md) (vision/OCR), [T5](./2026-09-15-llm-orchestration-architecture.md) (LLM orchestration)
**Primary External Sources:** OMB M-25-21 (Apr 3, 2025); OMB M-25-22 (Apr 3, 2025); OMB M-22-09 (Jan 26, 2022); EO 14179 (Jan 23, 2025); EO 14365 (Dec 11, 2025); America's AI Action Plan (Jul 23, 2025); NIST AI 100-1 (AI RMF 1.0); NIST AI 600-1 (Jul 26, 2024); NIST SP 800-53 Rev 5; NIST SP 800-60 Vol II Rev 1 + IWD Rev 2; NIST SP 800-37 Rev 2; FIPS 199, FIPS 200, FIPS 201-2/3; FedRAMP 20x program (GSA, Mar 24, 2025); FedRAMP Marketplace; Treasury Directive 85-01 / TD P 85-01; **Section 508 Refresh / Revised 508 Standards (36 CFR 1194), incorporating WCAG 2.0 Level A and AA by reference**; TTB FY 2025 Congressional Justification; vendor-published FedRAMP authorization announcements (Microsoft, AWS, Google, Anthropic).

> **Framing — POLICY GRADIENT, NOT CHECKLIST.** Federal cloud-and-AI compliance is a *gradient of allowability*. The same architectural choice may be **Allowable**, **Allowable-with-controls**, or **Disallowed** depending on the workload classification, the data sensitivity, and the authorization tier of the surrounding boundary. The headline output is the **Q7.4 policy-gradation matrix**; everything else in this report supports it.

> **Revision note.** Removed a redundant matrix row (formerly Row N, restated Row A conditionally) and the filler DeepSeek row (folded into Row K and footnote [12]); reframed PRC-origin model treatment as analyst judgment rather than policy fact; attached explicit P20/P50/P80 confidence percentiles to the per-option WBS rather than only to the totals; corrected Section 508 baseline to **WCAG 2.0 AA** (the legal floor under the Revised 508 Standards) with WCAG 2.1/2.2 noted as best-practice design targets, not regulatory minima.

---

## Q7.1 — Workload-Sensitivity Classification Framework

### 7.1.1 The Axes

A defensible federal classification combines five orthogonal axes:

1. **FIPS 199 security categorization** of confidentiality / integrity / availability — each rated **Low / Moderate / High** based on the worst-case adverse impact of compromise. The system's overall categorization is the **high-water mark** across the three objectives.
2. **NIST SP 800-60 Vol II Rev 1 information-type mapping** — the catalog of federal information types that drives the *provisional* impact levels which the agency then adjusts.
3. **FIPS 200 minimum security requirements** — selects the NIST SP 800-53 Rev 5 control baseline (Low/Moderate/High).
4. **AI characteristics under OMB M-25-21** (replaces M-24-10's "rights-impacting / safety-impacting" dichotomy with a single "high-impact AI" definition; see Q7.5).
5. **Mission posture / availability sensitivity** — does an outage block statutory mission delivery, taxpayer revenue collection, or industry market access?

### 7.1.2 Classifying the TTB Label-Verification Prototype

**Information types (NIST SP 800-60 Vol II Rev 1, Appendices C & D):**

| Information element | NIST 800-60 type | Provisional C-I-A |
|---|---|---|
| Industry submitter application data (business name, permit no., contact info, formula data) | D.21.1 *Inspections and Auditing*; plus C.3.5 *Public Affairs* elements where consumer-facing | Low-Moderate-Low |
| Label image artwork (pre-public, pre-approval) | Industry-proprietary regulatory submission; analogous to D.21.1 + trade-secret considerations | Moderate-Moderate-Low |
| Rule-engine outputs / pass-fail / CFR citations | Inspection/auditing finding | Moderate-Moderate-Low |
| Authentication / audit logs | Standard system-management information types | Moderate-Moderate-Low |
| LLM prompts/responses (disambiguation only, per the deterministic core) | Derived from above; same boundary | Moderate-Moderate-Low |

**Aggregate FIPS 199 categorization (high-water-mark): MODERATE-MODERATE-LOW → overall MODERATE.**

The Confidentiality bump from Low to Moderate reflects:
- Pre-decisional regulatory submissions whose unauthorized disclosure could provide commercial advantage to competitors of the submitting industry member;
- Treasury's standing posture under TD P 85-01 of treating bureau regulatory data as Moderate by default unless explicitly downgraded;
- Privacy considerations for any individual permittees / sole proprietors who appear as submitters (PII mapping per draft SP 800-60r2 IWD, which is incorporating NIST SP 800-122 PII guidance into the categorization methodology).

The **Integrity** rating is Moderate because rule-engine output flows downstream to ALFD reviewers and ultimately to a federal regulatory action (label approval/rejection); a silent integrity compromise could distort approvals.

The **Availability** rating is Low because this is a backstop / efficiency tool for a 47-agent ALFD; the prior workflow (manual review without AI assistance) remains an available fallback. *A reasonable case can be made for Moderate availability if the system becomes the operational gating step for hitting the 5-second SLA per single-label review at scale; for the prototype we hold to Low and flag this as a re-categorization decision at production cutover.*

**FIPS 200 baseline:** Moderate → **NIST SP 800-53 Rev 5 Moderate baseline (~325 controls)**.

### 7.1.3 AI Characterization Under M-25-21

OMB M-25-21 §5 defines **"high-impact AI"** as AI "with an output that serves as a principal basis for decisions or actions that have a legal, material, binding, or significant effect on rights or safety," and §6 lists *presumed* high-impact categories. The list (per the published OMB memo and confirming agency compliance plans, e.g., DHS, GSA, VA, Federal Reserve, U.S. AbilityOne, EAC, CFPB) covers areas including critical infrastructure, government security, healthcare, robotics, defense, and access to critical services / strategic resources.

**Argument that the TTB system IS high-impact:**
- The output (pass / fail / needs-review with CFR citation) feeds an ALFD agent's regulatory determination on a Certificate of Label Approval (COLA), which has *legal effect* on the industry submitter's ability to introduce a product into commerce under 27 CFR Parts 4, 5, 7, and the FAA Act.
- Under M-25-21 §5, "a high-impact determination is possible whether there is or is not human oversight for the decision or action" — the presence of a human-in-the-loop ALFD reviewer does **not** by itself disqualify the system from the high-impact determination.
- If the AI suppresses or de-prioritizes a true defect (false negative in "needs-review"), the consequence is regulatory: a non-compliant label reaches market.
- The brief notes OQ-T5-9 explicitly raised whether TTB CAIO classifies this as high-impact.

**Argument that it is NOT high-impact:**
- Per the deterministic core the LLM **does not decide** pass/fail; the deterministic rule engine decides. The LLM only disambiguates borderline cases.
- The AI's output is advisory; the *principal basis* for the regulatory decision is (a) the deterministic rule engine + (b) the human ALFD reviewer.
- M-25-21 narrowed the presumed-high-impact list relative to M-24-10; alcohol-label compliance review is not on the presumed list. (M-25-21 §6.)
- Pilots that are limited in scale/duration, centrally tracked, with opt-out and notice, are exempt from the minimum risk practices floor (M-25-21 §4).

**Recommendation:** Treat the prototype **as if** high-impact for design purposes (apply the M-25-21 §4 minimum practices: pre-deployment testing, AI impact assessment, ongoing monitoring, training, human oversight, appeals, end-user feedback). This is defensible to the TTB CAIO and forecloses a costly redesign if the determination later goes against us. **Open Question OQ-7-1**: formal CAIO classification.

### 7.1.4 Mission Posture

Mission criticality: **Medium.** ALFD processes ~150,000 label applications/year against a 5-second SLA per review with 47 agents. The system improves throughput but is not load-bearing for tax collection or operational continuity. Treasury Strategic Objective 1.3 (Economically Resilient Communities) frames TTB's industry-facing services; degraded label processing produces business-friction effects, not life-safety or revenue effects.

---

## Q7.2 — Hosting-Option Gradient

| # | Hosting option | Typical authorization timeline (months) | Required controls (Rev 5 baseline) | Rough overhead cost (initial / annual) | Notes |
|---|---|---|---|---|---|
| H1 | **Public commercial cloud** (AWS, Azure Commercial, GCP), no FedRAMP | N/A — *not allowable* for federal Moderate workload absent waiver | NIST 800-53 Rev 5 Moderate **uninherited** | Vendor list price | Federal data above Low typically prohibited absent agency-specific exception; M-22-09 zero-trust and FISMA effectively foreclose. |
| H2 | **FedRAMP Low** (commercial CSP, Low baseline) | 12 mo legacy / **3-6 mo via 20x Phase 1 pilot path** | ~125 Rev 5 controls | $350K-$500K initial / $100K-$200K annual | Insufficient for our Moderate workload. |
| H3 | **FedRAMP Moderate** (Agency Authorization, Rev 5) | **12-18 months** (legacy median ~22 mo per GAO-24-106395) | ~325 Rev 5 controls | $500K-$1.5M-$2M init / $200K-$500K annual; 3PAO assessment $150K-$650K | The default tier for our workload. |
| H4 | **FedRAMP Moderate via 20x** (Phase 2, Nov 2025-Mar 2026) | **3-6 months target** (pilot data: first Phase-1 Low pilot completed in 119 days; ~5-week current legacy review queue at PMO) | KSI-aligned + Rev 5 Moderate controls expressed in OSCAL | Pilot data ~$100K-$300K; firming up | Phase 2 pilot is closed-cohort (~10 CSPs); broad availability targeted Q3 2026. |
| H5 | **FedRAMP High** (Agency Authorization, Rev 5) | **18-24 months**, sometimes 36 | ~421 Rev 5 controls | $1M-$3M+ init / $500K-$1M annual; 3PAO $300K-$800K | Required for High workloads; we are Moderate so this is overkill but inheritable for free if vendor already holds it. |
| H6 | **Azure Government (Azure Gov)** — FedRAMP High P-ATO + DoD IL2/4/5 | Inherited by the agency; bureau ATO on top typically 6-12 mo for Treasury bureau given prior controls reuse | Inherits FedRAMP High; bureau adds system-specific controls | Azure Gov pricing ~10-25% premium over commercial; ATO labor $200K-$600K for bureau-side work | TTB is on Azure since 2019 (Marcus interview); whether Gov vs Commercial tenant is **OQ-7-2**. |
| H7 | **AWS GovCloud (US)** — FedRAMP High JAB P-ATO + DoD IL2/4/5 | Same shape as H6 | Same as H6 | Similar cost profile; ITAR-eligible | Strong AI service ecosystem (Bedrock GovCloud, Textract). |
| H8 | **Google Cloud Assured Workloads (FedRAMP High)** | Same as H6 | Inherits >150 services under GCP High P-ATO | Similar cost profile | Vertex AI / Gemini auths recently expanded (FedRAMP High on Gen AI on Vertex AI; Agent Assist / Looker / Vector Search). |
| H9 | **DoD IL5/IL6** | N/A for civilian agency | DoD SRG | N/A | Civilian agencies cannot use IL5/6 — DoD-only categorization per DoD CC SRG §5.2.2.3. |
| H10 | **On-prem agency-managed** (Treasury data center / TTB server room) | Bureau ATO 6-12 mo if reusing Treasury enterprise security services; 12-24 mo greenfield | Full Rev 5 Moderate inherits no boundary controls; agency carries everything | $500K-$2M one-time stand-up + $200K-$400K annual ops; hardware capex on top | Strongest substitution; weakest scaling story. |
| H11 | **Air-gapped on-prem** | Same as H10 + 3-6 mo for cross-domain solution accreditation | Rev 5 + agency-specific air-gap controls (no inbound/outbound) | H10 + ~$100K-$300K for cross-domain | Overkill for Moderate; relevant only if data classification escalates. |

**Process detail (FedRAMP 20x).** GSA announced 20x March 24, 2025 (FedRAMP Director Pete Waterman). Phase 1 Low pilot ran April-September 2025; 26 submissions, 13 reviewed in-window, 12 pilot authorizations granted. Phase 2 Moderate pilot opened November 2025 with ~10-13 CSPs targeted; a Cohort 1 was selected December 10, 2025 (Confluent and others). Default 20x adoption for Moderate is targeted for **Q3 2026**, with FedRAMP planning to stop accepting new Rev 5-based agency authorizations at the end of FY27 (Phase 5). Submissions are required in OSCAL machine-readable format. (Sources: fedramp.gov/20x/, fedramp.gov/20x/phase-one/, fedramp.gov/20x/phase-two/, fedramp.gov 2025-12-10 announcement.)

**Civilian-agency continuous-monitoring overhead.** Monthly vulnerability scans + annual 3PAO reassessment + POA&M maintenance + Significant Change Notification (replacing the legacy Significant Change Request process under 20x). For Moderate, ConMon typically $150K-$350K/year; re-authorization cycle is annual reassessment plus a 3-year refresh.

---

## Q7.3 — Inference-Option Gradient

| # | Inference option | Allowability for our (Moderate) workload | M-25-21 / M-25-22 considerations |
|---|---|---|---|
| I1 | **Commercial cloud LLM API endpoint** (OpenAI direct, Anthropic direct, Google AI Studio) | **Disallowed without waiver.** No FedRAMP authorization on the inference endpoint; data egress to commercial multi-tenant boundary. | Still inventoried as an AI use case. Commercial API ToS may permit training on your inputs unless opted out — directly conflicts with M-25-22 prohibition on non-public agency data being used to train commercial models. |
| I2 | **FedRAMP-authorized cloud LLM API** — Azure OpenAI Service in **Azure Government** | **Allowable** for Moderate (Azure OpenAI Gov: FedRAMP High + DoD IL4/IL5; IL6 in Gov Secret). GPT-4o, GPT-4, GPT-3.5, DALL-E in scope. | High-impact AI minimum practices still required if classified as such per M-25-21 §4. Buy-American posture (M-25-22 §3c) satisfied. |
| I3 | **FedRAMP-authorized cloud LLM API** — **Amazon Bedrock in AWS GovCloud (US)** | **Allowable** for Moderate. Bedrock is FedRAMP High in GovCloud (Aug 2024); Anthropic Claude 3.5 Sonnet v1, Claude 3 Haiku, Meta Llama 3 8B/70B authorized to FedRAMP High + DoD IL4/IL5 in May/June 2025. Bedrock Agents, Guardrails, Knowledge Bases, Model Evaluation in scope. | Newer models (Llama 3.1+, Nova Premier) have no public roadmap into GovCloud as of research date. |
| I4 | **FedRAMP-authorized cloud LLM API** — **Generative AI on Vertex AI (Google)** | **Allowable** for Moderate. FedRAMP High via Assured Workloads; Gemini family in scope; Claude on Vertex AI authorized FedRAMP High + IL2 (March 2025). | Note: Google states explicitly that "individual LLMs aren't independently authorized under FedRAMP" — this is THE rule for the entire LLM gradient. |
| I5 | **Self-hosted open-weight LLM in FedRAMP cloud VM** (vLLM on GovCloud EC2 / Azure Gov VM) | **Allowable-with-controls.** Inherits the underlying compute boundary's authorization. Agency carries the model supply-chain review. | Agency must perform AI BOM review (training data provenance, license, country of origin, weights integrity). M-25-22 prohibits federal data being used to train publicly available models — for self-hosted weights this is moot, but the compliance plan must say so. |
| I6 | **Self-hosted open-weight LLM on agency on-prem** | **Allowable-with-controls.** Strongest substitution. | Same AI-BOM and supply-chain review obligations. CISA / Trump-admin "Buy American" posture (M-25-22 §3c) — Llama (Meta), Granite (IBM), Qwen (Alibaba) differ markedly here on country-of-origin grounds. *See country-of-origin note below — this is analyst risk judgment, not a categorical regulatory prohibition.* |
| I7 | **DeepSeek specifically** | **Disallowed (de facto federal-wide).** | "No DeepSeek on Government Devices Act" (HR 1121, Feb 7 2025); DOD, Navy, NASA, Commerce, USDA (via Microsoft Defender for Cloud Apps), and the U.S. House of Representatives have administratively blocked DeepSeek. Three states have banned. CISA/DHS posture is firmly hostile. **The "No Adversarial AI Act" (Cassidy/Rosen)** would extend ban logic to a broader registry but has not been enacted. |

**Country-of-origin note (analyst judgment, not regulatory fact).** The DeepSeek bans name DeepSeek specifically. There is **no current federal rule that categorically prohibits all PRC-origin open-weight models** (e.g., Qwen, PaddleOCR, PaddleOCR-VL) — even though they are Apache-2.0 licensed. However, the procurement *risk posture* under M-25-22 §3c (Buy American), the AI Action Plan's supply-chain emphasis, and the broader trajectory of foreign-adversary-AI legislation make PRC-origin frontier weights a material acquisition risk that a CAIO will almost certainly flag. Treat this as "additional CAIO-level review required and likely-but-not-certain disallowance," not "categorically forbidden." This distinction matters for honesty with the reader and for not overstating the policy floor.

**Other key cross-cutting rules:**
- **The "Individual LLMs aren't independently authorized under FedRAMP" rule** (Google Cloud documentation; mirrored in Microsoft and AWS guidance): the LLM is *software* operating inside an authorized cloud service; the cloud service holds the authorization, the LLM inherits it. A new model dropping into an authorized Bedrock / Azure OpenAI / Vertex deployment is not separately authorized — it is in or out of the existing scope at the *service* level.
- **M-25-21 §4 minimum practices apply regardless of where inference runs** if the system is high-impact: pre-deployment testing; AI impact assessment; ongoing monitoring; adequate training; human oversight, intervention, and accountability; consistent remedies/appeals; consult and incorporate user/public feedback.
- **AI BOM / supply-chain expectations** under M-25-22 §3, the AI Action Plan ("Winning the Race", July 23 2025), and the SBOM posture from CISA: vendor must disclose model provenance, training-data sources where possible, and weights integrity attestations.
- **EO 14179** (Jan 23, 2025, "Removing Barriers to American Leadership in AI") rescinded Biden EO 14110 and directed OMB to revise M-24-10 and M-24-18 — which produced M-25-21 and M-25-22. Subsequent EOs: EO 14275 (Apr 15, 2025, FAR reform), EO 14277/14278 (Apr 2025, AI workforce), EO 14319 (Jul 2025, ideological-neutrality in procured AI), EO 14365 (Dec 11, 2025, state-AI preemption / Litigation Task Force).

---

## Q7.4 — POLICY-GRADATION MATRIX (HEADLINE OUTPUT)

> **How to read this.** Rows are 13 plausible (workload × hosting × inference) combinations for our Moderate-Moderate-Low TTB system. The center column is the allowability tier for *this* workload. Allowability is **not** a property of the technology in the abstract — the same hosting/inference choice may be Allowable for one workload and Disallowed for another.
>
> Symbols: 🟢 **Allowable** (standard controls, ATO via inheritance) · 🟡 **Allowable-with-controls** (additional steps, agency-specific waivers, supply-chain review, or compensating controls) · 🔴 **Disallowed** (waiver / exception required; strong default presumption against).

| # | Hosting boundary | Inference option | Allowability (TTB Moderate-Moderate-Low, treated provisionally as high-impact AI per M-25-21) | Authorization timeline | Rough overhead cost (initial / annual) | Footnotes |
|---|---|---|---|---|---|---|
| **A** | Azure Government (FedRAMP High + IL4/5; TTB-incumbent platform) | **Azure OpenAI Service in Azure Gov** (GPT-4o, GPT-4) — FedRAMP High in scope | 🟢 **Allowable** (assumes TTB Azure tenant is Gov per OQ-7-2; if Commercial, downgrades to 🟡 with tenant-migration prereq) | 6-12 mo bureau ATO leveraging Treasury controls reuse | $250K-$600K initial bureau labor / $150K-$350K annual ConMon | [1][2][6] Strongest deployable path given TTB Azure incumbency. |
| **B** | Azure Government | **Azure AI Document Intelligence** (Read+Layout+styleFont, [T4](./2026-09-15-ocr-vision-architecture.md) prototype-pick) cloud-hosted | 🟢 **Allowable** | 6-12 mo (boundary inherited) | Inherits A; +$50K-$120K integration | [1][3] FedRAMP High + IL4/5 in Azure Gov; first-party Docker container available for substitution. |
| **C** | AWS GovCloud (US) (FedRAMP High JAB + IL4/5) | **Bedrock GovCloud** w/ Claude 3.5 Sonnet v1 or Claude 3 Haiku (FedRAMP High + IL4/5 May 2025) | 🟢 **Allowable** (compliance) / 🟡 **on deployability** at TTB given second-hyperscaler burden — see Q7.17 | 9-15 mo if Treasury establishes new GovCloud bureau ATO; 6-12 mo if Treasury already holds one | $400K-$900K initial / $200K-$450K annual | [4][6] Strongest cloud-OCR + LLM stack but introduces a *second* hyperscaler into TTB. |
| **D** | AWS GovCloud (US) | **Bedrock GovCloud** w/ Llama 3 8B/70B (FedRAMP High + IL4/5 May 2025) | Same as C | Same as C | Same as C — but per-call cost lower for Llama | [4][6] Llama 3 (8B/70B); Llama 3.1+ not yet GovCloud-authorized as of research date — if higher-spec model is needed, this row downgrades to 🟡. |
| **E** | Google Cloud Assured Workloads (FedRAMP High) | **Generative AI on Vertex AI** w/ Gemini (FedRAMP High); or **Claude on Vertex** (FedRAMP High + IL2) | 🟢 **Allowable** (compliance) / 🟡 **on deployability** — third-hyperscaler burden | 9-15 mo | $400K-$900K initial / $200K-$450K annual | [5][6][8] FedRAMP High since 2024-25; Treasury procurement vehicle availability is the binding constraint. |
| **F** | Azure Government | **AWS Textract** (FedRAMP High in GovCloud) for OCR + Azure OpenAI Gov for LLM (cross-cloud) | 🟡 **Allowable-with-controls** | 12-18 mo (two-boundary ATO) | $500K-$1.2M initial / $300K-$600K annual; data-egress charges | [10] Cross-cloud data flow requires explicit boundary documentation, agency procurement vehicle for both, and an interconnect security agreement; not recommended unless a specific Textract feature is required. |
| **G** | Azure Government VM (FedRAMP High) | **Self-hosted open-weight US-origin LLM** (Llama 3.1 8B; IBM Granite 8B Apache-2.0) on vLLM | 🟡 **Allowable-with-controls** | 6-12 mo (boundary inherited) + AI BOM review | Inherits A; +$100K-$250K for self-hosting setup; +$30K-$80K/mo GPU compute | [7][9] Strong substitution rehearsal. Carries supply-chain review burden (M-25-22 §3); model-card and training-data provenance documented as part of AI use-case inventory. |
| **H** | AWS GovCloud VM | **Self-hosted IBM Granite / Llama on vLLM** | 🟡 **Allowable-with-controls** | 9-15 mo | Similar to G | [7][9] |
| **I** | Treasury / TTB on-prem (bureau ATO) | **Self-hosted Llama 3.1 8B / Granite 8B** (US-origin) | 🟡 **Allowable-with-controls** | 12-24 mo greenfield; 6-12 mo if reusing TTB existing on-prem ATO boundary | $700K-$1.8M initial (incl. capex for GPU servers) / $250K-$550K annual | [7][9] Strongest substitutability and production parity; weakest scalability. |
| **I-alt** | Treasury / TTB on-prem | **Self-hosted Qwen3 / PaddleOCR-VL** (PRC-origin, Apache-2.0) | 🟡 **Allowable-with-elevated-review** under current rules; CAIO acquisition-risk review required and likely-disfavored under M-25-22 §3c Buy-American posture and the broader DeepSeek precedent. **Not categorically prohibited.** | Same as I + 2-4 mo CAIO supply-chain review | Same as I | [12] DeepSeek-specific bans (HR 1121, agency administrative blocks) do **not** by their terms cover all PRC-origin open-weight models; this row reflects analyst risk judgment, not regulatory mandate. |
| **J** | Azure Government | **GPT-4o via Azure OpenAI Gov** + **Tesseract / EasyOCR self-hosted** (Apache-2.0) for OCR | 🟡 **Allowable-with-controls** | 6-12 mo | Similar to A; +$30K-$60K self-hosted OCR overhead | [3] Tesseract (Apache-2.0) and EasyOCR (Apache-2.0) avoid the supply-chain question entirely. |
| **K** | Public commercial cloud (no FedRAMP) | Any LLM API (commercial endpoint), and any model-specific federal-banned option (DeepSeek) | 🔴 **Disallowed** | N/A — waiver path only | N/A | [13] Federal Moderate workload cannot be processed in commercial multi-tenant boundaries without an explicit agency-level exception; effectively unattainable for production. |
| **L** | Air-gapped on-prem (no internet egress) | **Self-hosted Granite / Llama** | 🟡 **Allowable-with-controls** | 18-30 mo | $1M-$2.5M initial / $400K-$800K annual | Overkill for our Moderate-Moderate-Low classification; only relevant if data sensitivity escalates. Provides the strongest sovereign-execution story. |
| **M** | Azure Government — **prototype tier** (this evaluation, not yet a production ATO) | **Azure Document Intelligence + Azure OpenAI Gov GPT-4o, single-shot, schema-strict, no agentic chains, M-25-21 §4 pilot exemption** | 🟢 **Allowable as a tracked pilot** | Pilot does not require full ATO; pre-existing Treasury sandbox or limited ATO boundary suffices | $80K-$200K prototype cost / Treasury sandbox compute | Per M-25-21 §4 pilot exemption: limited scale/duration, centrally tracked, opt-out + notice, minimum risk practices applied "where available." This is the recommended posture for the prototype phase; transition planning toward row A or G for production. |

### Footnotes

[1] Azure Government FedRAMP High P-ATO and DoD IL2/4/5 PA scope per `learn.microsoft.com/en-us/azure/azure-government/compliance/azure-services-in-fedramp-auditscope`.
[2] Azure OpenAI Service FedRAMP High in Azure Gov + IL4/IL5 announced September 2024; IL6 added in early 2025 (Microsoft Azure Government devblog).
[3] Azure AI Document Intelligence (formerly Form Recognizer) FedRAMP High + IL4/IL5 in scope; first-party Docker container shipped for on-prem use (mcr.microsoft.com/azure-cognitive-services/form-recognizer/{layout,read}-4.0).
[4] Amazon Bedrock FedRAMP High in AWS GovCloud (US-West) since August 2024; Anthropic Claude 3.5 Sonnet v1 + Claude 3 Haiku and Meta Llama 3 8B/70B authorized FedRAMP High + DoD IL4/IL5 May/June 2025 (AWS What's New, AWS Public Sector Blog, Anthropic blog).
[5] Google Cloud FedRAMP High P-ATO covers >150 services via Assured Workloads; Generative AI on Vertex AI achieved FedRAMP High; Claude on Vertex authorized FedRAMP High + IL2 (March 2025).
[6] "Individual LLMs aren't independently authorized under FedRAMP and there's no record of their authorization in the FedRAMP Marketplace. Instead, the Marketplace reflects authorizations for cloud services" — Google Cloud FedRAMP implementation guide; same rule applies across all hyperscalers.
[7] vLLM is Apache-2.0; Llama 3.x carries Meta's Llama Community License (acceptable-use restrictions and a 700M MAU clause that does not affect federal use); IBM Granite 3.x is Apache-2.0; Qwen 2.5/3 is Apache-2.0.
[8] Per Google Cloud documentation, FedRAMP High for Vertex requires Assured Workloads with the FedRAMP High control package; data residency is enforced via the boundary.
[9] Self-hosting in a FedRAMP cloud VM inherits the boundary's controls; the agency carries software supply-chain accountability for the model weights (AI BOM, NIST AI 600-1 §V "Value Chain and Component Integration" risk category).
[10] Amazon Textract: FedRAMP High authorized in AWS GovCloud (US) Regions and FedRAMP Moderate in US East/West (April 2021 announcement, AWS).
[12] HR 1121 "No DeepSeek on Government Devices Act" (Feb 7, 2025) and the agency administrative bans on DeepSeek (Navy, NASA, DOD, Commerce, USDA, House CAO ~Jan 30, 2025) are model-specific. The "No Adversarial AI Act" (Cassidy/Rosen) is a proposed broader registry framework, not enacted. Application of DeepSeek-precedent reasoning to Qwen / PaddleOCR / PaddleOCR-VL is analyst risk judgment.
[13] FedRAMP authorization is required for federal data above Low; OMB Circular A-130 governance and FISMA both foreclose commercial-cloud processing of Moderate data without explicit agency exception.

---

## Q7.5 — OMB M-24-10 → M-25-21 (and M-24-18 → M-25-22)

### 7.5.1 Rescission and Replacement

- **OMB M-24-10** ("Advancing Governance, Innovation, and Risk Management for Agency Use of Artificial Intelligence", March 28, 2024) was **rescinded April 3, 2025** by **OMB M-25-21** ("Accelerating Federal Use of AI through Innovation, Governance, and Public Trust").
- **OMB M-24-18** (the corresponding AI procurement memo) was rescinded April 3, 2025 by **OMB M-25-22** ("Driving Efficient Acquisition of Artificial Intelligence in Government").
- Both new memos were issued under **EO 14179** (Jan 23, 2025, "Removing Barriers to American Leadership in Artificial Intelligence").

### 7.5.2 M-25-21 Key Sections

- **§3(b)(ii)**: Agency CAIO governance bodies must issue an M-25-21 compliance plan by **December 26, 2025** (180 days). Update agency policies addressing AI cybersecurity and privacy by **May 6, 2026**.
- **§3(b)(v)**: Annual public AI Use Case Inventory submitted to OMB; pre-existing requirement under the Advancing American AI Act of 2022.
- **§4**: **Minimum risk-management practices for high-impact AI** — seven practices:
  1. Pre-deployment testing of models and risk mitigation plans.
  2. Pre-deployment AI impact assessment (intended purpose, expected benefit, model performance, ongoing impacts).
  3. Ongoing monitoring for performance and adverse impacts (privacy, civil rights, safety).
  4. Adequate human training and assessment.
  5. Additional human oversight, intervention, and accountability.
  6. Consistent remedies / appeals mechanisms.
  7. Consult and incorporate end-user / public feedback.
  - **§4 pilot exemption**: pilots that are limited in scale/duration, centrally tracked, with opt-out and notice, applying minimum practices "where available" — exempt from the floor.
  - Operational use cases must document compliance within **365 days** of deployment.
- **§4(a)(iv)**: Public reporting of risk determinations, waivers, and justifications. Waivers must be tracked and reported to OMB **within 30 days** of issuance.
- **§5**: **High-impact AI definition** — "AI with an output that serves as a principal basis for decisions or actions that have a legal, material, binding, or significant effect on rights or safety," with the explicit clarification that "a high-impact determination is possible whether there is or is not human oversight for the decision or action."
- **§6**: **Presumed high-impact categories** — critical infrastructure (incl. safety-critical functions of government facilities); access to critical services / strategic resources; healthcare; robotics & vehicles; defense; government security; employment; benefits administration; risk assessments about individuals; identification of criminal suspects; forecast of crime; tracking; etc.
- **§7**: Methods of Understanding AI Risk Management (informs ERM integration; many agencies leverage NIST AI RMF here).
- **§8**: CAIO authority to issue waivers from minimum practices via written determination, with central tracking.

### 7.5.3 M-25-22 Key Sections

- **§2c**: Applies to contracts awarded pursuant to a solicitation issued **on or after September 30, 2025**.
- **§3c**: "Buy American" — maximize use of US-developed AI products and services.
- **§3d**: Privacy — Senior Agency Official for Privacy involved pre-solicitation when systems handle PII.
- Vendor-lock-in protections: knowledge transfer, data and model portability, licensing/pricing transparency, code/model rights at contract closeout.
- Performance-based contracting: SOOs, PWS, QASPs, contract incentives.
- Use-of-Government-Data: contracts must permanently prohibit use of non-public agency input data and outputted results to train publicly or commercially available AI absent explicit agency consent.
- GSA AI procurement guide due ~Aug 26, 2025; GSA best-practices repository due ~January 27, 2026.

### 7.5.4 Net Effect for Our System

- We treat the system as **potentially high-impact AI** (Q7.1.3) and design to the §4 minimum practices floor.
- Our prototype phase qualifies as a **§4 pilot exemption** candidate if TTB centrally tracks it, limits scale (e.g., evaluation set, not 150K/year production volume), provides opt-out/notice, and applies the practices "where available."
- For procurement of any commercial AI components (Azure OpenAI Gov, Bedrock GovCloud, Vertex AI Gov, etc.), M-25-22 contract terms apply to any acquisition vehicle solicitation issued after Sept 30, 2025.

---

## Q7.6 — NIST AI RMF Application

### 7.6.1 The Four Core Functions (NIST AI 100-1, AI RMF 1.0, January 2023)

| Function | Application to our system |
|---|---|
| **Govern** | TTB CAIO designation; AI Use Case Inventory entry per Advancing American AI Act / M-25-21 §3(b)(v); CAIO classification of high-impact status (OQ-7-1); AI Impact Statement; written rationale documenting the deterministic-first design and the LLM's bounded role; integration with Treasury enterprise risk management per TD 85-01 and TD P 85-01. |
| **Map** | Use-case definition: ingest application + label image, return pass/fail/needs-review with CFR citation, bounding boxes, and image regions. Stakeholders: industry submitters (subjects of decisions), ALFD reviewers (operators), TTB regulatory leadership, Treasury OCIO. Data lineage: applicant submission → rule-engine validators → conditional LLM disambiguation → reviewer UI. NIST AI 600-1 12-category risk inventory done explicitly (see 7.6.2). |
| **Measure** | Pre-deployment testing per M-25-21 §4: per-field validator accuracy; LLM-disambiguation precision/recall against held-out gold set; fuzzy-match threshold sensitivity ([T3](./2026-09-15-rule-engine-architecture.md) reports 0.85/0.92 for brand names); confabulation rate on borderline cases; bbox/region accuracy; section-508 conformance testing. Ongoing monitoring telemetry per §4(c). |
| **Manage** | Acceptance thresholds; LLM kill-switch (deterministic-only fallback) per the deterministic core, substitutability and production parity; Plan of Action and Milestones (POA&M) tied to the Rev 5 ATO; M-25-21 §4(d) operator training; appeals / correction path for industry submitters. |

### 7.6.2 NIST AI 600-1 Generative AI Profile (July 26, 2024) — 12 Risk Categories Applied

| # | Category (NIST AI 600-1) | Applicability to TTB system |
|---|---|---|
| 1 | CBRN information / weapons | N/A |
| 2 | Confabulation | **Material.** LLM disambiguation could fabricate a non-existent CFR provision or a non-existent label element. Mitigated by the deterministic core (LLM does not decide), schema-strict outputs ([T5](./2026-09-15-llm-orchestration-architecture.md)), and rule-engine being source of truth for CFR citations. |
| 3 | Dangerous, violent, or hateful content | Low — domain is alcohol labels. |
| 4 | Data privacy | **Material.** Industry submitter business-confidential information; PII for sole-proprietor permittees. Addressed by Treasury TD 25-04 (Privacy Act handbook) and TD 25-08 (PII breach response). |
| 5 | Environmental impacts | Tracked but not material at this scale (~150K labels/year). |
| 6 | Harmful bias and homogenization | **Material.** Risk that the LLM systematically advantages large-brand label conventions over craft / minority-owned-business label aesthetics. Mitigated by deterministic-first; monitor approval-rate parity. |
| 7 | Human-AI configuration | **Material.** Ensure ALFD reviewer does not over-defer ("automation bias") to LLM disambiguation. M-25-21 §4(e) human-oversight practice. |
| 8 | Information integrity | **Material.** Confabulated CFR citations or bbox coordinates degrade the integrity of the regulatory record. |
| 9 | Information security | Standard 800-53 Rev 5 SI/SC family; prompt-injection vector through label image text or application data. |
| 10 | Intellectual property | Industry-submitted artwork is the submitter's IP; M-25-22 prohibits its use to train commercial models. |
| 11 | Obscene, degrading, abusive content | Low. |
| 12 | Value chain and component integration | **Material.** Self-hosted vs cloud LLM choice flows here. AI BOM, supply-chain review, foreign-adversary model exclusion. |

### 7.6.3 Operationalization 2024-2026

NIST released NIST AI 600-1 July 26, 2024 and a concept note for an AI RMF Profile on Trustworthy AI in Critical Infrastructure on April 7, 2026. Per the July 2025 AI Action Plan ("Winning the Race"), references to DEI in NIST AI RMF are slated to be removed; the underlying disparate-impact legal framework under Title VII (codified 1991) is unchanged.

---

## Q7.7 — AI-Specific Procurement / Use Restrictions Beyond M-25-21

| Constraint | Source | Application to our prototype |
|---|---|---|
| **Buy-American AI** | M-25-22 §3c; AI Action Plan July 2025; EO 14275 (Apr 15, 2025, FAR reform) | Prefer US-origin LLMs (Llama / Granite / GPT) and US-origin OCR (Azure DI / AWS Textract / Google Document AI / Tesseract) over PRC-origin (Qwen, PaddleOCR) for federal acquisition. |
| **DeepSeek federal-wide ban posture** | HR 1121 (Feb 7 2025); No Adversarial AI Act (proposed); agency administrative blocks (Navy, NASA, DOD, Commerce, USDA, House CAO) | DeepSeek specifically: disallowed by default. Other PRC-origin open-weight models: elevated CAIO review under analyst-judgment risk-extension; not categorically banned. |
| **EO 14179 (Jan 23, 2025)** | Federal Register | Sets the deregulatory direction; rescinded EO 14110; produced M-25-21/22 within 60 days. |
| **EO 14319 (July 2025) — "ideologically neutral" AI** | White House July 23, 2025 EO package | Federal procurement prefers AI models that are "truthful and ideologically neutral." Operational guidance still emerging. |
| **EO 14365 (Dec 11, 2025)** | White House | Establishes AI Litigation Task Force for state-AI-law preemption challenges; Sec. of Commerce evaluation of state AI laws within 90 days. Tangential to our prototype but flags an unstable interagency policy environment. |
| **Open-weight models — preference** | AI Action Plan (Jul 2025): "the Federal government should create a supportive environment for open models" | Llama / Granite / Mistral / Pixtral / Qwen-class are *encouraged* in principle; supply-chain origin still constrains in practice. |
| **Training-data provenance / AI BOM** | NIST AI 600-1 §V (Value Chain); CISA SBOM guidance; M-25-22 vendor-attestation expectations | Document for any LLM/VLM used in the system. |
| **Licensing posture for federal use** | Federal acquisition practice; OGC interpretation | Apache-2.0 / MIT preferred; **Llama Community License** (Meta) acceptable for federal — the 700M monthly active user clause does not constrain federal use; **OpenRAIL** generally acceptable; **xLAM CC-BY-NC-4.0** is **NOT** acceptable for federal commercial-mission use because of the Non-Commercial restriction. |
| **Export controls on AI models** | EAR commerce controls; AI Action Plan export-control posture | Not directly binding on a domestic civilian agency deployment, but vendor's export-control compliance posture is a procurement consideration. |
| **CISA SBOM / Software Supply Chain (EO 14028 carryover)** | CISA SBOM Minimum Elements | Required for any vendor-supplied AI system component. |

---

## Q7.8 — OCR/Vision Options Compliance Posture (uses [T4](./2026-09-15-ocr-vision-architecture.md) outputs)

| Option | Authorization status | Position on the gradient | Required controls |
|---|---|---|---|
| **Azure AI Document Intelligence** (prototype pick per [T4](./2026-09-15-ocr-vision-architecture.md)) | FedRAMP High in Azure Government; DoD IL2/IL4/IL5; FIRST-PARTY DOCKER CONTAINER for substitution | 🟢 **Allowable** for our Moderate workload in Azure Gov | Inherit boundary; document container deployment configuration if used on-prem; ConMon for the bureau system. |
| **AWS Textract** | FedRAMP High in GovCloud (April 2021, JAB P-ATO); FedRAMP Moderate in commercial US East/West | 🟢 **Allowable** in GovCloud; 🟡 in commercial requires waiver for Moderate workloads | Service-listed in GovCloud — strongest cloud-OCR auth posture among hyperscalers. |
| **Google Document AI** | Inherits Google Cloud FedRAMP High P-ATO (>150 services in scope) via Assured Workloads | 🟢 **Allowable** | No on-prem container — substitution requires falling back to a different OCR for on-prem mode. |
| **Tesseract / EasyOCR** | Apache-2.0; not directly FedRAMP authorized; inherit from underlying compute boundary | 🟡 **Allowable-with-controls** | Self-hosted; SBOM and supply-chain review required; FIPS 140-3 cryptography on the host. |
| **PaddleOCR** | Apache-2.0; PRC-origin (Baidu); inherits compute boundary | 🟡 **Allowable-with-elevated-review** under analyst-judgment supply-chain posture | Same self-host controls + CAIO supply-chain review. Not categorically prohibited; expect procurement-side scrutiny. |
| **VLMs in cloud — Claude on Bedrock GovCloud** | FedRAMP High + IL4/5 (Claude 3.5 Sonnet v1, Claude 3 Haiku) | 🟢 **Allowable** | Bedrock guardrails; M-25-21 minimum practices if high-impact. |
| **VLMs in cloud — GPT-4o via Azure OpenAI Gov** | FedRAMP High + IL4/IL5/IL6 | 🟢 **Allowable** | Azure Gov tenant; Buy-American satisfied. |
| **VLMs in cloud — Gemini via Vertex AI** | FedRAMP High via Assured Workloads | 🟢 **Allowable** | New hyperscaler dependency for Treasury / TTB. |
| **Open VLMs — Qwen2.5-VL / PaddleOCR-VL (Apache-2.0, PRC-origin)** | Self-hostable, inherits compute boundary | 🟡 **Allowable-with-elevated-review** | Apply DeepSeek-precedent risk reasoning analytically; CAIO acquisition review required. |
| **Open VLMs — Llama 3.2 Vision (Llama Community License)** | Self-hostable; on-prem or cloud VM | 🟡 **Allowable-with-controls** | License is acceptable for federal use; AI BOM required. |
| **Open VLMs — Pixtral (Apache-2.0)** | Self-hostable; French-origin (Mistral) | 🟡 **Allowable-with-controls** | Not flagged under foreign-adversary posture; SBOM required. |

---

## Q7.9 — LLM/Orchestration Compliance Posture (uses [T5](./2026-09-15-llm-orchestration-architecture.md) outputs)

[T5](./2026-09-15-llm-orchestration-architecture.md) chose **single-shot tool-call only** (no multi-step agents) with **schema-strict structured outputs**. This is the right design under M-25-21 and NIST AI 600-1 because it bounds the LLM's authority and makes confabulation containable.

| Option | Position on gradient | Notes |
|---|---|---|
| **Cloud LLM API (commercial, no FedRAMP)** — OpenAI direct, Anthropic direct, Google AI Studio | 🔴 **Disallowed** for Moderate federal data absent explicit waiver | Even for "AI use cases that must still be inventoried," sending Moderate workload data to a commercial endpoint is foreclosed by FISMA + OMB Circular A-130. |
| **Cloud LLM API (FedRAMP)** — Azure OpenAI in Azure Gov, Bedrock GovCloud, Vertex AI Gov | 🟢 **Allowable**, strongest path | The recommended production path; the LLM inherits the cloud service's authorization (the "individual LLMs aren't independently authorized" rule). |
| **Self-hosted open-weight LLM in FedRAMP-authorized cloud VM** (vLLM on Azure Gov VM or AWS GovCloud EC2; Llama 3.1 8B, Granite 8B) | 🟡 **Allowable-with-controls** for US/EU-origin weights; 🟡 with elevated review for PRC-origin (Qwen3 8B) | Inherits boundary auth; agency carries supply-chain review (AI BOM, NIST AI 600-1 V&C). [T5](./2026-09-15-llm-orchestration-architecture.md) noted Bedrock GovCloud authorized Llama 3 8B/70B in May 2025. |
| **Hybrid (cloud OCR + self-hosted LLM)** | 🟡 **Allowable-with-controls** | Boundary documentation must show data-flow paths and any cross-boundary egress; an interconnect security agreement may be required. Common production pattern. |

**Per-call cost** (from [T5](./2026-09-15-llm-orchestration-architecture.md)): negligible at 150K labels/year — ~$750-$1,800/yr cloud — so cost is **not** the binding constraint; compliance and substitutability are.

---

## Q7.10 — Rule Engine and Deterministic Components

The deterministic Python rule engine ([T3](./2026-09-15-rule-engine-architecture.md)) carries a **minimal AI-specific compliance burden** because:

- It is not "AI" within the M-25-21 §2 definition (no model inference; deterministic per-field validators with declared match policies and explicit fuzzy-match thresholds 0.85/0.92).
- Confidence aggregation is min-aggregate (not multiplicative) — auditable.
- LLM is invoked only for borderline cases per the deterministic core; rule engine outputs CFR citation + bbox + image region for every reject.

**Standard application security applies (NIST SP 800-53 Rev 5):**

| Control family | Application |
|---|---|
| **AC** (Access Control) | RBAC for ALFD agents / supervisors / admins; PIV/CAC enforcement at the application layer. |
| **AU** (Audit and Accountability) | Per NIST SP 800-92 logging guidance; immutable audit trail of every rule-engine decision, every LLM invocation, every reviewer override. |
| **IA** (Identification & Authentication) | FIPS 201-2/3 PIV-card-based authentication; MFA per M-22-09. |
| **SC** (System & Communications Protection) | TLS 1.2+ in transit; FIPS 140-3 modules; encryption at rest. |
| **SI** (System & Information Integrity) | Input validation; flaw remediation; security alerts; ConMon. |

**AI-specific overhead is zero for the rule engine itself.** It only attaches at the LLM/VLM boundary, where M-25-21 §4 minimum practices kick in (and only if our high-impact determination stands).

---

## Q7.11 — Typical Authorization Timelines (Concrete Numbers)

| Item | Number | Source |
|---|---|---|
| **Civilian-agency Moderate ATO duration (legacy Rev5)** | 12-18 months from initial submission; up to 24-36 mo with remediation cycles | Vanta, Knox Systems, Workstreet, Schellman, GAO-24-106395 |
| **Median backlog before 20x** | ~22 months | GAO-24-106395 |
| **FedRAMP 20x Phase 1 (Low) result** | First pilot completed in ~119 days; 12 of 26 submissions authorized in window | fedramp.gov/20x/phase-one/ |
| **FedRAMP 20x Phase 2 (Moderate) target** | 3-6 months end-to-end; pilot Nov 2025-Mar 2026; default Q3 2026 | fedramp.gov/20x/phase-two/, Workstreet, Cabrillo Club |
| **Current legacy Rev5 PMO review queue** | ~5 weeks at PMO (queue cleared FY25) | fedramp.gov 2025-07-30 update |
| **FedRAMP 20x default deadline for new authorizations** | Q3 2026 | fedramp.gov, Cabrillo Club |
| **Rev5 sunset** | FedRAMP stops accepting new Rev5-based agency authorizations end of FY27 | fedramp.gov/20x/ Phase 5 |
| **Continuous monitoring overhead — Moderate** | Monthly vulnerability scans + annual 3PAO + POA&M; $150K-$350K/year | Vanta, Secureframe, Paramify, Workstreet |
| **Re-authorization cadence** | Annual reassessment + 3-year refresh | FedRAMP PMO standard |
| **Treasury bureau ATO for our system (estimate)** | 6-12 months reusing Treasury enterprise controls; 12-18 mo greenfield | Inferred from TD P 85-01 governance + IRS IRM 1.33.9 / IRM 10.8.2 cost conventions analogue |

---

## Q7.12 — Compliance Overhead Cost Components (per GAO-20-195G)

> **Cost-estimating posture (federal cost-analysis conventions).** All figures are presented as **ranges with confidence percentiles**, mapped to a Work Breakdown Structure (WBS), and grounded in OMB A-94 (Nov 2023) discounting where multi-year. Labor figures cite OPM and Treasury salary-table conventions. We deliberately use ranges, not point estimates, per GAO-20-195G's four pillars: comprehensive, well-documented, accurate, credible.

### 7.12.1 Personnel (loaded annual labor — full-time-equivalent base)

| Role | Federal employee loaded (incl. benefits, 30-35% on top of OPM GS base) | Contractor loaded |
|---|---|---|
| Compliance / security engineer (GS-13 to GS-14 equivalent) | $150K-$220K | $200K-$350K |
| Privacy officer / SAOP-side reviewer | $140K-$200K | $200K-$300K |
| 3PAO consulting engineer (vendor-side) | N/A | $250K-$400K |
| Legal / acquisition reviewer | $160K-$220K | $250K-$380K |

### 7.12.2 3PAO Assessment (vendor-disclosed market data 2025-2026)

| Tier | Range |
|---|---|
| FedRAMP Low | $30K-$80K |
| FedRAMP Moderate | $150K-$650K (typical $250K-$500K) |
| FedRAMP High | $300K-$800K |
| FedRAMP 20x (Moderate, pilot) | early indicative $100K-$300K end-to-end (firming up) |

### 7.12.3 Tooling & Continuous Monitoring

- Vulnerability scanners, SIEM, OSCAL/GRC platform: **$50K-$200K/year**
- Vendor "FedRAMP premium" (often ~30% markup on Gov-tier services): factor into the inference and OCR line items.

### 7.12.4 POA&M Maintenance and Documentation

- **0.5-1.0 FTE** ongoing.

### 7.12.5 Re-authorization Cycle

- **~$50K-$150K every 3 years** (refresh package, 3PAO touch-up).

### 7.12.6 WBS for Our System (Per Recommended Option, 5-Year Horizon, FY26 dollars)

> **Confidence percentiles per line item.** Following GAO-20-195G step 9, each WBS line is presented with a P20 (low / favorable conditions), P50 (most likely), and P80 (high / should-cost reserve). Total-row P-bands derive from the line items, not from a separate calculation.

#### Option A — Azure Gov + Azure OpenAI Gov + Azure DI

| WBS | Description | P20 | P50 | P80 |
|---|---|---|---|---|
| 1 | Project management | $200K | $300K | $460K |
| 2 | System development & integration | $400K | $600K | $920K |
| 3 | ATO package (initial) | $250K | $425K | $690K |
| 4 | 3PAO assessment (initial) | $150K | $225K | $345K |
| 5 | Continuous monitoring (annual × 5) | $750K | $1.25M | $1.75M |
| 6 | Cloud / compute (annual × 5) | $250K | $425K | $600K |
| 7 | LLM/inference (annual × 5) | $4K | $6.5K | $9K |
| 8 | M-25-21 §4 minimum practices (Yr1 + Yr2-5) | $240K | $360K | $530K |
| 9 | Section 508 / accessibility | $130K | $195K | $290K |
| 10 | Re-authorization (Yr 3) | $50K | $100K | $170K |
| **Total 5-yr TCO** | | **~$2.4M** | **~$3.9M** | **~$5.8M** |

#### Option C — AWS GovCloud + Bedrock + Textract

| WBS | Description | P20 | P50 | P80 |
|---|---|---|---|---|
| 1 | Project management | $250K | $350K | $520K |
| 2 | System development & integration | $500K | $700K | $1.0M |
| 3 | ATO package (initial; 2nd hyperscaler stand-up) | $400K | $650K | $1.0M |
| 4 | 3PAO assessment (initial) | $200K | $350K | $580K |
| 5 | Continuous monitoring (annual × 5) | $1.0M | $1.6M | $2.3M |
| 6 | Cloud / compute (annual × 5) | $300K | $500K | $700K |
| 7 | LLM/inference (annual × 5) | $4K | $6.5K | $9K |
| 8 | M-25-21 §4 minimum practices | $240K | $360K | $530K |
| 9 | Section 508 / accessibility | $130K | $195K | $290K |
| 10 | Re-authorization (Yr 3) | $80K | $140K | $230K |
| **Total 5-yr TCO** | | **~$3.1M** | **~$4.9M** | **~$7.2M** |

#### Option G — Self-hosted Llama / Granite in Azure Gov VM

| WBS | Description | P20 | P50 | P80 |
|---|---|---|---|---|
| 1 | Project management | $250K | $350K | $520K |
| 2 | System development & integration | $600K | $800K | $1.15M |
| 3 | ATO package (initial; AI BOM + supply-chain review) | $400K | $650K | $1.0M |
| 4 | 3PAO assessment (initial) | $200K | $350K | $580K |
| 5 | Continuous monitoring (annual × 5) | $1.25M | $1.875M | $2.5M |
| 6 | GPU compute (annual × 5; Azure Gov VM ND-series) | $500K | $900K | $1.4M |
| 7 | LLM/inference (embedded in 6) | — | — | — |
| 8 | M-25-21 §4 minimum practices | $240K | $360K | $530K |
| 9 | Section 508 / accessibility | $130K | $195K | $290K |
| 10 | Re-authorization (Yr 3) | $80K | $140K | $230K |
| **Total 5-yr TCO** | | **~$3.65M** | **~$5.6M** | **~$8.2M** |

#### Option I — On-prem self-hosted (Treasury / TTB data center)

| WBS | Description | P20 | P50 | P80 |
|---|---|---|---|---|
| 1 | Project management | $300K | $425K | $635K |
| 2 | System development & integration | $700K | $1.0M | $1.45M |
| 3 | ATO package (initial; greenfield bureau ATO) | $700K | $1.1M | $1.65M |
| 4 | 3PAO equivalent / assessment | $300K | $500K | $800K |
| 5 | Continuous monitoring (annual × 5) | $1.5M | $2.25M | $3.0M |
| 6 | GPU hardware capex (amortized 5 yr) + ops | $1.25M | $1.875M | $2.5M |
| 7 | LLM/inference (embedded in 6) | — | — | — |
| 8 | M-25-21 §4 minimum practices | $240K | $360K | $530K |
| 9 | Section 508 / accessibility | $130K | $195K | $290K |
| 10 | Re-authorization (Yr 3) | $100K | $175K | $290K |
| **Total 5-yr TCO** | | **~$5.2M** | **~$7.9M** | **~$11.2M** |

OMB A-94 (Nov 2023) discounting at the published real discount rate for federal IT investments should be applied for present-value comparison if the comparison horizon exceeds 3 years.

> **Caveat on confidence-band rigor.** The P20/P50/P80 bands above are GAO-style triangular distributions over the input ranges, not Monte Carlo simulations. A production-grade estimate would simulate joint variation across line items per GAO-20-195G step 9. For the prototype phase these single-variable bands are appropriate; for a real Exhibit 300 they would need to be replaced with Monte Carlo output.

---

## Q7.13 — Treasury IT Compliance Baseline

**Authoritative documents (publicly available unless noted):**

- **Treasury Directive 85-01** (March 10, 2008): authorizes TD P 85-01 ("Treasury IT Security Program") and applies to all bureaus, offices, and organizations including offices of inspectors general; CIO is authorized to prescribe, publish, and maintain TD P 85-01.
- **Treasury Directive Publication TD P 85-01**: Treasury IT Security Program — bureau-wide controls, mapped against NIST 800-53. *Latest revisions are non-public.*
- **Treasury Directive 85-03** (Jan 9, 2009): authorities of the DASIS/CIO during IT security incidents.
- **Treasury Directive 25-04** (May 6, 2024): Privacy Act of 1974 implementation.
- **Treasury Directive 25-07** (Jan 11, 2022): Privacy and Civil Liberties Impact Assessment (PCLTA / PCLIA).
- **Treasury Directive 25-08** (Dec 22, 2009; admin-edited Jul 16, 2024): PII safeguarding and breach response — one-hour reporting to TSSSOC.
- **Treasury Acquisition Procedures (TAP) Subpart 1007.70**: pre-award technology acquisition planning, including security and privacy considerations. Applicable to any procurement vehicle TTB uses for the system.
- **IRS IRM 10.8.2** (analogous bureau-level implementation): IT Security Roles and Responsibilities — referenced because it makes the TD P 85-01 → bureau implementation pattern public; useful as a model for inferring TTB's likely posture, since TTB-specific bureau IRM-equivalents are non-public.
- **IRS IRM 1.33.9** (analogous): bureau cost and budget conventions, useful as the Treasury-bureau analog for our cost work.

**Inference (PROVISIONAL).** TTB-specific IT security policy is non-public. Based on the public Treasury baseline and the IRS analogue, we infer:
- TTB inherits TD P 85-01 controls and may have a bureau supplement (analogous to IRS IRM 10.8.x series).
- ATO authority for TTB systems sits with the TTB CIO (or shared with Treasury OCIO for cross-bureau systems).
- Treasury enterprise services (identity, SOC, ConMon platform) are likely available for TTB systems to inherit, reducing bureau-side ATO labor.

---

## Q7.14 — TTB IT Environment Specifics

### 7.14.1 What we know from the Marcus interview

- **Azure migration completed in 2019.**
- **FedRAMP authorization "took 18 months just for the paperwork."** (Consistent with the Rev5 legacy 12-18 mo timeline; corroborates GAO-24-106395.)
- **Agency firewall blocked the prior scanning vendor's ML endpoints** — strongly suggests a tightly governed egress posture, consistent with M-22-09 zero-trust **Networks** pillar.
- **Outbound traffic blocked to many domains** — prototype must plan for whitelisting any cloud-AI endpoints; any commercial-cloud LLM SaaS endpoint is presumptively blocked.

### 7.14.2 What we infer from public sources

- **TTB FY 2025 Congressional Justification** ($1.784M for myTTB IT modernization): "TTB learned in late FY 2023 that the IT platform underpinning Permits Online, its current permitting system, will no longer be supported by the software vendor as of December 2025." **Implication:** TTB IT bandwidth in FY26 is partially absorbed by this migration; integration with the label-verification prototype is competing for capacity.
- **myTTB platform** (ttb.gov/online-services) is the active integration vector for COLAs Online + Formulas Online + Permits Online.
- **TTB FY 2023 actuals**: ~28% label error rate, 23% formula error rate; voluntary compliance measurement is the primary tax-administration strategy.
- **Treasury Modernizing Government Technology Working Capital Fund**: a likely funding-vehicle option for the prototype-to-production transition.

### 7.14.3 Open questions (PROVISIONAL — flagged)

- **OQ-7-2**: Is TTB's Azure tenant Commercial or Government? Marcus's "FedRAMP took 18 months" comment plus the firewall-blocking-ML-endpoints story strongly suggests **Azure Government**, but this is not confirmed in public sources. *Material* to whether row A in Q7.4 is 🟢 or downgrades to 🟡.
- **OQ-7-3**: TTB outbound traffic posture — egress whitelisting policy, Treasury TIC (Trusted Internet Connection) integration, and the mechanism by which a prototype LLM endpoint would get added to the allowlist.
- **OQ-7-4**: Does TTB have an existing myTTB Permits ATO that the prototype could share boundary with? If yes, materially shortens our ATO timeline.
- **OQ-7-5**: TTB's identity infrastructure — PIV/CAC integration via Treasury Federation Solution / Common Approach to Identity Assurance (CAIA, Treasury Bureau of the Fiscal Service standard) vs. Login.gov vs. ID.me vs. SailPoint IIQ.
- **OQ-7-6**: Existing AI/ML deployments at TTB — none publicly disclosed in TTB FY 2025 budget materials; the FY 2026 AI use-case inventory under M-25-21 §3(b)(v) may answer this once published.

---

## Q7.15 — Identity and Access Patterns

**Standards baseline:**

- **FIPS 201-2 / 201-3** — Personal Identity Verification of Federal Employees and Contractors. Treasury employees, detailees, contractors all hold a HSPD-12 PIV card.
- **OMB M-22-09** (Jan 26, 2022) — "Moving the U.S. Government Toward Zero Trust Cybersecurity Principles," organized around the **CISA Zero Trust Maturity Model five pillars**:
  1. **Identity** — centralized identity management; phishing-resistant MFA; PIV at the application layer (not just the network).
  2. **Devices** — agency tracks and monitors all devices; security posture used to grant access.
  3. **Networks** — agency systems isolated; encrypted traffic flowing between and within them.
  4. **Applications & Workloads** — apps available securely over the internet.
  5. **Data** — data-pillar progress per the Federal Zero Trust Data Security Guide.

**Treasury-specific:**

- **Treasury Federation Solution / Common Approach to Identity Assurance (CAIA)** — Bureau of the Fiscal Service uses CAIA + SailPoint IdentityIQ for permission management and a Single Sign-On layer. PIV/CAC linking to Fiscal Service SSO accounts is the established pattern (piv.treasury.gov / CASS).
- For non-PIV-eligible external users, ID.me and Login.gov are the supported third-party CSPs; ID.me is the IAL2-rated path for Treasury applications as Login.gov did not (at last research) have a current IAL2-compliant offering.

**Application to our system:**

| Role | Identity source | Auth pattern |
|---|---|---|
| ALFD agent (TTB employee) | Treasury PIV card | PIV cert at app layer (FIPS 201-3); centralized via Treasury Federation Solution / CAIA |
| Supervisor / admin (TTB employee) | Same | Same; RBAC-elevated role |
| TTB IT operator | Same | Privileged access management on top |
| Industry submitter (external) | Login.gov / ID.me (already used by myTTB ecosystem) | IAL2 via ID.me where required; NIST SP 800-63 IAL/AAL/FAL alignment |

**Audit logging** per **NIST SP 800-92** (Computer Security Log Management): every access, every rule-engine decision, every LLM invocation, every reviewer override — written to an immutable audit store with retention per Treasury records-management directives.

**Gap analysis vs. prototype.** The prototype has simple application-layer auth for the developer-facing UI. Production must:
- Replace simple-auth with PIV-at-application-layer (cert-binding-to-user pattern documented by GSA USAccess).
- Federate to Treasury identity (whichever endpoint TTB designates — OQ-7-5).
- Implement Conditional Access policies per M-22-09 (device signal + identity).
- Add FIPS 140-3 cryptography on session tokens.
- Map RBAC roles to Treasury position-based access patterns.

---

## Q7.16 — Section 508 Specifications

### 7.16.1 Standards Baseline

- **Section 508 of the Rehabilitation Act**, 29 U.S.C. § 794d.
- **Section 508 Refresh** (Revised 508 Standards, 36 CFR 1194), effective **January 18, 2018**, incorporated **WCAG 2.0 Level A and Level AA** by reference. **This is the legal floor for federal IT accessibility.** WCAG 2.1 and 2.2 are *not* incorporated into Section 508 by reference; they should be treated as best-practice design targets, not regulatory minima.
- The **DOJ ADA Title II Final Rule (April 2024)** sets WCAG 2.1 AA for state and local governments — this does not apply to federal agencies, but is shaping convergent industry practice.
- **WCAG 2.2** was finalized October 2023; building to 2.2 is a defensible best-practice posture and is recommended for new federal builds because it forecloses likely future Refresh updates.
- **U.S. Access Board** maintains the standards; **GSA Section 508 program** (section508.gov) maintains the **Accessibility Requirements Tool (ART)** and the **DHS Trusted Tester** program for conformance testing.
- **VPAT** (Voluntary Product Accessibility Template, ITI) is the de facto procurement-disclosure document.

### 7.16.2 Specific UI Requirements (mapped to the WCAG 2.0 AA legal floor with 2.1/2.2 best-practice extensions noted)

| Requirement | Source (legal floor) | Application |
|---|---|---|
| Keyboard navigation | WCAG 2.1.1 (in WCAG 2.0 AA) | Batch upload UI, evidence display, image-region viewer must be fully keyboard-operable. |
| Screen reader compatibility | WCAG 1.3.1, 4.1.2 / Revised 508 502, 503 | All bbox / image-region annotations must have text-equivalent alt + ARIA labeling. |
| Contrast ratio | WCAG 1.4.3 | 4.5:1 normal text; 3:1 large text. |
| Color not sole conveyance | WCAG 1.4.1 / Revised 508 410 | **Critical for our system.** Image-region highlighting (red bbox = violation) must include a non-color cue (icon, label, pattern). |
| Focus management | WCAG 2.4.3, 2.4.7 | Reviewer pane focus on next decision card; clear visible focus indicator. |
| Table semantics | WCAG 1.3.1 | Batch UI tables (150K-label review queue) need proper `<th>` scope, captions, summaries. |
| **Best-practice extensions (WCAG 2.1 AA)** | Not legally required, recommended | Reflow (1.4.10), non-text contrast (1.4.11), focus-visible rules; protects against future Refresh. |
| **Best-practice extensions (WCAG 2.2 AA)** | Not legally required, recommended | Focus appearance, dragging movements, target size minimum (24×24 CSS pixels). |
| Senior-friendly UX | TTB project benchmark ("73-year-old benchmark") | Larger default font sizes; minimum 16px body text; generous tap targets; reduced reliance on hover; persistent nav. |

### 7.16.3 Implications for Our Components

- **Image-region highlighting:** every bbox/region must carry a label and/or icon, not only color.
- **Batch upload UI:** progress indicators must be perceivable to screen readers (ARIA live regions); the table of label statuses must be navigable by keyboard with logical reading order.
- **Evidence display:** alt text on every image; magnification at least 200% per WCAG 1.4.4; user-controllable highlight overlay.
- **CFR-citation tooltip:** must be available via keyboard focus, not hover-only.

### 7.16.4 Conformance Testing

Use the **Trusted Tester v5** harmonized test process (GSA / DHS) or contract a Section 508 evaluation firm. Produce an Accessibility Conformance Report (ACR / VPAT 2.5+) before production cutover. The ACR must explicitly state conformance level against the WCAG 2.0 AA legal floor; any 2.1/2.2 conformance can be reported additionally.

---

## Q7.17 — "COMPLIANT" vs. "DEPLOYABLE" Gap (CRITICAL)

> Federal IT projects historically die not at the compliance line but at the *deployability* line. A pure-compliance answer that ignores agency-specific friction will not survive a federal audience.

| Architectural option | Compliant? | Deployable at TTB? | Specific friction |
|---|---|---|---|
| **A — Azure Gov + Azure OpenAI Gov + Azure DI** | ✅ Yes | **Likely yes, but depends on:** (1) TTB's Azure tenant being Gov vs Commercial (OQ-7-2); (2) Treasury procurement vehicle availability for Azure OpenAI Gov line item (M-25-22 §2c contract terms post-Sept 30, 2025); (3) firewall whitelisting for Azure OpenAI Gov endpoints; (4) ATO inheritance from any existing Treasury enterprise Azure Gov authorization. | If TTB tenant is Commercial, must stand up a Gov tenant first — adds 6-12 months. |
| **C — AWS GovCloud + Bedrock + Textract** | ✅ Yes | **Possible but materially harder:** TTB has no public AWS footprint. Standing up a second hyperscaler requires a separate Treasury procurement vehicle, separate ATO for the AWS GovCloud boundary, separate firewall/egress rules, and separate identity federation. **Realistic timeline penalty: +6-12 months and +$500K-$1M on top of the cost ranges in Q7.12.6.** | Compliance is fine; deployability is the killer. |
| **E — Vertex AI / Gemini** | ✅ Yes | Same as C — three-hyperscaler problem at Treasury. | Avoid unless a specific Gemini/Vertex feature is uniquely required. |
| **G — Azure Gov VM self-hosted Llama / Granite** | ✅ Yes | **Likely yes, given TTB Azure incumbency:** but introduces ML-Ops responsibilities (model serving infra, GPU capacity, vLLM operations, model-update governance) that TTB historically has not staffed. | Strong substitution rehearsal; staffing/skills gap is the binding constraint. |
| **I — On-prem self-hosted** | ✅ Yes | **Hard at TTB:** TTB ran an on-prem environment pre-2019 but migrated to Azure deliberately. Reversing that posture for one system is a budget-and-staffing fight. Treasury OCIO may push back on bureau-level GPU clusters as an enterprise architecture deviation. | Architecturally cleanest for substitutability but politically/operationally hardest. |
| **K — Commercial cloud LLM API** | ❌ No | ❌ No | Foreclosed by both compliance and deployability; included for completeness. |
| **M — Tracked pilot under M-25-21 §4 exemption (current state)** | ✅ Yes for prototype | ✅ Yes — this is the operating posture today | Must transition to A or G before scaling beyond pilot constraints. |

**The deployability hierarchy at TTB (most-to-least deployable for our system):**

1. **Row A (Azure Gov + Azure OpenAI Gov + Azure DI)** — leverages incumbent Azure relationship; existing Treasury procurement vehicles; existing firewall/egress patterns; PIV/CAIA identity already federated.
2. **Row G (self-hosted Llama in Azure Gov VM)** — same incumbent advantages, plus strongest production-parity story; main risk is ML-Ops staffing.
3. **Row M (current pilot tier)** — only valid through prototype phase.
4. **Rows C / E** — possible but introduces a second hyperscaler; only compelling if TTB strategically wants to multi-cloud.
5. **Row I (on-prem)** — strongest sovereignty story; reverses the 2019 migration posture; long timeline.
6. **Row K** — disallowed.

---

## Q7.18 — Production-Readiness Gap Categories

Tagged for the README's trade-offs section.

| Component | Current prototype state | Gap category |
|---|---|---|
| **Rule engine ([T3](./2026-09-15-rule-engine-architecture.md))** — deterministic Python, declarative validators, fuzzy thresholds 0.85/0.92, min-aggregate confidence | Production-quality logic; standard application-security hardening pending | **"Acceptable for production but suboptimal"** — needs FIPS 140-3 crypto, immutable audit log, FISMA-grade logging hooks. |
| **OCR ([T4](./2026-09-15-ocr-vision-architecture.md)) — Azure Document Intelligence cloud** | Functional in prototype | **"Acceptable for prototype, must be configured for production"** — switch to Azure Gov endpoint, configure customer-managed keys, validate IL5 isolation if applicable. |
| **OCR ([T4](./2026-09-15-ocr-vision-architecture.md)) — Azure DI Docker container alternative** | Validated as substitution path | **"Acceptable for production but suboptimal"** — substitution path exists; on-prem container deployment requires its own ATO supplement. |
| **LLM orchestration ([T5](./2026-09-15-llm-orchestration-architecture.md)) — single-shot, schema-strict, GPT-4o** | Implemented per the deterministic core | **"Acceptable for prototype, must be re-pointed for production"** — production must call Azure OpenAI Gov endpoint inside Azure Gov tenant; commercial endpoint is disallowed. |
| **LLM kill-switch / deterministic-fallback** | Implemented | **"Acceptable for production"** — required by the deterministic core and by M-25-21 §4(d) human-oversight practice. |
| **Authentication / SSO** | Simple developer auth | **"Acceptable for prototype, must be fixed for production"** — replace with PIV-at-app-layer + Treasury Federation / CAIA + Conditional Access. |
| **Audit logging** | Application-level logs | **"Acceptable for prototype, must be fixed for production"** — must conform to NIST 800-92, Treasury TD 85-03 incident response, 1-hour PII breach reporting (TD 25-08). |
| **Section 508 / WCAG 2.0 AA conformance** | Partial — keyboard nav exists; image-region highlighting uses color-only | **"Architecturally blocking — requires redesign in two places"** — image-region annotations need non-color cues; ARIA landmarks for batch UI; ACR/VPAT before production. |
| **AI Use Case Inventory entry (M-25-21 §3(b)(v))** | Not yet filed | **"Acceptable for prototype if pilot exemption applies; must be filed before production cutover."** |
| **AI Impact Assessment (M-25-21 §4(b))** | Not yet authored | **"Acceptable for prototype, must be done before production."** |
| **PCLIA (Treasury TD 25-07)** | Not yet authored | **"Acceptable for prototype, must be done before production."** |
| **AI BOM / supply-chain attestations** | Documented for cloud LLMs (vendor-supplied); not yet documented for any self-hosted path | **"Acceptable for prototype if cloud-only; must be authored if Row G/I path is taken to production."** |
| **POA&M and ConMon hooks** | Not implemented | **"Acceptable for prototype, must be fixed for production"** — agency-wide tooling integration (vulnerability scanner, SIEM, OSCAL outputs). |
| **Outbound-traffic / firewall posture** | Prototype uses developer-laptop egress | **"Architecturally blocking — requires redesign"** — production must operate inside TTB egress whitelisting; for cloud LLM, the Azure OpenAI Gov endpoint must be added to the TTB allowlist explicitly (Marcus interview noted this killed the prior vendor). |
| **Re-categorization to high-impact AI** | Treated provisionally as high-impact for design | **"Acceptable for production but suboptimal until OQ-7-1 is closed"** — need formal CAIO determination before production cutover. |

---

## Open Questions / Research Gaps

| ID | Question | Why it matters |
|---|---|---|
| **OQ-7-1** | Does the TTB CAIO classify this system as M-25-21 high-impact AI? | Determines whether the §4 minimum-practices floor is mandatory for production (vs. pilot exemption only). |
| **OQ-7-2** | Is TTB's existing Azure tenant Commercial or Government? | Determines whether Row A in Q7.4 is 🟢 (Gov) or 🟡 with a tenant-migration prereq (Commercial → Gov). |
| **OQ-7-3** | TTB outbound-traffic posture and process for whitelisting Azure OpenAI Gov / Bedrock GovCloud endpoints. | Marcus's interview flagged this killed a prior vendor; concrete deployability constraint. |
| **OQ-7-4** | Does TTB have an existing myTTB Permits ATO boundary the prototype could share? | Materially shortens the ATO timeline and reduces cost in Q7.12.6. |
| **OQ-7-5** | Identity stack: PIV/CAIA vs Login.gov vs ID.me vs SailPoint IIQ — what does TTB use? | Drives the Q7.15 federation pattern. |
| **OQ-7-6** | Existing TTB AI/ML deployments and AI use-case inventory entries. | Establishes precedent for how the agency has handled prior AI authorization. |
| **OQ-7-7** | Current Bedrock GovCloud authorized model list (post-research date) — has Llama 3.1+ been added? | Affects Row D/G specifically; Anthropic and Meta models in scope are time-limited. |
| **OQ-7-8** | FedRAMP 20x Phase 2 outcomes (closing March 2026) — final Moderate authorization standard. | Affects whether row A/G/I production timelines benefit from the 20x acceleration once it's GA in Q3 2026. |
| **OQ-7-9** | Has Treasury issued bureau-level guidance under M-25-21 §3(b)(ii) (compliance plan due Dec 26, 2025)? | Directly governs how TTB classifies and operates this system. |
| **OQ-7-10** | TD P 85-01 current revision and whether any Treasury-specific overlay diverges from NIST 800-53 Rev 5 Moderate. | Documents the bureau-side controls that the system must meet beyond the FedRAMP boundary inheritance. |

---

## Cross-Topic Synthesis (Deferred)

Per task instructions, the cross-topic synthesis questions **X-3** (production-readiness gap across [T3](./2026-09-15-rule-engine-architecture.md)+[T4](./2026-09-15-ocr-vision-architecture.md)+[T5](./2026-09-15-llm-orchestration-architecture.md)+T7) and **X-7** (cost × policy × technical fit per option, T7+[T11](./2026-09-15-economic-cost-effectiveness-analysis.md)+[T12](./2026-09-15-decision-communication-visualization.md)) are **DEFERRED** to a later synthesis pass. They are not answered here.

---

*End.*