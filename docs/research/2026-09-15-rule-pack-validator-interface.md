# Rule Pack & Validator Interface (MVP)

Filed 2026-09-15.

**Project:** AI-Powered TTB Alcohol Label Verification Prototype
**Scope:** Rule Data & Validation Engine
**Authoritative regulatory source:** eCFR (current text of 27 CFR Parts 4, 5, 7, 16, as amended through T.D. TTB-176, 87 FR 7579 (Feb. 9, 2022) for Parts 5 and 7 modernization).

---

## TL;DR

- **YAML-as-data is the right format** for every MVP rule except the cpi lookup, which is encoded as a YAML decision table with explicit `interpolation: none` semantics; verbatim regulatory text (the §16.21 GOVERNMENT WARNING) lives in a separate hashed asset file referenced by SHA-256 from the rule.
- **ABV tolerances are correct as stated in [T9](./2026-09-15-verification-targets-research.md) §1** and verified against the current eCFR text: spirits ±0.3 pp (§5.65(c)), malt beverage ±0.3 pp with the §7.65(c) hard 0.5% floor, wine ±1.0 pp >14% / ±1.5 pp ≤14% (§4.36(b)(1)) with the §4.36(c) class-boundary anti-overlap constraint encoded as a hard post-condition.
- **Validator interface is Pydantic v2** (`FieldObservation` + `ExpectedValue` → `ValidationResult`), validators are referenced by string name (`equality_match`, `cpi_lookup`, `abv_band`, `verbatim_hash`, `fuzzy_brand`), the RuleLoader fail-closes on schema violation per [T3](./2026-09-15-rule-engine-architecture.md) §Q3.10, and confidence aggregates via `min` (never multiplication) per [T5](./2026-09-15-llm-orchestration-architecture.md) §Q5.7.

---

## Key Findings (Answers 1–13)

### 1. Final per-class MVP rule list (rule_id → CFR citation → reason code)

The reason-code grammar `BIN.SUB.SPECIFIC[.QUALIFIER]` from [T8](./2026-09-15-federal-ux-for-senior-users.md) is used; bins follow [T1](./2026-09-15-ttb-regulatory-framework.md) §7.3 (`BRAND`, `CLASS_TYPE`, `ALCOHOL_CONTENT`, `NAME_ADDRESS`, `NET_CONTENTS`, `WARNING`, `ALLERGEN`, `LEGIBILITY`).

**Common (Part 16 — applies to all classes ≥0.5% ABV)**

| rule_id | CFR | Reason code |
|---|---|---|
| `common.warning.present` | 27 CFR §16.21 | `WARNING.PRESENCE.MISSING` |
| `common.warning.verbatim` | 27 CFR §16.21 | `WARNING.VERBATIM.MISMATCH` |
| `common.warning.heading_caps_bold` | 27 CFR §16.22(a)(2) | `WARNING.STYLE.HEADING_NOT_BOLD_CAPS` |
| `common.warning.contrasting_bg` | 27 CFR §16.22(a)(1) | `WARNING.LEGIBILITY.NO_CONTRAST` |
| `common.warning.type_size_min` | 27 CFR §16.22(b) | `WARNING.TYPE_SIZE.UNDER_MIN` |
| `common.warning.cpi_max` | 27 CFR §16.22(a)(4) | `WARNING.TYPE_SIZE.CPI_EXCEEDED` |
| `common.warning.separate_apart` | 27 CFR §16.21 | `WARNING.PLACEMENT.NOT_SEPARATE` |

**Wine (Part 4)**

| rule_id | CFR | Reason code |
|---|---|---|
| `wine.brand.present` | 27 CFR §4.32(a)(1), §4.33 | `BRAND.PRESENCE.MISSING` |
| `wine.class_type.present` | 27 CFR §4.32(a)(2), §4.34 | `CLASS_TYPE.PRESENCE.MISSING` |
| `wine.alcohol.present_or_table` | 27 CFR §4.32(b)(1), §4.36(a) | `ALCOHOL_CONTENT.PRESENCE.MISSING` |
| `wine.alcohol.format` | 27 CFR §4.36(b)(1) | `ALCOHOL_CONTENT.FORMAT.INVALID` |
| `wine.alcohol.tolerance_band` | 27 CFR §4.36(b)(1) | `ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND` |
| `wine.alcohol.no_class_boundary_cross` | 27 CFR §4.36(c) | `ALCOHOL_CONTENT.TOLERANCE.CROSSES_CLASS_BOUNDARY` |
| `wine.name_address.present` | 27 CFR §4.32(a)(3), §4.35 | `NAME_ADDRESS.PRESENCE.MISSING` |
| `wine.net_contents.present` | 27 CFR §4.32(b)(2), §4.37 | `NET_CONTENTS.PRESENCE.MISSING` |
| `wine.sulfite_declaration` | 27 CFR §4.32(e) | `ALLERGEN.SULFITE.MISSING` (conditional) |

**Distilled spirits (Part 5)**

| rule_id | CFR | Reason code |
|---|---|---|
| `spirits.brand.present` | 27 CFR §5.63(a), §5.64 | `BRAND.PRESENCE.MISSING` |
| `spirits.class_type.present` | 27 CFR §5.63(a), Subpart I | `CLASS_TYPE.PRESENCE.MISSING` |
| `spirits.alcohol.present` | 27 CFR §5.63(a), §5.65(a) | `ALCOHOL_CONTENT.PRESENCE.MISSING` |
| `spirits.alcohol.format` | 27 CFR §5.65(b) | `ALCOHOL_CONTENT.FORMAT.INVALID` |
| `spirits.alcohol.tolerance_band` | 27 CFR §5.65(c) | `ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND` |
| `spirits.same_field_of_vision` | 27 CFR §5.63(a) | `LEGIBILITY.FIELD_OF_VISION.SPLIT` |
| `spirits.name_address.present` | 27 CFR §5.63(b)(1), §5.66/§5.67/§5.68 | `NAME_ADDRESS.PRESENCE.MISSING` |
| `spirits.net_contents.present` | 27 CFR §5.63(b)(2), §5.70 | `NET_CONTENTS.PRESENCE.MISSING` |

**Malt beverages (Part 7)**

| rule_id | CFR | Reason code |
|---|---|---|
| `malt.brand.present` | 27 CFR §7.63(a)(1), §7.64 | `BRAND.PRESENCE.MISSING` |
| `malt.class_type.present` | 27 CFR §7.63(a)(2), Subpart I | `CLASS_TYPE.PRESENCE.MISSING` |
| `malt.alcohol.conditional_required` | 27 CFR §7.63(a)(3) | `ALCOHOL_CONTENT.PRESENCE.MISSING` (conditional) |
| `malt.alcohol.format` | 27 CFR §7.65(b) | `ALCOHOL_CONTENT.FORMAT.INVALID` |
| `malt.alcohol.tolerance_band` | 27 CFR §7.65(c) | `ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND` |
| `malt.alcohol.floor_05` | 27 CFR §7.65(c) | `ALCOHOL_CONTENT.TOLERANCE.BELOW_HARD_FLOOR` |
| `malt.name_address.present` | 27 CFR §7.63(a)(4), §7.66/§7.67/§7.68 | `NAME_ADDRESS.PRESENCE.MISSING` |
| `malt.net_contents.present` | 27 CFR §7.63(a)(5), §7.70 | `NET_CONTENTS.PRESENCE.MISSING` |

### 2. Cpi table — YAML decision table or Python validator?

**Recommendation: YAML decision table with explicit `interpolation: none` semantics**, called by a generic `validator: cpi_lookup` reference. The §16.22(a)(4) table is a closed enumeration of three points (1 mm → 40 cpi, 2 mm → 25 cpi, 3 mm → 12 cpi) with no regulatory authority to interpolate between them; the regulation is itself written as a tabular rule. Encoding it in YAML keeps the rules-as-data invariant from the deterministic core, makes the comparison auditable by a reviewer who is not a Python developer, and leaves the validator (a generic key-lookup) as one of ~5 named primitives. A bespoke Python function would (a) hide a regulatory citation inside compiled code, (b) defeat the rule-pack version diff workflow, and (c) tempt future contributors to add interpolation, which would silently invent an unauthorized standard.

### 3. ABV tolerance encoding — verified against current eCFR

Confirmed against eCFR (current as of 2026-04): §4.36(b)(1) and (c), §5.65(c), §7.65(c). The §4.36 numbering survived the 2022 modernization (only Parts 5 and 7 were renumbered under T.D. TTB-176, 87 FR 7579); §4.36(c) anti-overlap language is unchanged from T.D. ATF-275 (1988). The encoding is in deliverable (a) below.

### 4. Verbatim warning string storage

**Recommendation: separate hashed asset file referenced by SHA-256 from the rule.** The verbatim text from §16.21 is:

> `GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.`

Store as `assets/warnings/govt_warning_16_21.txt` (UTF-8, LF, no trailing newline). The rule references it with both a path and a SHA-256 of the canonicalized bytes. This (a) prevents YAML escaping/whitespace drift from corrupting the verbatim string, (b) makes the file diffable in CI, (c) lets the loader hash-verify on startup and fail-closed if the file is mutated, and (d) keeps the regulatory text at exactly one location in the repository (single source of truth, per the declared per-field policies).

