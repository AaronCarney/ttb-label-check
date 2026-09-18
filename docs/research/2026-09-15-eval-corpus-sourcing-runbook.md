# Eval Corpus Sourcing Runbook — Production Target: 250 Labels, Real-First

> **Status: PRODUCTION-TARGET RUNBOOK.** Concrete walkthrough that translates the [T13](./2026-09-15-label-image-sourcing-survey.md) source survey into a ~26–32 hour curator effort yielding the ≥ 250-label corpus (≥ 97 happy-path, ≥ 20 borderline, ≥ 1 case per rule, Krippendorff α ≥ 0.80). The prototype right-sizing to ~50 labels was a calendar-driven scope cut that should not have been needed given that the canonical primary source (TTB Public COLA Registry) is CC0-licensed. This runbook is the path any next iteration follows to discharge that gap.
>
> **Companion docs:** the corpus specification set out below — sourcing mix, mandatory checklist, synthetic realism bar and anti-patterns. [T9](./2026-09-15-verification-targets-research.md) §3 (Registry access mechanics). [T13](./2026-09-15-label-image-sourcing-survey.md) §0 (sourcing ordering), §1.0 (Registry survey), §1.6 (PACER/CourtListener). The real-first sourcing rule. The corpus datasheet this design calls for (self-disclosure).

## §0 Target breakdown

The 250 number comes from the Wald-math sample size for a macro-F1 confidence interval (cited in [T9](./2026-09-15-verification-targets-research.md) §1 sample-size paragraph). Sourcing mix per the real-first sourcing rule (real-first ≥ 70% floor, synthetic ≤ 30% supplement only):

| Slice | Count | % | Source bucket | Provenance prefix |
|---|---|---|---|---|
| Registry positives (clean) | 160 | 64% | TTB Public COLA Registry ([T13](./2026-09-15-label-image-sourcing-survey.md) §1.0) | `cola-{14-char-ttbid}` |
| Litigation negatives | 30 | 12% | PACER / CourtListener exhibits ([T13](./2026-09-15-label-image-sourcing-survey.md) §1.6) | `pacer-{case-id}` or `courtlistener-{docket-id}` |
| **Real subtotal** | **190** | **76%** | — | — |
| Borderline degradation | 50 | 20% | Controlled degradation of Registry images | `synthetic-derived-from-cola-{ttbid}@{script-sha}` |
| Pure synthetic supplement | 10 | 4% | PIL/SVG label-realistic renders, only for per-rule gaps | `synthetic-{slug}@{build-script-sha}` |
| **Synthetic subtotal** | **60** | **24%** | — | — |
| **Total** | **250** | **100%** | — | — |

Real-image floor of 76% beats the real-first sourcing rule's ≥ 70% requirement by 6 points — buffer absorbs Registry-curation rejection (degraded scans, wrong class, applicant typos).

## §1 Class-balance stratification

| Class | % of corpus | Real (Registry+PACER) | Borderline degradation | Pure synthetic supplement | Subtotal |
|---|---|---|---|---|---|
| **Spirits** | 30–40% | 60 (50 Registry + 10 PACER) | 20 | 5 | 85 (34%) |
| **Wine** | 30–40% | 60 (55 Registry + 5 PACER) | 20 | 3 | 83 (33%) |
| **Malt** | 20–30% | 70 (55 Registry + 15 PACER) | 10 | 2 | 82 (33%) |
| **Total** | — | 190 | 50 | 10 | 250 |

Spirits has the deepest rule pack per [S5](./2026-09-15-rule-pack-validator-interface.md); wine and malt are weighted toward their absolute coverage rather than industry-mix proportion.

## §2 Per-source pull plans

### §2.1 TTB Public COLA Registry — target 160 labels (positives + class balance)

**Mechanism (per [T9](./2026-09-15-verification-targets-research.md) §3, [T13](./2026-09-15-label-image-sourcing-survey.md) §1.0).** Search at `https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do`; per-record pull via the URL pattern `viewColaDetails.do?action=publicDisplaySearchBasic&ttbid={14-char-ttbid}`. License: CC0 (data.gov entry `015-TTB-54`). Per-record retrieval is HTML-only; image asset is a CDN-served JPEG/PNG linked from the detail page.

