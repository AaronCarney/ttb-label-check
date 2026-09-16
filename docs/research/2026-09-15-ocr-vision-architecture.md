# OCR & Vision Architecture (Research Deep-Dive)

Filed 2026-09-15.

**Project:** AI-powered TTB Alcohol Label Verification Prototype
**Topic:** T4 (OCR & Vision Architecture)
**Scope:** Q4.1–Q4.10 of this topic. Cross-topic synthesis questions (X-1, X-2, X-3) explicitly deferred.
**Decision references:** substitutability (cloud-substitutable architecture), per-field match policies (declared explicitly, not buried in code), rejection reasoning (required on every disposition), the economics-and-policy test (TCO + FedRAMP/ATO story for every option).
**Depth weighting:** Q4.2 ≈30%, Q4.4 ≈20%, remaining 50% across Q4.1, Q4.3, Q4.5–Q4.10.

**Project artifacts consulted:**
- [T1](./2026-09-15-ttb-regulatory-framework.md), [T2](./2026-09-15-cola-operational-context.md), original take-home brief
- `docs/PRD.md` (hard / strong / stretch tier mapping; the outbound-network constraint that frames where the vision layer can run), `ARCHITECTURE.md` (vision-layer position), `docs/decisions/` (substitutability, per-field match policies, rejection reasoning, the economics-and-policy test), and the open questions on preprocessing cost-versus-benefit and "needs better photo" as a first-class disposition
- Three standing limitations of the prototype directly inform this topic: (a) "Image-quality robustness is best-effort. Labels with severe glare, extreme angles, or poor resolution may fail-out as 'needs better photo' rather than be recovered" → ratifies Q4.6 disposition policy; (b) "Cloud inference is acceptable for the prototype... architecture is designed to allow this swap, but it is not implemented" → ratifies Q4.9 phased-migration framing; (c) "No persistent storage or audit trail. Session-only" → constrains Q4.7 (no inter-application image caching; per-application reconciliation only)

**Primary external sources consulted (selection):**
- FedRAMP Marketplace (marketplace.fedramp.gov), fedramp.gov, AWS, Google Cloud, Microsoft compliance pages
- Google Document AI docs (cloud.google.com/document-ai), AWS Textract docs, Azure AI Document Intelligence docs (learn.microsoft.com)
- Tesseract docs (tesseract-ocr.github.io), PaddleOCR (github.com/PaddlePaddle/PaddleOCR), EasyOCR (github.com/JaidedAI/EasyOCR)
- Anthropic Claude vision docs (platform.claude.com/docs), OpenAI API pricing, Google Vertex AI / Gemini docs
- 27 CFR §16.21 / §16.22 (eCFR), TTB ALFD pages, TTB COLAs Online FAQ, TTB Public COLA Registry
- arXiv: OCRBench v2 (2501.00321), Pixtral 12B (2410.07073), Qwen2.5-VL Tech Report (2502.13923), Stroke Width Transform (Epshtein et al., CVPR 2010), BRISQUE (Mittal et al., TIP 2012), NIQE (Mittal et al.)
- OmniAI OCR benchmark, Codesota benchmarks aggregator (treated as secondary, cross-checked vs. primary)

**Reading-mode note on freshness:** Several cost/benchmark statements come from 2025/2026-dated vendor pages and aggregator sites; pricing is quoted as observed at research date. Authorization status of specific cloud services is from official compliance pages and FedRAMP Marketplace summaries; the canonical source of truth at runtime is marketplace.fedramp.gov. Where aggregator sources speculate (e.g., "could," "may," post-dated 2026 model releases), the report flags those explicitly rather than treating them as confirmed.

---

## Q4.1 — Extraction Requirements Specification

The vision layer must surface, per uploaded label image, a structured envelope per field. [T1](./2026-09-15-ttb-regulatory-framework.md)'s regulatory framework defines the *what*; this section defines the vision-layer contract for the *how*.

**Per-field requirements table** (gated by [T1](./2026-09-15-ttb-regulatory-framework.md); additional layout/typographic columns derived from 27 CFR §16.22 and from the warning-formatting subrules):

| Field | Plain Text | Bounding Region | Caps Detection | Bold/Weight | Font Size (mm) | Layout/Panel | Color/Contrast | Other |
|---|---|---|---|---|---|---|---|---|
| Brand name | Required | Required (polygon preferred over axis-aligned bbox) | Optional (informational) | Optional | Optional | Required (front/back/neck/side) | — | Cross-image dedup if it appears on >1 panel |
| Class/type designation | Required | Required | — | — | Optional (some classes have minimum type size in TTB rules; out of scope of §16.22) | Required | — | Must match TTB-allowed designations from [T1](./2026-09-15-ttb-regulatory-framework.md) |
| Alcohol content (ABV%) | Required | Required | — | — | Optional | Required | — | Must parse "X% alc/vol", "X.X% ABV", "X% by volume"; tolerance from T.D. TTB-158 (±0.3 pp spirits) checked downstream |
| Net contents | Required | Required | — | — | Required (TTB has minimum sizes per §4.38, §5.32, §7.28; not §16.22 — but same DPI math applies) | Required | — | Normalize "750 mL", "12 FL OZ", "1 PT 6 FL OZ" to canonical units |
| Bottler/Producer name and address | Required | Required | — | — | Optional | Required | — | NER will be needed downstream; vision returns the span(s) |
| Country of origin | Required (when present) | Required | — | — | — | Required | — | Imports only; absence is informational, not error |
| Government warning — verbatim text | **Required, character-exact** | Required | **Required (just "GOVERNMENT WARNING" prefix)** | **Required (just "GOVERNMENT WARNING" prefix)** | **Required for full statement** | Required (any panel allowed) | **Required (must be on contrasting background)** | Continuity check: must be one paragraph, not split |
| Government warning — formatting | — | — | Boolean: prefix is uppercase | Boolean: prefix is bold AND remainder is not bold | mm value with DPI-derived uncertainty; CPI (chars/inch) computed from bbox + char count | — | Foreground vs. background luminance contrast ratio (see Q4.4.6) | "Continuous statement" check from line/paragraph layout |

**Notes on the per-field contract:**

- **Bounding region** is the polygon (or quadrilateral for rotated text) plus an axis-aligned bbox. Polygons are preferred because labels are frequently photographed at angles and curved-bottle labels render warped text. AWS Textract returns both `BoundingBox` and `Polygon` per WORD/LINE; Google Document AI returns `boundingPoly`; Azure Document Intelligence returns `polygon` arrays — substitution interface should standardize on polygons.
- **Caps detection** is intentionally split: trivially derivable from text (`s == s.upper()`), but with the OCR caveat in Q4.4 (a single uppercase letter could be "I" cap or "i" cap rendered in a true small-caps font; this is the "all-caps rendering" vs. "uppercase characters" distinction).
- **Bold/weight** is required for §16.22(a)(2) — only the first two words must be bold, and the remainder *may not* be bold. So this is not a single boolean; it is at minimum a per-token weight signal for the first two words and the rest of the warning.
- **Font size in mm** is derived (Q4.4 math) from text-box height in pixels divided by DPI metadata, multiplied by 25.4. The DPI is taken from EXIF/PNG pHYs chunk where available; otherwise from the COLAs Online "Step 3" applicant-supplied label dimensions (printed-label width/height mm) divided by image pixel dimensions.
- **Color/contrast** computation is detailed in Q4.4.6 below. The vision layer reports signals (WCAG ratio, ΔL*, background uniformity); the rule engine adjudicates against §16.22(a)(1).
- **Provenance:** every field returned must include the `image_id` (which uploaded image it came from), supporting Q4.7's multi-image reconciliation.

---

## Q4.2 — OCR Approach Trade-offs (PRIMARY DEPTH SECTION)

This section evaluates four families — **Cloud OCR**, **Self-hosted OCR**, **Cloud VLMs**, **Self-hosted/Hybrid VLMs** — under both prototype and production-parity (substitutability) constraints, with a federal-policy lens (the economics-and-policy test).

### 4.2.1 Cloud OCR services

#### Google Document AI (Enterprise Document OCR + Layout / Form Parser)
- **Accuracy on label imagery:** Google does not publish label-specific benchmarks. On general document benchmarks Document AI is competitive; the underlying Document OCR and the newer Gemini-powered "Layout Parser" (Nov 2025/Gemini 2.0/2.5) score well on OmniDocBench-class document parsing per third-party comparisons. For *natural-scene/photographic* text (i.e., bottle photographs of etched/embossed labels per TTB FAQ), Document AI is less differentiated from Vision API's `TEXT_DETECTION`, which is the scene-text path; many practitioners use Cloud Vision OCR for photographic text and Document AI for "document-style" 2D label artwork.
- **Cost (verified 2025/2026 on cloud.google.com/document-ai/pricing):**
  - Enterprise Document OCR: **$1.50/1,000 pages** for first 5M pages/month, **$0.60/1,000 pages** thereafter.
  - Layout Parser (Gemini-backed): **$10/1,000 pages**.
  - Form Parser / Custom Extractor: **~$30/1,000 pages**, dropping to ~$20/1,000 at scale.
  - Each JPEG/PNG image counts as one page.