For the canonical bytes (single trailing newline excluded; ASCII; smart quotes normalized to ASCII), the SHA-256 is computed and pinned at rule-loader startup; the value is recorded in `reason_codes.yaml` and the rule file, and any drift triggers `WARNING.VERBATIM.HASH_DRIFT` and refuses startup. **Do not hard-code the hash in this document** — compute it once during repo bootstrap from the canonicalized file and commit both the file and the hash together; the `RuleLoader` then enforces the equality at every startup.

### 5. Brand-name fuzzy match policy

The [T3](./2026-09-15-rule-engine-architecture.md) suggestion (RapidFuzz `token_set_ratio` ≥ 0.85) is appropriate but should run as the **last** stage of a layered pipeline:

1. **Exact match** on raw OCR string vs. expected brand → `match: exact` (confidence inherited from OCR).
2. **Normalized exact** (Unicode NFKC, casefold, strip punctuation, collapse whitespace, drop legal suffixes like "®", "™", "Co.", "Inc.") → `match: normalized`.
3. **Fuzzy fallback**: RapidFuzz `fuzz.token_set_ratio(normalized_a, normalized_b) / 100.0 ≥ 0.85` → `match: fuzzy` with score reported in `Evidence.match_score`.

`token_set_ratio` is the right scorer for brand fields (handles word reordering and extra adjectives like "Brand", which §4.39(j) explicitly allows). The threshold 0.85 sits below the empirical floor for human-judged "same brand with OCR noise" and above the typical ceiling for unrelated brands; lower it only if the [S4](./2026-09-15-eval-harness-design.md) fixtures show false negatives, never raise it without a fixture-driven precision/recall study. Never use fuzzy matching for the §16.21 verbatim string — that is hash-only.

### 6. YAML rule shape — confirmed and refined

Adopt the [T3](./2026-09-15-rule-engine-architecture.md)-suggested shape and add the following production fields:

- `effective_date` (ISO-8601, when the rule begins applying — usually the CFR amendment date)
- `supersedes` (optional list of rule_ids retired by this rule)
- `rule_pack_version` (semver of the parent pack; the loader pins the matrix)
- `test_fixtures` (list of fixture IDs in [S4](./2026-09-15-eval-harness-design.md) that exercise this rule, both pass and fail cases — required, fail-closed if empty)
- `notes` (free-text reviewer commentary; ignored by the engine)
- `disabled` (bool, default false; disabled rules load but never fire — used for staged rollout)
- `confidence_floor` (per [T5](./2026-09-15-llm-orchestration-architecture.md) §Q5.5 minimum aggregated confidence below which result is `INSUFFICIENT_EVIDENCE`)

The full shape is shown in the deliverable (a) examples.

### 7. Reason-code registry — separate file

**Recommendation: separate `reason_codes.yaml` registry**, loaded once and referenced by code in every rule. Inlining produces drift (two rules with the same intent end up with subtly different `WARNING.TYPE_SIZE.UNDER_1MM` vs. `WARNING.TYPESIZE.UNDER_1MM` codes), prevents catalog-style C-EvidencePanel hover text, and breaks the §7.3 taxonomy invariant. Loader fail-closes if any rule references a code not present in the registry.

### 8. Rule versioning — research prototype

**Recommendation: YAML header field `rule_pack_version: <semver>` plus git tags; no version in filename.** Rationale:

- Filename versioning (`wine-v1.2.0.yaml`) creates path churn for every change and breaks `git blame` continuity.
- Git tags alone don't survive `kubectl cp` or zip exports.
- A `rule_pack_version` field inside each file (or a top-level `pack.yaml` for the directory) lets the running engine emit it in every `ValidationResult.engine_meta` for traceability, and the git tag remains the canonical release marker.

For an MVP, individual rule-file versioning is overkill; version the **pack** (the `rules/` tree) as a unit using semver bumped on every CFR-derived change.

### 9. Pydantic v2 input contract — confirmed with prototype refinements

Per [T3](./2026-09-15-rule-engine-architecture.md) §Q3.2: `FieldObservation + ExpectedValue → ValidationResult`. Pydantic v2 confirmed. Prototype-specific deviations:

- Use `model_config = ConfigDict(extra='forbid', frozen=True)` on all four models — strict, immutable, fail-loud.
- `Evidence` and `ValidationResult` are frozen so they can be cached and shared across the audit trail.
- `Decimal` (not `float`) for ABV values to avoid 14.0 vs 13.999999 boundary bugs.
- `confidence` typed as `Annotated[float, Field(ge=0.0, le=1.0)]`.
- `bbox` typed as `tuple[int, int, int, int]` (x, y, w, h in pixels of the source image at native resolution; crop coordinates in [T4](./2026-09-15-ocr-vision-architecture.md) normalized form).
- Defer FastAPI request models to a thin shim layer — the engine itself takes raw `FieldObservation` instances, not HTTP payloads.

Full implementation in deliverable (c).

### 10. Evidence shape — for C-EvidencePanel

Beyond the [T3](./2026-09-15-rule-engine-architecture.md) minimum (`bbox`, `extracted_text`, `confidence`, `matched_against_value`), the UI needs:

- `field_id` (which rule consumed this evidence)
- `source` (one of `ocr`, `layout`, `classifier`, `derived`)
- `page_id` / `panel` (which label face the bbox is on — front/back/neck/wrap)
- `image_uri` (so the UI can crop and zoom)
- `match_kind` (`exact`, `normalized`, `fuzzy`, `hash`, `numeric_band`, `lookup`, `none`)
- `match_score` (optional float for fuzzy/lookup)
- `normalized_text` (post-NFKC/casefold form actually compared)
- `notes` (engine breadcrumb, e.g. "applied 14% boundary clamp")

### 11. Confidence aggregation — min vs. multiplication

**Confirmed: min-aggregate is correct for this engine.** Reasons:

1. **Independence assumption fails.** Multiplication (`p_ocr * p_layout * p_match`) assumes the three signals are statistically independent; they are not — OCR confidence and layout confidence are both functions of the same input image. Multiplying correlated probabilities artificially deflates confidence and makes thresholds unstable.
2. **Bounded weakest-link semantics.** A rule's pass/fail correctness is upper-bounded by its weakest signal. If the OCR engine is 0.6 confident the warning text reads `GOVERNMENT WARN1NG`, then no amount of high-confidence layout detection can rescue the verbatim match. `min(0.6, 0.99, 0.95) = 0.6` is the honest answer.
3. **Calibration friendliness.** `min` preserves the OCR engine's calibration; multiplying does not. Confidence-band thresholds ([T3](./2026-09-15-rule-engine-architecture.md) §Q3.5) stay interpretable.
4. **Determinism per [T5](./2026-09-15-llm-orchestration-architecture.md) §Q5.7.** Min is associative, commutative, and order-independent — it composes the same way regardless of the order in which evidence arrives, which the deterministic-first principle requires.
5. **Failure mode honesty.** When OCR returns 0.0 ("character could not be read"), multiplication zeros the whole result; min does too — but min lets the UI surface *which* signal failed, because it's the argmin.

### 12. Engine failure modes — MVP subset of the 13 from [T3](./2026-09-15-rule-engine-architecture.md) §Q3.10

For an MVP, **8 of 13 are essential, 5 deferrable.** Essential, fail-closed at startup or per-request:

1. Malformed YAML / loader schema violation → refuse to start
2. Missing required field on `FieldObservation` → return `INSUFFICIENT_EVIDENCE`
3. Validator timeout (per-rule budget exceeded) → return `TIMEOUT`, fail-closed
4. Reason-code not in registry → refuse to start
5. Verbatim asset hash mismatch → refuse to start
6. OCR/upstream dependency failure on a required field → return `INSUFFICIENT_EVIDENCE` for affected rules only, do not crash the engine
7. Confidence below `confidence_floor` → return `INSUFFICIENT_EVIDENCE`
8. Rule-pack version mismatch with engine-supported range → refuse to start

Deferrable to post-MVP: rule-rule dependency cycles, partial-result merging across distributed workers, rule shadowing detection, fuzzy-match tie-breaking telemetry, COLA-form-driven dynamic rule selection. The MVP runs single-process, single-pack, so these are not yet exercisable.

### 13. Per-rule timeout budget — pick one

**Pick 250 ms per rule.** Justification:

- Pure equality / lookup / numeric-band rules (the majority) finish in <5 ms, leaving generous headroom.
- Fuzzy brand match using RapidFuzz `token_set_ratio` with a candidate set of one expected value is sub-millisecond on CPython; even with 100 expected aliases it stays under 50 ms.
- The verbatim hash check (`common.warning.verbatim`) plus normalization runs <10 ms.
- 250 ms gives a 5× safety margin on the slowest plausible MVP rule (a fuzzy match against a long alias list with normalization), while keeping a 30-rule sequential evaluation under 7.5 s wall-clock — well within the engine SLO.
- 100 ms is too tight (one GC pause and a fuzzy rule trips the budget unnecessarily); 300 ms is acceptable but masks unintended slowdowns and is harder to alert on. 250 ms threads the needle.

Per-pack global budget: `n_rules * 250 ms + 500 ms loader overhead`.

---

## Deliverables (a)–(f)

### (a) YAML rule files

#### `rules/common/health_warning.yaml`