**Curator setup (~30 min, one-time).**
- Verify `robots.txt` posture before bulk pulls ([T9](./2026-09-15-verification-targets-research.md) §3 flagged unverified at research time).
- Set up a CSV scratchpad with columns: `ttbid`, `class`, `brand`, `applicant`, `abv_pct`, `net_contents_ml`, `country_of_origin`, `approval_date`, `image_url`, `download_status`, `expected_disposition`, `notes`.
- Configure rate limit at 1 req / 2 s to stay polite (no published rate limit; conservative default).

#### §2.1.1 Spirits Registry pull — target 50 labels (~3 hours)

Search strategies, listed in priority order:

1. **Class/Type stratification.** Run separate searches for each of: `BOURBON WHISKY`, `RYE WHISKY`, `SCOTCH WHISKY`, `VODKA`, `GIN`, `BRANDY`, `RUM`, `TEQUILA`, `LIQUEUR`. Pull 5–8 entries per class for a stratified spirits sub-corpus. **Yield: ~50 labels in ~2 hours.**
2. **ABV variance.** Within each class, sample across the legal range — 35–50% for whiskey, 80+% for over-proof bottlings, 15% for liqueurs. Hits the ABV tolerance rules and the boundary-case anti-overlap rule.
3. **Net-contents variance.** Sample 200ml, 375ml, 750ml, 1L, 1.75L. Hits the net-contents rules including non-standard fills.
4. **Origin variance.** ≥ 5 US states + ≥ 5 imports. Hits geographic-claim rules.
5. **Brand-name complexity.** Include possessives (e.g., `STONE'S THROW`), alphanumeric (e.g., `1792`), multi-word (e.g., `BLUE RIDGE RESERVE`), and compound (e.g., `HIGH WEST DOUBLE RYE`). Hits BRAND.NAME.* rule family + Stage-A normalization.

**Time estimate.** 50 labels × ~4 min/label (search, screenshot, copy ID, fill metadata) = ~200 min ≈ 3 h.

#### §2.1.2 Wine Registry pull — target 55 labels (~3.5 hours)

1. **Varietal stratification.** `CABERNET SAUVIGNON`, `MERLOT`, `CHARDONNAY`, `PINOT NOIR`, `RIESLING`, `ZINFANDEL`, `SAUVIGNON BLANC`, `CHAMPAGNE`, `PROSECCO`, `PORT`. Pull 5–7 per varietal.
2. **ABV variance.** 7–14% for table wine, 17–22% for fortified.
3. **Sub-class variance.** Still wine, sparkling, fortified, dessert.
4. **Origin variance.** ≥ 5 AVAs (Napa, Sonoma, Willamette, Finger Lakes, Walla Walla) + ≥ 5 EU imports.
5. **Vintage-claim cases** for FR-3xx vintage/age statement rules.

**Time estimate.** 55 × ~4 min = ~220 min ≈ 3.5 h.

#### §2.1.3 Malt Registry pull — target 55 labels (~3.5 hours)

1. **Style stratification.** `LAGER`, `IPA`, `STOUT`, `PORTER`, `WHEAT BEER`, `WHEAT ALE`, `PILSNER`, `PALE ALE`, `BARLEY WINE`. Pull 5–8 per style.
2. **ABV variance.** 4–6% standard, 8–12% craft, 0.5% non-alcoholic, 5–8% malt liquor.
3. **Container variance.** 12 oz, 16 oz, 22 oz, 750 ml, 25.4 oz.
4. **Origin variance.** Domestic + EU + Mexican + Asian imports.

**Time estimate.** 55 × ~4 min = ~220 min ≈ 3.5 h.

#### §2.1.4 Registry yield checkpoint

After §2.1.1–§2.1.3, the curator has 160 Registry labels with metadata. Spot-check 10% (~16 labels) for image quality — reject and replace any below 600 px on the short side or with severe scan artifacts. **Reserve ~30 min for spot-check + replacement.**

