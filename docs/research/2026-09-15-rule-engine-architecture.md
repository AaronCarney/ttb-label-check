# Validation / Rule Engine Architecture

Filed 2026-09-15.

> AI-Powered TTB Alcohol Label Verification Prototype
> Scope: 27 CFR Parts 4 (wine), 5 (distilled spirits), 7 (malt beverages), and 16 (health warning).
> Anchor decisions: the deterministic core (rules decide, the model does not), substitutability (cloud/on-prem parity), per-field match policies (each field declares its own), the spirits ABV tolerance (regulatory tolerances are data, not constants), rejection reasoning (full evidence on every fail/needs-review), 5-second SLA.
>
> This document answers Q3.1–Q3.10 in order. Cross-topic synthesis questions (X-1 end-to-end time budget, X-2 component decision tree, X-3 production-readiness gaps, X-4 rules-as-data vs. code) are deliberately deferred and are **not** answered here.

---

## Q3.1 — Rule representation patterns

The five candidate representations are evaluated against four properties that matter for a federal regulatory verifier: **maintainability** (how easily a non-engineer compliance SME can read/edit a rule), **auditability** (can you produce a human-and-machine-traceable record of *which rule fired with what evidence*), **performance** (fits inside a 100–300 ms slice of the 5-s SLA), and **TTB-style nuance** (tolerance windows, fuzzy matching, format/typography checks).