```yaml
rule_pack: common
rule_pack_version: "0.1.0"
rules:

  - rule_id: common.warning.present
    cfr_citation: "27 CFR §16.21"
    applies_to_classes: [wine, spirits, malt]
    reason_code: WARNING.PRESENCE.MISSING
    severity: reject
    match_policy: required_presence
    validator: presence_check
    evidence_required: [warning_block_bbox, warning_block_text]
    confidence_floor: 0.50
    effective_date: "1989-11-18"
    test_fixtures: [F-COMMON-WARN-PASS-01, F-COMMON-WARN-MISSING-01]

  - rule_id: common.warning.verbatim
    cfr_citation: "27 CFR §16.21"
    applies_to_classes: [wine, spirits, malt]
    reason_code: WARNING.VERBATIM.MISMATCH
    severity: reject
    match_policy: verbatim_hash
    validator: verbatim_hash
    asset:
      path: assets/warnings/govt_warning_16_21.txt
      sha256_pin: "<computed-at-bootstrap-and-committed>"
      normalization: [nfkc, ascii_quotes, collapse_whitespace, strip_outer_ws]
    evidence_required: [warning_block_text]
    confidence_floor: 0.60
    effective_date: "1989-11-18"
    test_fixtures: [F-COMMON-WARN-PASS-01, F-COMMON-WARN-PARAPHRASE-01]

  - rule_id: common.warning.heading_caps_bold
    cfr_citation: "27 CFR §16.22(a)(2)"
    applies_to_classes: [wine, spirits, malt]
    reason_code: WARNING.STYLE.HEADING_NOT_BOLD_CAPS
    severity: reject
    match_policy: style_check
    validator: heading_style_check
    parameters:
      target_phrase: "GOVERNMENT WARNING"
      required_case: upper
      required_weight: bold
      remainder_must_not_be_bold: true
    evidence_required: [warning_block_text, warning_block_styles]
    confidence_floor: 0.50
    effective_date: "1989-11-18"
    test_fixtures: [F-COMMON-WARN-STYLE-PASS-01, F-COMMON-WARN-STYLE-FAIL-01]

  - rule_id: common.warning.contrasting_bg
    cfr_citation: "27 CFR §16.22(a)(1)"
    applies_to_classes: [wine, spirits, malt]
    reason_code: WARNING.LEGIBILITY.NO_CONTRAST
    severity: reject
    match_policy: contrast_check
    validator: contrast_ratio_check
    parameters:
      min_contrast_ratio: 4.5     # WCAG AA proxy; CFR text says "readily legible"
    evidence_required: [warning_block_bbox, warning_block_fg_color, warning_block_bg_color]
    confidence_floor: 0.40
    effective_date: "1989-11-18"
    test_fixtures: [F-COMMON-WARN-CONTRAST-PASS-01, F-COMMON-WARN-CONTRAST-FAIL-01]

  - rule_id: common.warning.type_size_min
    cfr_citation: "27 CFR §16.22(b)"
    applies_to_classes: [wine, spirits, malt]
    reason_code: WARNING.TYPE_SIZE.UNDER_MIN
    severity: reject
    match_policy: lookup_band
    validator: type_size_min_lookup
    decision_table:
      key: container_volume_ml
      no_interpolation: true
      bands:
        - { max_ml: 237,    min_height_mm: 1 }   # ≤ 8 fl oz
        - { max_ml: 3000,   min_height_mm: 2 }   # > 237 ml ≤ 3 L
        - { max_ml: .inf,   min_height_mm: 3 }   # > 3 L
    evidence_required: [warning_block_text_height_mm, container_volume_ml]
    confidence_floor: 0.50
    effective_date: "1990-02-14"
    test_fixtures: [F-COMMON-TYPESIZE-PASS-01, F-COMMON-TYPESIZE-UNDER1MM-01]

  - rule_id: common.warning.cpi_max
    cfr_citation: "27 CFR §16.22(a)(4)"
    applies_to_classes: [wine, spirits, malt]
    reason_code: WARNING.TYPE_SIZE.CPI_EXCEEDED
    severity: reject
    match_policy: lookup_table
    validator: cpi_lookup
    decision_table_ref: tables/cpi_16_22_a_4.yaml
    evidence_required: [warning_block_text_height_mm, warning_block_cpi_measured]
    confidence_floor: 0.50
    effective_date: "1990-02-14"
    test_fixtures: [F-COMMON-CPI-PASS-01, F-COMMON-CPI-FAIL-1MM-01, F-COMMON-CPI-FAIL-2MM-01]

  - rule_id: common.warning.separate_apart
    cfr_citation: "27 CFR §16.21"
    applies_to_classes: [wine, spirits, malt]
    reason_code: WARNING.PLACEMENT.NOT_SEPARATE
    severity: reject
    match_policy: layout_check
    validator: layout_isolation_check
    parameters:
      min_isolation_px: 4   # tunable; encodes "separate and apart from all other information"
    evidence_required: [warning_block_bbox, surrounding_text_bboxes]
    confidence_floor: 0.40
    effective_date: "1989-11-18"
    test_fixtures: [F-COMMON-WARN-ISOLATION-PASS-01, F-COMMON-WARN-ISOLATION-FAIL-01]
```

#### `rules/wine/wine.yaml`

```yaml
rule_pack: wine
rule_pack_version: "0.1.0"
rules:

  - rule_id: wine.brand.present
    cfr_citation: "27 CFR §4.32(a)(1), §4.33"
    applies_to_classes: [wine]
    reason_code: BRAND.PRESENCE.MISSING
    severity: reject
    match_policy: fuzzy_or_exact
    validator: fuzzy_brand
    parameters:
      stages: [exact, normalized, fuzzy]
      fuzzy_scorer: token_set_ratio
      fuzzy_threshold: 0.85
    evidence_required: [brand_text, expected_brand]
    confidence_floor: 0.50
    effective_date: "1936-12-15"
    test_fixtures: [F-WINE-BRAND-PASS-01, F-WINE-BRAND-FUZZY-01, F-WINE-BRAND-MISSING-01]

  - rule_id: wine.class_type.present
    cfr_citation: "27 CFR §4.32(a)(2), §4.34"
    applies_to_classes: [wine]
    reason_code: CLASS_TYPE.PRESENCE.MISSING
    severity: reject
    match_policy: enumerated_match
    validator: enumerated_match
    parameters:
      allowed_values_ref: tables/wine_class_type_4_34.yaml
      allow_statement_of_composition: true
    evidence_required: [class_type_text]
    confidence_floor: 0.50
    effective_date: "1936-12-15"
    test_fixtures: [F-WINE-CLASS-PASS-01, F-WINE-CLASS-MISSING-01]

  - rule_id: wine.alcohol.present_or_table
    cfr_citation: "27 CFR §4.32(b)(1), §4.36(a)"
    applies_to_classes: [wine]
    reason_code: ALCOHOL_CONTENT.PRESENCE.MISSING
    severity: reject
    match_policy: conditional_presence
    validator: alcohol_presence_or_table_designation
    parameters:
      table_designation_terms: ["table wine", "light wine"]
      threshold_pct: 14.0
    evidence_required: [alcohol_text, class_type_text]
    confidence_floor: 0.50
    effective_date: "1936-12-15"
    test_fixtures: [F-WINE-ALC-PRESENT-01, F-WINE-ALC-TABLE-01, F-WINE-ALC-MISSING-01]

  - rule_id: wine.alcohol.format
    cfr_citation: "27 CFR §4.36(b)(1)"
    applies_to_classes: [wine]
    reason_code: ALCOHOL_CONTENT.FORMAT.INVALID
    severity: reject
    match_policy: regex_match
    validator: regex_match
    parameters:
      pattern: '^\s*(?:alcohol|alc\.?)\s*[0-9]{1,2}(?:\.[0-9]+)?\s*%?\s*(?:by\s+volume|/\s*vol\.?|vol\.?)\s*$'
      ignore_case: true
    evidence_required: [alcohol_text]
    confidence_floor: 0.50
    effective_date: "1936-12-15"
    test_fixtures: [F-WINE-ALC-FORMAT-PASS-01, F-WINE-ALC-FORMAT-FAIL-01]

  - rule_id: wine.alcohol.tolerance_band
    cfr_citation: "27 CFR §4.36(b)(1)"
    applies_to_classes: [wine]
    reason_code: ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND
    severity: reject
    match_policy: numeric_band
    validator: abv_band
    tolerance:
      class_boundary_pct: 14.0
      below_or_equal_boundary:
        plus_pp: 1.5
        minus_pp: 1.5
      above_boundary:
        plus_pp: 1.0
        minus_pp: 1.0
      no_class_boundary_cross: true   # see wine.alcohol.no_class_boundary_cross
      precision_pp: 0.1
    evidence_required: [labeled_abv_pct, actual_abv_pct]
    confidence_floor: 0.60
    effective_date: "1988-07-18"
    test_fixtures:
      - F-WINE-ALC-12-PASS-01
      - F-WINE-ALC-12-FAIL-LOW-01
      - F-WINE-ALC-18-PASS-01
      - F-WINE-ALC-18-FAIL-HIGH-01

  - rule_id: wine.alcohol.no_class_boundary_cross
    cfr_citation: "27 CFR §4.36(c)"
    applies_to_classes: [wine]
    reason_code: ALCOHOL_CONTENT.TOLERANCE.CROSSES_CLASS_BOUNDARY
    severity: reject
    match_policy: hard_constraint
    validator: abv_class_boundary_check
    parameters:
      class_boundary_pct: 14.0
      message: >
        Alcohol content statement (whether direct or range) may not, with tolerance,
        overlap a prescribed class limitation per §4.36(c). A 13.5% label cannot be
        defended by a 14.5% actual reading.
    evidence_required: [labeled_abv_pct, actual_abv_pct]
    confidence_floor: 0.60
    effective_date: "1988-07-18"
    test_fixtures:
      - F-WINE-ALC-13-5-LABEL-14-5-ACTUAL-FAIL-01
      - F-WINE-ALC-14-1-LABEL-13-9-ACTUAL-FAIL-01

  - rule_id: wine.name_address.present
    cfr_citation: "27 CFR §4.32(a)(3), §4.35"
    applies_to_classes: [wine]
    reason_code: NAME_ADDRESS.PRESENCE.MISSING
    severity: reject
    match_policy: required_presence
    validator: presence_check
    evidence_required: [bottler_name_text, bottler_address_text]
    confidence_floor: 0.50
    effective_date: "1936-12-15"
    test_fixtures: [F-WINE-NAMEADDR-PASS-01, F-WINE-NAMEADDR-MISSING-01]

  - rule_id: wine.net_contents.present
    cfr_citation: "27 CFR §4.32(b)(2), §4.37"
    applies_to_classes: [wine]
    reason_code: NET_CONTENTS.PRESENCE.MISSING
    severity: reject
    match_policy: required_presence
    validator: presence_check
    evidence_required: [net_contents_text]
    confidence_floor: 0.50
    effective_date: "1936-12-15"
    test_fixtures: [F-WINE-NET-PASS-01, F-WINE-NET-MISSING-01]

  - rule_id: wine.sulfite_declaration
    cfr_citation: "27 CFR §4.32(e)"
    applies_to_classes: [wine]
    reason_code: ALLERGEN.SULFITE.MISSING
    severity: reject
    match_policy: conditional_presence
    validator: conditional_presence
    parameters:
      condition: "sulfite_ppm >= 10"
      required_phrase_any_of: ["Contains Sulfites", "Contains a Sulfating Agent", "Contains Sulfiting Agents"]
      case_insensitive: true
    evidence_required: [back_label_text, sulfite_ppm]
    confidence_floor: 0.50
    effective_date: "1987-07-09"
    test_fixtures: [F-WINE-SULFITE-PASS-01, F-WINE-SULFITE-MISSING-01]
```