### §2.2 PACER / CourtListener — target 30 labels (negatives, brand/geographic rules)

**Mechanism (per [T13](./2026-09-15-label-image-sourcing-survey.md) §1.6).** Lanham Act §43(a) and state UDAP cases attach disputed labels as exhibits. PACER charges ~$0.10/page (capped $3.00/document); CourtListener (Free Law Project) hosts a substantial subset for free.

**Case-line targets (illustrative; verify each at execution time):**

| Rule slice | Case lines | Expected yield |
|---|---|---|
| Brand-name claims (FR-2xx BRAND.NAME.*) | Tito's Handmade Vodka class actions; Anheuser-Busch beer-labeling MDL | ~10 |
| Geographic-origin (geo-claim subset) | Templeton Rye (Iowa vs. Indiana); Kona Brewing (Hawaii vs. mainland); Maker's 46 | ~10 |
| Aged-statement claims | Templeton Rye small-batch / age-statement litigation | ~5 |
| Health/category claims | Malibu, Bacardi geographic-association cases | ~5 |

**Workflow.**
1. Search CourtListener at `courtlistener.com` by case name; pull free exhibits where available.
2. For PACER-only cases, target the complaint document (which usually attaches the label as Exhibit A) rather than the full docket — keeps cost ≤ $50 total for ~20 cases.
3. Each label gets an `expected.json` derived from the complaint's stated allegations: e.g., `expected_disposition: fail`, `expected_per_rule: [{rule_id: "BRAND.GEO.MISLEADING", result: "fail", reason_code: "BRAND.GEO.OUT_OF_STATE"}]`.
4. Save under `fixtures/_corpus/courtlistener-{docket-id}/label.{png,jpg}` or `fixtures/_corpus/pacer-{case-id}/`.

**Time estimate.** 30 labels × ~15 min/label (case lookup, exhibit retrieval, expected-envelope authoring) = ~7.5 hours. **PACER cost: ≤ $50.**

**Class-balance contribution.** This slice runs heavy on spirits and beer per the case-line concentration; ~10 spirits / 5 wine / 15 malt is a defensible split based on the prevailing litigation patterns.

### §2.3 Synthetic-from-Registry borderline degradation — target 50 labels (~6 hours)

**Mechanism.** Take Registry images from §2.1, apply controlled degradation tuned to drop OCR confidence into the medium band (confidence aggregation, `WARNING.LEGIBILITY.*` reason codes). The CC0 lineage is preserved via the provenance prefix.

**Degradation pipeline (`scripts/degrade_label.py`, deterministic, fixed RNG seed).**

| Degradation | Parameter range | Failure mode it elicits |
|---|---|---|
| Gaussian blur | σ = 2.0–4.5 | OCR low-confidence on small text (warning block, ABV) |
| JPEG compression | Q = 20–40 | Blocking artifacts on text edges; degrades font-stroke detection |
| Glare overlay | radial light leak, opacity 0.25–0.45 | Specular-highlight occlusion of warning block |
| Perspective transform | 5°–15° tilt | Camera-angle simulation; tests OCR robustness on non-rectified text |
| Rotation | 2°–8° | Off-axis capture |
| Combination | 2–3 of above | Real-world handheld-photo composition |