| Option | Maintainability | Auditability | Performance | TTB-Nuance Fit | Notes |
|---|---|---|---|---|---|
| **Hard-coded validators** (one Python function per field) | Low — every rule change is a code change and PR cycle | Medium — git history is the audit trail; runtime evidence has to be hand-built | High — pure Python, no interpreter overhead | High — full host language available | The classic "imperative business logic" anti-pattern Fowler warns about for rule-heavy domains (Fowler, *Should I use a Rules Engine?*, martinfowler.com). |
| **Rules-as-data** (YAML/JSON consumed by a generic engine) | High — SMEs edit YAML; rules diff cleanly | High — the rule document *is* the artifact; version it, sign it, attach to audit log (Fowler, *Refactoring to an Adaptive Model*, 2015) | High when interpreter is small; libraries like `json-rules-engine` (CacheControl) and Cerberus (Iarocci) are µs-class per rule | Medium-High — needs typed extensions for tolerance/fuzzy/format | YAML/JSON is what we already need for per-field match policies (match policy declared, not buried in code). |
| **Decision tables (DMN-style)** | Very high for tabular rules (e.g., the §16.22(a)(4) cpi table; the wine ABV tolerance matrix) | Very high — DMN tables are themselves the executable spec (OMG DMN 1.5, June 2023; Drools DMN docs) | High — Drools/Kogito compile DMN to bytecode; commonly sub-ms per evaluation | Medium — DMN FEEL handles numeric tolerance well, weaker for OCR-shaped ambiguity | Heavy tooling footprint (Drools/Kogito on JVM, Camunda) is friction for a Python prototype; Trisotech and Camunda offer DMN engines but cross-runtime serialization is the value. |
| **Custom DSL (ANTLR/PEG)** | Medium — a clean DSL is readable, but writing one is a major project (Fowler, *Domain-Specific Languages*, 2010) | Medium — the DSL source is auditable, but the parser/compiler is a trust boundary | High once compiled | High — total expressive control | Over-engineered for an 18-rejection-bin, ~25-rule prototype. Build only after the rule shape stabilizes. |
| **Hybrid (declarative for simple, code for complex)** | High — simple rules in YAML, "escape hatch" Python validator for the genuinely irregular ones (cf. Easy Rules, j-easy, and Clara Rules' Clojure approach) | High — both halves traceable | High | High — best of both | Aligns with Fowler's recommendation to keep rule engines "embedded into larger systems" rather than as the whole system. |

**Recommendation: Hybrid, weighted toward rules-as-data (YAML).**

Rationale specific to this project:

1. **Per-field match policies already require an explicit declaration per field**, which is rules-as-data by another name. Treating the entire rule set as YAML simply finishes that job.
2. **The spirits ABV tolerance requires tolerance values to live in the rule set, not in code.** Putting `0.3 pp`, `1.0 pp`, `1.5 pp`, `0.5%` floor, etc. ([T1](./2026-09-15-ttb-regulatory-framework.md)) in YAML keys is exactly what TTB regulatory updates (e.g., T.D. TTB‑158 changing spirits tolerance from ±0.15 to ±0.3 pp) demand: a content edit, not a deploy.
3. **Rejection reasoning requires structured evidence on every disposition.** A YAML rule with a stable `rule_id`, `cfr_citation`, and `reason_code` field becomes the audit-trail anchor automatically.
4. **The cardinal §16.22(a)(4) cpi table (1mm→40, 2mm→25, 3mm→12) is intrinsically a decision table.** It should live as a DMN-shaped decision-table block inside the YAML, with explicit "no interpolation" semantics.
5. **A small subset of rules genuinely need code** — the warning-text format check (caps + bold + verbatim string + line-break tolerance) is not cleanly expressible as data. These rules are referenced by name from YAML (`validator: warning_text_format_v1`) so the YAML still owns the policy choice; the Python validator only owns the *mechanism*.
6. **DMN/Drools is rejected as the engine** because it imposes a JVM dependency, complicates substitutability for firewall-friendly federal deployment, and the rule volume (~25 rules per class × 3 classes plus health warning) does not justify Rete/PHREAK forward-chaining. A simple condition–action interpreter (cf. Easy Rules, json-rules-engine) is sufficient and avoids the implicit-flow debugging hazard Fowler highlights.
7. **A custom DSL is rejected** as premature optimization for a take-home prototype.

The YAML rule set is then the single regulatory source of truth: human-readable, diff-able, signable, versionable (Q3.8), and the deterministic rule core is the reference interpreter.

---

## Q3.2 — Validator interface specification

A validator is the smallest unit that the rule engine invokes. It consumes a `FieldObservation` (what was extracted from the label) plus an `ExpectedValue` (what the application data says) and produces a `ValidationResult`. The contract below is language-agnostic but illustrated in Pydantic v2 (Pydantic Docs, *Validators*, current; functional `BeforeValidator`/`AfterValidator`/`WrapValidator`/`PlainValidator` patterns) because that is the project's likely Python stack.

### Input contract

```python
from decimal import Decimal
from typing import Literal, Optional, Annotated
from pydantic import BaseModel, Field

class BoundingBox(BaseModel):
    # Normalized (0..1) per AWS Textract convention; or pixel-space if T4 emits pixel.
    left: float; top: float; width: float; height: float
    coord_space: Literal["normalized", "pixel"] = "normalized"

class FieldObservation(BaseModel):
    """What T4 (OCR/vision) extracted from the label image for one field."""
    field_name: str                               # e.g. "brand_name", "abv_statement"
    raw_text: Optional[str]                       # exact glyph string as OCR returned it
    normalized_text: Optional[str]                # NFC + lower + stripped, see Q3.3
    numeric_value: Optional[Decimal]              # parsed if the field is numeric (ABV, vol)
    ocr_confidence: float = Field(ge=0.0, le=1.0) # per-field min word confidence
    bbox: Optional[BoundingBox]
    candidates: list[str] = []                    # alternative reads if OCR was ambiguous
    font_attrs: Optional["FontAttrs"] = None      # bold/italic/cpi/measured height (mm)
    image_uri: str                                # for evidence packaging

class FontAttrs(BaseModel):
    is_bold: Optional[bool]
    is_italic: Optional[bool]
    measured_x_height_mm: Optional[Decimal]
    measured_cpi: Optional[Decimal]               # characters per inch
    contrast_ratio: Optional[Decimal]             # for legibility check
    detector_version: str                         # who measured this and how

class ApplicationField(BaseModel):
    """What the COLA application submission claims."""
    field_name: str
    expected_value: Optional[str | Decimal | bool]
    declared_class: Literal["wine", "spirits", "malt"]
    container_size_ml: Optional[Decimal]
    is_import: bool = False
    vintage_claimed: bool = False
    appellation_claimed: bool = False

class ValidatorContext(BaseModel):
    """Cross-field state passed through the engine for composition."""
    rule_set_version: str                         # SemVer (Q3.8)
    cfr_effective_date: str                       # ISO date, lookup-time anchor
    application: dict[str, ApplicationField]
    observations: dict[str, FieldObservation]
    upstream_results: dict[str, "ValidationResult"]   # for dependent validators
```

### Output contract

```python
class Evidence(BaseModel):
    extracted_text: Optional[str]
    expected_value: Optional[str | Decimal | bool]
    bbox: Optional[BoundingBox]
    image_uri: Optional[str]
    ocr_confidence: Optional[float]
    measurements: dict[str, Decimal] = {}         # e.g. {"x_height_mm": 1.6, "cpi": 28}

class ValidationResult(BaseModel):
    rule_id: str                                  # stable, e.g. "WARN-TXT-EXACT-001"
    field_name: str
    disposition: Literal["pass", "fail", "needs_review", "not_applicable"]
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: Literal["high", "medium", "low"]
    reason_code: Optional[str]                    # hierarchical code, see Q3.6
    human_message: Optional[str]                  # template-rendered
    cfr_citation: Optional[str]                   # e.g. "27 CFR §5.65(b)"
    cfr_url: Optional[str]                        # eCFR deep link
    severity: Literal["blocking", "needs_review", "advisory"] = "blocking"
    evidence: Evidence
    match_policy_used: str                        # "exact" | "tolerance" | "fuzzy" | "format"
    elapsed_ms: float
```

This shape borrows from established API-error patterns: **RFC 9457 "Problem Details for HTTP APIs"** (Nottingham, Wilde, Dalal, July 2023; obsoletes RFC 7807) — `type`/`title`/`status`/`detail`/`instance` map onto `reason_code`/`human_message`/`disposition`/`evidence`/`rule_id`. **HL7 FHIR `OperationOutcome`** (R4/R5) provides the same `severity` × `code` × `details` × `diagnostics` × `location` shape used by national clinical APIs.

### How a validator declares its match policy

The match policy is **declared in the rule**, not chosen in the validator (per-field match policies). YAML excerpt:

```yaml
- rule_id: BRAND-NAME-MATCH-001
  field: brand_name
  cfr_citation: "27 CFR §4.33(b)"
  match_policy:
    type: fuzzy
    pre_normalize: [nfkc, casefold, strip_punct, normalize_ampersand, drop_leading_the]
    scorer: rapidfuzz.token_set_ratio
    pass_threshold: 0.92
    needs_review_threshold: 0.85
  reason_code_on_fail: BRAND.NAME.MISMATCH

- rule_id: SPIRITS-ABV-TOL-001
  field: abv
  applies_when: { class: spirits }
  cfr_citation: "27 CFR §5.65(b)-(c)"
  match_policy:
    type: tolerance
    tolerance_pp: 0.3
    arithmetic: decimal
  reason_code_on_fail: ABV.SPIRITS.OUT_OF_TOLERANCE
```

The Python validator class implements only the mechanism; the policy parameters are injected at build time. This is structurally the **JSR-380 / Jakarta Bean Validation 2.0 constraint composition** model (beanvalidation.org, 2.0/3.0 spec): a constraint annotation declares parameters; the `ConstraintValidator<A,T>` implements behavior; and constraint composition is achieved by annotating one constraint with others.

### Composition (one validator's input depends on another)

Two complementary mechanisms:

1. **Logical composition (AND/OR/XOR)** — modeled on **JSON Schema 2020-12** (`allOf`, `anyOf`, `oneOf`, `not`; json-schema.org *Combining Schemas*) and **Hibernate Validator's** composed constraints. A `WarningLegibilityRule` composes:

```yaml
- rule_id: WARN-LEGIBILITY-001
  composition: allOf
  rules:
    - WARN-FONT-MIN-HEIGHT
    - WARN-FONT-MAX-CPI
    - WARN-FONT-CAPS-BOLD
    - WARN-FONT-CONTRAST
```

2. **Dependency / fact composition** — modeled on `json-rules-engine`'s "almanac" (CacheControl/json-rules-engine docs), Drools' "agenda groups" / "rule flow groups" (Drools docs, ch. 7), and Pydantic v2 `model_validator(mode="after")`. The engine evaluates rules in topological order over their `requires:` edges:

```yaml
- rule_id: WARN-FONT-MIN-HEIGHT
  field: warning_x_height_mm
  requires:
    - CONTAINER-SIZE-LOOKUP-001    # produces effective container_size_ml
  match_policy:
    type: tolerance_lookup
    table: warning_min_height_by_container
    arithmetic: decimal
```

`CONTAINER-SIZE-LOOKUP-001` resolves the container size (from application data, validated against the bottle's declared size); `WARN-FONT-MIN-HEIGHT` then reads it through `ctx.upstream_results["CONTAINER-SIZE-LOOKUP-001"]`. A cycle-detection step at engine load-time refuses to start with a cyclic rule graph (engine failure mode, Q3.10).

Equivalent fluent-API shape (cf. **FluentValidation** in .NET) is also possible:

```python
warning_legibility = (
    Rule("WARN-LEGIBILITY-001")
      .requires("CONTAINER-SIZE-LOOKUP-001")
      .all_of(min_height, max_cpi, caps_bold, contrast)
      .cite("27 CFR §16.22(a)(2)–(4)")
)
```

The YAML is canonical; the fluent form is for engineer tests.

---

## Q3.3 — Match policy implementations

Per-field match policies say each field declares one of four policies. The engine implements each as a pluggable strategy.

### 3.3.1 Exact match

"Exact" is never byte-equality on OCR output; it is **canonical equality after a declared normalization pipeline**.

Mandated normalization pipeline (declared per field in the rule):

| Step | Spec | Default for label text fields |
|---|---|---|
| Unicode normalization | **UAX #15 (Unicode TR15)**, NFC vs NFKC. NFC preserves canonical equivalents; NFKC additionally folds compatibility equivalents (`ﬃ`→`ffi`, full-width digits→ASCII, superscripts) (unicode.org/reports/tr15). | **NFKC** for label text (we want `ﬁne` to compare equal to `fine`); **NFC only** for the verbatim §16.21 warning string, where the regulation's text is itself canonical and we should not silently fold compatibility variants. |
| Case folding | `str.casefold()` (Python stdlib `unicodedata`); per **UAX #31** identifier rules and **UAX #44** general category, casefolding is the safe lowercase for comparison. | Applied unless the rule is case-sensitive (e.g., `GOVERNMENT WARNING` caps check). |
| Whitespace | Collapse runs of `\s` (Unicode whitespace per `\p{Z}` + `\t\n\r\f\v`) to single space; strip leading/trailing. | Always for prose; **preserved** for the warning's two numbered sentences when verifying line/paragraph structure. |
| Smart quotes / dashes | Map U+2018/U+2019 → `'`, U+201C/U+201D → `"`, U+2013/U+2014 → `-`. | Applied for fuzzy/exact text fields; not applied to the warning verbatim check. |
| Ligatures | Handled by NFKC. | — |
| Zero-width chars | Strip U+200B (ZWSP), U+200C (ZWNJ), U+200D (ZWJ), U+FEFF (BOM). | Always — these are commonly injected by upstream OCR/PDF pipelines. |
| Line-break handling | Normalize `\r\n` and `\r` to `\n`; for warning verbatim check, allow the regulation's two sentences to span lines (the regulation does not mandate single-line presentation). | Per-rule. |

Python primitives used: `unicodedata.normalize("NFKC", s)`, `str.casefold()`, `re.sub(r"\s+", " ", s).strip()`. Reference: **Unicode TR15** (current draft tr15-58 / formal NFC/NFKC definitions); Python `unicodedata` library docs.

Engine wiring: each rule names its pipeline by an ordered list of step IDs (e.g. `pre_normalize: [strip_zwsp, nfkc, casefold, collapse_ws, smart_quotes_to_ascii]`). The pipeline is itself versioned.

### 3.3.2 Tolerance match

ABV is the canonical example. Key implementation choices:

1. **Use `decimal.Decimal`, not `float`.** Python `decimal` module (Python 3 docs) provides correctly-rounded fixed-point arithmetic per the IBM General Decimal Arithmetic spec, avoiding the well-known `0.1 + 0.2 == 0.3` failure modes that would silently shift a 0.30 boundary.
2. **Compare with a declared tolerance**, not `math.isclose()`'s relative tolerance, because the regulation specifies an *absolute* tolerance in percentage points.
3. **Encode floors and class boundaries explicitly** — they cannot be expressed as a single tolerance window.

Rule encoding for the [T1](./2026-09-15-ttb-regulatory-framework.md) tolerance values:

```yaml
- rule_id: ABV-SPIRITS-TOL
  applies_when: { class: spirits }
  cfr_citation: "27 CFR §5.65(b)-(c)"
  match_policy:
    type: tolerance
    tolerance_pp: "0.3"             # T.D. TTB-158 raised from 0.15
    arithmetic: decimal

- rule_id: ABV-WINE-TOL
  applies_when: { class: wine }
  cfr_citation: "27 CFR §4.36(b)(1)-(c)"
  match_policy:
    type: piecewise_tolerance
    arithmetic: decimal
    bands:
      - when: "labeled_abv > 14.0"
        tolerance_pp: "1.0"
      - when: "7.0 <= labeled_abv <= 14.0"
        tolerance_pp: "1.5"
      - when: "labeled_abv < 7.0"
        tolerance_pp: "0.75"
    hard_constraints:
      - "actual_abv and labeled_abv must lie on the same side of 14.0"
        # the 14% wine-class line cannot be crossed regardless of tolerance

- rule_id: ABV-MALT-TOL
  applies_when: { class: malt }
  cfr_citation: "27 CFR §7.65(c)"
  match_policy:
    type: tolerance
    tolerance_pp: "0.3"
    arithmetic: decimal
    hard_constraints:
      - "actual_abv >= 0.5"                       # cannot cross floor
      - "if labeled_descriptor in {'low alcohol','reduced alcohol'}: actual_abv < 2.5"
```

Reference comparator (pseudocode):

```python
from decimal import Decimal
def tolerance_pass(actual: Decimal, expected: Decimal, tol_pp: Decimal) -> bool:
    return abs(actual - expected) <= tol_pp
```

Hard constraints are evaluated first; if violated, the result is `fail` regardless of tolerance match.

### 3.3.3 Fuzzy match

See Q3.4 for the algorithm and threshold; engine integration is identical to other policies — it returns a `score ∈ [0,1]` plus the match band, and the rule's declared `pass_threshold` and `needs_review_threshold` partition outcomes.

### 3.3.4 Format match (caps + bold + size + cpi + contrast)

The validator's responsibility is **policy** — given measurements, decide pass/fail. [T4](./2026-09-15-ocr-vision-architecture.md) (OCR/vision) is responsible for **measurement**. The contract between them must be explicit.

**[T4](./2026-09-15-ocr-vision-architecture.md) must emit, per warning text region:**

- The `LINE`/`WORD` block list with bounding boxes — e.g., AWS Textract `Block`/`Geometry`/`BoundingBox` (Textract API docs), Tesseract hOCR `ocrx_word` with `bbox` and `x_wconf` (UB Mannheim hOCR spec; rOpenSci tesseract docs), Google Document AI `tokens[].layout`.
- Per-word `is_bold: bool|null` and `is_italic: bool|null`. Tesseract sets the `bold` attribute in hOCR `ocr_line`/`ocrx_word` `title` when LSTM detects bold; Document AI returns `style.bold`; Textract does not natively return bold — when using Textract, we use a downstream heuristic (stroke width / thickness ratio over a font-detection model) and tag results with `detector_version` so the rule can require a minimum detector confidence.
- Measured `x_height_mm` derived from bbox height in pixels × pixel-size-in-mm (which requires DPI from EXIF or the upload UI; if absent the engine must fail with `ENGINE.MEASUREMENT.MISSING_DPI`, Q3.10).
- Measured `cpi` derived as `(num_chars / line_width_px) * px_per_inch`.
- Measured `contrast_ratio` per WCAG 2.1 relative luminance.

**The engine then:**

- For caps: requires `raw_text("GOVERNMENT WARNING") == raw_text` after stripping non-letters, AND every letter in that span has `Unicode_Category` `Lu`. (No reliance on the OCR engine's own case detection; we look at code points.)
- For bold: requires `is_bold == True` for every word in `"GOVERNMENT WARNING"` span, using the rule's required minimum detector confidence.
- For min height & cpi: looks up the **§16.22(a)(4) cardinal table** (1mm→40 cpi max; 2mm→25; 3mm→12) — encoded as a DMN-style decision table (FEEL `closed` semantics, no interpolation):

```yaml
warning_min_height_x_height_mm:
  cardinal_table:                 # closed: no interpolation
    - container_max_ml: 237
      min_x_height_mm: "1.0"
      max_cpi: 40
    - container_max_ml: 1000
      min_x_height_mm: "2.0"
      max_cpi: 25
    - container_max_ml: ~          # > 1L
      min_x_height_mm: "3.0"
      max_cpi: 12
```

The split of responsibilities is therefore: **[T4](./2026-09-15-ocr-vision-architecture.md) owns physical measurement and OCR confidence; the engine owns regulatory thresholds, table lookups, pass/fail decisions, and CFR citations**. This division satisfies the deterministic core (the rule engine decides) and lets us swap [T4](./2026-09-15-ocr-vision-architecture.md) vendors without touching rule policy.

---

## Q3.4 — Fuzzy matching algorithm and threshold for brand names

### 3.4.1 Survey

| Family | Representative algorithms | Strengths | Weaknesses for brand names |
|---|---|---|---|
| Edit distance | **Levenshtein** (V. I. Levenshtein, "Binary codes capable of correcting deletions, insertions and reversals," *Soviet Physics Doklady* 10(8):707–710, 1966); **Damerau–Levenshtein** (F. J. Damerau, "A technique for computer detection and correction of spelling errors," *CACM* 7(3):171–176, 1964 — adds adjacent transposition); **Jaro** (M. A. Jaro, "Advances in record linkage methodology as applied to matching the 1985 Census of Tampa, FL," *JASA* 84(406):414–420, 1989); **Jaro–Winkler** (W. E. Winkler, "String comparator metrics and enhanced decision rules in the Fellegi-Sunter model of record linkage," *Proc. ASA Survey Research Methods*, 1990 — boosts shared-prefix scores) | Mature, fast, well-understood | Operate at character level, blind to word reordering ("Stone's Throw Vineyards" vs "Vineyards, Stone's Throw") |
| Token-based ratios | **RapidFuzz** `fuzz.ratio`, `partial_ratio`, `token_sort_ratio`, `token_set_ratio`, `WRatio` (RapidFuzz docs, github.com/rapidfuzz; descended from FuzzyWuzzy but MIT-licensed and Levenshtein-correct) | Robust to word order; `token_set_ratio` returns 100 when one string's tokens are a subset of the other | Loses information about word order; can over-match short stop-word-heavy names |
| Embedding-based | **Sentence-BERT** (Reimers & Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," EMNLP 2019); character-CNN / fastText subword; OpenAI/Cohere embeddings | Handles semantics ("Eagle Crest" ≈ "Eagle's Peak"?), multilingual, robust to misspellings | Requires inference (~10–100 ms with cloud, much more on-prem CPU); cost; over-matches semantically related but legally distinct brands; calibration is unknown |
| Rule-augmented exact | NFKC + `casefold` (per **UAX #31** identifier-style folding); strip punctuation; normalize possessives (`'s`/`’s` → empty or unified); normalize `&` ↔ `and`; drop leading `THE `; collapse whitespace | Cheap, deterministic, explainable, matches how humans read brand names | Only catches near-typographic variants |

Authoritative coverage of these methods is in Christen, *Data Matching: Concepts and Techniques for Record Linkage, Entity Resolution, and Duplicate Detection*, Springer, 2012; and Köpcke, Thor & Rahm, "Evaluation of entity resolution approaches on real-world match problems," *PVLDB* 3(1):484–493, 2010, which finds that token-based and learning-based methods consistently outperform pure edit-distance on real product data — directly relevant to brand names.

### 3.4.2 Concrete behavior on the canonical case

`"STONE'S THROW"` vs `"Stone's Throw"`:

- **Pure Levenshtein**: distance = 11 (case differs in 11 letters), normalized similarity ≈ 0.15 — would **fail** as a brand match.
- **Jaro–Winkler** (case-sensitive): low — same problem.
- **`fuzz.ratio` after `default_process`** (RapidFuzz's lowercase + non-alphanumeric strip): 100 — passes.
- **`token_set_ratio` after `default_process`**: 100 — passes.
- **Rule-augmented exact** (NFKC + casefold + strip punct → both become `stones throw`): equal — passes.

Adversarial cases (after the rule-augmented preprocessor: NFKC, casefold, strip punctuation, normalize `&`↔`and`, drop leading `the`, collapse whitespace):

| Pair (post-norm) | Levenshtein | `token_set_ratio` | Sentence-BERT cosine | Recommended outcome |
|---|---|---|---|---|
| `stones throw` vs `stones throw` | 1.00 | 100 | ~1.00 | **pass** (exact after norm) |
| `stones throw` vs `stone throw` | 0.92 | 95.6 | ~0.97 | **needs_review** — possessive removed; may be the same brand |
| `stones throw` vs `stoned throw` | 0.92 | 95.6 | ~0.93 | **needs_review** — single-letter typo, agent should adjudicate |
| `stones throw` vs `stone throw vineyards` | 0.61 | 100 (subset!) | ~0.85 | **needs_review, not pass** — `token_set_ratio` over-matches; we apply a length-ratio guard |
| `stones throw` vs `mountain ridge` | 0.07 | 28.6 | ~0.30 | **fail** |

The `token_set_ratio` subset behavior (RapidFuzz docs explicitly note "returns 100.0 if one string is a subset of the other") is the dominant failure mode for brand names. We mitigate it with a length ratio guard: if `token_set_ratio == 100` but `min(len) / max(len) < 0.6`, the score is downgraded to `WRatio` (which weights token-sort/token-set/partial differently and re-penalizes length disparity).

### 3.4.3 Recommended layered pipeline

```
INPUT: extracted_brand, application_brand
  ↓
1. Rule-augmented normalize (both):
     NFKC → casefold → strip "the " prefix → strip non-alphanumeric except space →
     replace " & " with " and " → collapse spaces → trim
  ↓
2. If normalized strings equal → return PASS, score 1.00, policy "exact-after-norm"
  ↓
3. Compute s = max(fuzz.token_set_ratio, fuzz.WRatio) / 100
     length_guard = min(len) / max(len)
     if length_guard < 0.6: s = min(s, fuzz.WRatio / 100)
  ↓
4. Decision:
     s ≥ 0.92 → PASS (high)
     0.85 ≤ s < 0.92 → NEEDS_REVIEW (medium); attach top-3 candidates;
                         optional: AI tiebreak (LLM judge with restricted prompt
                         that decides "same brand y/n" — the deterministic core allows AI to
                         resolve ambiguity, not to decide pass/fail; therefore
                         the LLM may only narrow needs_review to a strong
                         needs_review or escalate, never flip to PASS unsupervised)
     s < 0.85 → FAIL
```

### 3.4.4 Justifying the 0.85/0.92 thresholds

- 0.85 is consistent with what RapidFuzz/FuzzyWuzzy practitioner literature uses as a "probably the same" cutoff for short product names; Köpcke/Thor/Rahm (2010) report F1-optimal thresholds for token-based scorers in the 0.80–0.90 range across real-world product datasets.
- We bias **upward** (0.92 for pass, not 0.85) because TTB rejection asymmetry penalizes false approval more than false rejection: a wrongly-approved label can ship; a wrongly-flagged label costs a second human review (Q3.5). The agent absorbs the false-positive cost; the public absorbs the false-negative cost.
- The ~7-point band [0.85, 0.92) is reserved for `needs_review` so a human always sees borderline cases.
- Sentence-BERT/embedding scorers are **not** in the default pipeline because (a) they lack a calibrated threshold for legal-name matching, (b) they introduce a model dependency that complicates on-prem deployment, and (c) Reimers & Gurevych (2019) explicitly tune SBERT for sentence-level STS, not short-name matching. We keep them as an optional escalator inside the `needs_review` band when the agent requests an AI tiebreak.

---

## Q3.5 — Confidence-scoring methodology

### 3.5.1 Sources of uncertainty

A validator's confidence reflects the joint likelihood that **the extracted observation is correct** AND **the matching decision is correct**:

1. **Per-word OCR confidence** — Tesseract `x_wconf` (0–100) per word in hOCR (rOpenSci/tesseract docs); AWS Textract `Confidence` per `Block` (Textract API docs); Google Document AI `confidence` per token.
2. **Field-level OCR confidence** — minimum or 5th-percentile word confidence over the field's bounding region (minimum is more conservative; 5th-percentile is more robust to a single bad glyph).
3. **Match score** — fuzzy ratio in `[0,1]`, tolerance distance scaled to `[0,1]`, format check booleans.
4. **Ambiguity** — if [T4](./2026-09-15-ocr-vision-architecture.md) returned multiple plausible reads (`candidates`), the spread between top-1 and top-2 is a structural uncertainty signal.
5. **Missingness** — if either application data or extracted observation is absent, the rule's outcome should be `needs_review` (not `fail`) with `reason_code: ENGINE.INPUT.MISSING`.

### 3.5.2 Combining confidences across the pipeline

Three mainstream options in the probabilistic-combination literature:

| Combination | Formula | Pro | Con |
|---|---|---|---|
| Multiplicative (independence assumption) | `c = c_ocr × c_match` | Standard if signals are conditionally independent | Compounds quickly: 0.9 × 0.9 = 0.81 |
| Minimum (weakest-link / Zadeh fuzzy AND) | `c = min(c_ocr, c_match)` | Preserves the worst signal as the bottleneck | Discards information |
| Learned (Platt scaling / logistic) | `c = σ(w₀ + w₁·c_ocr + w₂·c_match + …)` | Calibrated to ground truth | Needs labeled data; overkill for prototype |

**Recommendation for the prototype: minimum-with-multiplicative-tiebreak.**

```python
combined = min(c_ocr, c_match)
if combined > 0.95 and c_ocr * c_match < 0.85:
    combined = c_ocr * c_match  # demote when both are individually weak
```

Rationale: the minimum rule is conservative and explainable (you can always tell the agent which signal pulled confidence down). For production, replace with **temperature-scaled logistic regression** trained on an internal label corpus; on the calibration of model-derived confidences, see Guo, Pleiss, Sun & Weinberger, "On Calibration of Modern Neural Networks," ICML 2017 (PMLR 70:1321–1330; arXiv:1706.04599) — modern deep nets are systematically over-confident, and a single-parameter temperature scaling on a held-out set is "surprisingly effective" at fixing this. Any model-derived confidence (LLM judge, OCR vendor scores, embedding similarities) should be calibrated against an internal validation set before being multiplied into the pipeline confidence.

### 3.5.3 Bands and asymmetric costs

Asymmetry: false approval is far worse than false rejection in a regulatory setting. The bands are biased accordingly. Default policy table (each rule may override per `match_policy`):

| Policy type | Pass band | Needs-review band | Fail band |
|---|---|---|---|
| Exact (after declared normalization) | combined ≥ 0.95 | 0.80 ≤ combined < 0.95 | < 0.80 |
| Tolerance (numeric, `decimal.Decimal`) | within tol AND `c_ocr ≥ 0.85` | within tol AND `c_ocr < 0.85`, OR within 0.05 pp of band edge | outside tol |
| Fuzzy (Q3.4) | match score ≥ 0.92 AND `c_ocr ≥ 0.80` | 0.85 ≤ match < 0.92 | < 0.85 |
| Format (caps/bold/cpi/contrast) | hard pass; no review band unless detector confidence < 0.80 | detector confidence ≥ 0.50 and any soft-fail | hard fail |

Per-policy bands (rather than a single global threshold) honor the constraint stated in Q3.5: exact match has only pass/fail in the success path; fuzzy has a meaningful needs-review band; tolerance respects edge cases.

### 3.5.4 Surfacing to the agent

- Numeric `confidence ∈ [0,1]` and `confidence_band ∈ {high, medium, low}` are both exposed on every `ValidationResult`.
- UI presentation: a three-color "confidence ribbon" alongside disposition (green = high, amber = medium, red = low). Color encodes band; the ribbon's hover state shows the underlying components (e.g., "OCR 0.97 × match 0.88 → 0.88, low band"). This follows the FHIR `OperationOutcome.severity` convention (`fatal | error | warning | information | success`) projected onto color.
- A "why?" affordance expands the rule chain — the rule_id, CFR citation with eCFR deep link, image region cutout, expected vs extracted text, and which bin in the 18-bin reason taxonomy this falls into.

---

## Q3.6 — Rejection-reason data model

### 3.6.1 Schema (Pydantic v2; equivalent JSON Schema follows)

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field, AnyUrl

ReasonCode = str   # validated by regex below

class FieldRef(BaseModel):
    canonical_name: str             # e.g. "warning.text" or "abv.value"
    bbox: Optional[BoundingBox] = None
    image_uri: Optional[AnyUrl] = None

class CFRCitation(BaseModel):
    title: int                      # 27
    part: int                       # 4 | 5 | 7 | 16
    section: str                    # "5.65(b)-(c)"
    url: AnyUrl                     # e.g. https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-5/subpart-G/section-5.65
    effective_date: str             # ISO date

class EvidenceBlock(BaseModel):
    extracted_text: Optional[str]
    expected_value: Optional[str]
    measurements: dict[str, str] = {}      # decimal-as-string for safety
    ocr_confidence: Optional[float]
    image_region: Optional[BoundingBox]

class RejectionReason(BaseModel):
    """A single line item in the engine's audit log entry."""
    reason_code: ReasonCode = Field(
        pattern=r"^[A-Z][A-Z0-9_]*(\.[A-Z][A-Z0-9_]*){1,4}$"
    )
    bin: Literal[                          # the 18 T1 bins
        "BRAND_NAME", "CLASS_TYPE", "ABV", "NET_CONTENTS", "GOVERNMENT_WARNING",
        "BOTTLER_PRODUCER_INFO", "ADDRESS", "ORIGIN", "VINTAGE", "APPELLATION",
        "VARIETAL", "AGE_STATEMENT", "PROHIBITED_CLAIM", "FONT_LEGIBILITY",
        "CONTRAST_LEGIBILITY", "MISBRANDING", "ALLERGEN_SULFITE", "OTHER"
    ]
    severity: Literal["blocking", "needs_review", "advisory"]
    disposition: Literal["fail", "needs_review"]
    field: FieldRef
    cfr: CFRCitation
    evidence: EvidenceBlock
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: Literal["high", "medium", "low"]
    human_message: str               # rendered from a template
    template_id: str                 # references the i18n message catalog
    rule_id: str
    rule_set_version: str            # SemVer (Q3.8)
    model_version: Optional[str]     # if AI orchestration touched it
    timestamp: str                   # RFC 3339
```

### 3.6.2 Hierarchical reason codes (tied to [T1](./2026-09-15-ttb-regulatory-framework.md)'s 18 bins)

The grammar is `BIN.SUB.SPECIFIC[.QUALIFIER]`:

```
GOVERNMENT_WARNING.TEXT.MISSING
GOVERNMENT_WARNING.TEXT.MISSING_COLON
GOVERNMENT_WARNING.TEXT.WORDING_VARIANT
GOVERNMENT_WARNING.FORMAT.CAPS_REQUIRED
GOVERNMENT_WARNING.FORMAT.BOLD_REQUIRED
GOVERNMENT_WARNING.FORMAT.MIN_HEIGHT_VIOLATION
GOVERNMENT_WARNING.FORMAT.CPI_EXCEEDED
GOVERNMENT_WARNING.FORMAT.CONTRAST_INSUFFICIENT
ABV.SPIRITS.OUT_OF_TOLERANCE
ABV.WINE.OUT_OF_TOLERANCE.GT14
ABV.WINE.OUT_OF_TOLERANCE.MID
ABV.WINE.OUT_OF_TOLERANCE.LT7
ABV.WINE.CLASS_LINE_CROSSED
ABV.MALT.OUT_OF_TOLERANCE
ABV.MALT.FLOOR_CROSSED
ABV.MALT.LOW_ALCOHOL_LIMIT_EXCEEDED
BRAND_NAME.MISMATCH.HIGH_CONFIDENCE
BRAND_NAME.MISMATCH.NEEDS_REVIEW
APPELLATION.AVA.NOT_ON_WHITELIST
ORIGIN.IMPORT.MISSING_COUNTRY
ENGINE.INPUT.MISSING                      # engine-level (Q3.10)
ENGINE.RULE.VERSION_MISMATCH              # engine-level (Q3.10)
```

The first segment maps 1:1 to a [T1](./2026-09-15-ttb-regulatory-framework.md) bin; analytics queries like "how many `ABV.*.OUT_OF_TOLERANCE` last quarter?" become trivial. Codes are content-defined, **not** numerically encoded, so adding a new bin or sub-code is backwards-compatible (consumers ignore unknown codes per RFC 9457 §3 guidance for problem-detail extensions).

### 3.6.3 Audit log entry composition

Each application evaluation produces an audit envelope:

```json
{
  "evaluation_id": "ulid:01J...",
  "timestamp": "2026-09-12T17:43:11Z",
  "application_id": "TTB-2026-0123456",
  "rule_set_version": "1.7.2",
  "cfr_effective_date": "2025-04-15",
  "model_versions": {
    "ocr": "textract-2025.10",
    "llm_orchestrator": "gpt-4o-2025-09",
    "vision": "internal-bold-v0.4"
  },
  "overall_disposition": "needs_review",
  "results": [ ValidationResult, ... ],
  "rejection_reasons": [ RejectionReason, ... ],
  "elapsed_ms": 3812
}
```

This composition pattern is borrowed from established regulatory-tech analogs:

- **RFC 9457 / 7807 Problem Details** (Nottingham, Wilde, Dalal, 2023) — `type` (URL to reason-code docs), `title` (human_message), `status` (HTTP layer), `detail`, `instance`, plus extensions. We expose the rejection-reason envelope as `application/problem+json` for any HTTP surface.
- **HL7 FHIR `OperationOutcome`** — `issue.severity` ∈ {fatal, error, warning, information, success}; `issue.code` from `IssueType` valueset; `issue.details.coding` for system-specific codes; `issue.diagnostics`; `issue.expression` (FHIRPath for the offending element). Maps directly to our `severity`, `bin`, `reason_code`, `human_message`, `field.canonical_name`.
- **OASIS XACML 3.0** — Decision (`Permit | Deny | NotApplicable | Indeterminate`) + `StatusCode` + `Obligations`. Our `disposition` ∪ `not_applicable` mirrors the four-valued result.
- **OWASP error reporting / CWE** — codes are stable identifiers; we deliberately avoid free-form messages as primary keys.
- **ISO 20022 reason codes** (financial messaging) and **FINRA reject codes** — both demonstrate the four-segment hierarchical code grammar used here.
- **FDA eCTD validation criteria** and **FAA SARA / SBSS validation** — both publish numbered, severity-coded validation rule lists; we mirror that publishing model so the rule set itself becomes citable in submissions.

---

## Q3.7 — Per-class rule routing

### 3.7.1 Should the system detect class from the label?

**Yes, but only as a corroborator, never as the primary source.** The application data carries the legally declared class (`wine | spirits | malt`); the engine should also extract a label-side class signal (statement of class/type, e.g., "VODKA", "TABLE WINE", "INDIA PALE ALE") because:

- A class disagreement is itself a rejection-grade finding (misbranding bin in [T1](./2026-09-15-ttb-regulatory-framework.md)) — silently honoring the application would mask a real problem.
- Detection is cheap: the class/type statement is a small, high-contrast field, and the OCR pipeline already runs.

### 3.7.2 What if application and label disagree?

The recommendation is **deterministic, conservative, and explicit**:

1. Use the **application-declared class** as the primary routing key for which rules apply.
2. Compute a **label-implied class** in parallel.
3. If they disagree:
   - Set overall disposition to `needs_review`.
   - Emit a `CLASS_TYPE.APPLICATION_LABEL_DISAGREE` reason code with both values and the bbox of the label evidence.
   - **Continue evaluating the rule set under the application-declared class** (do not silently re-route), so the agent sees both the class disagreement *and* what would have failed under the declared class.
   - Never override the application class automatically.

This is consistent with the deterministic core (the rule engine decides) and rejection reasoning (every disposition fully evidenced).

### 3.7.3 Conditional rules

[T1](./2026-09-15-ttb-regulatory-framework.md)'s Q1.2 conditional cases (country of origin only for imports; vintage rules only when vintage claimed; appellation rules only when stated) are expressed declaratively in YAML using a `applies_when` clause:

```yaml
- rule_id: ORIGIN-IMPORT-COUNTRY-001
  field: country_of_origin
  applies_when: "application.is_import == true"
  cfr_citation: "27 CFR §4.35 / §5.32"
  match_policy: { type: exact, pre_normalize: [nfkc, casefold, collapse_ws] }

- rule_id: VINTAGE-DATE-VALID-001
  field: vintage_year
  applies_when: "application.vintage_claimed == true"
  ...

- rule_id: AVA-WHITELIST-001
  field: appellation
  applies_when: "application.appellation_claimed == true"
  match_policy:
    type: set_membership
    set_ref: ava_whitelist_v2025q4   # 279 AVAs, refresh quarterly
```

The `applies_when` predicate is evaluated by a small expression evaluator (no eval; safe AST whitelist of `==`, `!=`, `and`, `or`, `not`, attribute access, and comparators on declared types). Rules whose predicate is false return `disposition: not_applicable` (analogous to XACML `NotApplicable`) and are excluded from the overall pass/fail count.

This is **declarative when-clauses**, not imperative routing. References:

- **Drools agenda groups & rule-flow groups** (Drools docs, ch. 7 Running) — the equivalent JVM-world mechanism. We adopt the *idea* (focus/predicate gating) without the heavy machinery.
- **DMN context entries / FEEL `if … then … else`** (OMG DMN 1.5) for rule applicability.
- **`json-rules-engine` "almanac" facts** (CacheControl) — predicates over runtime facts.
- **Feature-flag patterns** (LaunchDarkly-style) for a/b'ing rule changes.
- **Predicate-based dispatch** in CLOS/Clojure (Clara Rules) and Python pattern matching for the implementation idiom.

The evaluation order is: (1) gather facts (application + observations), (2) evaluate `applies_when` for each rule to get the applicable subset, (3) topologically sort by `requires:` edges, (4) run each validator, (5) aggregate.

---

## Q3.8 — Versioning and update strategy

### 3.8.1 Rule-set versioning

The rule set is versioned per **SemVer 2.0.0** (Preston-Werner, semver.org/spec/v2.0.0.html):

- **MAJOR**: a backwards-incompatible change to rule semantics (e.g., a rule's `disposition` could change from `fail` to `pass` for the same input — anything that could flip a historical evaluation).
- **MINOR**: backwards-compatible additions (a new rule, a new `applies_when` branch that only adds applicability, a new reason_code).
- **PATCH**: clarifications, message wording, non-semantic refactors.
- Pre-release identifiers (`1.8.0-rc.1`) for staged rollout; build metadata (`1.7.2+ttb-196`) to tie a release to a specific Treasury Decision.

Versions are signed (cosign / sigstore equivalent) and the signature is stored alongside the rule artifact.

Each rule additionally carries:

```yaml
rule_id: ABV-SPIRITS-TOL-001
effective_date: "2020-04-13"     # T.D. TTB-158 effective date
sunset_date: null                # null = currently active
supersedes: ABV-SPIRITS-TOL-000  # forward chain for transitions
```

Effective dates are *separate* from rule-set version because a single TTB amendment can simultaneously introduce one rule (effective today) and another (effective in 90 days). The engine reads `cfr_effective_date` from the application's submission timestamp and selects the rule body that was effective on that date.

### 3.8.2 Migration strategy when rules change

Tooling pattern is borrowed from database migrations (Flyway/Liquibase docs, flywaydb.org and liquibase.org):

| DB-migration concept | Rule-set analog |
|---|---|
| Versioned migration scripts (`V1__create.sql`) | Versioned rule pack (`rules_v1.7.2.yaml`) |
| Repeatable migrations | Reference data refresh (the 279 AVAs, the 41 Allowable Revisions list) |
| `flyway info` / changelog | A signed manifest enumerating which rules were added/changed/removed and which CFR sections changed |
| Schema validation (`validate`) | Rule-set linter: verifies (a) every `rule_id` is unique, (b) every `cfr_citation` resolves on eCFR, (c) every `reason_code` matches the regex, (d) DAG of `requires:` is acyclic, (e) every `applies_when` parses, (f) all match policies have sane thresholds |
| Rollback scripts | Each rule-set release has a regression test pack: ~50 known-good and known-bad applications. A new version cannot ship if any historical case flips disposition unintentionally |
| Liquibase changesets / preconditions | A changeset YAML enumerates: "Rule X added (T.D. TTB-196); Rule Y modified (tolerance from 0.15 to 0.30 pp); Rule Z deprecated 2026-09-13" |

This is consistent with FAA and FDA eCTD practice, where validation rule lists are themselves versioned, dated, and accompanied by release notes.

### 3.8.3 Time-of-submission rule version

**Apply the rule set that was effective on the submission date**, not the engine's current rule set. This is the standard *temporal rule-set* pattern (cf. event-sourcing and bitemporal databases; OMG DMN 1.5 §11.4 versioning notes):

```python
def evaluate(application):
    rule_set = rule_registry.get_effective_at(
        submission_ts=application.submitted_at,
        # or: application.requested_evaluation_date
    )
    return engine.run(application, rule_set=rule_set)
```

For applications submitted before T.D. TTB-196 (Nov 2024) effective date, the older rule pack is loaded; the engine never silently retro-applies new rules. Exceptions (e.g., a corrective rule the agency declares retroactive) are explicit `retroactive: true` flags on the rule body and produce a `RULESET.RETROACTIVE_APPLIED` advisory in the audit log.

### 3.8.4 Audit trail

Every evaluation envelope (Q3.6) records:

- `rule_set_version` (SemVer)
- `cfr_effective_date` (ISO date used to select rules)
- `model_versions[ocr|llm_orchestrator|vision]`
- `code_version` (engine git SHA)
- `rule_pack_signature` (cosign signature digest)

This satisfies rejection reasoning down to the version layer: a regulator auditing a years-old approval can reconstruct exactly which rule body fired on which evidence with which models. Source patterns: SemVer 2.0.0 (Preston-Werner), Flyway / Liquibase migration history tables, OMG DMN 1.5 §6 model versioning, OASIS XML versioning conventions, and FAA/FDA practice of pinning validation rule versions to submission dates.

---

## Q3.9 — Performance budget within 5s SLA

### 3.9.1 Rule count and per-rule budget

Estimated rule counts (one beverage class plus health warning):

| Group | Rules |
|---|---|
| Brand name match (with fuzzy, possibly LLM tiebreak) | 1 |
| Class/type statement | 2 |
| ABV + class-specific tolerance | 2–3 |
| Net contents (volume) and standards-of-fill | 2 |
| Bottler/producer/importer name & address | 3–4 |
| Origin / appellation (conditional) | 2 |
| Vintage / age statements (conditional) | 2 |
| Government warning text (verbatim) | 1 |
| Government warning format (caps, bold, x-height, cpi, contrast) | 5 |
| Prohibited claims / misbranding scan | 1–2 |
| Allergen / sulfite (where applicable) | 1 |
| **Total** | **~22–25** |

Per-rule wall-clock target: **median 2–6 ms, p99 ≤ 30 ms**, yielding an aggregate engine time of 60–150 ms at p50 and 200–300 ms at p99 under sequential evaluation. Even json-rules-engine and Cerberus benchmarks show µs-class evaluation for simple condition-action rules; our overhead is dominated by string normalization (NFKC + casefold) and RapidFuzz scoring (RapidFuzz typically 10⁶ comparisons/sec on commodity hardware), both of which are negligible per call.

### 3.9.2 Where parallelism helps and hurts

Helpful:

- **Independent field validators** (brand, class, ABV, container size, address) — naturally parallel; use a thread or asyncio gather.
- **Format checks** (caps, bold, height, cpi, contrast) on disjoint regions — parallel.

Hurts (or no benefit):

- **Shared OCR text** — already produced once upstream; no benefit to re-OCR'ing.
- **Shared LLM call** — coalesce into a single LLM call when multiple rules need an AI tiebreak (batched), rather than firing N calls in parallel and amplifying cost and tail.
- **Rules with `requires:` edges** — evaluate in topological waves; within a wave, parallelize.

### 3.9.3 Time-budget breakdown (defensible, p50; **engine slice 100–300 ms**)

| Stage | p50 | p99 | Notes |
|---|---|---|---|
| Input handling (upload, image normalize, validate JSON) | 100 ms | 300 ms | |
| OCR / vision ([T4](./2026-09-15-ocr-vision-architecture.md)) — single label, cloud | 1500 ms | 2800 ms | Textract / Document AI typical |
| AI orchestration (LLM disambiguation, optional tiebreak; batched) | 800 ms | 1500 ms | Single batched call dominates; tiebreak only on `needs_review` |
| **Rule engine evaluation** | **150 ms** | **300 ms** | Fits Q3.9 target |
| Reasoning / evidence assembly + audit log | 80 ms | 200 ms | |
| Response serialization and transport | 70 ms | 150 ms | |
| **Total** | **~2.7 s** | **~5.0 s** | Within SLA at p99 |

Cross-topic note: this row's allocation will be reconciled with **X-1 (end-to-end time budget)**, which is out of scope for this document.

### 3.9.4 Tail latency notes

Per Dean & Barroso, "The Tail at Scale," *CACM* 56(2):74–80, 2013, even rare per-component slowdowns compound at scale. Practitioner techniques relevant here:

- **Hedged requests** — duplicate the OCR request to a second backend if the first hasn't returned in p95 time; use whichever returns first. Costly but reduces tail.
- **Tied requests** — same idea, with cancellation of the loser.
- **Selective replication** for hot rule packs.
- **Per-stage timeouts** with structured timeout codes (Q3.10) so a slow component degrades to `needs_review` rather than blocking the SLA.

For the rule engine itself, the dominant tail risks are: (a) cold-start of the YAML loader (mitigate by preloading at process start), (b) regex backtracking on adversarial OCR strings (mitigate by RE2 or capped regex; never use `re` for user-supplied patterns), and (c) GIL contention if Python workers share state — measure p50 vs p99 explicitly per rule and alert on p99/p50 > 5×.

---

## Q3.10 — Failure-mode taxonomy of the engine itself

These are *engine* failures (the rule machinery itself failed), distinct from *label* failures (the rules detected a bad label). Every engine failure must (a) be visible to the user with a non-misleading disposition, (b) be observable to operators with structured fields, and (c) never silently degrade to a `pass`.

| # | Failure mode | User-facing disposition | Reason code | Structured log fields | Notes |
|---|---|---|---|---|---|
| 1 | Missing required input (no application data) | `needs_review` (whole-evaluation level) | `ENGINE.INPUT.APPLICATION_MISSING` | `evaluation_id`, `expected_inputs[]`, `received_inputs[]` | Never `fail` — we cannot fail a check we did not run |
| 2 | Missing required input (no label image) | `needs_review` | `ENGINE.INPUT.LABEL_IMAGE_MISSING` | same | |
| 3 | Conflicting / overlapping rules trigger contradictions | `needs_review` for affected fields | `ENGINE.RULE.CONFLICT` | `rule_ids[]`, `field`, `dispositions[]` | The rule loader's linter should catch this at load time; runtime occurrence is an operator alert |
| 4 | Ambiguous OCR input (multiple plausible reads, no clear winner) | `needs_review` for that field | `ENGINE.OBSERVATION.AMBIGUOUS` | `field`, `candidates[]`, `top1_conf`, `top2_conf` | LLM tiebreak may be invoked; if still ambiguous, surface to agent |
| 5 | Unexpected beverage class (not wine/spirits/malt) | `needs_review` whole-evaluation; `fail` on class field | `CLASS_TYPE.UNKNOWN` | `application.declared_class`, `label_implied_class` | Engine refuses to invent a rule pack for unknown classes |
| 6 | Class disagreement (application vs label) | `needs_review` (Q3.7) | `CLASS_TYPE.APPLICATION_LABEL_DISAGREE` | both classes, evidence | Continue under application class |
| 7 | Rule-set version mismatch (application predates current pack) | resolved by temporal selection (Q3.8); a *real* mismatch is a config error | `ENGINE.RULESET.VERSION_NOT_FOUND` | `submitted_at`, `requested_version`, `available_versions[]` | Operator alert |
| 8 | Validator exception (unhandled error inside a rule) | `needs_review` for that rule (never silent pass) | `ENGINE.VALIDATOR.EXCEPTION` | `rule_id`, exception type, redacted stack | Treated like a Drools/json-rules-engine fault |
| 9 | Per-rule timeout (rule exceeded its budget) | `needs_review` for that rule | `ENGINE.VALIDATOR.TIMEOUT` | `rule_id`, `budget_ms`, `elapsed_ms` | |
| 10 | Whole-evaluation timeout (5 s SLA exhausted) | `needs_review` whole-evaluation; partial results returned | `ENGINE.SLA.TIMEOUT` | partial results, last completed rule | Tail-tolerance pattern (Dean & Barroso 2013) |
| 11 | Missing measurement (e.g., DPI not present, can't compute mm) | `needs_review` for that rule | `ENGINE.MEASUREMENT.MISSING_DPI` | `field`, missing-attr name | Caps/bold/cpi/contrast checks need physical units |
| 12 | Reference data unavailable (AVA whitelist load failed) | `needs_review` for affected rules | `ENGINE.REFERENCE_DATA.UNAVAILABLE` | dataset name, version, error | |
| 13 | Model unavailable (LLM tiebreak endpoint down) | `needs_review` for borderline rules; deterministic rules unaffected | `ENGINE.MODEL.UNAVAILABLE` | model name, error | the deterministic core ensures pass/fail still works without AI |

The taxonomy is grounded in:

- **Google SRE practice** — *Site Reliability Engineering* (Beyer et al., 2016), *The Site Reliability Workbook* (2018): every error must be observable, attributable, and have a structured code; "fail open" vs "fail closed" must be an explicit choice (here: closed — we never silently pass).
- **Dean & Barroso, "The Tail at Scale" (2013)** for timeout patterns, partial-result handling, and tail-tolerant design.
- **Hyrum's Law** (Wright) — in observability, every emitted log field becomes load-bearing for somebody downstream. We commit to a stable field schema per reason code so dashboards do not silently break.
- **ISO/IEC 25010:2023 reliability sub-characteristics** — *availability, fault tolerance, recoverability, faultlessness* (arc42 ISO 25010 mapping; pacificcert.com summary). Each row above maps to one of these.
- **IEEE Std 1044-2009** error/anomaly classification taxonomy (severity × priority × type) — informs the `severity` field.

---

## Caveats and scope notes

- This document deliberately does not answer cross-topic questions **X-1** (end-to-end time budget reconciliation), **X-2** (decision tree across components), **X-3** (production-readiness gaps), or **X-4** (rules-as-data vs. code synthesis). Where this document needs a placeholder for those (e.g., the time-budget table in Q3.9), the figures are local to the rule-engine slice and are explicitly subject to X-1.
- **Reconciliation with the take-home brief.** The brief's "common elements" enumeration — brand name, class/type, ABV, net contents, bottler/producer name and address, country of origin (imports), and the government health warning — is the hard-tier rule footprint this engine targets. That enumeration matches the ~22–25 rule estimate in Q3.9 and the bin coverage in Q3.6. Beverage-class-specific rules (vintage, age statements, appellations, AVA whitelist enforcement) sit in the same YAML schema but are stretch per the class-depth scope call and `docs/PRD.md`.
- **Reconciliation with the prototype's stated limitations.** It is accepted that the *prototype implementation* may hard-code rules and that a production version would externalize them as data. The Q3.1 recommendation here is the production-parity *design*, which per-field match policies already commit the project to. The practical reconciliation: the prototype may ship with a small hard-coded validator set whose shape mirrors the YAML schema in this document (same field names, same `match_policy` keys, same reason codes), so migration to a YAML-driven engine becomes mechanical rather than a rewrite. The standing caveat that the error-case taxonomy needs real-data validation is acknowledged in the next bullet.
- Tolerance numbers, the §16.22(a)(4) cpi cardinal table, the 18-bin rejection taxonomy, and the 279-AVA whitelist are taken as given from [T1](./2026-09-15-ttb-regulatory-framework.md); this document does not re-derive them. The rule pack's job is to encode them faithfully, not to second-guess them. The 18-bin set is itself flagged in [T1](./2026-09-15-ttb-regulatory-framework.md) §7.3 as a non-authoritative working set synthesized from BAM/ALFD/industry sources; validating it against real ALFD rejection data is production work, not prototype work.
- "Confidence" in this document means *the engine's own confidence in its disposition*, not a regulatory probability. Per Guo et al. (2017), any model-derived probability we ingest from the OCR vendor or LLM tiebreak must be calibrated against an internal label set before being used as input to band thresholds.
- The recommendation to use rule-augmented exact + RapidFuzz `token_set_ratio`/`WRatio` rather than embeddings for brand-name matching is conservative and explicitly favors explainability and on-prem deployability (substitutability) over the marginal recall lift embeddings might offer. If a future evaluation against an internal brand-name corpus shows materially better F1 from a calibrated SBERT or fastText layer, escalate it to *additional* tier between 0.85–0.92 rather than replacing the deterministic core.
- DMN/Drools is acknowledged as the industry-standard rules platform, but is rejected for this prototype on grounds of runtime weight, JVM dependency, and the modest rule count. The recommended hybrid YAML approach can later be migrated to DMN (the cardinal tables are already DMN-shaped) without rewriting the rule semantics.
- Where library versions matter: Pydantic v2.x, RapidFuzz ≥ 3.x, Python ≥ 3.11 (`decimal.Decimal`, `unicodedata`, structural pattern matching). Tesseract ≥ 5.x or Textract / Document AI for OCR; bold detection currently weakest in Textract and is the most likely [T4](./2026-09-15-ocr-vision-architecture.md)-side gap for §16.22(a)(2) compliance.