#### `rules/spirits/spirits.yaml`

```yaml
rule_pack: spirits
rule_pack_version: "0.1.0"
rules:

  - rule_id: spirits.brand.present
    cfr_citation: "27 CFR §5.63(a), §5.64"
    applies_to_classes: [spirits]
    reason_code: BRAND.PRESENCE.MISSING
    severity: reject
    match_policy: fuzzy_or_exact
    validator: fuzzy_brand
    parameters:
      stages: [exact, normalized, fuzzy]
      fuzzy_scorer: token_set_ratio
      fuzzy_threshold: 0.85
    evidence_required: [brand_text, expected_brand]
    confidence_floor: 0.50
    effective_date: "2022-02-09"   # T.D. TTB-176 modernization
    test_fixtures: [F-SPIRITS-BRAND-PASS-01, F-SPIRITS-BRAND-MISSING-01]

  - rule_id: spirits.class_type.present
    cfr_citation: "27 CFR §5.63(a), 27 CFR Part 5 Subpart I"
    applies_to_classes: [spirits]
    reason_code: CLASS_TYPE.PRESENCE.MISSING
    severity: reject
    match_policy: enumerated_match
    validator: enumerated_match
    parameters:
      allowed_values_ref: tables/spirits_standards_of_identity_5_subpart_I.yaml
    evidence_required: [class_type_text]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-SPIRITS-CLASS-PASS-01, F-SPIRITS-CLASS-MISSING-01]

  - rule_id: spirits.alcohol.present
    cfr_citation: "27 CFR §5.63(a), §5.65(a)"
    applies_to_classes: [spirits]
    reason_code: ALCOHOL_CONTENT.PRESENCE.MISSING
    severity: reject
    match_policy: required_presence
    validator: presence_check
    evidence_required: [alcohol_text]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-SPIRITS-ALC-PRESENT-01, F-SPIRITS-ALC-MISSING-01]

  - rule_id: spirits.alcohol.format
    cfr_citation: "27 CFR §5.65(b)"
    applies_to_classes: [spirits]
    reason_code: ALCOHOL_CONTENT.FORMAT.INVALID
    severity: reject
    match_policy: regex_match
    validator: regex_match
    parameters:
      # accepts e.g. "40% alc/vol", "Alc. 40 percent by vol.", "Alc 40% by vol", "40% Alcohol by Volume"
      pattern: '(?i)^\s*(?:alcohol|alc\.?)?\s*[0-9]{1,2}(?:\.[0-9]+)?\s*%?\s*(?:alcohol|alc\.?)?\s*(?:by\s+volume|/\s*vol\.?|vol\.?|by\s*vol\.?)\s*$'
    evidence_required: [alcohol_text]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-SPIRITS-ALC-FORMAT-PASS-01, F-SPIRITS-ALC-FORMAT-FAIL-01]

  - rule_id: spirits.alcohol.tolerance_band
    cfr_citation: "27 CFR §5.65(c)"
    applies_to_classes: [spirits]
    reason_code: ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND
    severity: reject
    match_policy: numeric_band
    validator: abv_band
    tolerance:
      symmetric:
        plus_pp: 0.3
        minus_pp: 0.3
      precision_pp: 0.1
    evidence_required: [labeled_abv_pct, actual_abv_pct]
    confidence_floor: 0.60
    effective_date: "2022-02-09"     # T.D. TTB-176 raised to ±0.3
    test_fixtures: [F-SPIRITS-ALC-36-PASS-01, F-SPIRITS-ALC-36-FAIL-LOW-01, F-SPIRITS-ALC-36-FAIL-HIGH-01]

  - rule_id: spirits.same_field_of_vision
    cfr_citation: "27 CFR §5.63(a)"
    applies_to_classes: [spirits]
    reason_code: LEGIBILITY.FIELD_OF_VISION.SPLIT
    severity: reject
    match_policy: layout_check
    validator: same_field_of_vision_check
    parameters:
      required_fields: [brand_text, alcohol_text, class_type_text]
      cylindrical_arc_pct: 40
    evidence_required: [brand_bbox, alcohol_bbox, class_type_bbox, container_geometry]
    confidence_floor: 0.40
    effective_date: "2022-02-09"
    test_fixtures: [F-SPIRITS-FOV-PASS-01, F-SPIRITS-FOV-FAIL-01]

  - rule_id: spirits.name_address.present
    cfr_citation: "27 CFR §5.63(b)(1), §5.66/§5.67/§5.68"
    applies_to_classes: [spirits]
    reason_code: NAME_ADDRESS.PRESENCE.MISSING
    severity: reject
    match_policy: required_presence
    validator: presence_check
    evidence_required: [bottler_or_importer_text]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-SPIRITS-NAMEADDR-PASS-01, F-SPIRITS-NAMEADDR-MISSING-01]

  - rule_id: spirits.net_contents.present
    cfr_citation: "27 CFR §5.63(b)(2), §5.70"
    applies_to_classes: [spirits]
    reason_code: NET_CONTENTS.PRESENCE.MISSING
    severity: reject
    match_policy: required_presence
    validator: presence_check
    evidence_required: [net_contents_text]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-SPIRITS-NET-PASS-01, F-SPIRITS-NET-MISSING-01]
```

#### `rules/malt/malt.yaml`