- **Latency:** Synchronous online processing tier; provisioned quotas are 30–120 pages/min (model dependent). Single-image typical wall-clock: ~1–2 s for Enterprise OCR; 2–5 s for Layout Parser / Gemini-backed processors.
- **FedRAMP authorization (per cloud.google.com/security/compliance/fedramp and Google's FedRAMP scope page):**
  - Google Cloud has **FedRAMP High P-ATO** (with 100+ services in scope as of the 2025 expansion announcement). Document AI is included in Google Cloud's FedRAMP scope under Assured Workloads.
  - **Note on individual processors:** Google's compliance documentation explicitly states that "individual LLMs aren't independently authorized under FedRAMP" — the Marketplace records authorizations at the *service* level. Document AI inherits the underlying Google Cloud FedRAMP boundary. For prototype federal use, the "Document AI in Assured Workloads / FedRAMP High Data Boundary" configuration is the relevant deployment, **not** the public commercial endpoint.
- **On-prem substitution:** No first-party container distribution of Document AI. Migration path is to PaddleOCR or Tesseract for the OCR layer and a self-hosted VLM (e.g., Qwen2.5-VL) for the Layout Parser / Form Parser equivalent.
- **License:** Proprietary SaaS.

#### AWS Textract
- **Accuracy on label imagery:** Textract is document-tuned and uses key-value-pair / table / signature features beyond raw OCR. It performs well on forms but is reported to lag on natural-scene/photo text vs. Cloud Vision and vs. modern VLMs on label-style imagery. AWS itself differentiates "Rekognition DetectText" (scene text) from "Textract" (documents) — for photographs of bottles, **Rekognition** is more appropriate than Textract.
- **Cost (per aws.amazon.com/textract/pricing):**
  - DetectDocumentText (raw OCR): **$1.50/1,000 pages** (first 1M), **$0.60/1,000 pages** above.
  - AnalyzeDocument with FORMS: **$50.00/1,000 pages**.
  - AnalyzeDocument with TABLES: **$15.00/1,000 pages**.
  - AnalyzeDocument with QUERIES: **$15.00/1,000 pages**.
  - Each image is 1 page. JPEG/PNG synchronous; PDF/TIFF only async.
- **Latency:** Synchronous DetectDocumentText typically returns in ~0.3–1 s on a single label image; async path adds polling overhead.
- **FedRAMP authorization (per AWS compliance pages, marketplace.fedramp.gov):**
  - **Amazon Textract: FedRAMP High in AWS GovCloud (US); FedRAMP Moderate in commercial US-East/West regions** (announced April 2021; still current).
  - This is the **strongest cloud-OCR authorization story** as of 2026: Textract is independently in scope for FedRAMP High (not just inheriting from the underlying region).
- **On-prem substitution:** No first-party Textract container. Substitution path = PaddleOCR / Tesseract for raw OCR; LayoutLMv3 or a VLM for the FORMS/TABLES feature set.
- **Confidence:** word-level `Confidence` 0–100 (Q4.5).
- **License:** Proprietary SaaS.

#### Azure AI Document Intelligence (formerly Form Recognizer)
- **Accuracy on label imagery:** Read API (raw OCR) is competitive with Textract DetectDocumentText. Layout API additionally returns paragraphs/headings/tables. Critical for our use case: Azure Document Intelligence is the **only major cloud OCR with a first-class typographic-style add-on** (`features=styleFont`) returning `fontWeight` (bold/normal), `fontStyle` (italic/normal), `similarFontFamily`, `color`, `backgroundColor`, plus per-style confidence (per learn.microsoft.com add-on capabilities page). This directly maps to §16.22 detection.
- **Cost (per azure.microsoft.com/pricing/details/ai-document-intelligence):**
  - Read model: **$1.50/1,000 pages** (drops to **$0.60/1,000** above 1M).
  - Prebuilt models (invoice, receipt, layout-with-structure): **$10/1,000 pages**.
  - Custom Extraction / Custom Generative: **$30/1,000 pages**.
  - **Add-ons (incl. styleFont): $6/1,000 pages on top of base.**
  - **Container pricing = cloud pricing** (Microsoft offers an on-prem Docker container for some Document Intelligence models).
- **Latency:** ~1–2 s for Read; 2–4 s for Layout + styleFont.
- **FedRAMP authorization (per learn.microsoft.com/azure/azure-government/compliance):**
  - **Azure** (commercial): FedRAMP High P-ATO via JAB. Document Intelligence is in scope.
  - **Azure Government** (US Gov regions Arizona/Texas/Virginia): FedRAMP High P-ATO; DoD IL2/IL4/IL5 PA. Document Intelligence is in the FedRAMP High scope list for Azure Government.
  - **Azure OpenAI Service:** FedRAMP High in Azure Government (Sept 2024) and DoD IL4/IL5; subsequently authorized at IL6 for top-secret per Microsoft's announcements (Feb 2025).
- **On-prem substitution (KEY DIFFERENTIATOR):** Microsoft offers **Document Intelligence as a Docker container** that can be run on customer infrastructure with the same API surface (`prebuilt-read`, `prebuilt-layout`, custom models). Microsoft's own pricing page states "Container pricing is the same as cloud service pricing." This is the *only* major cloud OCR with a true on-prem-parity container option, which makes Azure Document Intelligence uniquely strong against the substitutability mandate.
- **Confidence:** per-word `confidence`; per-style `confidence`.
- **License:** Proprietary; container has connected/disconnected modes (disconnected requires commitment tier).

#### Cloud-OCR comparison summary

| Feature | Google Document AI | AWS Textract | Azure Doc Intelligence |
|---|---|---|---|
| Raw OCR price (1k pp) | $1.50 → $0.60 | $1.50 → $0.60 | $1.50 → $0.60 |
| Layout/structure price | $10 (Layout Parser) | $15 (TABLES) / $50 (FORMS) | $10 (prebuilt-layout) + $6 styleFont add-on |
| Per-token typographic style output | No | No | **Yes** (`fontWeight`, `fontStyle`, `similarFontFamily`, `color`, `backgroundColor`) |
| Bounding region | `boundingPoly` (polygon) | `BoundingBox` + `Polygon` | `polygon` |
| Confidence | Per-token (Document.Page.Token.confidence) | Per-WORD/LINE 0–100 | Per-word + per-style |
| FedRAMP scope (commercial) | Inherited (Google Cloud High P-ATO) | **Service-listed: Moderate** | Inherited (Azure High P-ATO) |
| FedRAMP scope (government cloud) | Assured Workloads / FedRAMP High | **Textract on GovCloud: FedRAMP High** | **Azure Gov FedRAMP High; DoD IL2/4/5** |
| On-prem container (1st-party) | No | No | **Yes (same API)** |
| Best cloud-→-on-prem story | Weakest | Medium (must rebuild on Tesseract/PaddleOCR) | **Strongest** |

### 4.2.2 Self-hosted OCR engines

#### Tesseract 5
- **Accuracy on label imagery:** Optimized for clean printed scanned text. Multiple comparisons (TildAlice 10k product-label benchmark; Toon Beerten medium comparison; arXiv 2602.02223 OCR-for-assistive-tech evaluation) report Tesseract 5 has CER around **0.18 on real product labels** — substantially worse than EasyOCR/PaddleOCR on photographic/scene text. Tesseract is poor on rotated text (>5° degrades sharply) and natural-scene imagery.
- **Cost:** Free; only compute. CPU-only is workable (Tesseract is the lightest engine — sub-second/page on modest CPU).
- **Latency:** Fast initialization (<0.3 s); ~0.1–0.5 s/image typical.
- **FedRAMP:** Not applicable (open-source library). Inherits the FedRAMP authorization of whatever FedRAMP-High-authorized compute it runs on (e.g., Azure Gov VM, AWS GovCloud EC2, Google Cloud Assured Workloads VM, or on-prem). This is the cleanest on-prem story from a compliance standpoint.
- **License:** Apache 2.0.
- **Typographic output:** HOCR/ALTO; `WordFontAttributes` returns `is_bold`, `is_italic`, `pointsize`, `is_serif`, `is_smallcaps`, `font_id`. **Critical caveat for Q4.4:** the LSTM engine (default in Tesseract 4/5, `--oem 1`) has effectively broken or absent font-attribute output (issue #1074, #2781, #1371). Reliable bold/italic detection requires `--oem 0` (legacy engine), and even then accuracy is mixed; community confirms hOCR `<strong>`/`<em>` tags are unreliable. Practical conclusion: Tesseract alone is **not sufficient** for §16.22 bold detection.
- **Languages:** 100+ traineddata files; 35+ scripts (per tesseract-ocr.github.io).
- **Container availability:** Official-ish Docker images and many community variants; Debian/Ubuntu packages.

#### PaddleOCR (PP-OCR series; PP-OCRv4/v5; PaddleOCR-VL)
- **Accuracy on label imagery:** Best of the open-source non-VLM trio for scene/label text. Multiple evaluations: PaddleOCR is the strongest open-source on photographic text and has the highest "average confidence" scores (~0.93) among the three. PP-OCRv5 supports 100+ languages. The newer **PaddleOCR-VL 0.9B / 1.5** (2025/2026) is a small-VLM variant scoring 92.86–94.5 on OmniDocBench.
- **Cost:** Free. GPU strongly recommended for production throughput; CPU works for prototype-scale (≤5s SLA on modest images).
- **Latency:** Initialization ~4 s. Per-image ~0.3–1 s on GPU; 1–3 s on CPU.
- **FedRAMP:** Not applicable (library). Same inheritance pattern as Tesseract.
- **License:** **Apache 2.0** — production-safe.
- **Typographic output:** Layout output (PP-StructureV3) gives bounding polygons, table cells, key-value fields, and reading order. PaddleOCR does **not** natively return `fontWeight` per token; bold detection has to be implemented separately (stroke-width approach, per Q4.4) or via the PaddleOCR-VL VLM path which can be prompted for typography.
- **Container availability:** Docker images; runs on PaddlePaddle framework (Baidu).
- **Note on framework:** PaddlePaddle is less common in U.S. federal stacks than PyTorch/TensorFlow; this introduces a small learning-curve / supply-chain consideration but does not affect compliance.

#### EasyOCR
- **Accuracy on label imagery:** Better than Tesseract on scene text; comparable to PaddleOCR for short text but generally a bit lower at longer/dense documents. CRAFT detection + CRNN recognition deep-learning stack.
- **Cost:** Free; GPU strongly recommended.
- **Latency:** ~2–3 s init; 0.5–2 s per image with GPU.
- **License:** **Apache 2.0**.
- **Languages:** 80+ supported.
- **Typographic output:** None — EasyOCR returns text + bbox + confidence only; no font weight, no font size, no style. **Not suitable as the sole engine for §16.22 enforcement.**
- **Container:** Yes; pip-installable; CPU mode supported.

### 4.2.3 Cloud Vision-Language Models

#### Anthropic Claude (Sonnet 4.5 / Opus 4.x) via API or Bedrock
- **Accuracy on label/document tasks:** OmniAI OCR benchmark shows GPT-4o ≈ 75% JSON-extraction accuracy at the time of the benchmark; Claude Sonnet variants are within a few points. Frontier VLMs handle layout + reasoning + extraction in one pass and are robust to rotation, decorative backgrounds, and curved/warped label text in ways traditional OCR is not. Limitation: VLMs are not infallible on fine-grained perception (arXiv 2407.06581 "Vision Language Models are Blind" shows degraded performance on small-pixel features and intersecting lines).
- **Cost (per platform.claude.com/docs/en/about-claude/pricing, April 2026):**
  - Sonnet 4.5: **$3 / million input tokens, $15 / million output**.
  - A typical label image at 1568px long edge is ~1,600 image tokens (≈$0.0048 per image input, plus output tokens).
  - Per-page realistic cost: **~$0.005–$0.02**.
- **Latency:** 1–4 s typical for single-image extraction with structured-output schema; can stretch with extended thinking enabled.
- **FedRAMP authorization (per anthropic.com/news/claude-in-amazon-bedrock-fedramp-high, support.claude.com public-sector FAQ, May 2025):**
  - **Claude 3.5 Sonnet v1 and Claude 3 Haiku via Amazon Bedrock in AWS GovCloud (US): FedRAMP High + DoD IL4/5 authorized.**
  - Anthropic's own Claude Enterprise SaaS: **NOT FedRAMP authorized.** "Claude for Government" (C4G) is a separate FedRAMP High offering.
  - **Claude via Google Vertex AI in Assured Workloads:** FedRAMP High and IL2 authorized for select Claude models.
  - **Caveat:** newer Claude versions (Sonnet 4.5/4.6, Opus 4.x) are *not yet uniformly authorized* in GovCloud Bedrock at FedRAMP High — agencies must verify the specific model snapshot they intend to use against current FedRAMP Marketplace listing.
- **On-prem substitution:** Claude is not self-hostable. Substitute with Llama 3.x Vision, Qwen2.5-VL, InternVL3, or Pixtral.
- **License:** Proprietary; ToS varies by deployment surface.

#### OpenAI GPT-4o / GPT-5.x via OpenAI API or Azure OpenAI Service
- **Accuracy:** GPT-4o tied or led most VLM-OCR benchmarks 2024–2025; GPT-5/5.1/5.2 expected to extend this.
- **Cost:** GPT-4o ≈ $2.50/M input, $10/M output. GPT-5.2 series ≈ $1.75/M input, $14/M output per OpenAI pricing page. Per-image costs depend on detail mode: typical label image at "high detail" ~1k–3k input tokens.
- **Latency:** 1–3 s.
- **FedRAMP authorization:**
  - **Azure OpenAI in Azure Government: FedRAMP High** (announced Aug 2024 covering GPT-4 and subsequently GPT-4o); **DoD IL4/IL5** approved (Sept 2024); **IL6** approved Feb 2025.
  - **OpenAI direct API: NOT FedRAMP authorized.** Federal-sector use of GPT-4o requires going through Azure OpenAI in Azure Gov.
  - **Caveat:** Azure Gov's available model catalog lags commercial Azure OpenAI. As of early 2026, Azure Gov has GPT-4.1 and o3-mini available; newer models (GPT-5.x, GPT-5.2) likely not yet authorized in Azure Gov boundaries.
- **On-prem substitution:** Not self-hostable. Same VLM family substitutes apply.
- **License:** Proprietary.

#### Google Gemini (1.5 Pro, 2.0/2.5 Flash, 3.x Pro) via Vertex AI
- **Accuracy:** Gemini family is competitive with GPT-4o family on document/OCR benchmarks; Gemini 2.5 Pro and 3.x Pro lead recent leaderboards on certain tasks.
- **Cost:** Gemini 2.5 Pro: $1.25/M input ≤200k context; $2.50/M >200k. Gemini Flash variants are cheaper still.
- **Latency:** 1–3 s.
- **FedRAMP authorization (per cloud.google.com/blog/topics/public-sector):**
  - **Generative AI on Vertex AI (which hosts Gemini): FedRAMP High** (announced 2025).
  - Supported FedRAMP-High Gemini models include the Gemini family and Anthropic partner models with Provisioned Throughput.
- **On-prem substitution:** Gemini is not self-hostable. Substitute via open VLMs.
- **License:** Proprietary.

#### Open-source VLMs (Qwen2.5-VL, Llama 3.2 Vision, InternVL3, Pixtral, PaddleOCR-VL)
- **Accuracy on document/OCR:** **Qwen2.5-VL 72B matches or exceeds GPT-4o** on document and OCR tasks per its tech report (arXiv 2502.13923). **Pixtral 12B** outperforms Llama 3.2 11B and Qwen2-VL 7B at similar size. **InternVL3-14B** scores ~94% on simpler entity matching but ~85% on key-information-extraction tasks. **PaddleOCR-VL 0.9B and 1.5** post extremely strong document-parsing scores (92–94 OmniDocBench composite) at very small size.
- **Cost:** GPU compute only. Qwen2.5-VL-7B/3B run on a single 24-48GB GPU; 72B requires multi-GPU or quantization. Llama 3.2 90B vision requires ~80GB. PaddleOCR-VL 0.9B runs on commodity GPU.
- **Latency:** Highly hardware-dependent. 7B-class VLMs: ~2–5 s/image on a single A10/L4-class GPU. Larger 70B+ models: 5–15 s without batching.
- **FedRAMP authorization:**
  - "Individual LLMs aren't independently authorized under FedRAMP." When deployed self-hosted, the **infrastructure** carries FedRAMP authorization; the **model** does not. Customer is responsible for the model's supply-chain/security review.
  - Models hosted by FedRAMP-authorized cloud (e.g., Llama 3 on Bedrock GovCloud has FedRAMP High + IL4/5 auth alongside Claude).
- **License:**
  - Qwen2.5-VL: Apache 2.0.
  - Llama 3.2 Vision: Llama 3.2 Community License (commercial-permitted with restrictions; >700M MAU clause).
  - Pixtral 12B: Apache 2.0.
  - InternVL3: MIT-style.
  - PaddleOCR-VL: Apache 2.0.

### 4.2.4 Hybrid: OCR + VLM

A common production pattern: run a fast self-hosted OCR engine (PaddleOCR) for raw-text extraction with bbox + confidence; then send the pre-cropped warning region (or the whole label) to a VLM (Claude / Gemini / Qwen2.5-VL) for typography and reasoning. Benefits:
- Cheap, deterministic raw-text path.
- VLM reasoning only on the small subset that needs it (the warning).
- Cost amortizes well across the 5s SLA.
- Easier to swap pieces.

This is the recommended pattern (see "Recommendation" below).

### 4.2.5 Comparison matrix (consolidated)

| Option | Accuracy on labels | $/page (input) | Latency | FedRAMP (commercial) | FedRAMP (gov) | On-prem? | License |
|---|---|---|---|---|---|---|---|
| Google Document AI | Good | $0.0015 base / $0.01 layout | 1–2s | Inherited High | Assured Workloads High | No | Proprietary |
| AWS Textract | Good (forms-tuned) | $0.0015 base / $0.05 forms | <1s | **Moderate (service-listed)** | **High in GovCloud** | No | Proprietary |
| Azure Doc Intelligence | Good + style add-on | $0.0015 + $0.006 style | 1–2s | High (P-ATO) | **High Az Gov + IL2/4/5** | **Yes (container)** | Proprietary |
| Tesseract 5 | Mediocre on photos | $0 + compute | <0.5s | n/a | n/a | Yes | Apache 2.0 |
| PaddleOCR (PP-OCRv5) | Best open-source | $0 + compute | 0.3–1s GPU | n/a | n/a | Yes | Apache 2.0 |
| EasyOCR | OK | $0 + compute | 0.5–2s | n/a | n/a | Yes | Apache 2.0 |
| Claude 3.5 Sonnet (Bedrock) | Excellent | ~$0.005–0.02/img | 1–4s | High (Bedrock) | **High GovCloud + IL4/5** | No (use open VLM) | Proprietary |
| GPT-4o (Azure OpenAI) | Excellent | ~$0.005–0.02/img | 1–3s | High (Azure) | **High Az Gov + IL4/5/6** | No | Proprietary |
| Gemini 2.5 Pro (Vertex) | Excellent | ~$0.003–0.015/img | 1–3s | n/a (GA on Vertex) | **High via Vertex** | No | Proprietary |
| Qwen2.5-VL 7B/72B | Very good (≈GPT-4o) | $0 + GPU compute | 2–8s | n/a | n/a | **Yes** | Apache 2.0 |
| Llama 3.2 Vision 11B/90B | Good | $0 + GPU | 2–10s | n/a | High via Bedrock GovCloud | **Yes** | Llama Community |
| Pixtral 12B | Very good | $0 + GPU | 2–6s | n/a | n/a | **Yes** | Apache 2.0 |
| PaddleOCR-VL 0.9B/1.5 | Excellent on docs | $0 + GPU | 1–3s | n/a | n/a | **Yes** | Apache 2.0 |

### 4.2.6 Recommendation

**Prototype pick:** **Azure AI Document Intelligence (Read + Layout + styleFont add-on)** in commercial Azure during dev, fronted by a `VisionExtractor` interface (Q4.9). Optionally augment with a single Claude-via-Bedrock or Gemini-via-Vertex call per warning region for layout-reasoning fallback when typography confidence is low.

**Reasoning:**
1. styleFont gives us per-token `fontWeight=bold|normal` directly — uniquely solves §16.22 detection without us building stroke-width analysis from scratch.
2. Has a **first-party Docker container** (the only one of the three majors) — cleanest substitution story.
3. Authorized at FedRAMP High in Azure Government (Arizona/Texas/Virginia) with DoD IL2/4/5 — strongest production-parity federal story.
4. Pricing is competitive ($1.50 + $6 styleFont = $7.50/1k pages; well within prototype budget).

**Production pick:** Same engine (Azure Document Intelligence Read + Layout + styleFont), running in **Azure Government via Assured Workloads** OR running on customer-managed infrastructure as the **Document Intelligence container**. ATO inherits Azure Gov FedRAMP High + DoD IL4/5.

**Open-source backstop (substitutability escape valve):** PaddleOCR (PP-OCRv5) for raw OCR + a self-hosted small VLM (Qwen2.5-VL-7B or PaddleOCR-VL 1.5) for the typography/layout reasoning where styleFont is unavailable. This gives a fully air-gapped, Apache-2.0-licensed, FedRAMP-inheritance path if Azure OCR cannot be procured for any reason.

**Substitution interface:** see Q4.9 for a concrete Python `VisionExtractor` ABC.

---

## Q4.3 — Preprocessing Pipeline

Most COLA Registry images are **2D label artwork** (PNG/JPEG of the printed label as designed) — for these, preprocessing is largely unnecessary because the artwork is already deskewed, well-lit, and not photographed. For **photographs of bottles required when labels are etched/embossed/molded/painted** (per TTB FAQ "Prepare Images for Upload"), preprocessing matters substantially.

### 4.3.1 Preprocessing operations

| Step | Purpose | Cost (latency) | Benefit | Library | Recommendation |
|---|---|---|---|---|---|
| Format/colorspace normalize (BGR→RGB, sRGB) | Consistent inputs | <10 ms | Required | OpenCV (`cv2.cvtColor`) | **Always run** |
| Resolution check (DPI metadata, pixel size) | Quality gate | <5 ms | Triage | PIL/Pillow `image.info['dpi']` | **Always run** (Q4.6) |
| Deskew | Correct rotation 0–45° | 30–80 ms | High on photos | OpenCV `minAreaRect` over dilated text contours; or Hough transform | Run if `abs(angle) > 1°` detected |
| Glare/specular highlight removal | Recover blown-out regions | 50–200 ms (inpainting) | Variable; can hurt on artwork | OpenCV `cv2.inpaint` with INPAINT_NS or INPAINT_TELEA after threshold mask | Conditional: only on bottle photos |
| Contrast enhancement (CLAHE) | Improve OCR on faded text | 20–50 ms | Medium | OpenCV `cv2.createCLAHE` | Conditional: low contrast detected |
| Background separation (label vs. bottle) | Crop to label | 100–500 ms | High on photos | GrabCut, U^2-Net saliency, or simple color thresholding | Optional, mainly for photographed bottles |
| Resolution upscaling (super-resolution) | Improve sub-1mm font OCR | 200ms–2s | Variable | OpenCV DNN super-resolution (EDSR/ESPCN models); Real-ESRGAN | Last-resort; usually not within 5s SLA |
| Color normalization / white-balance | Stable contrast metrics | 10–30 ms | Helps §16.22(a)(1) | OpenCV gray-world or simple histogram stretching | Run before contrast computation |

### 4.3.2 Latency budget within 5s SLA

A reasonable per-image preprocessing pipeline:
- Always-run normalize + DPI check + light deskew: ~50 ms.
- Conditional glare/contrast (when detected): +100–250 ms.
- OCR/VLM call: 0.5–4 s.
- Postprocess + confidence/contract assembly: <100 ms.
- **Headroom for multi-image (Q4.7):** budget enforces preprocessing-per-image cap of ~200 ms when ≥3 images per application.

### 4.3.3 Notes

- For etched/embossed/molded labels (where the label is engraved or raised on the bottle and photographed), edge-aware sharpening and adaptive thresholding (Sauvola or Niblack via scikit-image) are more useful than CLAHE. These cases are minority but should not crash the pipeline.
- Image-quality metrics (BRISQUE/NIQE, Q4.6) should run *before* preprocessing decisions so we know when an image is unrecoverable.
- Per the TTB FAQ "Prepare Images for Upload" page, applicants should crop to the label before upload; in practice many do not, so a label-vs-background separation pass is occasionally necessary.

---

## Q4.4 — Typography & Formatting Detection (PRIMARY DEPTH SECTION)

The §16.22 ruleset requires *typographic* judgments that go beyond returning text. This section addresses each rule mechanically.

### 4.4.1 Caps detection: "all-caps rendering" vs. "uppercase characters"

**The OCR distinction problem:** if OCR returns the string `"GOVERNMENT WARNING"`, that uppercase string could have been:
1. The text **rendered as small-caps** (which is allowed under §16.22 — the rule says "capital letters," and small caps are uppercase glyph forms).
2. The text **rendered in all-caps font weight** (also allowed).
3. The text **input as uppercase letters** in a mixed-case-capable font (also allowed).
4. The text **rendered in a lowercase font that the OCR misread** (very rare; would not pass).

For our purposes, all four "look uppercase" outcomes satisfy §16.22(a)(2)'s "capital letters" requirement. The verification need is simpler than it first appears: **do the rendered glyphs of the first two words look like capital letters?** This is a yes/no of the printed appearance, not of the underlying string.

Practical detection strategy:
- **Primary:** check that the OCR-returned string for the first two words equals `"GOVERNMENT WARNING"` exactly (including case).
- **Secondary (against false positives where OCR auto-uppercases):** verify glyph height is consistent across all letters (capital letters have approximately equal cap-height; if there are descenders or lowercase ascender/x-height variation, the rendering is mixed-case). Compute the bounding-box height per character/word polygon; expect low variance for true caps.
- **Tertiary:** Tesseract `WordFontAttributes.is_smallcaps` flags small-caps rendering; Azure Document Intelligence `style.fontStyle` does not directly say "all-caps" but `fontWeight` and bounding-box height patterns combined are sufficient.

### 4.4.2 Bold weight detection

This is the hardest part of §16.22 and the part most likely to produce false negatives (bold *missed*) or false positives (bold *imagined* on a heavy-regular weight).

**What major engines return:**

| Engine | Per-token bold output | Notes |
|---|---|---|
| Tesseract (legacy --oem 0) | `WordFontAttributes` `is_bold` boolean from `FontInfo.is_bold()` | Works on legacy engine; accuracy mixed; LSTM (`--oem 1`, default) does not populate it reliably (issue #1074). |
| Tesseract (LSTM --oem 1) | Effectively unavailable | Issues #1074, #1371, #2781 confirm font-attributes are broken with LSTM models. |
| PaddleOCR (PP-OCR v5) | Not natively returned | Layout output gives boxes/cells but not weight. PP-StructureV3 detects headings (which often correlate with bold) but not bold directly. |
| EasyOCR | Not returned | Text + bbox + confidence only. |
| AWS Textract | Not returned | No font-weight in `Block` schema. |
| Google Document AI | **`Document.Page.Token.StyleInfo`**: `font_weight` (numeric) and `bold` boolean ("equivalent to font_weight is at least 700") per the StyleInfo class reference. Also `font_size` in points and pixels, `letter_spacing`, `font_type`. | This is per-token, post-processing-detected from the rendered glyphs. Quality varies. |
| Azure Document Intelligence | **`styles[].fontWeight`** = `"bold" \| "normal"` with confidence; per text-span via `spans[].offset` / `spans[].length` referencing the global `content` string. Requires `features=styleFont` add-on (+$6/1k pages). | Most direct match for §16.22(a)(2). |
| Claude / GPT-4o / Gemini (VLM) | Yes, when prompted, qualitative ("the text 'GOVERNMENT WARNING' appears bold; the remainder is regular weight"). Self-reported, not logit-based. Reliability varies; needs structured-output schema discipline. | Excellent for sanity-checking; not a substitute for a calibrated detector. |

**Stroke-width-based bold detection (the open-source fallback):**

The Stroke Width Transform (SWT) — Epshtein, Ofek & Wexler (CVPR 2010) — computes per-pixel stroke width as the distance between paired image gradients. Bold text has measurably wider strokes (relative to glyph height) than regular text in the same font family. Algorithm summary:
1. Run Canny edge detection.
2. For each edge pixel, traverse along the gradient direction until hitting an opposite-gradient edge; record the distance as the stroke width.
3. Group pixels into connected components (candidate characters).
4. Compute median stroke width per character / per word.
5. Compute the ratio `stroke_width / x_height` (or `/ char_height`). Empirically:
   - Regular weight: ratio ≈ 0.06–0.10
   - Bold weight: ratio ≈ 0.12–0.18
   - Heavy/black: ratio > 0.20
6. Bold detection: threshold the ratio (e.g., >0.11) within the same word/line context.

A more script-aware alternative is the **morphological-opening bold detector** (Sai et al., NCVPRIPG 2013): open the binarized sub-image with a structuring element sized to `stroke_width(s) + 1`. Normal text disappears; bold characters partially survive. Used as a Boolean detector, this is robust to fonts and scripts.

Both SWT-based methods are CPU-fast (10–100 ms per warning region) and well-suited as a deterministic backstop when the OCR engine doesn't return weight.

**Bold detection failure modes:**
- **Heavy regular vs. bold:** "Helvetica Black" (a heavy regular weight) can stroke-width-match a "Helvetica Bold." Without font-family info, a stroke-width detector cannot disambiguate. Practical mitigation: §16.22 doesn't actually distinguish "bold" from "heavy" — the underlying intent is *visual emphasis*. We adopt a permissive threshold that accepts any weight ≥ semibold as compliant for the GOVERNMENT WARNING prefix, and rejects only when the prefix weight is *not measurably greater* than the remainder weight in the same image (relative comparison rather than absolute threshold).
- **Compressed/condensed bold:** "Compressed" fonts have narrower glyphs but identical stroke-to-x-height ratios; the §16.22(a)(3) "letters not compressed" rule is a *separate* test (Q4.4.4 below).
- **Anti-aliased rendering at low DPI:** at 120 DPI minimum (TTB FAQ), 1 mm text height is ~5 px — anti-aliasing dominates and stroke-width measurement becomes noisy. Mitigation: compute SWT only when DPI ≥ 200 (300 DPI is recommended by practitioners); for lower DPI, fall back to engine-reported weight + VLM verification.

### 4.4.3 Continuous-statement vs. broken-layout detection

§16.22 requires the warning be a "continuous paragraph" — not split with arbitrary other content interleaved.

Detection approach:
1. Identify the line/word polygons containing the warning text (via OCR result iterator).
2. Check that consecutive lines have:
   - Approximately consistent baseline-to-baseline spacing (within ±50% of median line height).
   - Approximately consistent left-edge alignment (within a paragraph), or center-alignment, or justified, but not jumping panels.
   - No intervening unrelated text between warning lines (no third-party text, image elements, or large gaps > 2× line height).
3. If the warning text spans multiple OCR `paragraph` blocks (Azure Document Intelligence and Google Document AI both have `paragraph` granularity), this is a discontinuity flag.

Edge case: §16.22(a)(2) and TTB FAQ explicitly allow other text *on the same line as the last sentence of the warning* (e.g., "contains sulfites") provided it is "separate and apart" — this is a regulatory carveout the rule engine handles, but the vision layer should still report exact bbox/spacing so the rule engine can adjudicate.

### 4.4.4 Font size in physical units (mm) — DPI math

**Conversion math:**
- `text_height_inches = text_pixel_height / image_DPI`
- `text_height_mm = text_height_inches × 25.4`

DPI source priority:
1. **Image embedded DPI metadata** — JPEG (Exif `XResolution`/`YResolution`), PNG (`pHYs` chunk).
2. **Form 5100.31 Item 9 dimensions** — applicant declares the printed label width × height in mm (or inches). Then `DPI = image_pixel_width / printed_label_width_inches`. This is the most authoritative source because it ties to the actual printed label, not to scanner metadata that may be wrong.
3. **TTB COLAs Online Step 3 dimensions field** — same data as Form 5100.31 but captured in the online flow.
4. **Fallback (low confidence):** TTB FAQ minimum 120–170 DPI assumption. Use only for triage; never for compliance decisions.

**Compressed-letters detection (§16.22(a)(3)):**
- For each warning character, compute width / height aspect ratio.
- Compare against typical aspect ratios for the detected font family or against a "normal" range (~0.4–0.7 width-to-height for Latin uppercase).
- Flag aspect ratios <0.35 as potentially compressed.
- Cross-check against §16.22(a)(4) chars-per-inch table (1mm=40 cpi max, 2mm=25, 3mm=12) — compute CPI from `(num_chars / line_pixel_width) × DPI` and compare to the rule's max.

**Container-size to font-size mapping (§16.22(b)):**
- ≤237 mL (8 fl oz): 1 mm minimum
- 237 mL < container ≤ 3 L: 2 mm minimum
- > 3 L: 3 mm minimum
- The vision layer reports the measured mm; the rule engine matches against the container size from net-contents extraction.

### 4.4.5 Edge cases

- **OCR cannot tell bold vs. heavy regular** (covered above): mitigation = relative comparison within the same image, plus VLM second opinion.
- **Warning in non-Latin script** (e.g., import labels with the warning translated — though TTB requires the *English* warning per ABLA): Tesseract supports 100+ scripts; PaddleOCR supports 100+; Azure Document Intelligence Read supports ~165 languages. But §16.21 mandates the **exact English text**, so any non-English warning is a compliance failure regardless of detection. The vision layer's job here is just to detect that an English-warning span is *missing*.
- **Decorative/shadow drop-shadows on the warning** can confuse stroke-width detection. Mitigation: SWT is robust to outline effects only when used carefully; binarization with adaptive thresholding before SWT helps.
- **Foil/embossed/printed-on-glass warnings** photographed with glare on the warning: the warning region might fail BRISQUE/NIQE quality gating; surface as "needs better photo" (Q4.6) rather than guessing.
- **Compressed → unreadable:** §16.22(a)(3) says letters cannot be compressed in a manner that makes the warning not readily legible. This is a judgment call combining aspect ratio + CPI + image quality; the vision layer should report all three signals and let the rule engine combine them.

### 4.4.6 Contrasting-background detection (§16.22(a)(1))

§16.22(a)(1) requires the warning be on a "contrasting background." TTB has no published numeric threshold. The vision layer computes signals; the rule engine applies policy (consistent with per-field match policies).

**Computation:**
1. From the warning text bbox/polygon, segment foreground (stroke) pixels via Otsu/Sauvola adaptive threshold within the region.
2. Compute median foreground luminance L_fg and median background luminance L_bg in CIE Lab L* channel (perceptually uniform; better than raw RGB).
3. Compute WCAG contrast ratio: `(max(L_fg, L_bg) + 0.05) / (min(L_fg, L_bg) + 0.05)`.
4. Also report ΔL* (Lab lightness delta) as a secondary signal — useful when foreground/background hues differ but luminances are close.
5. Detect background uniformity: standard deviation of background-pixel luminance within the bbox. High variance (e.g., warning over a busy photographic background) is itself a contrast-failure mode independent of mean contrast.

**Output to rule engine:**
```json
"contrast": {
  "wcag_ratio": 6.3,
  "delta_L_star": 58.2,
  "background_luminance_stddev": 4.1,
  "contrast_confidence": 0.92
}
```

**Policy:** the threshold (e.g., WCAG 4.5:1) is set by the rule engine, not the vision layer. The vision layer reports; the rule engine adjudicates. This separation is consistent with per-field match policies declared explicitly and is flagged in Open Questions #1 (TTB has not ratified a numeric threshold; engagement with ALFD SMEs needed).

**Failure modes specific to this check:**
- Foil-stamped, holographic, or metallic-ink warnings — luminance varies with viewing angle and is not deterministic from a single image.
- Warning printed over photographic imagery (e.g., a vineyard photo on the back of a wine label) — high background variance even when mean contrast is acceptable.
- Clear-acetate labels showing beverage color through the substrate — background luminance depends on what's in the bottle at photograph time.

For these, the contrast subsystem reports `contrast_confidence` low and surfaces a quality flag rather than a hard pass/fail.

---

## Q4.5 — Confidence Scoring Contract

Every extraction must carry a **calibrated confidence**. The contract between vision and downstream [T3](./2026-09-15-rule-engine-architecture.md) confidence-modeling layer:

### 4.5.1 What each engine returns

| Engine | Granularity | Range/scale | Calibrated? |
|---|---|---|---|
| Tesseract | per-WORD `confidence` (0–100) via ResultIterator; per-character via blob choice | 0–100 | Loosely; based on choice probabilities; can be miscalibrated post-LSTM |
| PaddleOCR | per-detection-box recognition score | 0.0–1.0 | Empirically reasonable but uncalibrated |
| EasyOCR | per-detection confidence | 0.0–1.0 | Uncalibrated |
| AWS Textract | per-WORD/LINE/CELL/QUERY_RESULT `Confidence` | 0–100 | "Probability that prediction is correct" per AWS docs; AWS recommends thresholds 50% (archival) to 90%+ (financial). Reasonably calibrated. |
| Google Document AI | per-Token `confidence`; per-StyleInfo per-attribute `confidence` | 0.0–1.0 | Per Google docs, reasonably calibrated |
| Azure Document Intelligence | per-word `confidence`; per-style `confidence` (e.g., 0.98 on bold detection); per-paragraph implied | 0.0–1.0 | Per Microsoft docs |
| VLMs (Claude, GPT-4o, Gemini) | **No native confidence**. Logit-based confidence is generally not exposed for vision models. Self-reported confidence ("I'm 90% sure") via prompt is unreliable. | qualitative | **Not calibrated** — must wrap with structured output + an out-of-band check |

### 4.5.2 Vision-layer confidence contract (proposed)

For each field in the per-field requirements table (Q4.1), the vision layer returns:

```json
{
  "field": "government_warning_text",
  "value": "GOVERNMENT WARNING: (1) ...",
  "bbox": [...polygon...],
  "image_id": "front_label_image_3",
  "confidence": {
    "extraction": 0.94,
    "typography": 0.88,
    "layout": 0.99,
    "overall": 0.85
  },
  "engine": "azure_doc_intelligence_v4.0",
  "processing_ms": 1342
}
```

`overall` is the minimum of contributing confidences (or a calibrated weighted product). [T3](./2026-09-15-rule-engine-architecture.md)'s confidence-aggregation layer will further calibrate to ground truth using a held-out labeled validation set.

### 4.5.3 Calibration

- Calibration set: a sample of past TTB approvals/rejections with known ground-truth field values.
- Method: Platt scaling or isotonic regression per engine, per field type.
- **Cross-engine normalization:** Tesseract's word confidence ranges differently from Textract's; calibrating each to a common P(correct) scale lets [T3](./2026-09-15-rule-engine-architecture.md) aggregate without engine-specific logic.

### 4.5.4 Contract with [T3](./2026-09-15-rule-engine-architecture.md) (Q3.5 deferred — cross-topic synthesis)

**Cross-topic synthesis ([T3](./2026-09-15-rule-engine-architecture.md)↔T4) is DEFERRED per task instructions.** The vision layer's responsibility is to expose the calibrated confidence per field; [T3](./2026-09-15-rule-engine-architecture.md) owns aggregation and decision-thresholding policy.

---

## Q4.6 — Failure Modes & "Needs Better Photo" Disposition

The vision layer must be willing to say "I cannot reliably extract this" rather than return a low-confidence guess that the rule engine downstream may or may not flag. This makes "needs a better photo" a first-class disposition. This is consistent with the prototype's explicit posture: "Image-quality robustness is best-effort. Labels with severe glare, extreme angles, or poor resolution may fail-out as 'needs better photo' rather than be recovered." The brief's "Notes for the researcher" reinforces this: graceful degradation, not heroic recovery.

### 4.6.1 Failure-mode taxonomy

| Failure | Detector | Threshold | Disposition |
|---|---|---|---|
| Image too low resolution | Pixel dimensions + DPI metadata | <120 DPI per TTB FAQ; <800 px on long edge | "needs better photo: low resolution" |
| Severe blur | BRISQUE (Mittal, IEEE TIP 2012) and/or NIQE (Mittal et al.) | BRISQUE > 60 (0–100 scale, higher = worse); NIQE > 8 | "needs better photo: blurred" |
| Severe glare/reflection | Local saturation analysis: count of pixels with V>240 in HSV inside the label region | >5% of label area saturated | "needs better photo: glare obscures content" |
| Rotated past recoverable angle | Hough/minAreaRect angle detection | abs(angle) > 45° with low text-density → unrecoverable | "needs better photo: orientation not recoverable" |
| Partial occlusion | Connected-component analysis vs. expected label aspect; or VLM-prompted check | label coverage <85% of image | "needs better photo: label partially occluded" |
| Multiple labels in one image (front + back photographed together) | Saliency / region-proposal detector | >1 label-shaped region detected | Either auto-split or "please upload separately" |
| OCR returns no text | Engine returns empty | n/a | "no text extracted — possibly blank/wrong image" |
| Warning text not detectable on any image | Across all uploaded images | Required warning not found with reasonable confidence | Pass to rule engine as "warning not detected" — *not* a vision-layer "needs better photo" |

### 4.6.2 BRISQUE/NIQE for quality gating

- **BRISQUE:** SVR trained on natural-scene statistics in the spatial domain. Returns a single score 0–100 (lower = better). LIVE database benchmark; widely used. OpenCV has BRISQUE via the `quality` module; Python implementations are mature.
- **NIQE:** completely blind; based on natural-scene-statistic deviation. Doesn't require training on distorted images. Returns ~3 (sharp) to ~12 (very blurred). Experimentally NIQE better discriminates blur, BRISQUE better discriminates noise (per JATIT V99 No9 study).
- **PIQE:** alternative perception-based metric, complementary to BRISQUE/NIQE.
- Best practice: **run BRISQUE + NIQE in parallel; gate when both fail their respective thresholds**, to reduce false positives.

### 4.6.3 Disposition output

The vision layer's response envelope includes a top-level `disposition` field:
- `"ok"` — extracted with reasonable confidence
- `"needs_better_photo"` — with `reason` field from above taxonomy
- `"engine_failure"` — internal error, retry possible
- `"format_rejected"` — image format/size violates TTB upload rules (handled before vision layer in most cases)

This disposition is a first-class signal to the orchestrating agent.

---

## Q4.7 — Multi-Image Handling

Per TTB rules, a single application can have several uploaded images: front, back, neck, side, can-flat, "wrap." The COLAs Online Step 3 image-tagging UI lets applicants tag each image as "Brand," "Back," "Neck," "Side," "Other." The §16.21 warning can appear on **any** of these labels.

### 4.7.1 Approach

1. **Process images independently** through the vision layer (parallel), returning per-image per-field extractions.
2. **Tag each extraction with `image_id` and `panel`** (from COLAs Online metadata when available; from heuristic detection otherwise). Provenance is essential for the rule engine to explain its decision.
3. **Cross-image deduplication and reconciliation:**

   *Deduplication* applies to fields that may legitimately appear on multiple panels:
   - **Government warning:** if the same warning text appears on both front and back at high confidence, this is **one** compliant warning instance, not two violations and not double-counting toward §16.21. Dedup key: normalized warning text (case-folded, whitespace-collapsed). All instances must individually pass §16.22 formatting; the rule engine adjudicates the union.
   - **Brand name:** brand commonly appears on front, back, neck. Dedup key: case-folded, punctuation-stripped string with edit-distance ≤2 fold-in (handles OCR noise across panels). Report all surface forms back to the rule engine — Dave's STONE'S THROW vs. Stone's Throw test depends on the rule engine seeing the variants, not the vision layer collapsing them.
   - **ABV, net contents, class/type, bottler:** dedup by canonical-form match (post-unit-normalization for net contents, post-tolerance-rounding for ABV).

   *Reconciliation* applies when fields conflict across images:
   - Aggregate by highest-confidence value, but **always preserve the per-image evidence** so the rule engine can flag conflicts.
   - **Conflict policy:** if "Brand X" appears on the front at confidence 0.95 and "Brand Y" appears on the back at confidence 0.88, the vision layer returns both with provenance; the rule engine decides whether this is a typo, an OCR error, or a genuine compliance issue.
   - For the warning specifically: detection on **any** image with sufficient quality is compliant per §16.21 placement rules (front/back/side all acceptable). Multiple appearances each get individual §16.22 verification.

4. **Performance budget:** for K images per application within the 5s SLA:
   - Parallelize image processing (each preprocessing + OCR/VLM call independently).
   - Practical cap: 5 images × ~1 s/image with 2-3-way parallelism = ~2–3 s wall-clock.
   - For applications with >5 images, the orchestrator enforces a queue; remaining images processed beyond 5s SLA but still asynchronously delivered to the rule engine.

5. **Session-only constraint:** no inter-application caching; deduplication scope is bounded to the images of one application within one processing session. Persistent dedup across applications would require persistent storage that the prototype explicitly does not have.

### 4.7.2 Provenance

Every extracted field carries:
- `image_id` (uploaded filename / COLAs Online image ID)
- `panel` (from applicant tag or heuristic)
- `bbox` (polygon on that image)
- `engine` and `engine_version`
- `processing_timestamp`

This enables the rule engine to render decisions like "Warning detected on 'back_label_2.png' at panel=Back, position [polygon], formatting verified OK."

### 4.7.3 Leveraging COLAs Online Step 3 metadata

When the upstream submission flow provides applicant-supplied panel tags, the vision layer **uses them as priors** (not as ground truth — applicants make mistakes). For example, if applicant says image is "Back" and we detect a brand-name centered prominently with no warning, we accept the tag. If applicant says "Back" but we detect what looks like the front (large brand mark, no warning, no nutritional/back-of-label content), we surface a low-priority "label tag mismatch" warning to the human reviewer.

---

## Q4.8 — Multilingual & Non-English Labels

Imports may have predominantly non-English content (e.g., Spanish on tequila, French on Bordeaux, Italian on amari, German on Riesling). The §16.21 *warning* must be in English regardless. Other label content (brand, class, etc.) may be in another language with English equivalents required per separate TTB rules.

### 4.8.1 Scope decision

- **Prototype scope:** English warning detection + bilingual brand/class extraction (best-effort). Out-of-scope: full non-English text extraction, sentiment/regulatory checks on non-English claims.
- **Production scope:** support for ~10–20 languages covering the majority of imports (Spanish, French, Italian, German, Portuguese, Japanese, Mandarin/Cantonese for sake/baijiu imports, Greek, etc.). Required for production by TTB workflow, deferred for prototype.

### 4.8.2 Multilingual capability of each option

| Option | Languages |
|---|---|
| Tesseract | 100+ (script files); 35+ scripts |
| PaddleOCR (PP-OCRv5) | 100+ (PaddleOCR-VL: 109–111) |
| EasyOCR | 80+ |
| Google Document AI / Cloud Vision | ~200+ for OCR |
| AWS Textract | Extended set added 2023; documented support is narrower than competitors but growing |
| Azure Document Intelligence (Read) | ~165 languages |
| Claude / GPT-4o / Gemini (VLMs) | Effectively all major scripts; quality varies but covers the import set well |

### 4.8.3 Graceful degradation

For prototype:
- Run primary engine in English mode for warning detection.
- Run a secondary multilingual pass (in PaddleOCR multilingual mode or VLM with a prompt like "extract all text regardless of language") for full text capture.
- If no English warning is detected on any image and the application is flagged as an import (from Form 5100.31 metadata), surface to the rule engine: "warning not detected — possible English-warning compliance failure on import."

---

## Q4.9 — Production-Parity Substitution Story

This section directly implements the substitutability mandate.

### 4.9.1 Migration architecture

The vision layer is wrapped behind an abstract interface. The orchestrating application instantiates a concrete `VisionExtractor` subclass at startup based on configuration. **No application code references engine-specific types.**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict

class Disposition(Enum):
    OK = "ok"
    NEEDS_BETTER_PHOTO = "needs_better_photo"
    ENGINE_FAILURE = "engine_failure"
    FORMAT_REJECTED = "format_rejected"

@dataclass
class Polygon:
    points: List[tuple]  # [(x1,y1), (x2,y2), ...]

@dataclass
class Confidence:
    extraction: float
    typography: float
    layout: float
    overall: float

@dataclass
class TypographyAttrs:
    is_bold: Optional[bool]
    is_italic: Optional[bool]
    is_caps: Optional[bool]
    font_size_mm: Optional[float]
    similar_font_family: Optional[str]
    bold_confidence: Optional[float]

@dataclass
class ExtractedField:
    field_name: str
    text: str
    bbox: Polygon
    image_id: str
    panel: Optional[str]
    typography: Optional[TypographyAttrs]
    confidence: Confidence
    engine: str
    engine_version: str

@dataclass
class ImageQualitySignals:
    dpi: Optional[float]
    brisque_score: Optional[float]
    niqe_score: Optional[float]
    glare_fraction: Optional[float]
    skew_degrees: Optional[float]

@dataclass
class ExtractionResult:
    image_id: str
    fields: List[ExtractedField]
    disposition: Disposition
    disposition_reason: Optional[str]
    quality: ImageQualitySignals
    processing_ms: int

class VisionExtractor(ABC):
    """Abstract vision-layer interface. Implementations swap freely."""

    @abstractmethod
    def extract(
        self,
        image_bytes: bytes,
        image_id: str,
        applicant_panel_tag: Optional[str] = None,
        printed_label_dims_mm: Optional[tuple] = None,  # (width_mm, height_mm) from Form 5100.31
        beverage_class: Optional[str] = None,            # 'wine'|'spirits'|'malt'
        target_fields: Optional[List[str]] = None,
    ) -> ExtractionResult: ...

    @abstractmethod
    def supports_typography(self) -> bool: ...

    @abstractmethod
    def supports_languages(self) -> List[str]: ...

    @property
    @abstractmethod
    def engine_name(self) -> str: ...

    @property
    @abstractmethod
    def fedramp_status(self) -> Dict[str, str]:
        """e.g., {'commercial': 'Inherited (Az High)', 'gov': 'FedRAMP High'}"""
        ...
```

Concrete implementations to ship in the prototype:
- `AzureDocIntelligenceExtractor` (cloud)
- `AzureDocIntelligenceContainerExtractor` (on-prem container, same API surface)
- `PaddleOCRExtractor` (open-source, on-prem)
- `BedrockClaudeExtractor` (cloud VLM, FedRAMP High via GovCloud Bedrock)
- `HybridOCRPlusVLMExtractor` (composes a raw-OCR engine + VLM for typography)

### 4.9.2 Quality gap (cloud vs. best on-prem, 2026 state)

| Aspect | Cloud (best) | Best on-prem | Gap |
|---|---|---|---|
| Raw OCR accuracy | Azure Read / Document AI | PaddleOCR PP-OCRv5 | Small (a few % CER on label-style imagery) |
| Layout/structure | Azure prebuilt-layout, Document AI Layout Parser | PP-StructureV3, PaddleOCR-VL 1.5 | Closing rapidly; PaddleOCR-VL leads OmniDocBench |
| Per-token bold/style | **Azure styleFont (unique)** | Stroke-width transform + VLM | Azure has a real edge here; on-prem requires more engineering |
| Latency | Sub-2s typical | Sub-3s on GPU; 3–8s on CPU | Cloud wins on cold-start, on-prem can win on warm path |
| Reasoning over content | VLM (Claude/Gemini/GPT-4o) | Open VLM (Qwen2.5-VL, PaddleOCR-VL, Pixtral) | 2024 gap was large; 2025/2026 gap is small per OmniAI bench (open ≈ 75% vs. GPT-4o 75%) |

### 4.9.3 Hardware requirements for on-prem

- **PaddleOCR (PP-OCRv5):** runs on CPU (slow) or modest GPU (T4/L4/A10 24GB). Prototype-level: a single L4 or A10 handles 5–20 req/s.
- **Qwen2.5-VL-7B:** single A10/L4 GPU, ~16-24GB VRAM; 4-bit quantized fits on consumer 16GB cards.
- **Qwen2.5-VL-72B / Llama 3.2 90B Vision:** multi-GPU, A100/H100 class.
- **PaddleOCR-VL 0.9B / 1.5:** consumer GPU; very efficient.
- **Azure Document Intelligence container:** Microsoft publishes Linux container images; runs on commodity CPU for Read, GPU optional for Layout/Custom; commitment-tier license required.

### 4.9.4 Phased migration

Cloud inference is acceptable for the prototype; the architecture is *designed* to allow the swap to on-prem, but the swap is not implemented in the take-home. The phased plan below is what production looks like once that swap becomes mandatory.

- **Phase 0 (prototype):** Azure Document Intelligence (cloud, commercial Azure, Read + Layout + styleFont).
- **Phase 1 (ATO prep):** Same engine, deployed in Azure Government with FedRAMP High inheritance via Assured Workloads.
- **Phase 2 (production):** Azure Document Intelligence container deployed in customer-managed environment (TTB-controlled cloud or on-prem) for the most data-sensitive workloads.
- **Phase 3 (full open-source fallback):** PaddleOCR + Qwen2.5-VL or PaddleOCR-VL hosted in Azure Gov / AWS GovCloud / on-prem GPU servers; preserved as a "break glass" option if Azure Document Intelligence becomes unavailable for any reason. The interface guarantees code paths don't change.

---

## Q4.10 — Real-World Label Characteristics (gated by [T2](./2026-09-15-cola-operational-context.md))

[T2](./2026-09-15-cola-operational-context.md) confirmed inputs to the system:
- **Format:** JPEG/PNG only (PDF/TIFF rejected).
- **File size:** ≤1.5 MB per image.
- **Resolution:** 120–170 DPI minimum per TTB FAQ; 300 DPI recommended by practitioners.
- **Color:** full color permitted; black-and-white discouraged.
- **Multi-image:** front/back/neck/side/can-flat/wrap each uploaded separately.
- **Etched/embossed/painted/molded:** photograph of filled bottle required (not artwork).
- **Volume:** 55,528 label apps received YTD 2026; processing 1–5 days.

### 4.10.1 What can be inferred from the public Public COLA Registry interface

The Public COLA Registry (ttbonline.gov/colasonline/publicSearchColasBasic.do) exposes images for COLAs from 1999-present. The interface is searchable but not bulk-downloadable without scraping. From TTB documentation and reasonable practitioner knowledge:

- **Typical image: front-only label artwork (PNG/JPEG)** at ~150 DPI, sized 800–2000 px on the long edge, with a file size well under the 1.5 MB cap.
- **Mode:** rectangular 2D label artwork with the design exactly as printed. This is the common case and benefits from minimal preprocessing.
- **Decorative complexity:** highly variable. Wine labels in particular have ornate calligraphic typefaces, illustrations, foil simulations, watermarks, and color gradients — these stress traditional OCR (Tesseract struggles) but are well within VLM and modern PaddleOCR/Azure capabilities.
- **Text density:** front labels often low text density (brand, vintage, varietal). Back labels often high (warning, nutritional, distributor info, marketing copy).
- **Multi-image distribution:** anecdotal practitioner reports suggest wine COLAs commonly have 2 images (front + back); spirits commonly 2–3 (front + back + neck); malt beverages variable; some applications have 5+. **Empirical distribution from a sampled subset of the registry would be a research-gap to fill in a follow-on.**
- **Etched/embossed/molded:** practitioner reports suggest a small but non-zero share. These photographs introduce the heaviest preprocessing burden (Q4.3).
- **Clear acetate** (per Form 5100.31 instructions): labels are often printed on transparent acetate that shows the bottle contents through the label. The submitted image is then a photograph of the bottle with the acetate label affixed, which has unique challenges (color background = beverage color showing through; specular reflection from acetate; varying contrast).

### 4.10.2 Gap

A meaningful sample of the Public COLA Registry (n ≥ 500 across wine, spirits, malt) would establish:
- Concrete distribution of resolution, DPI, file size.
- Distribution of image count per application and panel mix.
- Frequency of edge cases (etched/embossed/painted, transparent labels, photographic vs. artwork).

The Public COLA Registry provides programmatic access via the API (catalog.data.gov references "API Docs" for the registry); a sampling effort is **out of scope for this T4 research** but should be planned as a follow-on data-collection task. Its findings would calibrate preprocessing thresholds, BRISQUE/NIQE gates, and the bold-detection threshold ratios in Q4.4.

---

## Cross-Topic Synthesis Questions (X-1, X-2, X-3): DEFERRED

Per the task instructions, cross-topic synthesis questions (e.g., interactions between [T1](./2026-09-15-ttb-regulatory-framework.md) regulatory framework, [T3](./2026-09-15-rule-engine-architecture.md) confidence model, and T4 vision layer; [T5](./2026-09-15-llm-orchestration-architecture.md)/[T6](./2026-09-15-batch-processing-architecture.md) agent-orchestration questions; [T7](./2026-09-15-federal-deployment-compliance.md) reporting/UI integration) are explicitly **deferred** to a separate synthesis pass.

---

## Summary Recommendations

1. **Prototype primary engine: Azure AI Document Intelligence** (Read + prebuilt-layout + styleFont add-on), in commercial Azure during dev.
   - Per-token `fontWeight=bold|normal` is a unique fit for §16.22.
   - Has a first-party on-prem container (substitutability satisfied).
   - FedRAMP High in Azure Government + DoD IL2/4/5 (the federal-policy story).
2. **Prototype VLM augmentation:** Claude 3.5 Sonnet via Bedrock GovCloud (FedRAMP High + IL4/5) for warning-region typography sanity-checks. Triggered only when styleFont confidence is below threshold.
3. **Production primary engine:** Same Azure Document Intelligence in Azure Government (Assured Workloads, FedRAMP High path).
4. **Open-source backstop ("break glass"):** PaddleOCR (PP-OCRv5) + Qwen2.5-VL-7B or PaddleOCR-VL 1.5, both Apache 2.0, deployable on any FedRAMP-High-authorized GPU compute (or on-prem). Stroke-Width Transform-based bold detector implemented as a deterministic fallback when no engine-native fontWeight is available.
5. **Substitution interface:** the `VisionExtractor` ABC defined in Q4.9. All application code uses this; no engine-specific types leak.
6. **Confidence contract:** structured per-field confidence (extraction, typography, layout, overall), calibrated via Platt or isotonic regression against a held-out labeled set; [T3](./2026-09-15-rule-engine-architecture.md) owns aggregation and policy.
7. **Quality gating:** BRISQUE + NIQE in parallel for blur detection; HSV-saturation analysis for glare; DPI metadata + Form 5100.31 dimensions for resolution gating. "needs better photo" is a first-class disposition.
8. **Preprocessing:** minimal for COLA Registry artwork (always-run normalize + DPI + light deskew); conditional more-aggressive pipeline for photographs of bottles (etched/embossed/molded/painted).
9. **Multi-image handling:** parallel processing with provenance per field; leverage COLAs Online Step 3 panel tags as priors not ground truth; session-only dedup scope.
10. **Multilingual:** English-warning detection in scope for prototype; broader multilingual extraction deferred to production scope.

## Open Questions / Research Gaps

1. **WCAG-equivalent contrast threshold for §16.22(a)(1) "contrasting background":** TTB regulations do not specify a numeric contrast ratio. Recommend engaging ALFD subject-matter experts to ratify a luminance-contrast policy (e.g., WCAG AA 4.5:1 or AAA 7:1, or a TTB-specific value). The vision layer can compute multiple ratios (see Q4.4.6); the policy decision belongs to TTB.
2. **Public COLA Registry empirical sampling:** distribution of resolution/DPI, image count per application, panel mix, and edge-case frequency (etched/embossed/clear-acetate) needs a sampled study (n≥500). Required for calibrating thresholds.
3. **Bold/heavy-regular disambiguation:** §16.22 does not formally distinguish them; we recommend a permissive policy (any weight ≥ semibold, with weight strictly greater than the rest of the warning, satisfies). Confirm with ALFD.
4. **FedRAMP-High status of newest model snapshots** (Claude Sonnet 4.5/4.6, Opus 4.x; GPT-5.x in Azure Gov; Gemini 3.x in Vertex Gov): authorization of specific snapshots lags the public-cloud release. Re-verify against marketplace.fedramp.gov at design-finalization time. The architecture should not assume the very-latest model is FedRAMP-authorized in Gov regions; pin to a specific authorized snapshot.
5. **Azure Document Intelligence container licensing/commitment-tier costs** for production-scale on-prem deployment: needs procurement-side investigation; not publicly priced for arbitrary deployment.
6. **Latency budget for VLM second-opinions within 5s SLA**: requires empirical measurement on representative TTB images at the chosen production endpoints (Bedrock GovCloud Claude, Vertex Gemini, Azure OpenAI Gov GPT-4o). Single-image VLM calls are typically 1–4 s; with K=3 images and a VLM call per warning, the 5s SLA may not hold. The recommended mitigation is to invoke VLM only conditionally on low styleFont confidence and only on the cropped warning region (not the full label), making sub-second VLM latency achievable.
7. **AWS Bedrock vs. Vertex Gemini vs. Azure OpenAI as the FedRAMP-High VLM endpoint** is partly a procurement question rather than a technical one: all three offer FedRAMP-High-authorized VLM access in Gov regions; the choice may be governed by existing TTB cloud-procurement vehicles rather than capability differences.