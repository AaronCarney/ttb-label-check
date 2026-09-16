# Stakeholder Frameworks Applied

Filed 2026-09-15.

> Working PM notebook for the TTB AI label verification take-home. Six frameworks applied to the four named stakeholders from the brief: **Sarah Chen** (Deputy Director), **Dave Morrison** (28-yr Senior Agent), **Jenny Park** (Junior Agent, 8 months), **Marcus Williams** (IT Sys Admin). Plus Janet (Seattle field office, named-but-not-interviewed) and the production-stage stakeholders the phase-dependent stakeholder priority already anticipates.
>
> **What's stated vs. inferred.** Quotes and roles are stated (transcripts in the brief). Internal states ("Thinks", "Feels"), pre-mortem probabilities, and emergent-stakeholder activation triggers are inferred — flagged with `[INF]`.

---

## TL;DR

- The phase-dependent stakeholder priority is the right call. Salience analysis confirms it concretely: Dave is **Dominant** (Power+Legitimacy, time-flexible) at prototype stage; Marcus flips from **Dormant** to **Definitive** the moment we say "production"; Sarah moves from sole sponsor to one of several gatekeepers.
- The highest-leverage finding from this exercise is for the **demo**, not the architecture: Dave's first 30 seconds determine whether the take-home reviewer (likely watching with Dave's mindset in mind) leans in or folds arms. The STONE'S THROW case has to be in the first three demo labels.
- Pre-mortem top risk is not a technical failure — it's that **the deployed URL cold-starts past Sarah's 5-second expectation on her first click**, killing trust before the system has a chance to show anything. Cheap to mitigate, easy to miss.
- The original four-interview slate misses **Janet** (already flagged), the **take-home reviewer** themselves (the literal grader), and the **labor union** (NTEU; latent at prototype, definitive if production framing changes).

---

## Frameworks and citations