```yaml
rule_pack: malt
rule_pack_version: "0.1.0"
rules:

  - rule_id: malt.brand.present
    cfr_citation: "27 CFR §7.63(a)(1), §7.64"
    applies_to_classes: [malt]
    reason_code: BRAND.PRESENCE.MISSING
    severity: reject
    match_policy: fuzzy_or_exact
    validator: fuzzy_brand
    parameters:
      stages: [exact, normalized, fuzzy]
      fuzzy_scorer: token_set_ratio
      fuzzy_threshold: 0.85
    evidence_required: [brand_text, expected_brand]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-MALT-BRAND-PASS-01, F-MALT-BRAND-MISSING-01]

  - rule_id: malt.class_type.present
    cfr_citation: "27 CFR §7.63(a)(2), 27 CFR Part 7 Subpart I"
    applies_to_classes: [malt]
    reason_code: CLASS_TYPE.PRESENCE.MISSING
    severity: reject
    match_policy: enumerated_match
    validator: enumerated_match
    parameters:
      allowed_values_ref: tables/malt_classes_7_subpart_I.yaml
    evidence_required: [class_type_text]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-MALT-CLASS-PASS-01, F-MALT-CLASS-MISSING-01]

  - rule_id: malt.alcohol.conditional_required
    cfr_citation: "27 CFR §7.63(a)(3)"
    applies_to_classes: [malt]
    reason_code: ALCOHOL_CONTENT.PRESENCE.MISSING
    severity: reject
    match_policy: conditional_presence
    validator: conditional_presence
    parameters:
      condition: "contains_added_nonbeverage_flavors_or_alcohol_ingredients == true and not_only_hops_extract == true"
    evidence_required: [alcohol_text, formulation_metadata]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-MALT-ALC-FMB-PASS-01, F-MALT-ALC-FMB-MISSING-01]

  - rule_id: malt.alcohol.format
    cfr_citation: "27 CFR §7.65(b)"
    applies_to_classes: [malt]
    reason_code: ALCOHOL_CONTENT.FORMAT.INVALID
    severity: reject
    match_policy: regex_match
    validator: regex_match
    parameters:
      # ABV abbreviation explicitly NOT allowed per TTB malt-beverage labeling guidance
      pattern: '(?i)^\s*(?:alcohol|alc\.?)\s*[0-9]{1,2}(?:\.[0-9])?\s*%?\s*(?:by\s+volume|/\s*vol\.?|vol\.?)\s*$'
      forbidden_substrings: ["ABV", "abv"]
    evidence_required: [alcohol_text]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-MALT-ALC-FORMAT-PASS-01, F-MALT-ALC-FORMAT-FAIL-ABV-01]

  - rule_id: malt.alcohol.tolerance_band
    cfr_citation: "27 CFR §7.65(c)"
    applies_to_classes: [malt]
    reason_code: ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND
    severity: reject
    match_policy: numeric_band
    validator: abv_band
    tolerance:
      symmetric:
        plus_pp: 0.3
        minus_pp: 0.3
      precision_pp: 0.1
    evidence_required: [labeled_abv_pct, actual_abv_pct]
    confidence_floor: 0.60
    effective_date: "2022-02-09"
    test_fixtures: [F-MALT-ALC-5-PASS-01, F-MALT-ALC-5-FAIL-HIGH-01]

  - rule_id: malt.alcohol.floor_05
    cfr_citation: "27 CFR §7.65(c)"
    applies_to_classes: [malt]
    reason_code: ALCOHOL_CONTENT.TOLERANCE.BELOW_HARD_FLOOR
    severity: reject
    match_policy: hard_constraint
    validator: abv_hard_floor
    parameters:
      hard_floor_pct: 0.5
      message: >
        A malt beverage labeled as containing 0.5% or more alcohol by volume may not
        contain less than 0.5% alcohol by volume, regardless of the ±0.3 pp tolerance.
    evidence_required: [labeled_abv_pct, actual_abv_pct]
    confidence_floor: 0.60
    effective_date: "2022-02-09"
    test_fixtures: [F-MALT-ALC-FLOOR-FAIL-01]

  - rule_id: malt.name_address.present
    cfr_citation: "27 CFR §7.63(a)(4), §7.66/§7.67/§7.68"
    applies_to_classes: [malt]
    reason_code: NAME_ADDRESS.PRESENCE.MISSING
    severity: reject
    match_policy: required_presence
    validator: presence_check
    evidence_required: [bottler_or_importer_text]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-MALT-NAMEADDR-PASS-01, F-MALT-NAMEADDR-MISSING-01]

  - rule_id: malt.net_contents.present
    cfr_citation: "27 CFR §7.63(a)(5), §7.70"
    applies_to_classes: [malt]
    reason_code: NET_CONTENTS.PRESENCE.MISSING
    severity: reject
    match_policy: required_presence
    validator: presence_check
    evidence_required: [net_contents_text]
    confidence_floor: 0.50
    effective_date: "2022-02-09"
    test_fixtures: [F-MALT-NET-PASS-01, F-MALT-NET-MISSING-01]
```

### (b) Cardinal cpi decision table — `tables/cpi_16_22_a_4.yaml`

```yaml
# §16.22(a)(4) — Maximum characters per inch by minimum required type size.
# Source: 27 CFR §16.22(a)(4) (current eCFR; T.D. ATF-294, 55 FR 5421, Feb. 14, 1990,
# as amended by T.D. 372, 61 FR 20723, May 8, 1996; T.D. TTB-91, 76 FR 5477, Feb. 1, 2011).
# This table is normative — no interpolation between rows is authorized by the regulation.

cfr_citation: "27 CFR §16.22(a)(4)"
key: min_required_type_height_mm
result: max_characters_per_inch
no_interpolation: true            # explicit: do NOT linearly interpolate.
on_below_smallest_key: error      # if measured < 1 mm, raise; size_min rule handles separately.
on_above_largest_key: clamp_to_max  # if ≥ 3 mm, the 12 cpi cap applies; CFR text upper-bounds at 3 mm.
on_between_keys: round_up_to_next_key  # 1.5 mm is treated as 2 mm bucket (stricter cpi cap)
bands:
  - { min_required_type_height_mm: 1, max_characters_per_inch: 40 }
  - { min_required_type_height_mm: 2, max_characters_per_inch: 25 }
  - { min_required_type_height_mm: 3, max_characters_per_inch: 12 }

# Notes for the validator:
#   * Look up the row whose `min_required_type_height_mm` equals the row chosen by
#     §16.22(b) (rule common.warning.type_size_min) for the container's volume class.
#   * Compare measured cpi to `max_characters_per_inch`; fail if measured > maximum.
#   * Do NOT compute `40 - 15*(h-1)` or similar; the regulation enumerates three points only.
```

### (c) Pydantic v2 contracts — `src/engine/contracts.py`

```python
"""TTB label-verification engine — wire contracts.

Exact implementation of T3 §Q3.2 (FieldObservation + ExpectedValue → ValidationResult)
with prototype refinements from S5.

All models are frozen and forbid extras: fail-loud, immutable, audit-friendly.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums and primitive types
# ---------------------------------------------------------------------------


class BeverageClass(str, Enum):
    WINE = "wine"
    SPIRITS = "spirits"
    MALT = "malt"


class Severity(str, Enum):
    REJECT = "reject"           # T1 §7.3: hard fail, COLA-blocking
    WARN = "warn"               # advisory; reviewer attention
    INFO = "info"               # passive note


class Outcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"
    TIMEOUT = "timeout"
    ERROR = "error"             # internal engine fault; fail-closed


class MatchKind(str, Enum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY = "fuzzy"
    HASH = "hash"
    NUMERIC_BAND = "numeric_band"
    LOOKUP = "lookup"
    REGEX = "regex"
    LAYOUT = "layout"
    NONE = "none"


class EvidenceSource(str, Enum):
    OCR = "ocr"
    LAYOUT = "layout"
    CLASSIFIER = "classifier"
    DERIVED = "derived"
    METADATA = "metadata"


# Reason code: BIN.SUB.SPECIFIC[.QUALIFIER] grammar from T8.
ReasonCode = Annotated[
    str,
    Field(
        pattern=r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*){2,3}$",
        description="Reason code in BIN.SUB.SPECIFIC[.QUALIFIER] form per T1 §7.3.",
    ),
]

# Confidence is a probability in [0, 1].
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]

# Pixel bounding box: (x, y, w, h) at native source resolution.
BBox = Annotated[
    tuple[int, int, int, int],
    Field(description="(x, y, width, height) in pixels at the source image's native resolution."),
]


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """A single piece of evidence supporting (or contradicting) a rule outcome.

    Used by the C-EvidencePanel UI to show users *why* a rule passed or failed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str                                  # which field/rule consumed this
    source: EvidenceSource                         # ocr | layout | classifier | derived | metadata
    page_id: str | None = None                     # e.g. "front", "back", "neck", "wrap"
    panel: str | None = None                       # logical panel name from T4 layout
    image_uri: str | None = None                   # for the UI to crop/zoom
    bbox: BBox | None = None
    extracted_text: str | None = None              # raw OCR output
    normalized_text: str | None = None             # post NFKC/casefold/etc.
    matched_against_value: str | None = None       # the ExpectedValue that was compared
    match_kind: MatchKind = MatchKind.NONE
    match_score: Confidence | None = None          # for fuzzy / lookup
    confidence: Confidence                         # signal confidence (e.g. OCR conf)
    notes: str | None = None                       # engine breadcrumb


# ---------------------------------------------------------------------------
# FieldObservation (engine input #1 — what the upstream stack saw)
# ---------------------------------------------------------------------------


class FieldObservation(BaseModel):
    """Everything the upstream OCR + layout stack observed for a single field.

    A rule consumes one or more FieldObservations plus an ExpectedValue and
    produces a ValidationResult.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str                                  # e.g. "brand", "alcohol", "warning_block"
    beverage_class: BeverageClass
    observed_value: Any | None = None              # str, Decimal, dict, etc.
    evidence: tuple[Evidence, ...] = ()
    timestamp_ms: int | None = None
    upstream_meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence")
    @classmethod
    def _at_least_one_or_explicit_none(cls, v: tuple[Evidence, ...]) -> tuple[Evidence, ...]:
        # Empty evidence tuple is allowed (the validator may return INSUFFICIENT_EVIDENCE);
        # this hook exists so future strict modes can flip it.
        return v


# ---------------------------------------------------------------------------
# ExpectedValue (engine input #2 — what the rule + COLA say should be there)
# ---------------------------------------------------------------------------


class ExpectedValue(BaseModel):
    """The reference value(s) a rule compares against."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    value: Any | None = None                       # canonical expected scalar
    aliases: tuple[str, ...] = ()                  # acceptable alternate forms
    abv_labeled_pct: Decimal | None = None         # for ABV rules
    abv_actual_pct: Decimal | None = None          # if known (lab analysis)
    container_volume_ml: Decimal | None = None     # for §16.22(b) / §16.22(a)(4)
    parameters: dict[str, Any] = Field(default_factory=dict)
    source_cola: str | None = None                 # COLA / T2 reference id


# ---------------------------------------------------------------------------
# ValidationResult (engine output)
# ---------------------------------------------------------------------------


class EngineMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engine_version: str
    rule_pack_version: str
    rule_pack: str
    started_at_ms: int
    elapsed_ms: int


class ValidationResult(BaseModel):
    """The single, immutable outcome of evaluating one rule on one COLA."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    cfr_citation: str
    beverage_class: BeverageClass
    outcome: Outcome
    severity: Severity
    reason_code: ReasonCode | None = None          # populated on FAIL or warnings
    aggregated_confidence: Confidence              # min over evidence (T5 §Q5.7)
    evidence: tuple[Evidence, ...] = ()
    expected: ExpectedValue | None = None
    observed: FieldObservation | None = None
    message: str | None = None                     # human-readable explanation
    engine_meta: EngineMeta

    @field_validator("reason_code")
    @classmethod
    def _reason_code_required_on_fail(cls, v, info):  # pragma: no cover (illustrative)
        outcome = info.data.get("outcome")
        if outcome == Outcome.FAIL and v is None:
            raise ValueError("reason_code is required when outcome is FAIL")
        return v


# ---------------------------------------------------------------------------
# Rule definition shape (loaded from YAML; validated on engine startup)
# ---------------------------------------------------------------------------


class RuleDefinition(BaseModel):
    """A single rule as parsed from rules/**/*.yaml.

    The YAML loader (RuleLoader) builds this from each rule entry and refuses
    to start the engine on any schema violation (fail-closed per T3 §Q3.10).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    cfr_citation: str
    applies_to_classes: tuple[BeverageClass, ...]
    reason_code: ReasonCode
    severity: Severity
    match_policy: str
    validator: str                                  # primitive name, e.g. "abv_band"
    evidence_required: tuple[str, ...]
    confidence_floor: Confidence = 0.5
    parameters: dict[str, Any] = Field(default_factory=dict)
    tolerance: dict[str, Any] | None = None
    decision_table: dict[str, Any] | None = None
    decision_table_ref: str | None = None
    asset: dict[str, Any] | None = None
    effective_date: str                             # ISO-8601 date
    supersedes: tuple[str, ...] = ()
    rule_pack_version: str | None = None            # injected from pack header
    rule_pack: str | None = None                    # injected from pack header
    test_fixtures: tuple[str, ...]                  # at least one required
    disabled: bool = False
    notes: str | None = None

    @field_validator("test_fixtures")
    @classmethod
    def _at_least_one_fixture(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("Each rule must list at least one test_fixtures entry.")
        return v
```

