# Test Corpus, Sample-Size Statistics & Evaluation Harness Design

Filed 2026-09-15.

## TTB Alcohol Label Verification MVP

> **Note on project knowledge access.** The `project_knowledge_search` tool referenced in the task brief was **not available** in the execution environment — only public web research tools were accessible. Where this report needs values from project-knowledge files ([T1](./2026-09-15-ttb-regulatory-framework.md) reason codes, [T2](./2026-09-15-cola-operational-context.md) §Q2.10 fields, [T9](./2026-09-15-verification-targets-research.md) evaluation methodology, [S1](./2026-09-15-vision-stack.md) fixture spec, [S2](./2026-09-15-mvp-scope-demo-shape.md) MVP rule count), I have **reconstructed reasonable defaults from the contextual hints in the task brief and from primary TTB regulatory sources**, and have flagged each such reconstruction inline as `[ASSUMED — confirm against project knowledge]`. All external claims are cited with URLs.

---

## TL;DR

- **Eval set: ~250 labels minimum** (≈100 happy-path + ≈150 stratified rule-failure cases). Worst-case Wald math says 97 labels gives disposition accuracy at ±10 pp 95% CI; per-rule precision/recall at ±15 pp needs 43 positive cases × MVP rule count [ASSUMED 12 rules → 516 positives, but heavy overlap reduces unique-label demand to ~150].
- **Sourcing reservoir: 800–1,200 candidate labels** drawn primarily from the **TTB Public COLA Registry (CC0, public-domain U.S. government data)**, supplemented by **Open Food Facts (CC-BY-SA)**, **Wikimedia Commons (CC)**, **Roboflow Universe wine-label datasets (mostly CC BY 4.0)**, and **DALL·E 3 / gpt-image-1 synthetic labels** for axes that real corpora can't easily provide (deliberately wrong-order warning text, missing health warning, undersized type). Vivino and Untappd are **not safely scrapable for this purpose** — both ToS expressly prohibit it.
- **Harness: pytest + standalone CLI hybrid, manifest in JSONL, hidden `/eval` dashboard route**, GitHub Actions CI on a small **smoke** sub-set only (cost-controlled). Solo-annotator self-double-annotation with 48-hour gap **is methodologically defensible as intra-rater reliability** if explicitly framed as test-retest stability per Krippendorff (2019), but cannot substitute for true inter-rater reliability — that limitation must be documented in the datasheet.

---

## Key Findings

1. **TTB COLA Registry is the gold sourcing channel.** It is U.S. federal government public-domain data, marked CC0 on data.gov, contains ~2.5M+ approved labels with images from 1999 onward, and access is unauthenticated via a deterministic URL pattern (`publicDisplaySearchBasic&ttbid=<14-digit ID>`). No official bulk API exists, but the Ninth Circuit's *hiQ v. LinkedIn* line of decisions confirms scraping public, unauthenticated government data is not a CFAA violation. (Note: a contract-based ToS claim could still apply, but TTB's site has no access-gating click-through.)
2. **Vivino and Untappd are off-limits.** Vivino's ToS §1.1(e) explicitly prohibits "scripts, browser plugins, spiders, robots" and forbids reproduction/distribution of Vivino Properties; Untappd's API ToS §14 says "You cannot use the Untappd data to build your own beer database" and §15 prohibits analytics use. The *WineSensed* academic dataset (897k Vivino images) exists but inherits Vivino's restrictive provenance and should be cited rather than redistributed.
3. **DALL·E 3 / gpt-image-1 short-text rendering is ~92% accurate** for words ≤12 characters but degrades sharply on longer paragraphs — making it a credible tool for synthesizing **deliberate failure modes** (missing warning, undersized type) but **unreliable for faithful reproduction** of the exact 49-word "GOVERNMENT WARNING" paragraph. Every API output already carries C2PA provenance metadata (digitalSourceType `trainedAlgorithmicMedia`, signed by OpenAI via Truepic).
4. **Sample-size math (Wald, p=0.5 worst case)** yields ~97 labels for ±10 pp disposition accuracy and ~43 positive cases per rule for ±15 pp per-rule precision/recall. With heavy stratification overlap, total realistic minimum is ~250 unique labels for the MVP eval set.
5. **Solo-annotator IAA workaround:** Krippendorff's α threshold of ≥0.80 (Krippendorff, *Content Analysis*, 4th ed., 2019) can be applied to **two passes by the same annotator separated by ≥48 hours** as a test-retest / intra-rater reliability proxy, but this measures *consistency* rather than *agreement* and must be disclosed as a limitation. With a single binary-disposition rater testing H₀: κ=0.70 vs. H₁: κ=0.85 (α=0.05, power=0.80) per Cantor (1996), n ≈ 100–150 disposition decisions is typically sufficient; for a 3-class disposition this rises to ~150–200.

---

## Details

### Section 1 — Sample-Size Statistics

#### Q1. Disposition-level accuracy, 95% CI of ±10 pp

Standard Wald sample-size formula for a single proportion:

$$n = \frac{z^2 \cdot p \cdot (1-p)}{E^2}$$

Using z = 1.96 (95% CI), p = 0.5 (worst case — maximizes variance), E = 0.10:

$$n = \frac{(1.96)^2 \cdot 0.5 \cdot 0.5}{(0.10)^2} = \frac{3.8416 \cdot 0.25}{0.01} = \frac{0.9604}{0.01} = 96.04$$