**Sub-corpus design.**
- 20 mild blur (σ = 2.0–3.0) — most should still extract; a fraction lands in `needs_review`.
- 15 JPEG-compression — exercises font-stroke-width detection (the warning heading's bold check).
- 10 glare — exercises legibility-gate.
- 5 perspective + rotation — exercises perspective-correction in the vision seam.

**Provenance.** Each degraded label records: source TTB ID, degradation script SHA, RNG seed, parameter values. Provenance string: `synthetic-derived-from-cola-{ttbid}@{script-sha}`.

**Time estimate.** 6 hours: 4 h building/tuning the degradation script, 1 h running it across 50 source images, 1 h spot-checking that the degraded set actually lands in the borderline band (run the eval harness against 5 samples to verify confidence drops into 0.55–0.75 range).

### §2.4 Pure-synthetic supplement — target ≤ 10 labels (~3 hours)

**Trigger condition.** Only if §2.1–§2.3 fail to provide ≥ 1 positive case for any of the MVP rules. Per-rule coverage gap analysis (§3 below) determines the exact need.

**Realism bar (the real-first sourcing rule).**
- Canvas ≥ 600×900 px, paper or cream stock (RGB ≈ #FAF6EE / #F4EFE0).
- Frame: rounded-rect border or printed frame at canvas edge.
- Type hierarchy: brand banner (large, bold, ≥ 36pt), product line (medium, italic or alt-weight, ≈ 22pt), body text (≈ 14pt), Government Warning block (uppercase per `common.warning.heading_caps_bold`, ≈ 11pt).
- Layout: brand top, body middle, warning bottom — same vertical ordering as a real bottle label.
- TTF fonts only (e.g., Liberation Serif/Sans, Open Sans). PIL's `ImageFont.load_default()` bitmap font is **explicitly disallowed** as an anti-pattern.
- Optional: faux-engraving stripe, faux foil seal, desaturated watermark.
- Build script must produce byte-identical output on re-run (deterministic font hinting, fixed RNG seed).

**Time estimate.** 3 hours: 2 h building the realistic-render script (`scripts/build_realistic_synthetic.py`), 1 h producing ≤ 10 supplement entries with per-rule targeting.

### §2.5 Skipped sources (rationale)

| Source | Decision | Rationale |
|---|---|---|
| TTB FOIA ([T13](./2026-09-15-label-image-sourcing-survey.md) §1.1) | Skip; file early in v1 | 6–12 wk processing window; not viable for any prototype-to-pilot timeline. |
| Market Compliance ([T13](./2026-09-15-label-image-sourcing-survey.md) §1.2) | Skip | No image yield. |
| Federal Register ([T13](./2026-09-15-label-image-sourcing-survey.md) §1.3) | Skip; use as rule-pack QA | Text-only adverse-action notices. |
| TTB Industry Circulars ([T13](./2026-09-15-label-image-sourcing-survey.md) §1.4) | Skip; use as rule-pack QA | Text guidance. |
| State ABC ([T13](./2026-09-15-label-image-sourcing-survey.md) §1.5) | Skip | Federal preemption; near-zero image yield. |
| Academic OCR ([T13](./2026-09-15-label-image-sourcing-survey.md) §1.7) | Use only for legibility-gate slice | Out of domain for rule eval. |
| Industry / trade ([T13](./2026-09-15-label-image-sourcing-survey.md) §1.8) | Skip | NDA-bound. |

## §3 Per-rule positive coverage matrix

The corpus specification requires ≥ 1 positive case per MVP rule. The runbook produces this matrix automatically because the Registry pull and PACER curation are already stratified across class × ABV × net-contents × origin. Per-rule mapping (illustrative):

| Rule family | Rule IDs | Source slice that covers |
|---|---|---|
| Government Warning | `common.warning.present`, `.verbatim`, `.heading_phrase`, `.heading_caps_bold`, `.type_size_min`, `.contrasting_bg` | All 160 Registry labels carry a warning; 5 PACER cases challenge formatting. |
| Class / Type | `*.class_type.present`, `*.class_type.matches_application`, `spirits.class_type.matches_soi` | Class stratification in §2.1.1–§2.1.3 hits every class. |
| ABV Tolerance | `*.alcohol.present`, `*.alcohol.format`, `*.alcohol.matches_application`, `*.alcohol.tolerance_band` | ABV variance in §2.1.* + 5–10 borderline degradations targeted at ABV character recognition. |
| Net Contents | `*.net_contents.present`, `*.net_contents.matches_application` | Net-contents variance across all three classes. |
| Brand Name | `*.brand.present`, `*.brand.matches_application` | PACER §2.2 negatives + Registry brand-complexity sub-pull. |
| Geographic Claim | BRAND.GEO.* | PACER §2.2 (Templeton, Kona, Maker's 46). |
| Legibility | the needs-better-photo gate, WARNING.LEGIBILITY.* | Borderline degradations §2.3 (glare, blur, JPEG compression). |
| Confidence Aggregation | the borderline-band confidence rule | Borderline slice as a whole. |

After §2.1–§2.4 pulls, run a coverage-check script that scans the eval manifest against the rule registry and reports any uncovered rule. Pure-synthetic supplement (§2.4) fills the gap; if a rule cannot be covered by either real or synthetic sourcing, it gets explicit "OUT OF SCOPE FOR MVP CORPUS" tagging in the datasheet.

## §4 Sequenced execution plan

**Total curator effort: ~26–32 hours over 5–7 working days.**

| Day | Task | Hours | Deliverable |
|---|---|---|---|
| 1 | Registry setup (§2.1) + spirits pull (§2.1.1) | 0.5 + 3 = 3.5 | 50 spirits images + metadata CSV |
| 2 | Registry wine pull (§2.1.2) | 3.5 | 55 wine images + metadata CSV |
| 3 | Registry malt pull (§2.1.3) + spot-check (§2.1.4) | 3.5 + 0.5 = 4 | 55 malt images + 16-label QA pass |
| 4 | PACER / CourtListener curation (§2.2) | 7.5 | 30 negatives + per-case `expected.json` |
| 5 | Degradation pipeline build + run (§2.3) | 6 | 50 borderline images + script + datasheet entries |
| 6 | Coverage gap analysis (§3) + pure-synthetic supplement (§2.4) | 1 + 3 = 4 | ≤ 10 realistic synthetic images + script |
| 7 | Datasheet authoring + manifest validation + ratio enforcement | 3 | datasheet updated; manifest-schema check passes |
| **Total** | — | **~31.5** | 250 manifest entries with provenance, expected envelopes, and class balance verified |

PACER cost: ≤ $50. Curator cost: 31.5 h × hourly rate. **No software-licensing or API cost.**

## §5 Quality gates (acceptance criteria)

The runbook is complete when **all** of the following hold:

1. **Manifest schema validates** — the manifest-schema check passes against the 250-entry manifest.
2. **Class-balance ratios hold** — spirits 30–40%, wine 30–40%, malt 20–30% (computed at runtime from `class_balance_tag`).
3. **Real-image floor ≥ 70%** — counted as `provenance.source` matching `^cola-` or `^pacer-` or `^courtlistener-` ≥ 175 / 250.
4. **Synthetic share ≤ 30%** — counted as `^synthetic-` ≤ 75 / 250.
5. **Per-rule positive coverage ≥ 1** — every MVP rule in the rule registry has at least one positive entry in `expected_per_rule`.
6. **Borderline-band ≥ 20** — `borderline_band: true` count ≥ 20 (corpus floor).
7. **Happy-path ≥ 97** — `expected_disposition: pass` count ≥ 97 (corpus floor).
8. **Synthetic realism bar enforced** — for every `^synthetic-` row, an automated image-property check (`tests/test_synthetic_realism.py`, to be authored) verifies: ≥ 600×900 px, mean canvas color in paper-stock range (RGB ≈ #FAF6EE ± tolerance), edge-detection finds a frame, font is not the PIL bitmap default. Pure-text-on-white renders fail this gate.
9. **Datasheet self-discloses** — the datasheet records the actual sourcing breakdown, any gaps, and a reproducibility statement.
10. **Provenance is reproducible** — every `^synthetic-*@{sha}` entry can be re-derived from the build script at the cited SHA; deterministic check.

## §6 Reproducibility guarantees

- Every Registry image carries its TTB ID; the curator's CSV and the manifest's `provenance.source` agree.
- Every PACER/CourtListener exhibit is cited to its docket; the curator's CSV records the case caption, court, year, and document number.
- Every synthetic asset (degradation or pure) cites the build script's git SHA and the input parameters; re-running from that SHA produces byte-identical PNGs.
- The runbook itself is versioned; PRs that materially change the per-source counts, time estimates, or quality gates must update this doc.