### (d) RuleLoader spec — fail-closed schema validation on startup

```python
# src/engine/rule_loader.py
"""RuleLoader — loads YAML rule packs, validates against Pydantic schema,
and refuses to start the engine on any violation (T3 §Q3.10 fail-closed).

This module is a *spec*: it defines the loader's contract and the exact
error-handling behavior required of the implementation. The actual primitive
validators (equality_match, cpi_lookup, abv_band, etc.) are out of scope.
"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from pathlib import Path
from typing import Iterable

import yaml
from pydantic import ValidationError

from .contracts import RuleDefinition

LOG = logging.getLogger(__name__)


class RuleLoaderError(RuntimeError):
    """Fatal: engine must not start. T3 §Q3.10 fail-closed."""


# Whitelist of validator primitive names. New names must be added here AND
# implemented before a rule referencing them can pass loader validation.
_KNOWN_VALIDATORS = frozenset({
    "presence_check",
    "conditional_presence",
    "equality_match",
    "regex_match",
    "enumerated_match",
    "fuzzy_brand",
    "verbatim_hash",
    "abv_band",
    "abv_hard_floor",
    "abv_class_boundary_check",
    "alcohol_presence_or_table_designation",
    "type_size_min_lookup",
    "cpi_lookup",
    "heading_style_check",
    "contrast_ratio_check",
    "layout_isolation_check",
    "same_field_of_vision_check",
})

_REASON_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*){2,3}$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class RuleLoader:
    """Load and validate every YAML file under `rules_root`.

    Behavior contract:
      1. Walk `rules_root` recursively for *.yaml files.
      2. Parse each file with safe_load. Fail-closed on YAMLError.
      3. Each file MUST have top-level keys: rule_pack (str), rule_pack_version
         (semver), rules (list). Fail-closed otherwise.
      4. Each rule entry is parsed into a RuleDefinition via Pydantic v2.
         ValidationError is fail-closed.
      5. Cross-file checks (also fail-closed):
            a. rule_id is globally unique.
            b. validator name is in _KNOWN_VALIDATORS.
            c. reason_code matches the regex AND exists in the reason_codes
               registry (passed in via `reason_codes`).
            d. asset.path exists on disk and its sha256 matches asset.sha256_pin.
            e. decision_table_ref points at an existing file and parses.
            f. test_fixtures non-empty; every fixture id known to the S4 manifest
               (if a manifest is supplied; warning otherwise during MVP).
            g. supersedes references resolve to a known rule_id (or to a rule_id
               present in `retired_rules`).
            h. rule_pack_version is a valid semver.
      6. On success returns a frozenset[RuleDefinition] and logs a manifest.
    """

    def __init__(
        self,
        rules_root: Path,
        reason_codes: dict[str, dict],
        s4_fixture_ids: frozenset[str] | None = None,
        retired_rules: frozenset[str] = frozenset(),
        engine_supported_pack_range: tuple[str, str] = ("0.1.0", "0.2.0"),
    ) -> None:
        self.rules_root = rules_root
        self.reason_codes = reason_codes
        self.s4_fixture_ids = s4_fixture_ids
        self.retired_rules = retired_rules
        self.engine_supported_pack_range = engine_supported_pack_range

    def load(self) -> frozenset[RuleDefinition]:
        defs: list[RuleDefinition] = []
        seen_ids: set[str] = set()
        errors: list[str] = []

        for path in sorted(self.rules_root.rglob("*.yaml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                errors.append(f"{path}: YAML parse error: {e}")
                continue

            if not isinstance(raw, dict):
                errors.append(f"{path}: top level must be a mapping")
                continue

            pack = raw.get("rule_pack")
            pack_ver = raw.get("rule_pack_version")
            rules = raw.get("rules")

            if not isinstance(pack, str) or not pack:
                errors.append(f"{path}: missing or empty rule_pack")
            if not isinstance(pack_ver, str) or not _SEMVER_RE.match(pack_ver or ""):
                errors.append(f"{path}: rule_pack_version must be semver, got {pack_ver!r}")
            if not isinstance(rules, list):
                errors.append(f"{path}: rules must be a list")
                continue

            lo, hi = self.engine_supported_pack_range
            if pack_ver and not (lo <= pack_ver < hi):
                errors.append(
                    f"{path}: rule_pack_version {pack_ver!r} outside engine-supported "
                    f"range [{lo}, {hi})"
                )

            for entry in rules:
                if not isinstance(entry, dict):
                    errors.append(f"{path}: rule entry is not a mapping: {entry!r}")
                    continue
                entry = {**entry, "rule_pack": pack, "rule_pack_version": pack_ver}
                try:
                    rd = RuleDefinition.model_validate(entry)
                except ValidationError as e:
                    errors.append(f"{path}/{entry.get('rule_id','?')}: {e}")
                    continue
                # Cross-checks
                self._check_unique(rd, seen_ids, errors, path)
                self._check_validator(rd, errors, path)
                self._check_reason_code(rd, errors, path)
                self._check_asset(rd, errors, path)
                self._check_fixtures(rd, errors, path)
                self._check_supersedes(rd, seen_ids, errors, path)
                defs.append(rd)

        if errors:
            for e in errors:
                LOG.error("RuleLoader: %s", e)
            raise RuleLoaderError(
                f"Refusing to start: {len(errors)} rule-pack validation error(s). "
                "See log for details. (T3 §Q3.10 fail-closed.)"
            )

        LOG.info("RuleLoader: loaded %d rules from %s", len(defs), self.rules_root)
        return frozenset(defs)

    # --- cross-checks -------------------------------------------------------

    def _check_unique(self, rd, seen, errors, path):
        if rd.rule_id in seen:
            errors.append(f"{path}: duplicate rule_id {rd.rule_id!r}")
        else:
            seen.add(rd.rule_id)

    def _check_validator(self, rd, errors, path):
        if rd.validator not in _KNOWN_VALIDATORS:
            errors.append(
                f"{path}/{rd.rule_id}: unknown validator {rd.validator!r}; "
                f"add to _KNOWN_VALIDATORS and implement before referencing."
            )

    def _check_reason_code(self, rd, errors, path):
        if not _REASON_CODE_RE.match(rd.reason_code):
            errors.append(f"{path}/{rd.rule_id}: reason_code {rd.reason_code!r} fails grammar")
            return
        if rd.reason_code not in self.reason_codes:
            errors.append(
                f"{path}/{rd.rule_id}: reason_code {rd.reason_code!r} not in registry; "
                f"add to reason_codes.yaml first."
            )

    def _check_asset(self, rd, errors, path):
        if not rd.asset:
            return
        ap = rd.asset.get("path")
        pin = rd.asset.get("sha256_pin")
        if not ap or not pin:
            errors.append(f"{path}/{rd.rule_id}: asset must have path and sha256_pin")
            return
        full = (self.rules_root.parent / ap).resolve()
        if not full.exists():
            errors.append(f"{path}/{rd.rule_id}: asset file not found: {full}")
            return
        normalized = self._canonicalize_asset(full, rd.asset.get("normalization", []))
        actual = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if pin != actual:
            errors.append(
                f"{path}/{rd.rule_id}: asset hash drift; pinned={pin} actual={actual}"
            )

    @staticmethod
    def _canonicalize_asset(path: Path, ops: Iterable[str]) -> str:
        text = path.read_text(encoding="utf-8")
        for op in ops:
            if op == "nfkc":
                text = unicodedata.normalize("NFKC", text)
            elif op == "ascii_quotes":
                text = (text.replace("\u201c", '"').replace("\u201d", '"')
                            .replace("\u2018", "'").replace("\u2019", "'"))
            elif op == "collapse_whitespace":
                text = re.sub(r"\s+", " ", text)
            elif op == "strip_outer_ws":
                text = text.strip()
        return text

    def _check_fixtures(self, rd, errors, path):
        if self.s4_fixture_ids is None:
            return  # MVP: warn-only mode handled elsewhere
        unknown = [f for f in rd.test_fixtures if f not in self.s4_fixture_ids]
        if unknown:
            errors.append(
                f"{path}/{rd.rule_id}: test_fixtures not in S4 manifest: {unknown}"
            )

    def _check_supersedes(self, rd, seen, errors, path):
        for sid in rd.supersedes:
            if sid not in seen and sid not in self.retired_rules:
                errors.append(
                    f"{path}/{rd.rule_id}: supersedes unknown rule_id {sid!r}"
                )
```