- **Salience model** — Mitchell, R. K., Agle, B. R., & Wood, D. J. (1997). "Toward a Theory of Stakeholder Identification and Salience." *Academy of Management Review,* 22(4), 853–886. Three attributes (power, legitimacy, urgency) → seven types.
- **RACI** — Standard responsibility-assignment matrix; one Accountable per row.
- **Empathy map** — Gray, D. (2017 canvas), *Gamestorming* (Gray, Brown, Macanufo, 2010, O'Reilly). Six panels: Says / Thinks / Does / Feels / Pains / Gains.
- **JTBD** — Christensen, C. M. (2003), *The Innovator's Solution* (HBS Press); Christensen, Hall, Dillon & Duncan (2016), "Know Your Customers' Jobs to Be Done," *HBR* September. A job has functional, emotional, and social dimensions.
- **Pre-mortem** — Klein, G. (2007), "Performing a Project Premortem," *HBR* September (Reprint F0709A). Imagine the project failed; work backward to causes.
- **Stakeholder onion** — Alexander, I. (2005), "A Taxonomy of Stakeholders." Concentric rings, innermost = system, outermost = wider environment.

---

## Q10.1 — Salience model applied (prototype stage)

| Stakeholder | Power | Legitimacy | Urgency | MAW class |
|---|---|---|---|---|
| **Sarah Chen** | High — sponsor, owns evaluation, sets hard constraints | High — formal role (Deputy Director), grading authority | High — take-home is on a deadline, her team is drowning | **Definitive** (P+L+U) |
| **Dave Morrison** | Low formal power (no sign-off authority); high informal — adoption swings on his reaction | High — 28 years, recognized domain authority, coined the canonical edge case (STONE'S THROW) | Low-Medium — not personally time-pressed; his concerns are durable, not deadline-driven | **Dominant** (P+L) — informally. The Power/Interest grid would file him under "low power" and miss him. |
| **Jenny Park** | Low — junior, no decision rights | Medium — legitimate user voice, but limited tenure | Medium — eager, supplies edge cases readily | **Discretionary** (L only) — easy to please, low cost to satisfy, often forgotten |
| **Marcus Williams** | Low at prototype — explicitly said *"for a prototype, just don't do anything crazy"* | High — gatekeeper role on infra, security, federal compliance | Low — no time pressure on him in this phase | **Dormant** (P only) at prototype. Power exists, latent. |

**Reading the table.** The phase-dependent stakeholder priority ranks Sarah 100, Dave 90, Jenny 80, Marcus 70. Salience confirms the spread — Dave's "Dominant" classification justifies his 90, which Power/Interest would not. The interesting cell is Marcus: **Dormant** at prototype is correct, but Dormant stakeholders are exactly the ones a project sleepwalks past until they wake up. Worth noting.

---

## Q10.2 — Salience model applied (production stage)

Same four stakeholders, plus the emergent ones the phase-dependent stakeholder priority names. Re-running the attribution under a production-procurement frame:

| Stakeholder | Power | Legitimacy | Urgency | MAW class | Δ from prototype |
|---|---|---|---|---|---|
| Sarah Chen | High → **Medium** — decision authority shifts upward to the CIO and contracting | High | Medium | **Dominant** (P+L) | ↓ from Definitive |
| Dave Morrison | Low formal — unchanged | High | Low | **Discretionary** (L) | ↓ from Dominant — relative power drops as compliance roles enter |
| Jenny Park | Low | Medium | Low | **Discretionary** | ≈ unchanged |
| **Marcus Williams** | Low → **High** — owns ATO/FedRAMP/PII path, can block | High | Medium-High — federal cycles | **Definitive** (P+L+U) | ↑↑ from Dormant |
| TTB CIO / OCIO `[INF]` | High — final infra authority | High | Medium | **Dominant** | new |
| Contracting officers `[INF]` | High — controls vendor path | High | Medium | **Dominant** | new |
| Section 508 reviewer `[INF]` | Medium — can block accessibility | High | Low | **Discretionary** → **Dominant** if findings | new |
| NTEU (Treasury employees union) `[INF]` | High in any "AI replacing agents" framing | High | Becomes High instantly on any layoff signal | **Latent → Definitive** | new — see Q10.9 |

**Reading the shift.** This is the production-stage stakeholder map the phase-dependent stakeholder priority references. Three things move:
1. **Marcus rises three steps** (Dormant → Definitive). His prototype-era "don't do anything crazy" stance was a *gift* — it bought us speed at the cost of zero production information. We owe him a real conversation before any procurement framing.
2. **Dave's relative influence drops.** He's still legitimate, but in a procurement room with the CIO and contracting, his voice is one of many.
3. **Two new high-power stakeholders appear** (CIO, contracting) and one **dangerous-class** stakeholder (the union — Power+Urgency without Legitimacy of formal procurement role).

---

## Q10.3 — RACI matrix for the prototype build

One Accountable per row. "Us" = the take-home builder.

| Activity | Sarah | Dave | Jenny | Marcus | Us | Take-home reviewer `[INF]` |
|---|---|---|---|---|---|---|
| Requirements definition | **A** | C | C | I | R | I |
| Architecture decisions | A | C | I | C *(veto on production scope)* | **R** | I |
| Test corpus design | A | C *(STONE'S THROW)* | C *(altered warning)* | I | **R** | — |
| Build / implementation | A | I | I | I | **R** | — |
| Demo / submission | A | — | — | I | **R** | **A** *(grades it)* |
| Hand-off (if any) | **A** | I | I | C | R | — |
| Pre-mortem & risk review | A | C | I | C | **R** | — |
| 5s SLA validation | A | C | C | I | **R** | I |
| Reasoning-output design (rejection reasoning) | A | **C** *(must read as legible to him)* | C | I | **R** | I |
| Class-specific stretch features (the class-depth scope call) | A | C | C | I | **R** | I |

**Notes.**
- The phase-dependent stakeholder priority's tier order maps cleanly to A/C distribution: Sarah is A everywhere except where she explicitly delegated (Marcus on infra at production scope, take-home reviewer on grading).
- The take-home reviewer is added as a column because they are **Accountable on grading** — pretending otherwise is a category error.
- "Hand-off" assumes there is one. In a take-home there usually isn't, but if the prototype gets re-platformed, Sarah is A on what gets handed and to whom.

---

## Q10.4 — Empathy map: Sarah Chen

Stated material is from the transcript; inferred is tagged.

| Panel | Content |
|---|---|
| **Says** | "150,000 label applications a year." "Team of 47 agents." "5-second response time or nobody's going to use it." "Half our team is over 50." "Something my mother could figure out — she's 73." "Handle batch uploads — Janet from Seattle has been asking about this for years." "We tried a pilot with the scanning vendor last year. Disaster." |
| **Thinks** `[INF]` | The last vendor wasted my team's time. This take-home is a low-risk way to see whether AI here is actually possible. If I see one good idea in this submission I haven't seen elsewhere, that's a win for me — I get a story to tell upstairs. If I see a builder who doesn't understand the constraints, I quietly move on. |
| **Does** | Runs evaluation. Sets hard constraints (5s SLA, senior-friendly UI). Has authority to commission, dismiss, or escalate. Came to the meeting late from a personal commitment — life is busy; her time is the scarce resource. |
| **Feels** `[INF]` | Cautiously optimistic — she's spent leadership capital getting AI on the table. Quietly burned by the prior vendor. Protective of her team's time and credibility. Slightly impatient with vendor pitches that don't show their work. |
| **Pains** | Budget cuts (100 agents → 47). Tooling that's slower than doing it by hand. Tech-comfort variance across the team (Dave prints emails; Jenny's native digital). Peak-season batch dumps that overwhelm the queue. |
| **Gains** | Agents freed from "essentially data entry verification" to do judgment work. A defensible modernization story for leadership. A demo she can show Janet without apologizing. |

**Surfaces that aren't in the explicit requirements.**
- *Her time is the scarcest resource in this transaction.* The README and demo should respect that — front-load the punch line, don't bury it.
- *She is risk-averse on adoption, not on technology.* "Nobody's going to use it" is the real fail condition. The demo must read as adoptable, not just clever.
- *The 73-year-old-mother benchmark is testable.* It's not a metaphor; it's a usability standard.

---

## Q10.5 — Empathy map: Dave Morrison

Dave is the highest-leverage trust signal in the demo. Building this map specifically to answer: *what does he need to feel in the first 30 seconds to lean in?*

| Panel | Content |
|---|---|
| **Says** | "I've seen a lot of these 'modernization' projects come and go." "Remember the automated phone system from 2008? Supposed to reduce call volume." "STONE'S THROW vs Stone's Throw — technically a mismatch, obviously the same thing. You need judgment." "I'm not against new tools. Just don't make my life harder." "I spend enough time fighting with COLA as it is." |
| **Thinks** `[INF]` | Show me, don't tell me. If this thing flags STONE'S THROW as a fail, you don't understand the work. If it surfaces real issues with reasoning I can read, fine — I'll use it. |
| **Does** | Reviews labels by eye, fast. Catches nuance pattern-matching can't. Skeptical of dashboards. Probably closes pop-ups without reading. Prints emails. |
| **Feels** `[INF]` | Tired of being a beta tester for tools that don't ship. Quiet pride in his judgment. Slightly defensive about being characterized as "the 28-year guy who prints emails." Curious if anything will actually be different this time. |
| **Pains** | Tools that fail on obvious cases (STONE'S THROW). Tools that add steps without removing any. UI hunting. Modernization theater. |
| **Gains** | A tool that catches what *he'd* catch and asks for help on what *he'd* hesitate on. Gets through queue faster. Doesn't have to fight it. |

**The 30-second test.** Dave needs to see, in order:
1. **A label that looks normal pass cleanly with reasoning he can read** — establishes baseline competence.
2. **STONE'S THROW (or equivalent: case/punctuation variant) handled correctly as fuzzy-match pass** — the test he didn't ask us to pass but is mentally running.
3. **A clearly-bad label flagged with the *right* reason** — not a generic "rejected," but a specific cite to the rule.

If those three land, Dave folds the arms back open. This sequencing is the explicit input to demo design ([T8](./2026-09-15-federal-ux-for-senior-users.md)/[T9](./2026-09-15-verification-targets-research.md)/[T12](./2026-09-15-decision-communication-visualization.md) — synthesis question X-6, deferred).

---

## Q10.6 — JTBD framing for Sarah

Sarah's surface request is "verify labels faster." The deeper job, per Christensen's framing of "the progress a person is trying to make in a particular circumstance":

- **Functional job.** *"Free my agents from routine matching so they can do the judgment work the budget cuts already forced on them."* Note this is not "verify faster" — it's "shift the labor mix from clerical to expert." The 5s SLA is a *constraint* on the functional job, not the job itself.
- **Emotional job.** *"Stop feeling burned by tooling pilots."* The scanning-vendor disaster left a mark. She wants the relief of a tool that actually gets used after the demo ends.
- **Social job.** *"Be the leader who modernized ALFD without breaking it."* Visible to her team (didn't waste their time again), to Janet's office (finally addressed batch), to her chain of command (story to tell).

**Reframing surfaces three things the requirements miss:**
1. **The labor-mix outcome is the metric.** Not labels-per-hour. Showing %-time-on-judgment-vs-matching in any post-demo write-up speaks her language better than throughput numbers.
2. **"Adoptable" is a feature, not an attribute.** Things like "Dave can use this without complaining" or "Jenny's checklist becomes redundant" are JTBD-relevant features. They map to per-field match policies and to rejection reasoning, but they're not stated as requirements.
3. **The take-home submission is a demo of trustworthiness, not just capability.** This unblocks the README framing: lead with what we *didn't* do (auto-decide, scope creep, ignore Marcus's firewall point) as much as what we did.

---

## Q10.7 — Pre-mortem: top 5 failure scenarios

Per Klein (2007): assume the project failed badly; work backward to specific causes. Generic risks excluded; each item below is **specific to this take-home, these stakeholders, and the architecture in `ARCHITECTURE.md`**.

| # | Failure scenario | Probability `[INF]` | Severity | Mitigation |
|---|---|---|---|---|
| **1** | **Cold-start latency on the deployed URL exceeds 5s on the reviewer's first click.** Sarah's hard constraint is the first thing tested. Vercel/Render free-tier cold starts can hit 8–30s. The reviewer leaves a tab open, clicks once, gets a spinner, and the entire submission is colored by that moment. | High | Project-killing on Sarah's primary criterion | Use a platform with no cold start, or warm via a keep-alive ping. Document the choice in README. Test from a fresh browser on a different network within 24h of submission. |
| **2** | **Dave finds an obvious miss in the first three labels.** STONE'S THROW or equivalent fails. Or the warning check flags a correctly-formatted warning. The submission has no second chance once a 28-year reviewer's-mindset reads "doesn't understand the work." | Medium-High | Project-killing on the credibility front | The two highest-impact tests (the per-field fuzzy match for brand, and the reasoning output) must be rock-solid. Add the STONE'S THROW case as a literal test fixture in the repo. Run a Dave-mindset adversarial pass before submission. |
| **3** | **A regulatory citation in the reasoning output is wrong.** Rejection reasoning commits us to citing the rule. If we cite "27 CFR § 16.21" for a § 16.22 formatting issue, anyone with Dave's nuance reads it as an AI-confidently-wrong moment. Worse than no citation. | Medium | High — kills trust in the reasoning system | Cite only what we've verified against the source text. Where unverified, cite the section header level (e.g., "27 CFR Part 16") not the subsection. Have a small known-citations table in code, not generated. |
| **4** | **The demo lands flat because Sarah's team isn't represented in the demo audience.** This is from the brief's pre-mortem candidate list. The take-home is reviewed by people who may or may not include Dave/Jenny — but the *output* needs to read as if Dave were watching, even if he isn't. | Medium | Medium — undermines the persona work | The README and any demo video should explicitly call out the persona-driven test cases ("for the senior agent persona, here's the STONE'S THROW case"). Make the persona work legible to any reviewer. |
| **5** | **Marcus's firewall point gets ignored architecturally and the deployed app uses cloud APIs that "feel cloud-only."** Even though substitutability says cloud is acceptable for the prototype, an architecture that visibly couldn't be re-platformed signals to the reviewer that we didn't read the transcripts. | Medium | Medium — undermines production-parity story | Wrap OCR/vision behind an interface (substitutability already commits to this). Document the seam in README. List on-prem alternatives evaluated in the trade-offs section. |

**Cut for length but worth listing as #6–8** `[INF]`: scope-creep on stretch (the class-depth scope call) makes core look weak; reasoning-output verbose enough that Dave skims past it; batch UI present but not actually fed by the lookahead logic in `ARCHITECTURE.md` (looks like staging, not architecture).

---

## Q10.8 — Stakeholder onion (current + emergent)

```
                 ┌──────────────────────────────────────────────────────────────────┐
                 │  OUTSIDER BUT RELEVANT                                            │
                 │   • NTEU (federal agents' union) `[INF]`                          │
                 │   • CSPI / consumer-advocacy groups `[INF]`                       │
                 │   • Trade associations: DISCUS, Wine Institute, Beer Institute    │
                 │   • Section 508 / accessibility advocates `[INF]`                 │
                 │  ┌───────────────────────────────────────────────────────────┐   │
                 │  │  AFFECTED                                                 │   │
                 │  │   • Industry submitters (producers, importers, agents)    │   │
                 │  │   • FDA (cider/saké < 7% ABV edge cases)                  │   │
                 │  │   • Downstream regulators (state ABC boards) `[INF]`      │   │
                 │  │  ┌─────────────────────────────────────────────────────┐  │   │
                 │  │  │  ENABLER                                            │  │   │
                 │  │  │   • Marcus Williams (IT)                            │  │   │
                 │  │  │   • TTB CIO / OCIO `[INF]`                          │  │   │
                 │  │  │   • Contracting officers `[INF]`                    │  │   │
                 │  │  │   • Treasury IT compliance `[INF]`                  │  │   │
                 │  │  │  ┌───────────────────────────────────────────────┐  │  │   │
                 │  │  │  │  SPONSOR                                      │  │  │   │
                 │  │  │  │   • Sarah Chen (Deputy Director)              │  │  │   │
                 │  │  │  │   • Sarah's chain of command (Director,       │  │  │   │
                 │  │  │  │     Assistant Administrator) `[INF]`          │  │  │   │
                 │  │  │  │  ┌───────────────────────────────────────┐    │  │  │   │
                 │  │  │  │  │  CORE                                 │    │  │  │   │
                 │  │  │  │  │   • Dave Morrison (senior agent)      │    │  │  │   │
                 │  │  │  │  │   • Jenny Park (junior agent)         │    │  │  │   │
                 │  │  │  │  │   • Janet (Seattle field office)      │    │  │  │   │
                 │  │  │  │  │   • The other 44 ALFD agents          │    │  │  │   │
                 │  │  │  │  │   • Field offices beyond Janet's `[INF]`│  │  │  │   │
                 │  │  │  │  └───────────────────────────────────────┘    │  │  │   │
                 │  │  │  └───────────────────────────────────────────────┘  │  │   │
                 │  │  └─────────────────────────────────────────────────────┘  │   │
                 │  └───────────────────────────────────────────────────────────┘   │
                 └──────────────────────────────────────────────────────────────────┘

ALONGSIDE (not in any TTB ring): the take-home reviewer themselves —
   the actual grader. Often forgotten; literally Accountable on submission outcome.
```

**Three stakeholders the original four-interview slate missed:**

1. **Janet (Seattle field office).** Named in Sarah's transcript ("Janet has been asking about this for years"). Not interviewed. Already flagged in 04-research-topics A-4. She likely has the most concrete batch-workflow requirements of anyone — and she'd be a high-leverage second-round interview if this advances. *Activation:* on any pilot framing.

2. **The take-home reviewer.** The literal grader. Sits outside every TTB ring but is **A** on the only outcome the prototype actually produces. Often forgotten because they're framed as "the system reading our submission" rather than as a stakeholder. They are. *Activation:* now.

3. **NTEU (National Treasury Employees Union).** Latent at prototype stage. Activates the moment any framing of this work could be read as "AI replacing agents" — which is exactly the framing the brief itself opens with ("47 agents... back in the 80s they had over 100"). *Activation:* on any production proposal that doesn't lead with augment-not-replace.

**Inward-movement risk** (per the brief's prompt):
- *Marcus moves from Enabler to gatekeeping Core* the moment production is mentioned.
- *NTEU moves from Outsider to Sponsor-adjacent* if anyone in Sarah's chain frames the project as headcount reduction.
- *Industry submitters move from Affected to Sponsor-adjacent* if a state-level industry association files a comment that influences procurement priority.

---

## Q10.9 — Likely emergent stakeholders for production

Building from what the phase-dependent stakeholder priority already anticipates, and from the note that "lawyers, security reviewers, vendor management, the union, and adjacent teams... start surfacing" once a prototype exists.

| Emergent stakeholder | Activation trigger | Likely concern | What they'd ask for |
|---|---|---|---|
| **TTB CIO / OCIO staff** | First procurement conversation | ATO posture; integration with COLA's authorization boundary | System security plan; data flow diagram; vendor risk assessment |
| **Treasury IT compliance** | ATO process | FedRAMP level alignment; PII handling; document retention | FedRAMP authorization or moderate-baseline equivalent |
| **FedRAMP review board** | Any cloud component in production | Standard FedRAMP controls catalog | Authorization package |
| **Section 508 reviewers** | Any user-facing UI deployment | WCAG 2.1 AA compliance; screen-reader pass; keyboard nav | Accessibility conformance report (VPAT) |
| **NTEU** | "AI" framed anywhere near agent FTE numbers | Headcount; job content changes; training | Impact bargaining; written augmentation commitments |
| **Industry trade associations** (DISCUS, Wine Institute, Beer Institute) | Public announcement of any AI-assisted review | Consistency; transparency; appeals | Public documentation of how the tool is used; appeal process |
| **CSPI / consumer-advocacy groups** | Any public framing that could read as easing label scrutiny | Health-warning enforcement | Evidence the tool *raises* warning detection rate, not lowers it |
| **TTB Regulations & Rulings Division** | Any case where the tool's interpretation diverges from current rulings | Rule consistency | A defined process for surfacing AI-disagreements as candidate ruling questions |
| **Field offices beyond Janet's** | Pilot expansion | Workflow variance; local exception handling | Office-by-office configuration; escape hatches |
| **TTB Public Affairs** | First press inquiry | Message control | Approved talking points; named spokesperson |
| **Treasury OIG** | Any incident or audit cycle | Process integrity; audit trail | Logged decisions; reviewer accountability |

**Most underrated of these:** Section 508 and NTEU. Neither is mentioned in the brief; both can singlehandedly delay or kill a production rollout. Section 508 is a **box you check or fail to check**; if the prototype's UI is keyboard-hostile, that's a mark on the architecture even at this stage. NTEU is a **framing problem**, not a technical problem; the moment the project narrative sounds like replacement, the slope steepens fast.

---

## Q10.10 — Stakeholder log template and cadence

Per 05-gaps-and-limitations §3.1: maintain a *stakeholder log* (running provenance) separate from the *matrix snapshot* (point-in-time framework output).

### Log template

```yaml
- entry_id: 2026-09-10-001
  date: 2026-09-10
  channel: interview-transcript
  source: Sarah Chen
  said: "If we can't get results back in about 5 seconds, nobody's going to use it."
  derived_requirement: NFR-1 (5-second SLA per single-label review)
  status: captured
  follow_ups: []
  notes: Anchored by prior vendor pilot disaster.

- entry_id: 2026-09-10-002
  date: 2026-09-10
  channel: interview-transcript
  source: Dave Morrison
  said: "STONE'S THROW vs Stone's Throw — technically a mismatch, obviously the same thing."
  derived_requirement: STRONG-FUNC-005 (fuzzy/judgment-based brand match)
  derived_test_case: tests/fixtures/dave_stones_throw.json
  status: captured
  follow_ups: []
  notes: Canonical adoption-credibility test. Demo must include.

- entry_id: 2026-09-10-003
  date: 2026-09-10
  channel: interview-transcript
  source: Marcus Williams
  said: "For a prototype, just don't do anything crazy."
  derived_decision: Substitutability (production parity in design scope)
  status: captured
  follow_ups:
    - "Surface Marcus's full constraints when production framing arrives."
  notes: Latent gatekeeper. Don't mistake permission-to-proceed for endorsement.

- entry_id: 2026-09-10-004
  date: 2026-09-10
  channel: interview-transcript-mention
  source: Sarah Chen (mentioning Janet)
  said: "Janet from our Seattle office has been asking about this for years."
  derived_requirement: STRONG-FUNC-001 (batch upload)
  status: incomplete-source
  follow_ups:
    - "15-minute conversation with Janet (research topic A-4)."
  notes: Janet not directly interviewed. Surrogate signal only.
```

**Fields per entry, minimum:**
- `entry_id`, `date`, `channel` (interview / hallway / Slack / email / artifact-review)
- `source` (named individual or role)
- `said` (verbatim where possible; paraphrase tagged otherwise)
- `derived_requirement` and/or `derived_decision` (link out to `docs/PRD.md` / `docs/decisions/`)
- `status`: captured | partially-captured | incomplete-source | superseded
- `follow_ups`: list
- `notes`: free text, especially provenance for trade-offs

### Cadence

| Trigger | Action |
|---|---|
| **Phase gate** (kickoff → prototype demo → pilot → production) | Re-run salience + onion. Diff against prior snapshot. Note who moved rings. |
| **New requirement appears mid-stream** | Add a log entry. Tag the source. If the source is a stakeholder not in the current matrix, that's a signal to re-run the matrix. |
| **A previously-quiet stakeholder goes public** (e.g., Marcus engages substantively, Janet is added) | Re-run salience for the affected segment. |
| **Material scope change** (e.g., production framing introduced) | Full re-run. Use the production-stage matrix from Q10.2 as starting point. |
| **Incident or near-miss** | Log entry + immediate review of affected stakeholder's salience. |
| **Quarterly minimum** in any sustained engagement | Even without triggers, re-run. Drift is silent. |

**Maintenance ownership.** PM (or PM-equivalent role) maintains the log. Snapshots are circulated; the log itself is internal.

**Why log + snapshot separately** (from 05-gaps §3.1): the matrix is for current decisions; the log is for *future* trade-off defense — when someone six months from now asks "why didn't we do X?", the log shows who said what when. Without it, the project loses institutional memory exactly when it most needs it.

---

## Cross-topic deferrals

- **X-6 ([T8](./2026-09-15-federal-ux-for-senior-users.md) + [T9](./2026-09-15-verification-targets-research.md) + T10 + [T12](./2026-09-15-decision-communication-visualization.md))** — *"Demo path that hits Sarah, Dave, and Jenny's strongest signals, with appropriate visualization throughout."* This document's output supplies the persona-side input (Q10.4–Q10.6 empathy + JTBD work; Q10.7 #4 demo-audience risk). The actual demo-path synthesis is held for the X-6 conversation.
- Any architectural implication of the "two-tier strictness" (Dave's fuzzy nuance vs. Jenny's exactness) is **already encoded in per-field match policies**. This document confirms the decision; it does not redesign it.

---

## Caveats

- **Empathy maps are inference-heavy by design.** "Thinks" and "Feels" are educated reads on the transcripts, not measurements. Tagged `[INF]`. Validate by showing a draft to Sarah on a follow-up if one happens.
- **The phase-dependent stakeholder priority's percentages** (100/90/80/70) are useful as a tier signal, not as a literal weighting. Don't treat them as if they sum to anything.
- **The take-home reviewer** is treated above as a stakeholder. They are. But we don't know who they are individually, what their priors are, or whether Sarah, Dave, and Jenny are personally on the panel. The persona work is the best proxy we have.
- **Pre-mortem probabilities are subjective `[INF]`.** Klein's method works best when multiple people generate them independently and the consolidated list is the input. With a team of one on a take-home, this is a single-author list — read it as an opening contribution.
- **Salience is not stationary.** The Q10.1 and Q10.2 matrices are bookends. Real projects pass through intermediate states (pilot, scaled pilot, partial production). Re-run at each gate per Q10.10 cadence.