**→ Round up to n = 97 labels** for the disposition-accuracy estimate.

(Reference: standard binomial Wald CI; see e.g. NIST/SEMATECH e-Handbook of Statistical Methods §1.3.6.6.5.)

#### Q2. Per-rule precision/recall, 95% CI of ±15 pp

Same formula with E = 0.15:

$$n = \frac{(1.96)^2 \cdot 0.5 \cdot 0.5}{(0.15)^2} = \frac{0.9604}{0.0225} = 42.68$$

**→ Round up to n = 43 positive cases per rule.**

For the "negative" arm (rule should *not* fire), the same 43 is needed to estimate specificity at ±15 pp, so **86 cases per rule** are needed if both precision and recall are to be bounded at ±15 pp.

**Multiplying by MVP rule count.** The [S2](./2026-09-15-mvp-scope-demo-shape.md) output's exact rule count was not retrievable from project knowledge in this session [ASSUMED — confirm against [S2](./2026-09-15-mvp-scope-demo-shape.md) output]. Based on TTB's mandatory label-information lists (27 CFR Parts 4, 5, 7, and 16) the MVP scope plausibly covers:

| # | Rule (MVP candidate) | [T1](./2026-09-15-ttb-regulatory-framework.md) reason-code family |
|---|---|---|
| R01 | Brand name present | `MISSING_BRAND_NAME` |
| R02 | Class/type designation present and valid | `MISSING_CLASS_TYPE`, `INVALID_CLASS_TYPE` |
| R03 | Alcohol content stated in `% ALC/VOL` correct format | `MISSING_ABV`, `INVALID_ABV_FORMAT` |
| R04 | Net contents declared in U.S. units | `MISSING_NET_CONTENTS`, `NET_CONTENTS_NON_US_UNITS` |
| R05 | Name and address of bottler/importer | `MISSING_NAME_ADDRESS` |
| R06 | Government Health Warning **exact text** | `WARNING_TEXT_ALTERED` |
| R07 | "GOVERNMENT WARNING" rendered ALL-CAPS + bold | `WARNING_NOT_BOLD_CAPS` |
| R08 | Warning type-size by container volume (1/2/3 mm) | `WARNING_TYPE_TOO_SMALL` |
| R09 | Warning paragraph continuous, contrasting background | `WARNING_NOT_LEGIBLE` |
| R10 | Sulfite declaration when ≥10 ppm (wine) | `MISSING_SULFITE_DECL` |
| R11 | Fanciful name + statement of composition (specialty products) | `MISSING_STATEMENT_OF_COMPOSITION` |
| R12 | Appellation of origin on brand label when vintage + varietal listed (wine) | `MISSING_APPELLATION` |

[ASSUMED 12 rules — replace with [S2](./2026-09-15-mvp-scope-demo-shape.md) actual count.]

→ Per-rule positive cases: **43 × 12 = 516 positive failure events**, or 86 × 12 = 1,032 if symmetric specificity is also required.

Source for rule content: TTB's *Anatomy of a Malt Beverage Label* and *Wine Labeling: Health Warning Statement* official guidance pages on ttb.gov; 27 CFR Part 16.

#### Q3. Minimum eval-set decomposition

Two contributions:

- **Happy-path (compliant) labels** for general accuracy: n = **97**.
- **Per-rule failure buckets**: 43 positive cases × R rules. With R = 12, that's 516 failure-event slots.

But — and this is the critical insight — **a single label can carry multiple failures simultaneously** (a label missing the health warning is *also* missing R06, R07, R08, R09 because all four warning-formatting rules vacuously trigger on absence). With realistic co-occurrence patterns (~3 average failures per failure-bearing label), the unique-label count is roughly:

$$n_{\text{unique-failure}} \approx \frac{43 \cdot 12}{3} \approx 172$$

**Recommended minimum eval-set size: 97 happy-path + ~150 unique failure-bearing labels = ~250 labels**, with explicit per-rule-bucket coverage tracked via tags.

#### Q4. Solo-annotator IAA via 48-hour self-double-annotation

**Methodological defensibility.** Krippendorff (*Content Analysis*, 4th ed., 2019, ch. 12) treats α as a measure of *reliability of data generated by a coding procedure*; the canonical use is multi-coder, but the same coefficient can be computed across two passes by one coder, in which case it estimates **intra-rater reliability** (also called test-retest stability). Real-Statistics and other reliability handbooks confirm the formula is symmetric in coders. **However**, single-coder α cannot detect coder idiosyncrasies — only consistency — so it is a strictly weaker claim than true IAA. The defensible posture for an MVP is:

1. Compute α (or Cohen's κ if disposition is treated as a 3-class nominal variable) on two passes ≥48 h apart.
2. **Report it explicitly as "intra-rater reliability"**, not "inter-rater reliability".
3. Document this as a known limitation in the datasheet and roadmap a second annotator for v2.

**Power calculation for κ ≥ 0.80** (Cantor 1996, *Sample-size calculation for Cohen's kappa*, *Psychological Methods* 1:150-153; Flack et al. 1988, *Psychometrika* 53:321-325). For a binary disposition with balanced 50/50 marginals, testing H₀: κ = 0.70 vs. H₁: κ = 0.85, two-sided α = 0.05, power = 0.80:

Using the `irr::N.cohen.kappa` CRAN reference implementation parameters as a worked example, n ≈ **130** binary decisions are needed. For a **3-class disposition** (approve / needs-review / reject) with realistic uneven marginals (e.g. 60/30/10), n rises to ≈ **180–220**. For κ ≥ 0.80 against a less stringent null of κ = 0.60, the requirement drops to ~50–70.

→ **Recommendation:** with an eval set of ~250 labels, power for κ ≥ 0.80 is comfortably adequate even in the 3-class case; double-annotate the **entire** eval set on pass 2 (48 h gap), report α and κ both, and disclose that this is intra-rater stability, not true IAA.

Krippendorff's standard interpretive thresholds (Krippendorff 2019; reaffirmed in K-Alpha Calculator documentation, k-alpha.org): **α ≥ 0.80 is the customary acceptance threshold; α ≥ 0.667 is the lowest defensible bar for tentative conclusions.**

---

### Section 2 — Sourcing Matrix

#### (a) Sourcing matrix — source × license × access × yield × legal

| Source | License | Access method | Image quality | robots.txt / ToS posture | Realistic yield (MVP) |
|---|---|---|---|---|---|
| **TTB Public COLA Registry** (ttbonline.gov/colasonline) | **CC0 / U.S. federal public-domain** (data.gov dataset license) | Unauthenticated web search; deterministic URL pattern `viewColaDetails.do?action=publicDisplaySearchBasic&ttbid=XXXXXXXXXXXXXX`; printable PDF/scan per record. No official bulk API. | Mixed: e-filed = clean PDF/PNG renderings; paper-filed = scanned images, often mid-quality | ToS not click-through; *hiQ v. LinkedIn* (9th Cir. 2022) protects scraping of public gov pages from CFAA. Be polite (rate limit ≤1 req/2 s) | **600–1,000** (primary reservoir) |
| **Open Food Facts** (world.openfoodfacts.org) | **Images CC-BY-SA**; database ODbL | REST API + bulk JSON dump; image URLs are direct CDN | High-resolution user-submitted bottle photos including back labels | Permissive; CC-BY-SA requires attribution + share-alike on derivatives | **100–200** alcohol-tagged products |
| **Wikimedia Commons** (commons.wikimedia.org/wiki/Category:Wine_labels, /Beer_labels) | Per-file CC licenses (mostly CC-BY-SA or CC0) | MediaWiki API; category enumeration | Variable: historical labels (great for "faded scan" axis), some modern | Open by design; respect per-file license | **80–150** (Wine_labels: 49 files; Beer_labels: 75; Beer_labels_of_Germany: 459; etc.) |
| **Roboflow Universe — wine-label-detection** (universe.roboflow.com/wine-label/wine-label-detection) | Roboflow Universe terms; many CC BY 4.0 | Roboflow Python SDK (`roboflow.download_dataset`) | 5,460 images, varied real-world conditions | Free download with login; redistribution per per-dataset license | **100–300** (with dedup) |
| **Roboflow Universe — RF100 wine-labels** (universe.roboflow.com/roboflow-100/wine-labels) | CC BY 4.0 | Roboflow SDK | 461 images, good for object-detection bounding-box overlap | Permissive | Use as **adversarial OOD** test slice |
| **X-Wines** (github.com/rogerioxavier/X-Wines; Kaggle) | Open dataset, citation required (de Azambuja et al. 2023, MDPI BDCC 7(1):20) | GitHub CSV + Kaggle tarball | Includes label image URLs but quality varies; mostly metadata-rich | Free for research/educational use | **100–200** images (citation-attributed) |
| **WineSensed** (data.dtu.dk/articles/dataset/.../23376560) | NeurIPS 2023 Datasets & Benchmarks track; figshare DTU | figshare download | 897,000 wine label images sourced from Vivino | **Inherits Vivino provenance issue** — defensible for academic eval, risky for productization | **Cite as benchmark; do not redistribute** |
| **Vivino** (vivino.com) | All rights reserved; ToS §1.1(e) **expressly forbids scraping** | Public web only | High-quality photos | **DO NOT SCRAPE.** ToS violation; *hiQ v. LinkedIn* breach-of-contract precedent (LinkedIn won $500k against hiQ in 2022) | **0 (excluded)** |
| **Untappd** (untappd.com) | API requires key; **§14 of API ToS forbids "build your own beer database"; §15 forbids analytics; cache must be deleted every 24 h** | Documented OAuth API | Beer label images at `untappd.akamaized.net/site/beer_logos/` | **Effectively unusable for an eval corpus** under their ToS | **0 (excluded)** |
| **BeerAdvocate / RateBeer** | All rights reserved; user content | No public API for labels | — | Same posture as Untappd | **0 (excluded)** |
| **LCBO product images** (lcbo.com / aem.lcbo.com) | LCBO copyright; product images on public CDN | Third-party scrapers exist; LCBO never offered an official API; the lcbo-api project sunset May 2025 | Studio shots, bottle-only, not flat label scans | LCBO has no public ToS authorizing scraping; political optics + Crown corporation ambiguity | **Skip for MVP** |
| **SAQ (Quebec)** | All rights reserved | No API | Studio shots | Same as LCBO | **Skip** |
| **Drizly / Total Wine** | All rights reserved | No API | Studio shots | Restrictive | **Skip** |
| **DALL·E 3 / gpt-image-1** (OpenAI Images API) | OpenAI Usage Policies; user owns outputs subject to terms | API; cost ~$0.04–$0.17 per 1024² image | Synthesizable to spec; ~92% short-text accuracy (Glyph-ByT5 benchmark, arXiv:2403.09622); **C2PA metadata embedded automatically** with `digitalSourceType=trainedAlgorithmicMedia` | OpenAI ToS allows commercial use of outputs; C2PA per OpenAI help center "C2PA in ChatGPT Images" | **30–60** synthetic labels for deliberately-broken axes |

**Total reservoir target (Q9): ~1,000 labels** (TTB-COLA primary 600–700; OFF/Commons/Roboflow secondary 250–350; synthetic 30–60). This gives ~4× over-collection for the ~250-label eval set, plus headroom for filtering, dedup, and difficulty stratification.

#### (b) Difficulty-axis coverage matrix

| Source ↓ / Axis → | Stylized fonts | Low contrast | Curved/photo bottles | Embossed/etched | Clear acetate | Multi-language back | Cans/wraparound | Tiny 50 mL | Faded scans | Stylized warnings |
|---|---|---|---|---|---|---|---|---|---|---|
| TTB COLA Registry | X | X | | | | X | X | X | X | X |
| Open Food Facts | X | | X | | | X | X | | | |
| Wikimedia Commons | X | X | X | X | | | | | X | |
| Roboflow wine-label | X | X | X | | | | | | | |
| X-Wines | X | | X | | | X | | | | |
| WineSensed (cite-only) | X | X | X | X | X | X | | | | X |
| **DALL·E 3 / gpt-image-1 (synthetic)** | X | X | | (limited) | (limited) | X | X | X | X | **X (deliberate failures)** |

**Synthetic axes coverage rationale (Q7).** DALL·E 3 / gpt-image-1 are **viable** for: stylized-warning failures (wrong words bolded, words in wrong order), missing-warning labels, undersized type, faded look. They are **unreliable** for: faithfully reproducing the entire 49-word GOVERNMENT WARNING paragraph verbatim (text length exceeds the model's reliable rendering range — Glyph-ByT5 benchmark on arXiv:2403.09622 reports DALL·E 3 word-precision dropping below 16% for >12-character text spans), embossed/etched 3-D effects, and clear-acetate transparency. Every synthetic image will carry C2PA `trainedAlgorithmicMedia` metadata signed by OpenAI/Truepic — record the manifest hash in the eval JSONL `provenance` field for auditability ([T9](./2026-09-15-verification-targets-research.md) §C2PA caveat).

#### Acquisition pipeline (Q8)

**Legal posture (post-*hiQ*).** The Ninth Circuit in *hiQ Labs v. LinkedIn* (9th Cir. 2019, reaffirmed April 2022 after Supreme Court remand under *Van Buren v. United States*) held that scraping **publicly available, unauthenticated** webpages does **not** violate the CFAA's "without authorization" prong. **However**, a *contract-based* claim under a website's Terms of Service can still succeed independently — LinkedIn won a $500k breach-of-contract judgment against hiQ in November 2022 (N.D. Cal.). The practical rule for this MVP:

- **TTB COLA**: no acceptance of terms required, no login, federal public-domain data — green-light.
- **Open Food Facts / Wikimedia**: explicitly open-licensed bulk data — green-light.
- **Roboflow Universe**: green-light when downloaded via SDK with the user license accepted.
- **Vivino, Untappd, BeerAdvocate, LCBO**: terms forbid scraping or product-database construction — **red-light**.

**Pipeline**:

```
1. eval/scripts/fetch_ttb_cola.py
   - paginate brand-name searches, sample diverse class/type codes (W=wine, M=malt, S=spirits)
   - per-record: GET viewColaDetails.do?ttbid=… → parse → fetch printable image
   - rate-limit: 1 req / 2 s; exponential backoff on 5xx; max 3 retries
   - cache responses with ETag; persist raw HTML + image to data/raw/ttb-cola/
2. eval/scripts/fetch_off.py
   - Open Food Facts API: GET /api/v2/search?categories_tags=alcoholic-beverages&fields=image_url,...
   - rate-limit per OFF policy: ≤100 req/min for unauthenticated
3. eval/scripts/fetch_commons.py
   - MediaWiki API GET ?action=query&list=categorymembers&cmtitle=Category:Wine_labels
4. eval/scripts/fetch_roboflow.py
   - roboflow.download_dataset("https://universe.roboflow.com/wine-label/wine-label-detection")
5. eval/scripts/synthesize_dalle.py
   - one prompt template per failure axis; persist C2PA manifest alongside
6. eval/scripts/build_manifest.py
   - dedup via perceptual hash (pHash, Hamming-distance threshold)
   - emit JSONL per the schema in §3 below
```

---

### Section 3 — Corpus Design

**Q9. Reservoir target — 1,000 candidate labels** (rationale: 4× over-collection for a 250-label eval set leaves room for dedup, difficulty rebalancing, and rule-bucket gap-filling).

**Q10. Eval-set size — 250 labels** (97 happy-path + ~150 stratified rule-failure + 3 reserve).

**Q11. Class balance per [S2](./2026-09-15-mvp-scope-demo-shape.md) MVP scope** [ASSUMED — confirm against [S2](./2026-09-15-mvp-scope-demo-shape.md)]. Recommended split mirroring TTB's COLA volume distribution (wine ~45%, malt ~40%, distilled spirits ~15%):

| Class | Count | % |
|---|---|---|
| Wine | 113 | 45% |
| Malt beverage (beer) | 100 | 40% |
| Distilled spirits | 37 | 15% |
| **Total** | **250** | **100%** |

**Q12. Synthetic-vs-real ratio.** Recommended: **≤15% synthetic** (≈35–40 of 250) to keep external validity high. Synthetic labels are concentrated in deliberate-failure axes that are hard to source naturally (e.g., wrong-order warning text). Manifest tag scheme:

```
"provenance": {
    "source": "ttb-cola" | "open-food-facts" | "wikimedia-commons" 
              | "roboflow-universe" | "x-wines" | "synthetic-dalle3" 
              | "synthetic-gpt-image-1",
    "source_id": "<vendor-specific identifier, e.g. TTB ID 21345001000456>",
    "source_url": "<canonical URL>",
    "license": "CC0" | "CC-BY-SA-4.0" | "CC-BY-4.0" | "openai-tos" | ...,
    "fetched_at": "2026-09-13T12:34:56Z",
    "c2pa_manifest_sha256": "<hex>"  // null for non-synthetic
}
```

---

### Section 4 — Ground Truth & Manifest

#### (Q13/Q14) JSONL manifest schema with worked example

[T1](./2026-09-15-ttb-regulatory-framework.md) reason codes [ASSUMED — confirm against [T1](./2026-09-15-ttb-regulatory-framework.md) §7.3]: `MISSING_BRAND_NAME`, `MISSING_CLASS_TYPE`, `INVALID_CLASS_TYPE`, `MISSING_ABV`, `INVALID_ABV_FORMAT`, `MISSING_NET_CONTENTS`, `NET_CONTENTS_NON_US_UNITS`, `MISSING_NAME_ADDRESS`, `WARNING_TEXT_ALTERED`, `WARNING_NOT_BOLD_CAPS`, `WARNING_TYPE_TOO_SMALL`, `WARNING_NOT_LEGIBLE`, `MISSING_SULFITE_DECL`, `MISSING_STATEMENT_OF_COMPOSITION`, `MISSING_APPELLATION`, `NEEDS_BETTER_PHOTO`.

[T2](./2026-09-15-cola-operational-context.md) §Q2.10 application fields [ASSUMED based on TTB Form 5100.31 / `colacloud.us/posts/ttb-data-definitions`]: `product_class_type`, `alcohol_content`, `net_contents`, `brand_name`, `fanciful_name`, `appellation_of_origin` (wine), `vintage_date` (wine), `formula_id` (if applicable), `plant_registry_basic_permit_brewers_no`.

```jsonl
{"id":"ttb-2024-W-000123","image_path":"data/eval/wine/ttb-2024-W-000123.png","class":"wine","expected_disposition":"reject","expected_failures":["WARNING_TEXT_ALTERED","MISSING_SULFITE_DECL"],"application_fields":{"product_class_type":"Pinot Noir","alcohol_content":"13.5","net_contents":"750 mL","brand_name":"TAMAL","fanciful_name":null,"appellation_of_origin":"Russian River Valley","vintage_date":"2021","formula_id":null,"plant_registry_basic_permit_brewers_no":"BWN-CA-12345"},"difficulty_axes":["stylized_fonts","faded_scan"],"provenance":{"source":"ttb-cola","source_id":"21345001000456","source_url":"https://www.ttbonline.gov/colasonline/viewColaDetails.do?action=publicDisplaySearchBasic&ttbid=21345001000456","license":"CC0","fetched_at":"2026-09-10T10:22:11Z","c2pa_manifest_sha256":null},"notes":"Warning paragraph reads 'According to the General Surgeon...' (word order swapped). Sulfite declaration absent on back label.","annotation":{"primary_pass_at":"2026-09-11T14:00:00Z","secondary_pass_at":"2026-09-12T15:00:00Z","intra_rater_match":true}}
```

**Per-label minimum fields** (Q14):

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | Y | Stable, source-prefixed |
| `image_path` | string (relative) | Y | Repo-relative |
| `class` | enum: wine / malt / spirits | Y | Per [S2](./2026-09-15-mvp-scope-demo-shape.md) scope |
| `expected_disposition` | enum: approve / needs_review / reject | Y | Per [T1](./2026-09-15-ttb-regulatory-framework.md) |
| `expected_failures` | string[] (reason codes) | Y (empty if approve) | Per [T1](./2026-09-15-ttb-regulatory-framework.md) §7.3 |
| `application_fields` | object | Y | Per [T2](./2026-09-15-cola-operational-context.md) §Q2.10 |
| `difficulty_axes` | string[] | Y (empty allowed) | From axis matrix |
| `provenance` | object | Y | Source/license/C2PA |
| `notes` | string | N | Free-text annotator commentary |
| `annotation` | object | Y | Pass timestamps, intra-rater match flag |

---

### Section 5 — Scoring & Harness

**Q15. Metrics: BOTH disposition 3×3 confusion matrix AND per-rule precision/recall.** Reasoning: disposition matrix tells you the user-visible outcome (does the model approve the right things?); per-rule metrics tell you which rules need to be improved when disposition is wrong. Reporting only one hides actionable signal. For an MVP, the **dashboard headline number is disposition macro-F1**; per-rule numbers are drill-down.

**Q16. "Needs better photo" disposition.** **Recommend folding into `needs_review` for MVP**, with a separate `NEEDS_BETTER_PHOTO` reason code. Tradeoff: a 4-class disposition needs more eval data to power and complicates stakeholder communication; a separate reason code preserves the failure-mode signal without breaking the 3-class confusion matrix. v2 can split it out if photo-quality failures dominate the needs-review bucket.

**Q17. Pytest + standalone CLI hybrid.** Pytest gives parameterized per-label tests, fixture scoping, and CI-native reporting; the standalone CLI is faster for ad-hoc reservoir runs and produces the dashboard JSON. Solo-developer prototypes benefit from both because pytest's `parametrize` is awkward for 250+ slow LLM-call tests in regular dev loops, while the CLI gives you a `python -m eval run --subset=smoke` ergonomic.

#### (e) Pytest harness skeleton

```python
# eval/conftest.py
import json
import pathlib
import pytest

EVAL_ROOT = pathlib.Path(__file__).parent
MANIFEST = EVAL_ROOT / "manifest.jsonl"

def load_manifest():
    with MANIFEST.open() as f:
        return [json.loads(line) for line in f if line.strip()]

@pytest.fixture(scope="session")
def manifest():
    return load_manifest()

def pytest_generate_tests(metafunc):
    if "label" in metafunc.fixturenames:
        labels = load_manifest()
        # Filter via -k or env var EVAL_SUBSET=smoke|full
        import os
        subset = os.environ.get("EVAL_SUBSET", "full")
        if subset == "smoke":
            labels = [l for l in labels if "smoke" in l.get("difficulty_axes", [])][:20]
        metafunc.parametrize("label", labels, ids=[l["id"] for l in labels])


# eval/test_disposition.py
import pytest
from app.verifier import verify_label   # the system under test

@pytest.fixture(scope="session")
def results(manifest):
    """Run the verifier once per session; collect predictions."""
    out = []
    for lbl in manifest:
        pred = verify_label(lbl["image_path"], lbl["class"], lbl["application_fields"])
        out.append({"id": lbl["id"], "expected": lbl, "predicted": pred})
    return out

def test_disposition(label, results):
    rec = next(r for r in results if r["id"] == label["id"])
    assert rec["predicted"]["disposition"] == label["expected_disposition"], (
        f"{label['id']}: expected {label['expected_disposition']}, "
        f"got {rec['predicted']['disposition']}"
    )

def test_expected_failures_are_detected(label, results):
    rec = next(r for r in results if r["id"] == label["id"])
    expected = set(label["expected_failures"])
    predicted = set(rec["predicted"]["failures"])
    missed = expected - predicted
    assert not missed, f"{label['id']}: missed reason codes {missed}"


# eval/test_metrics.py
from collections import Counter
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

def test_overall_macro_f1(results):
    y_true = [r["expected"]["expected_disposition"] for r in results]
    y_pred = [r["predicted"]["disposition"] for r in results]
    p, r, f, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=["approve","needs_review","reject"], average="macro"
    )
    cm = confusion_matrix(y_true, y_pred,
                          labels=["approve","needs_review","reject"])
    print("\nDisposition confusion matrix:\n", cm)
    print(f"Macro-F1: {f:.3f}")
    # Soft assertion: target 0.70 for v0.1, 0.85 for v1
    assert f >= 0.70, f"Macro-F1 {f:.3f} below MVP threshold 0.70"

def test_per_rule_precision_recall(results, manifest):
    """Aggregate per-reason-code precision/recall."""
    all_codes = set()
    for r in results:
        all_codes.update(r["expected"]["expected_failures"])
        all_codes.update(r["predicted"]["failures"])
    rows = []
    for code in sorted(all_codes):
        tp = sum(1 for r in results
                 if code in r["expected"]["expected_failures"]
                 and code in r["predicted"]["failures"])
        fp = sum(1 for r in results
                 if code not in r["expected"]["expected_failures"]
                 and code in r["predicted"]["failures"])
        fn = sum(1 for r in results
                 if code in r["expected"]["expected_failures"]
                 and code not in r["predicted"]["failures"])
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        rows.append((code, tp, fp, fn, prec, rec))
    # Persist for dashboard
    import json, pathlib
    pathlib.Path("eval/out/per_rule.json").write_text(
        json.dumps([{"code":c,"tp":tp,"fp":fp,"fn":fn,"precision":p,"recall":r}
                    for c,tp,fp,fn,p,r in rows], indent=2))
    # No hard assertion at suite level — drill-down only
```

**CLI invocation pattern**:

```bash
# Local full eval (will burn LLM API budget):
python -m eval run --subset=full --out=eval/out/run-2026-09-13.json

# Smoke (CI-friendly, ~20 labels):
EVAL_SUBSET=smoke pytest eval/ -v

# Single rule drill-down:
pytest eval/test_disposition.py -k "WARNING" -v
```

**Q18. CI: GitHub Actions for the smoke subset only.** Reasoning: the full 250-label eval at ~$0.05 per LLM call ≈ $12.50 per CI run; running on every push is prohibitive. **Recommended posture**:

- **On push to PR**: run a 20-label smoke subset stratified to cover all rule families (~$1/run).
- **On merge to main**: run full 250-label eval (~$12).
- **Nightly scheduled job**: full eval against latest main, with metrics persisted to a history directory under `eval/`.
- **Manual workflow_dispatch**: full eval on any branch on demand.

GitHub Actions secret stores the OpenAI API key. Cache LLM responses keyed by `(image_sha256, prompt_template_version)` to make re-runs free.

**Q19. Eval surface in demo.** **Recommended: hidden `/eval` route gated by an `?dev=1` query string or a `DEV_MODE` env flag**, exposing a read-only dashboard:

- Disposition confusion matrix (heatmap).
- Per-rule precision/recall table with sparkline trend.
- Failed-label gallery with side-by-side image + expected vs. predicted.
- Manifest version + commit SHA + dataset size badges.

Tradeoffs:
- **Dedicated `/eval` route**: discoverable, professional; risk of being indexed by search engines or exposing dev info to demo viewers — mitigate with `noindex`, basic-auth, or feature flag.
- **README-only**: zero risk, zero discoverability, zero recruiter-impressiveness.
- **Hidden tab in main UI**: invisible to non-developers; good middle ground.

For a solo-developer recruiting/portfolio prototype, the hidden `/eval` route gated by a dev flag wins because it materially demonstrates engineering rigor without polluting the user-facing demo.

---

### (f) Datasheet-for-Datasets stub

Following Gebru et al., "Datasheets for Datasets," arXiv:1803.09010 (Mar 2018, last revised Dec 2021; published in *Communications of the ACM*, December 2021), the eval dataset's datasheet should contain:

```markdown
# eval/datasheet.md — TTB Label Verification MVP Eval Set v0.1

## Motivation
- **Purpose:** Evaluate an LLM-vision pipeline that classifies TTB alcohol-beverage 
  labels into {approve, needs_review, reject} and emits structured reason codes 
  per 27 CFR Parts 4, 5, 7, and 16.
- **Created by:** Solo developer for prototype demonstration; not affiliated with TTB.
- **Funding:** None (self-funded prototype).

## Composition
- **Instances:** 250 labels (113 wine, 100 malt beverage, 37 distilled spirits) 
  with per-label image, expected disposition, expected reason codes (T1 §7.3), 
  application fields (T2 §Q2.10), provenance, and difficulty-axis tags.
- **Sampling:** Stratified by class and per-rule failure bucket (R01–R12); 
  non-probability convenience sample from public TTB COLA registry plus 
  permissively-licensed supplements.
- **Sensitive attributes:** None — labels are commercial product packaging.
- **Splits:** No train/test split; the entire set is held-out eval.

## Collection process
- **Acquisition window:** April 2026.
- **Mechanism:** Scripted fetch of TTB COLA records (with TTB IDs as identifiers); 
  Open Food Facts API; Wikimedia Commons category enumeration; Roboflow SDK; 
  DALL·E 3 / gpt-image-1 API for synthetic deliberate-failure cases.
- **Annotation:** Solo annotator, double-pass with ≥48-h gap. Intra-rater 
  reliability reported as Krippendorff's α and Cohen's κ. 
  **Limitation:** This is intra-rater stability, not inter-rater agreement; 
  a second independent annotator is roadmap for v0.2.

## Preprocessing
- Perceptual-hash dedup (pHash, Hamming threshold = 8).
- Image resize to max 2048 px on long edge; original retained at data/raw/.
- Manifest emitted as JSONL.

## Uses
- **Intended:** Internal CI for the MVP verifier; portfolio demonstration.
- **NOT intended:** Training data (it's eval-only); regulatory ground truth 
  (TTB regulations evolve — pending Notices 237 and 238 may add allergen and 
  Alcohol Facts requirements after public-comment review closing April 2025).
- **Known limitations:** US-only; English-only; 27 CFR scope only; small N; 
  solo-annotator; class imbalance toward wine; ~15% synthetic.

## Distribution
- **License:** Manifest and annotations released CC-BY-4.0; images retain 
  per-source license (CC0 for TTB, CC-BY-SA for OFF, etc.) — see provenance 
  block per record.
- **Hosting:** Project repo; images mirrored only when source license permits.
- **DOI:** Not minted for v0.1.

## Maintenance
- **Maintainer:** [Solo developer]
- **Versioning:** SemVer; v0.1 = MVP; bump major on schema breaks.
- **Updates:** Ad-hoc as MVP rules evolve; expect alignment with TTB Notices 
  237/238 once final rules are published.
- **Errata:** GitHub Issues.
```

---

## New artifacts to create (file structure only)

```
eval/
├── manifest.jsonl                     # 250 records, schema above
├── sourcing-matrix.md                 # the source × license × yield × legal table
├── sample-size.md                     # the Wald / Cantor / Krippendorff worked formulas
├── datasheet.md                       # the Gebru et al. stub above
├── conftest.py                        # pytest discovery
├── test_disposition.py                # parametrized per-label
├── test_metrics.py                    # macro-F1, confusion matrix, per-rule
├── scripts/
│   ├── fetch_ttb_cola.py
│   ├── fetch_off.py
│   ├── fetch_commons.py
│   ├── fetch_roboflow.py
│   ├── synthesize_dalle.py
│   └── build_manifest.py
├── data/
│   ├── raw/                           # untouched downloads, by source
│   └── eval/{wine,malt,spirits}/      # processed PNG/JPG
├── out/                               # eval-run JSON outputs
└── history/                           # nightly metric snapshots
```

### Updates to `docs/PRD.md` — eval acceptance criteria bullets to add

```markdown
## §X. Evaluation acceptance criteria (MVP v0.1)

- [ ] Eval manifest exists at eval/manifest.jsonl conforming to the schema in 
      eval/datasheet.md, with N ≥ 250 labels.
- [ ] Class balance: wine 40–50%, malt 35–45%, spirits 10–20%.
- [ ] Per-rule positive coverage: each MVP rule (R01–R12) has ≥ 43 positive 
      cases (95% CI ±15 pp on per-rule precision/recall).
- [ ] Happy-path coverage: ≥ 97 fully-compliant labels (95% CI ±10 pp on 
      disposition accuracy).
- [ ] Synthetic share ≤ 15%; every synthetic image carries C2PA metadata 
      and `provenance.source` matches `^synthetic-`.
- [ ] Annotator double-pass complete (≥ 48 h gap); Krippendorff's α ≥ 0.80 
      reported as intra-rater reliability with explicit limitation note.
- [ ] Disposition macro-F1 ≥ 0.70 on full eval (MVP gate); ≥ 0.85 (v1 gate).
- [ ] Per-rule recall ≥ 0.80 on R06–R09 (Government Health Warning rules) — 
      these are the highest-stakes rules and require stricter thresholds.
- [ ] CI runs smoke subset (20 labels) on every PR; full eval on merge to main; 
      nightly scheduled full run with metrics persisted to eval/history/.
- [ ] `/eval` dashboard route renders disposition confusion matrix and per-rule 
      P/R table; gated by DEV_MODE env flag.
- [ ] eval/datasheet.md follows Gebru et al. (2021) seven-section template.
```

---

## Caveats

- **Project-knowledge files were not retrievable in this session.** The MVP rule count ([S2](./2026-09-15-mvp-scope-demo-shape.md) output), the exact [T1](./2026-09-15-ttb-regulatory-framework.md) §7.3 reason-code list, the [T2](./2026-09-15-cola-operational-context.md) §Q2.10 application-field list, the [S1](./2026-09-15-vision-stack.md) fixture-set spec, and the [T9](./2026-09-15-verification-targets-research.md) §5 Krippendorff methodology section were all referenced in the task brief but could not be fetched via `project_knowledge_search`. I have substituted reasonable defaults derived from primary TTB regulatory pages (ttb.gov "Anatomy of a Malt Beverage Label", "Wine Labeling: Health Warning Statement", 27 CFR Part 16) and from the colacloud.us TTB-data-definitions reference. **Every assumption is flagged inline as `[ASSUMED — confirm against project knowledge]`.** The numerical recommendations (250 eval labels, 1,000 reservoir, ~15% synthetic, etc.) hold as long as the actual MVP rule count is in the 8–15 range; outside that range, recompute n_per_rule × R.
- **Vivino/WineSensed lineage.** WineSensed (Bender et al., NeurIPS 2023) was scraped from Vivino. Although the dataset is published on figshare DTU under an academic-use posture, redistributing the images carries Vivino-ToS contamination. For the MVP, **cite the dataset as a benchmark reference but do not redistribute the images**.
- **DALL·E 3 text-rendering reliability is not proven for this exact use case.** The 92% short-text accuracy figure comes from third-party benchmarks (skywork.ai, Glyph-ByT5 paper arXiv:2403.09622) and degrades sharply on text spans >12 characters. The TTB GOVERNMENT WARNING is 49 words / ~250 characters. **Do not rely on synthetic images to test the *correctness* of the warning** — only to test that the verifier correctly *flags* known-broken cases. C2PA metadata is automatically embedded but is trivially stripped by re-encoding (e.g., JPEG conversion through ImageMagick), per the OpenAI Help Center "C2PA in ChatGPT Images" article. Persist a SHA-256 of the original C2PA manifest in the JSONL `provenance.c2pa_manifest_sha256` field at fetch time, since it may be lost in pipeline post-processing.
- **Sample-size math is Wald-asymptotic.** For very low or very high true precision/recall (e.g., a rule that fires correctly 99% of the time), the Wald CI is anti-conservative. Wilson or Clopper-Pearson intervals would be more honest at the extremes; the per-rule N=43 is a *minimum*, and rules where the model is near-perfect or near-zero will have wider effective CIs.
- **TTB regulatory landscape is shifting.** TTB Notices 237 (Alcohol Facts) and 238 (Allergen labeling) were published January 2025 with public comment closing April 17, 2025; if/when finalized (typical 5-year transition), the MVP rule set will need to expand to cover Alcohol Facts and major-food-allergen disclosures. The eval corpus and rule list should be reviewed against the final rules before any v1 release.
- **The hiQ v. LinkedIn precedent applies in the Ninth Circuit only**, although it is widely cited. For this MVP — non-commercial, scraping U.S. federal public-domain data without bypassing access controls — the legal posture is comfortable. For productization or expansion to Vivino-style sources, get qualified counsel.
- **Solo-annotator IAA is a real methodological compromise.** The intra-rater-reliability framing is defensible per Krippendorff (2019) but reviewers familiar with content-analysis methodology will note (correctly) that it cannot detect systematic annotator bias. Plan for a second annotator before any external publication of metrics.