**Failure modes the loader explicitly fails-closed on (matches §12 of Answer 12):**

1. YAML parse error on any rule file.
2. Top-level missing `rule_pack`, `rule_pack_version`, or `rules`.
3. `rule_pack_version` outside the engine-supported semver range.
4. Pydantic schema violation in any rule entry.
5. Duplicate `rule_id` across the tree.
6. Unknown `validator` primitive name.
7. `reason_code` failing grammar regex or not present in registry.
8. Asset file missing OR SHA-256 of canonicalized content not equal to `sha256_pin`.
9. Empty `test_fixtures`, or fixtures not in the [S4](./2026-09-15-eval-harness-design.md) manifest (when supplied).
10. `supersedes` pointing at unknown rule_id.

### (e) `reason_codes.yaml` — registry

```yaml
# Reason-code registry. Grammar: BIN.SUB.SPECIFIC[.QUALIFIER] (T8).
# Bins are taken from T1 §7.3 rejection-bin taxonomy.

version: "0.1.0"

bins:
  BRAND:           "Brand-name issues (presence, mismatch, misleading)"
  CLASS_TYPE:      "Class/type designation issues"
  ALCOHOL_CONTENT: "Alcohol-content statement issues"
  NAME_ADDRESS:    "Bottler/importer name & address issues"
  NET_CONTENTS:    "Net-contents statement issues"
  WARNING:         "Government health-warning issues (Part 16)"
  ALLERGEN:        "Allergen / sulfite / aspartame / FD&C Yellow #5"
  LEGIBILITY:      "Legibility / placement / field-of-vision"

codes:

  # --- BRAND ---------------------------------------------------------------
  BRAND.PRESENCE.MISSING:
    description: "Brand name absent from the brand label."
    cfr_anchors: ["27 CFR §4.32(a)(1)", "27 CFR §4.33", "27 CFR §5.63(a)", "27 CFR §5.64", "27 CFR §7.63(a)(1)", "27 CFR §7.64"]
    severity: reject

  # --- CLASS_TYPE ----------------------------------------------------------
  CLASS_TYPE.PRESENCE.MISSING:
    description: "Class/type designation absent or unrecognized."
    cfr_anchors: ["27 CFR §4.32(a)(2)", "27 CFR §4.34", "27 CFR §5.63(a)", "27 CFR §7.63(a)(2)"]
    severity: reject

  # --- ALCOHOL_CONTENT -----------------------------------------------------
  ALCOHOL_CONTENT.PRESENCE.MISSING:
    description: "Required alcohol-content statement is absent."
    cfr_anchors: ["27 CFR §4.32(b)(1)", "27 CFR §4.36(a)", "27 CFR §5.63(a)", "27 CFR §5.65(a)", "27 CFR §7.63(a)(3)"]
    severity: reject

  ALCOHOL_CONTENT.FORMAT.INVALID:
    description: "Alcohol-content statement does not match a permitted regulatory format."
    cfr_anchors: ["27 CFR §4.36(b)", "27 CFR §5.65(b)", "27 CFR §7.65(b)"]
    severity: reject

  ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND:
    description: "Actual alcohol content exceeds the regulatory tolerance band around the labeled value."
    cfr_anchors: ["27 CFR §4.36(b)(1)", "27 CFR §5.65(c)", "27 CFR §7.65(c)"]
    severity: reject

  ALCOHOL_CONTENT.TOLERANCE.CROSSES_CLASS_BOUNDARY:
    description: "Tolerance band, applied to the labeled ABV, crosses the 14% wine class boundary."
    cfr_anchors: ["27 CFR §4.36(c)"]
    severity: reject

  ALCOHOL_CONTENT.TOLERANCE.BELOW_HARD_FLOOR:
    description: "Actual ABV below the 0.5% hard floor for malt beverages labeled ≥0.5%."
    cfr_anchors: ["27 CFR §7.65(c)"]
    severity: reject

  # --- NAME_ADDRESS --------------------------------------------------------
  NAME_ADDRESS.PRESENCE.MISSING:
    description: "Bottler/distiller/importer name and address absent."
    cfr_anchors:
      - "27 CFR §4.32(a)(3)"
      - "27 CFR §4.35"
      - "27 CFR §5.63(b)(1)"
      - "27 CFR §5.66"
      - "27 CFR §5.67"
      - "27 CFR §5.68"
      - "27 CFR §7.63(a)(4)"
      - "27 CFR §7.66"
      - "27 CFR §7.67"
      - "27 CFR §7.68"
    severity: reject

  # --- NET_CONTENTS --------------------------------------------------------
  NET_CONTENTS.PRESENCE.MISSING:
    description: "Net-contents statement absent."
    cfr_anchors: ["27 CFR §4.32(b)(2)", "27 CFR §4.37", "27 CFR §5.63(b)(2)", "27 CFR §5.70", "27 CFR §7.63(a)(5)", "27 CFR §7.70"]
    severity: reject

  # --- WARNING (Part 16) ---------------------------------------------------
  WARNING.PRESENCE.MISSING:
    description: "Government health warning absent from the container."
    cfr_anchors: ["27 CFR §16.21"]
    severity: reject

  WARNING.VERBATIM.MISMATCH:
    description: "Health-warning text differs from the §16.21 verbatim string."
    cfr_anchors: ["27 CFR §16.21"]
    severity: reject

  WARNING.VERBATIM.HASH_DRIFT:
    description: "Verbatim asset file SHA-256 does not match the rule-pinned hash; engine refused to start."
    cfr_anchors: ["27 CFR §16.21"]
    severity: reject

  WARNING.STYLE.HEADING_NOT_BOLD_CAPS:
    description: "'GOVERNMENT WARNING' is not in bold capital letters, or the remainder is in bold."
    cfr_anchors: ["27 CFR §16.22(a)(2)"]
    severity: reject

  WARNING.LEGIBILITY.NO_CONTRAST:
    description: "Warning text does not appear on a contrasting background."
    cfr_anchors: ["27 CFR §16.22(a)(1)"]
    severity: reject

  WARNING.TYPE_SIZE.UNDER_MIN:
    description: "Warning text height below the §16.22(b) minimum for the container size class."
    cfr_anchors: ["27 CFR §16.22(b)"]
    severity: reject

  WARNING.TYPE_SIZE.CPI_EXCEEDED:
    description: "Warning text exceeds the §16.22(a)(4) maximum characters-per-inch for its height class."
    cfr_anchors: ["27 CFR §16.22(a)(4)"]
    severity: reject

  WARNING.PLACEMENT.NOT_SEPARATE:
    description: "Warning is not 'separate and apart from all other information'."
    cfr_anchors: ["27 CFR §16.21"]
    severity: reject

  # --- ALLERGEN ------------------------------------------------------------
  ALLERGEN.SULFITE.MISSING:
    description: "Sulfite declaration missing when total SO2 ≥ 10 ppm."
    cfr_anchors: ["27 CFR §4.32(e)"]
    severity: reject

  # --- LEGIBILITY ----------------------------------------------------------
  LEGIBILITY.FIELD_OF_VISION.SPLIT:
    description: "Mandatory information not within the same field of vision (spirits)."
    cfr_anchors: ["27 CFR §5.63(a)"]
    severity: reject
```

### (f) Rule-id → CFR → [S4](./2026-09-15-eval-harness-design.md) fixture mapping (one page)

| rule_id | CFR citation | [S4](./2026-09-15-eval-harness-design.md) fixtures (pass / fail) |
|---|---|---|
| common.warning.present | 27 CFR §16.21 | F-COMMON-WARN-PASS-01 / F-COMMON-WARN-MISSING-01 |
| common.warning.verbatim | 27 CFR §16.21 | F-COMMON-WARN-PASS-01 / F-COMMON-WARN-PARAPHRASE-01 |
| common.warning.heading_caps_bold | 27 CFR §16.22(a)(2) | F-COMMON-WARN-STYLE-PASS-01 / F-COMMON-WARN-STYLE-FAIL-01 |
| common.warning.contrasting_bg | 27 CFR §16.22(a)(1) | F-COMMON-WARN-CONTRAST-PASS-01 / F-COMMON-WARN-CONTRAST-FAIL-01 |
| common.warning.type_size_min | 27 CFR §16.22(b) | F-COMMON-TYPESIZE-PASS-01 / F-COMMON-TYPESIZE-UNDER1MM-01 |
| common.warning.cpi_max | 27 CFR §16.22(a)(4) | F-COMMON-CPI-PASS-01 / F-COMMON-CPI-FAIL-1MM-01, F-COMMON-CPI-FAIL-2MM-01 |
| common.warning.separate_apart | 27 CFR §16.21 | F-COMMON-WARN-ISOLATION-PASS-01 / F-COMMON-WARN-ISOLATION-FAIL-01 |
| wine.brand.present | 27 CFR §4.32(a)(1), §4.33 | F-WINE-BRAND-PASS-01, F-WINE-BRAND-FUZZY-01 / F-WINE-BRAND-MISSING-01 |
| wine.class_type.present | 27 CFR §4.32(a)(2), §4.34 | F-WINE-CLASS-PASS-01 / F-WINE-CLASS-MISSING-01 |
| wine.alcohol.present_or_table | 27 CFR §4.32(b)(1), §4.36(a) | F-WINE-ALC-PRESENT-01, F-WINE-ALC-TABLE-01 / F-WINE-ALC-MISSING-01 |
| wine.alcohol.format | 27 CFR §4.36(b)(1) | F-WINE-ALC-FORMAT-PASS-01 / F-WINE-ALC-FORMAT-FAIL-01 |
| wine.alcohol.tolerance_band | 27 CFR §4.36(b)(1) | F-WINE-ALC-12-PASS-01, F-WINE-ALC-18-PASS-01 / F-WINE-ALC-12-FAIL-LOW-01, F-WINE-ALC-18-FAIL-HIGH-01 |
| wine.alcohol.no_class_boundary_cross | 27 CFR §4.36(c) | — / F-WINE-ALC-13-5-LABEL-14-5-ACTUAL-FAIL-01, F-WINE-ALC-14-1-LABEL-13-9-ACTUAL-FAIL-01 |
| wine.name_address.present | 27 CFR §4.32(a)(3), §4.35 | F-WINE-NAMEADDR-PASS-01 / F-WINE-NAMEADDR-MISSING-01 |
| wine.net_contents.present | 27 CFR §4.32(b)(2), §4.37 | F-WINE-NET-PASS-01 / F-WINE-NET-MISSING-01 |
| wine.sulfite_declaration | 27 CFR §4.32(e) | F-WINE-SULFITE-PASS-01 / F-WINE-SULFITE-MISSING-01 |
| spirits.brand.present | 27 CFR §5.63(a), §5.64 | F-SPIRITS-BRAND-PASS-01 / F-SPIRITS-BRAND-MISSING-01 |
| spirits.class_type.present | 27 CFR §5.63(a), Part 5 Subpart I | F-SPIRITS-CLASS-PASS-01 / F-SPIRITS-CLASS-MISSING-01 |
| spirits.alcohol.present | 27 CFR §5.63(a), §5.65(a) | F-SPIRITS-ALC-PRESENT-01 / F-SPIRITS-ALC-MISSING-01 |
| spirits.alcohol.format | 27 CFR §5.65(b) | F-SPIRITS-ALC-FORMAT-PASS-01 / F-SPIRITS-ALC-FORMAT-FAIL-01 |
| spirits.alcohol.tolerance_band | 27 CFR §5.65(c) | F-SPIRITS-ALC-36-PASS-01 / F-SPIRITS-ALC-36-FAIL-LOW-01, F-SPIRITS-ALC-36-FAIL-HIGH-01 |
| spirits.same_field_of_vision | 27 CFR §5.63(a) | F-SPIRITS-FOV-PASS-01 / F-SPIRITS-FOV-FAIL-01 |
| spirits.name_address.present | 27 CFR §5.63(b)(1), §5.66/§5.67/§5.68 | F-SPIRITS-NAMEADDR-PASS-01 / F-SPIRITS-NAMEADDR-MISSING-01 |
| spirits.net_contents.present | 27 CFR §5.63(b)(2), §5.70 | F-SPIRITS-NET-PASS-01 / F-SPIRITS-NET-MISSING-01 |
| malt.brand.present | 27 CFR §7.63(a)(1), §7.64 | F-MALT-BRAND-PASS-01 / F-MALT-BRAND-MISSING-01 |
| malt.class_type.present | 27 CFR §7.63(a)(2), Part 7 Subpart I | F-MALT-CLASS-PASS-01 / F-MALT-CLASS-MISSING-01 |
| malt.alcohol.conditional_required | 27 CFR §7.63(a)(3) | F-MALT-ALC-FMB-PASS-01 / F-MALT-ALC-FMB-MISSING-01 |
| malt.alcohol.format | 27 CFR §7.65(b) | F-MALT-ALC-FORMAT-PASS-01 / F-MALT-ALC-FORMAT-FAIL-ABV-01 |
| malt.alcohol.tolerance_band | 27 CFR §7.65(c) | F-MALT-ALC-5-PASS-01 / F-MALT-ALC-5-FAIL-HIGH-01 |
| malt.alcohol.floor_05 | 27 CFR §7.65(c) | — / F-MALT-ALC-FLOOR-FAIL-01 |
| malt.name_address.present | 27 CFR §7.63(a)(4), §7.66/§7.67/§7.68 | F-MALT-NAMEADDR-PASS-01 / F-MALT-NAMEADDR-MISSING-01 |
| malt.net_contents.present | 27 CFR §7.63(a)(5), §7.70 | F-MALT-NET-PASS-01 / F-MALT-NET-MISSING-01 |

---

## Caveats

- **CFR text was verified against eCFR current content as of April 2026.** Parts 5 and 7 were renumbered by T.D. TTB-176 (87 FR 7579, Feb. 9, 2022); Part 4 was not. The §5.65(c) and §7.65(c) tolerance language and the §5.63 / §7.63 mandatory-information lists reflect that modernization. Part 16 has not been amended materially since T.D. TTB-91 (76 FR 5477, Feb. 1, 2011).
- **Surgeon General cancer-warning advisory (Jan. 2025):** the U.S. Surgeon General called for Congress to add a cancer warning to alcohol labels; that proposal would require statutory action and is **not** part of 27 CFR §16.21 today. The verbatim string in deliverable (a) reflects the *currently enforceable* §16.21 text, not the proposal. If/when Congress amends ABLA, a new rule-pack version (1.0.0+) will replace `common.warning.verbatim` and the asset file's hash.
- **Cpi table extrapolation:** §16.22(a)(4) enumerates only three (height, cpi) pairs. The decision-table policy `on_between_keys: round_up_to_next_key` is the *strictest* defensible interpretation (1.5 mm → 25 cpi cap, not interpolated to ~32). It is one defensible policy among several; TTB has not published guidance for fractional millimeter measurements, so the choice was made conservatively. Document this in S6 review.
- **Wine §4.36(b) range form (Alcohol __% to __% by volume):** the MVP's `wine.alcohol.tolerance_band` rule covers only the *direct* statement form. The range form (with §4.36(b)(2) range limits of 2 pp >14% / 3 pp ≤14%) is not in the MVP scope; add as `wine.alcohol.range_band` in a future pack.
- **Wine §4.36(b) sub-7% products:** under §24.257(a)(3), wines with <7% ABV stated on the label use a separate ±0.75 pp tolerance under Part 24, not §4.36; that is a Part 24/IRC labeling regime distinct from the FAA-Act regime in Part 4. The MVP's rule pack does not currently cover sub-7% wines; add only if [S4](./2026-09-15-eval-harness-design.md) fixtures require it.
- **§4.36 "tolerance" vs "range":** the eCFR text reads "a tolerance of 1 percent" (per the eCFR snippet); historical/some commentary phrases this as "1 percentage point". TTB's own consumer-facing guidance pages use "percentage points", consistent with [T9](./2026-09-15-verification-targets-research.md) §1's `pp` notation. The YAML uses `pp` to disambiguate.
- **`asset.sha256_pin` is a placeholder.** It must be computed at repo bootstrap from the canonicalized bytes of `assets/warnings/govt_warning_16_21.txt` (UTF-8, ASCII quotes, NFKC, single-spaced, trimmed) and committed. Until then, `RuleLoader` will fail-closed at startup — which is the correct behavior.
- **Validator names are placeholders for primitives, not implementations.** Per the user's CRITICAL constraint, none of the named primitives (`equality_match`, `cpi_lookup`, `abv_band`, etc.) are implemented in this deliverable; they exist as named handles in the YAML and as a whitelist in `RuleLoader._KNOWN_VALIDATORS`. Implementations are out of scope for this document.
- **`fuzzy_threshold: 0.85`** is normalized to the [0,1] interval; RapidFuzz returns 0–100, so the implementing primitive must divide by 100 (or compare against 85). Keep this normalization consistent across the codebase.