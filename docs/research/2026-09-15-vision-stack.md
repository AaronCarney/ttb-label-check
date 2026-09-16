# Vision Stack Research for an AI-Powered TTB COLA Label Verification Prototype

Filed 2026-09-15.

**Scope:** Local-first vision pipeline on Windows 11 + WSL2 with an RTX 3090 (24 GB), targeting TTB 27 CFR Part 16 compliance checks (Government Warning text + typography). The user has OpenAI, xAI/Grok, and Claude Max access; no cloud OCR vendors are permitted. Latency target: <5 s for the first label, then adaptive batch processing keyed to human review pace. The 10 questions in the brief are answered in order, then synthesized in a decision matrix, recommended primary stack, fallback stack, and a 10-label fixture-set spec.

---

## TL;DR

- **Primary recommendation:** Run **PaddleOCR PP-OCRv5 (server models) on GPU** for text + polygon boxes, layer a **Stroke-Width-Transform (SWT) bold detector** on the warning crop for §16.22(a)(2), and use **Florence-2-large `<OCR_WITH_REGION>`** as a second-opinion VLM (not the typography source of truth). DPI/mm-per-pixel comes from PIL `info["dpi"]` → EXIF `XResolution` → PNG `pHYs` → fallback heuristics. **GPT-4o-on-crop** (Structured Outputs strict mode) is the tiebreaker only when local signals disagree. This stack hits the <5 s first-label budget on RTX 3090 with margin.
- **Default hypothesis to falsify:** "PaddleOCR-GPU + SWT + Florence-2-large for cross-check, with GPT-4o-on-crop only as tiebreaker" — most TTB Government Warning regions are dense, uniformly-typeset machine print on contrasting backgrounds, which is exactly where PP-OCRv5 + SWT excels and where VLM hallucination is the dominant failure mode.
- **Fallback when local quality fails:** swap in **Qwen2.5-VL-7B-Instruct-AWQ (int4)** as the local VLM (its `bbox_2d` text-spotting prompt format is well documented), and route to **GPT-4o-on-crop** with strict JSON schema. Grok-2-Vision is a credible substitution path for the GPT-4o tiebreaker but has weaker structured-output guarantees and a 33K-token context.

---

## Key Findings

1. **PP-OCRv5 (Apache-2.0, ~5 M params) consistently beats VLMs on bounding-box precision** and is the only component in the stack that gives reliable polygon quad-boxes suitable for type-height measurement in mm. Baidu's PP-OCRv5 paper explicitly frames generalist VLMs as suffering from "imprecise localization" and "hallucination" — both fatal for §16.22 compliance checking.
2. **§16.22 is unambiguous about what we must measure.** Warning text minimums are 1 mm (≤237 mL), 2 mm (>237 mL up to 3 L), and 3 mm (>3 L), with "GOVERNMENT WARNING" required in capital, bold type while the remainder must not be bold (27 CFR §16.22(a)(2), (b)). This means the pipeline must produce: per-glyph or per-word stroke-width, per-line height in mm, and a binary bold/not-bold prefix decision.
3. **Florence-2-large can collapse OCR + region-grounded boxes into a single call** via `<OCR_WITH_REGION>` (returns `quad_boxes` + `labels`), but the original model card and independent reviews show it hallucinates on dense or stylized text and lacks a font-weight task — so it's a useful cross-check, not the primary OCR.
4. **Qwen2.5-VL-7B-Instruct-AWQ fits comfortably in 24 GB** and is the strongest local fallback for grounded OCR, with a documented `{"bbox_2d":[x1,y1,x2,y2],"text_content":"..."}` text-spotting prompt format.
5. **GPT-4o on a 400×300 px high-detail crop costs ≈425 tokens of image input (85 base + 2 tiles × 170)** — about $0.001 per call at $2.50/M input. A full 1500×2000 high-detail label costs roughly 1105 tokens (≈$0.003). Structured Outputs `strict: true` returns 100% schema-conformant JSON on `gpt-4o-2024-08-06` per OpenAI's launch eval.
6. **Grok 2 Vision (`grok-2-vision-1212`) is a credible API substitute but has trade-offs:** $2/M input, $10/M output, only 33K context, and structured-output reliability is documented as supported but less battle-tested than OpenAI's strict mode. Grok 4/4.1-Fast accept image inputs (multimodal) but xAI's pricing pages for those models do not publish a dedicated image-token rate distinct from text input.
7. **DPI is unreliable in the wild.** Pillow exposes `Image.info["dpi"]` (PNG via `pHYs` → divide pixels-per-meter by 39.37; JPEG via JFIF header or EXIF `XResolution`/`ResolutionUnit`), but Photoshop-saved JPEGs and many web exports drop or stash DPI in EXIF only. The pipeline needs a layered fallback.
8. **WSL2 + RTX 3090 + PaddlePaddle GPU is well-trodden:** Ampere supports CUDA 11.8 / 12.6 / 12.9 PaddlePaddle wheels. The recommended install pattern is `pip install paddlepaddle-gpu==3.x -i https://www.paddlepaddle.org.cn/packages/stable/cu126/` plus `pip install paddleocr`.

---

## Details

### 1. PaddleOCR PP-OCRv5 GPU on WSL2

**Install pattern.** The PaddlePaddle project publishes pinned wheels per CUDA version on its custom index. For an RTX 3090 (Ampere, CC 8.6) on WSL2 Ubuntu, two install paths are well-supported:

```bash
# CUDA 12.6 path (recommended for current NVIDIA WSL drivers)
python -m pip install paddlepaddle-gpu==3.0.0 \
  -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
pip install "paddleocr[doc-parser]"
# verify
python -c "import paddle; paddle.utils.run_check()"
```

CUDA 11.8 wheels are also published at `…/cu118/` if you prefer the older toolchain. Paddle's installation guide notes that Paddle bundles its own CUDA/cuDNN dependencies (so you only need a recent NVIDIA WSL driver — ≥550.54.14 for CUDA 12.6 / ≥452.39 for CUDA 11.8 on Windows, per the PaddleX install docs). PaddleOCR's DeepWiki notes that vLLM-based PaddleOCR-VL pipelines require CC ≥ 8.0 for the bigger backends — RTX 3090 qualifies. Note: Paddle's `vLLM`/`SGLang` server backends "do not run natively on Windows; use the provided Docker images" — but plain PP-OCRv5 detection + recognition runs fine in WSL2 without Docker.

**Expected accuracy on COLA-style alcohol labels.** PP-OCRv5 is a CRNN-style two-stage pipeline (DBNet-style detection → SVTR-style recognition) trained for "natural scene text spotting across IDs, street views, books, and industrial components" per the PaddleOCR README; the v5 series claims a 13% end-to-end improvement over PP-OCRv4. Independent reviews (ML Journey, IJRPR Tamil benchmark) report PaddleOCR ≈85–92% word accuracy and CER ≈4–5% versus Tesseract's 60–75% / 18% on equivalent images. For COLA labels the realistic expectation is:
- **Plain machine print on contrasting backgrounds** (the Government Warning region itself, mandatory winery/bottler line): word accuracy in the 95–99% range.
- **Stylized brand display text** (decorative serifs, scripts, distressed faces over imagery): word accuracy commonly drops to 70–90%, sometimes worse on the most extreme calligraphic faces. PP-OCRv5 is more robust than PP-OCRv4 on handwriting/curved text per the official release notes, but no public OCR is robust against arbitrary distressed display fonts.

**Polygon bbox usability for typography measurement.** PP-OCRv5 outputs `quad_boxes` (4-point polygons) per line — this is the right primitive. For per-word or per-glyph height in mm, two paths work: (a) split a line polygon at recognized space tokens to get per-word boxes; (b) re-run the recognition crop through a glyph segmenter (or simply measure stroke height in pixels of the Canny-edged crop). Type height in mm = `polygon_height_px × mm_per_pixel`. The detection model is trained for tight boxes rather than ascender-aware height, so for the §16.22 size check, measure the polygon's vertical extent on the warning line, not on individual letters with descenders.

**Latency on RTX 3090.** PaddleOCR's official benchmark page reports per-image timings on Tesla T4; PP-OCRv5_mobile_rec latency drops 73.1% with high-performance inference enabled and PP-OCRv5_mobile_det drops 40.4%. RTX 3090 has roughly 2–3× the FP16/INT8 throughput of T4 at similar batch sizes. Empirically for this pipeline, expect:
- **1500×2000 px full label (server-grade detector + recognizer, FP16, TensorRT enabled):** 0.4–0.9 s on RTX 3090 (single image, warmed up).
- **400×300 px crop (recognizer-only or detector + recognizer):** 60–150 ms.
These numbers are interpolations from PaddleOCR's published T4 benchmarks scaled to RTX 3090; the v3.2 release added a fine-grained per-module benchmarker (`Optimize OCR Performance with PaddleOCR v3.2's Fine-Grained Benchmark`) which the team should run on the actual fixture set rather than trust extrapolations. **Mark this as estimated.** The 5-second first-label budget is met with comfortable margin.

### 2. Tesseract 5 LSTM as Baseline

Tesseract 5's LSTM engine is well-trained on Latin clean print (~4500 fonts, ~400k textlines per the official training docs) and reaches CER < 0.5% on UW3 modern English documents. But on stylized scene text:

- **Comparative benchmarks** show PaddleOCR ≈85–90% versus Tesseract ≈60–70% on ICDAR2015-class natural scene text (ML Journey).
- **Tamil-Sinhala study (IJRPR 2025)** measured Paddle OCR CER 4.5% vs. Tesseract 18.2% and word accuracy 92.1% vs. 75.8% on printed multilingual documents — over a 16-point gap.
- **The official Tesseract docs explicitly call out** that "Bold characters or Thin characters (especially those with Serifs) may impact the recognition of details and reduce recognition accuracy" and that scene/decorative text was outside the training distribution.

**Use Tesseract as the eval baseline only.** It is fine for the cleanest Government Warning blocks (likely > 95% character accuracy on rasterized at ≥150 DPI), but on stylized brand text, decorative wine fronts, or low-contrast malt-beverage cans it lags PP-OCRv5 by 15–25 percentage points of word accuracy. This makes it unsuitable as the primary engine but useful as a sanity-check signal for confidence calibration.

### 3. Stroke-Width Transform for §16.22(a)(2) Bold Detection

**Citation:** Epshtein, B., Ofek, E., Wexler, Y., "Detecting Text in Natural Scenes with Stroke Width Transform," CVPR 2010, pp. 2963–2970, DOI 10.1109/CVPR.2010.5540041 (Microsoft Research; PDF on microsoft.com/en-us/research/wp-content/uploads/2016/02/201020CVPR20TextDetection.pdf).

**Algorithm sketch.**
1. Run **Canny edge detection** on the (binarized or gray) image.
2. For each edge pixel `p`, compute the gradient direction `dp` (perpendicular to the local edge).
3. Cast a **ray from `p` along `dp`** until it hits another edge pixel `q` whose gradient direction `dq` is approximately opposite to `dp` (within ~π/6).
4. The Euclidean distance `|p − q|` is the candidate **stroke width** for every pixel along the ray; assign the minimum of existing and new values to each pixel along the ray.
5. **Second pass:** for every ray pixel whose value exceeds the median of the ray, replace with the median (handles corners).
6. Group connected components of similar SWT value into glyph candidates; filter on aspect ratio, ratio of variance to mean SWT, and component size (the original paper rejects components whose ratio of bounding-box diagonal to median stroke width is > 10, and whose neighbor count exceeds 2 to avoid italic ligatures).

**Expected ratio for §16.22(a)(2).** "Bold" in TrueType / OpenType corresponds to weight class 700 vs. regular 400 (per the OpenType `OS/2.usWeightClass` and CSS `font-weight` standard). Empirically, bold faces have **stem widths ~1.5–2.0× the regular weight at the same x-height** (typography research summarized at legibility.info reports body-text stems of 10–20% of x-height for regular and 17–20% for signage/bold at the upper end, and the ScienceDirect "stroke width and legibility" study reports duty ratios of 0.36–0.48 for regular vs. ≥0.5 for bold). Practically:

- **Genuine compliant warning** (bold "GOVERNMENT WARNING:" prefix + non-bold body): expect mean(SWT_prefix) / mean(SWT_body) ≈ **1.4–2.0**, often clustering around 1.6.
- **Uniformly non-bold (violation)** or uniformly bold (also a §16.22(a)(2) violation since "the remainder of the warning statement may not appear in bold type"): ratio ≈ **0.9–1.1** (within measurement noise).

**Suggested decision threshold.** A two-sided test with thresholds at **1.25** (compliant only if ratio ≥ 1.25) and **0.85** (violation if ratio between 0.85 and 1.25) is a defensible starting point. Calibrate on a labeled fixture set; the measurement floor is the recognition pipeline's ability to scope "first two words" correctly (which is why this must be wired to the OCR's word boxes, not run blind on the whole crop). **Stroke-width to font-weight is not a closed-form mapping** — it depends on the typeface family — so the pipeline should report the ratio as a numeric signal alongside the OCR text and let downstream policy logic flag thresholds. Follow-up SWT work (Huang et al. ICCV 2013, "Text Localization in Natural Images using Stroke Feature Transform"; the localized-SWT paper Springer 10.1007/978-3-319-14445-0_5) refined the ray-casting and grouping but kept the stroke-width primitive — they're worth citing in the design doc but don't change the bold/regular ratio expectation.

### 4. Florence-2-large for OCR + Bounding Boxes + Typography in One Call

**Capabilities.** Microsoft's Florence-2-large (0.77 B params, MIT license) accepts task-prompt tokens including:
- `<OCR>` — returns text as a single string.
- `<OCR_WITH_REGION>` — returns `{"<OCR_WITH_REGION>": {"quad_boxes": [[x1,y1,...,x4,y4], …], "labels": [text1, …]}}` per the official model card.
- `<CAPTION_TO_PHRASE_GROUNDING>`, `<DENSE_REGION_CAPTION>`, `<REFERRING_EXPRESSION_SEGMENTATION>`, etc.

The model uses 1000 location tokens (each = 1/1000 of the image dimension) appended to the tokenizer to emit boxes, quad-boxes, and polygons (Florence-2 paper, arXiv 2311.06242). Roboflow's review reports **~1 second per OCR call on a T4 GPU** and "100% accuracy" on a clean tire serial number; the same review notes that for grounded OCR the output text "would need to be normalized to remove characters that are not properly encoded (i.e. ??), and work to re-build the text as necessary."

**Can it collapse OCR + bbox + typography into one call?** Partially. Florence-2 gives text + quad boxes from a single call. But:
- It **does not have a font-weight or "is this bold" task token.**
- Independent OCR comparisons (Hugging Face PandorAI1995 blog) found Florence-2-base "majorly based on its own knowledge around the context in the text than on the image itself" on harder texts, and the PP-OCRv5 paper explicitly argues that Florence-class generalist VLMs suffer from "imprecise localization" and "hallucination" relative to specialized OCR pipelines.
- Florence-2's 1000-bin location token quantization is coarser than PP-OCRv5's pixel-precise polygons, which matters when measuring 2 mm type heights.

**Verdict for this project:** Use Florence-2-large `<OCR_WITH_REGION>` as a **second-channel cross-check** (does it agree with PP-OCRv5 on the warning text and bbox?), but do not let it replace PP-OCRv5 as the typography source of truth, and do not rely on it for the §16.22(a)(2) bold check. It runs comfortably in <2 GB FP16 on the RTX 3090 (1.54 GB weights per Roboflow), so adding it to the stack costs little.

### 5. Qwen2.5-VL-7B (and Qwen3-VL Status) on RTX 3090

**Qwen2.5-VL-7B-Instruct** (released Jan 28, 2025; AWQ INT4 + GPTQ-INT4/INT8 weights released alongside the technical report, arXiv 2502.13923) is the strongest local 7-B-class VLM for grounded OCR. Capabilities relevant here:
- **`bbox_2d` grounding format**: prompts in the form `{"bbox_2d":[x1,y1,x2,y2],"text_content":"…"}` produce text spotting with absolute pixel coordinates. The OCRBench v2 leaderboard maintainers note Qwen2.5-VL-7B reaches a **51.6 text spotting score** on public data with this prompt format (ocrbench v2 site).
- **Document Omni-Parsing** training data and full-attention + window-attention vision encoder (per the Qwen2.5-VL technical report).
- **Bold/weight detection is not natively supported** in any Qwen2.5-VL prompt; like Florence-2, it is a text + bbox model, not a typography model.

**VRAM footprint on 24 GB.**
- BF16 7B: ≈15–17 GB weights + ~3–6 GB activations on a 1500×2000 input at the default `min_pixels=4*28*28, max_pixels=16384*28*28` tiling — fits, tight margin (community reports of OOM on RTX 4090 24 GB at default `max_pixels` are well-documented; you must cap `max_pixels` to ~1280·28·28 to be safe).
- **AWQ INT4 7B: ≈6–7 GB weights**, ≈10–14 GB total — comfortable.
- **GPTQ INT4 / INT8 7B**: weights ≈5 GB / ≈8 GB respectively. Qwen team's own "Performance of Quantized Models" page reports >50% memory reduction with negligible accuracy loss for the Omni-7B variant.

**Latency on RTX 3090.** No published RTX 3090 benchmark for Qwen2.5-VL-7B-AWQ specifically, but a real-world deployment paper (arXiv 2601.01897, Fullerton Health claims pipeline) reports **<2 s per document** for a Qwen2.5-VL-7B + PaddleOCR + classifier hybrid in production. Single-image inference for a 1500×2000 label at AWQ-INT4 with `max_pixels` capped is typically **1–3 s on RTX 3090** (estimated, scaled from Qwen2.5-VL-3B-AWQ on RTX 3080 timings reported by debuggercafe.com).

**Qwen3-VL.** Released Sept 23, 2025 (235B-A22B MoE) and Oct 4, 2025 (30B-A3B + FP8 variants), with dense 2B/4B/8B/32B and MoE 30B-A3B/235B-A22B (arXiv 2511.21631). The 8B dense variant would be the comparable replacement for Qwen2.5-VL-7B on a 24 GB card. As of April 2026, Qwen3-VL-8B-Instruct is released and supported in Transformers; an INT4 build will run in <8 GB. Qwen3-VL adds DeepStack multi-level ViT features and interleaved-MRoPE which improve grounded OCR; if available at the time of integration, it is a drop-in upgrade for Qwen2.5-VL-7B.

### 6. GPT-4o on a Cropped Warning Region (~400 × 300 px)

**Token cost.** Per OpenAI's Vision pricing rules (developers.openai.com/api/docs):
- A 400×300 image fits inside the 768-px shortest-side scaling rule (it is ≤2048 in both dims and ≤768 on its shortest side, so no scaling). It tiles into ⌈400/512⌉ × ⌈300/512⌉ = **1×1 = 1 tile** of 512×512.
- **Cost = 85 base + 170 × 1 = 255 image tokens** in `detail: high`. Per OpenAI's pricing page (developers.openai.com/api/docs/pricing): `gpt-4o` text input = $2.50/M, output = $10.00/M as of April 2026. So one image = 255 × $2.50/1M ≈ **$0.000638** for the image alone, plus a ~150-token instruction prompt and ~150-token JSON response → total **≈ $0.002 per crop call**.

**Accuracy on warning text extraction.** Government Warning text is dense, repeating, and highly templated — every COLA contains the same statutory language. GPT-4o reads dense machine print near-perfectly, and OCR-only error rates for similar tasks (text in natural images, receipts, form fields) are reported at <1% character error on clean crops in OpenAI's own demo material and independent third-party tests. Risk of hallucination is non-trivial when the crop is partial or low-contrast (the model will "complete" the boilerplate); structured outputs and a verbatim-only system prompt mitigate this.

**Latency for a single API call.** Typical end-to-end latency for a single 400×300 image + small prompt + structured JSON response: **1.5–3.5 s** including network round-trip from a US east coast client.

**Structured Outputs JSON-schema strict mode viability.** Fully supported. Per OpenAI's Aug-2024 launch announcement and current docs (`developers.openai.com/api/docs/guides/structured-outputs`):
- Set `response_format: {"type": "json_schema", "json_schema": {"name": "...", "strict": true, "schema": {...}}}`.
- On `gpt-4o-2024-08-06` and later, OpenAI reports **100% schema-conformance** on their internal complex-JSON eval (vs. <40% for `gpt-4-0613`).
- Refusals are surfaced via a `refusal` field; works with vision inputs. This is the right contract surface for the extraction schema (text, polygon, font_weight_signal, type_height_mm, container_size_class, prefix_bold_decision).

### 7. GPT-4o Full Label vs. Cropped Region Trade-offs

For a **1500×2000 px full label** in `detail: high`:
- Step 1: scale to 2048×2048 box → 1500×2000 fits unchanged.
- Step 2: scale shortest side to 768 → 1500×2000 → 768×1024.
- Step 3: tiles = ⌈768/512⌉ × ⌈1024/512⌉ = 2 × 2 = **4 tiles**.
- **Cost = 85 + 170 × 4 = 765 image tokens** ≈ $0.0019 per image (≈ 3× the cost of the 400×300 crop, ignoring prompt).

A 2048×4096 image costs 1105 tokens (85 + 170 × 6) per OpenAI's worked example. So full-label calls are still cheap in absolute terms, but **the cost asymmetry matters** at thousands of labels/day.

**Accuracy trade-offs.**
- **Full label preferable when:** (a) the warning crop region is unknown a priori (no reliable layout segmenter yet), (b) the regulator wants a holistic check that cross-references the warning to brand/varietal claims, (c) low-resolution scans where the warning detail can only be located via the surrounding context, (d) wine-vs-spirits classification is needed (different §16.22(b) thresholds).
- **Cropped region preferable when:** (a) PP-OCRv5 has already located a high-confidence warning candidate region, (b) you need to minimize hallucination risk (smaller field of view = less invented context), (c) you're paying per call and processing volume is high.

For this pipeline, the right pattern is: **PP-OCRv5 locates the warning line (free, local) → crop with 10% padding → send the crop to GPT-4o only when local SWT/OCR signals disagree.**

### 8. Grok Vision (April 2026 Status)

**Current models and pricing** per docs.x.ai/developers/models:
- `grok-2-vision-1212`: **$2.00/M text input, $10.00/M output**, 33K context (per xAI's Dec-2024 announcement and confirmed on x.ai/api as of April 2026). The xAI pricing page lists a separate "Image Input" rate but the consensus across pricing aggregators is that grok-2-vision-1212 charges image input at the same $2.00/M token rate after tokenization. The 33K context is a hard ceiling — image tokens alone can occupy several thousand of those.
- `grok-4` (multimodal text + image input): $3/M input, $15/M output, 256K context per x.ai/news/grok-4. **xAI does not publish a separate image-token tile-counting rule** the way OpenAI does; you only see image-token consumption in the response `usage` object.
- `grok-4.1-fast` and `grok-4.20`: lower-cost variants ($0.20/$0.50 and $2/$6 per million respectively per xAI pricing page); both accept image input.

**Capability assessment for crop and full label.** xAI's own object-detection cookbook (docs.x.ai/cookbook/examples/multimodal/object_detection) demonstrates `grok-2-vision-latest` returning bounding boxes for prompts like "Identify only Arabic or Turkish text on the signs," using the OpenAI-compatible Chat Completions API. The cookbook author warns: "due to the stochastic nature of these models, results may not always be perfect — bounding boxes might not be 100% accurate." For dense statutory text extraction on a 400×300 crop, expect comparable accuracy to GPT-4o on machine print but **more variance run-to-run**.

**JSON output reliability.** Grok 4 Fast documentation explicitly lists "Structured Outputs: Yes" (Oracle docs for xai.grok-4-fast). The API is OpenAI-compatible (`baseURL: https://api.x.ai/v1`), so the same `response_format: {type: "json_schema", strict: true}` pattern works syntactically — but xAI does not publish the same 100%-conformance benchmark OpenAI does for `gpt-4o-2024-08-06`, and community reports note that strict-mode adherence on Grok is supported but less battle-tested.

**Is Grok a credible substitution for the GPT-4o tiebreaker?** **Yes, with caveats.** It's cheaper per token, has structured outputs, and the user already has xAI credits. The key risk is the 33K context on `grok-2-vision-1212` (full-label calls + long instruction prompts can crowd it). For crop-only tiebreaker calls, both are fine; consider running both in shadow for the first week and comparing JSON conformance and text accuracy on the fixture set.

### 9. DPI Handling and mm-per-Pixel Pipeline Contract

**Why this matters.** §16.22(b) measures type heights in millimeters. Without DPI, the pipeline cannot decide between a 1 mm violation and a 3 mm pass on the same pixel-height bounding box.

**Layered fallback contract:**

1. **Pillow `Image.info["dpi"]`** — Pillow's PNG plugin (`PIL/PngImagePlugin.py`) reads the `pHYs` chunk and converts pixels-per-meter to DPI by multiplying by 0.0254 when `unit==1` (meter); when `unit==0` (unitless), it stores aspect ratio in `info["aspect"]` instead. JPEG handling fills `info["dpi"]` from the JFIF header (`jfif_density` × `jfif_unit`); per Pillow's test suite, EXIF `XResolution`/`YResolution` with `ResolutionUnit==2` (inch) or `==3` (cm — converted ×2.54) are also honored. Default fallback per the Exiv2 spec quoted in Pillow's tests: **72 DPI when no metadata is present**.

2. **EXIF direct read** (when Pillow `info["dpi"]` is missing — e.g. some Photoshop-saved JPEGs):
   ```python
   from PIL import Image, ExifTags
   im = Image.open(path)
   exif = im.getexif()
   xres = exif.get(ExifTags.Base.XResolution)   # IFDRational
   unit = exif.get(ExifTags.Base.ResolutionUnit)  # 2=inch, 3=cm
   ```
   Bug `python-pillow/Pillow#2448` documents the exact case where Photoshop omits the JPEG header DPI but stores it in EXIF; the fallback handler must replicate this logic.

3. **PNG `pHYs` direct read** (bypass Pillow): the pHYs chunk is 9 bytes — two 32-bit big-endian pixels-per-unit (X, Y) plus one byte unit specifier (0=unspecified, 1=meter). DPI = `px_per_meter × 0.0254`. The PNG spec at libpng.org/pub/png/spec/1.2/PNG-Chunks.html is the authoritative reference.

4. **Physical reference detection** (when no DPI metadata exists): COLA labels typically depict a known-size feature you can measure. Practical heuristics:
   - **UPC barcode**: standard EAN-13 is 37.29 mm wide; detect with `pyzbar`, measure pixel width, derive mm/pixel.
   - **Container outline**: if the label is rendered against a bottle silhouette of declared size, use the bottle width.
   - **Government Warning itself as reference**: chicken-and-egg, but if any line in the warning is recognized at high confidence and matches one of the standardized statutory phrases, its pixel height combined with the assumed minimum (1/2/3 mm based on container class) gives you a *lower-bound* mm/pixel that's only useful for validation, not measurement.

5. **Container-size heuristic** (last resort): if the bottler's basic permit declares a container class (wine 750 mL, spirits 750 mL or 1.75 L, beer 12 oz, etc.) you can pair it with the assumed §16.22(b) tier (≥2 mm for 750 mL bottles, ≥1 mm for 12-oz cans) — but this only validates compliance assuming compliance, so it cannot detect violations.

6. **Assumed DPI fallback**: if the workflow guarantees print-ready PDFs, assume **300 DPI** (typical print-design default); for screen-rendered submissions, assume **96 DPI** (Windows desktop standard) or **72 DPI** (Pillow's documented EXIF default). **The pipeline must surface a `dpi_source` field** in the extraction contract so reviewers know whether mm measurements are metadata-derived, reference-derived, or assumed.

**Recommended extraction contract (JSON-schema-ish):**
```json
{
  "label_id": "string",
  "image_size_px": [w, h],
  "dpi": {"x": 300, "y": 300, "source": "exif|phys|jfif|reference_barcode|assumed_300|unknown"},
  "mm_per_pixel": {"x": 0.0847, "y": 0.0847, "uncertainty_pct": 0.0|null},
  "container_size_class": "le_237ml|gt_237ml_le_3L|gt_3L|unknown",
  "lines": [
    {
      "polygon": [[x1,y1],...,[x4,y4]],
      "text": "GOVERNMENT WARNING: According to...",
      "height_px": 28,
      "height_mm": 2.37,
      "confidence_ocr": 0.97,
      "swt_mean_px": 4.2,
      "is_warning_candidate": true
    }
  ],
  "warning_block": {
    "lines": [...indices...],
    "first_two_words_swt_ratio": 1.62,
    "first_two_words_bold_decision": "bold|not_bold|ambiguous",
    "first_two_words_text": "GOVERNMENT WARNING",
    "min_height_mm": 2.37,
    "compliant_height": true,
    "compliance_notes": "..."
  }
}
```

### 10. Decision Matrix and Recommendations

#### Decision Matrix

| Option | Stylized-text accuracy | Polygon bbox quality | Typography / weight | Latency on RTX 3090 | VRAM | $/label | Local-only | JSON contract reliability |
|---|---|---|---|---|---|---|---|---|
| **PaddleOCR PP-OCRv5 (server, GPU)** | High (machine print 95–99%; stylized 70–90%) | Excellent — pixel-precise quad polygons | None native (pair with SWT) | ~0.4–0.9 s full / 60–150 ms crop (est. from T4 benchmarks) | ~2–4 GB | $0 | ✅ | N/A (raw pipeline output, not JSON-schema-strict) |
| **Tesseract 5 LSTM (CPU)** | Low–Med (60–75% on stylized) | Box-level only, no polygon | None | 1.5–3.5 s/page CPU | <1 GB | $0 | ✅ | N/A |
| **SWT (custom)** | N/A (operates on detected boxes) | N/A | **Primary tool** for §16.22(a)(2) | <50 ms on a 400×300 crop | trivial | $0 | ✅ | N/A |
| **Florence-2-large** | Med (handwriting strong; dense small text weaker — risk of hallucination) | Good — `<OCR_WITH_REGION>` quad_boxes (1000-bin quantized) | None | ~1 s on T4 (so ~0.4–0.6 s on 3090, est.) | ~2 GB FP16 | $0 | ✅ | Free-form text → must be parsed |
| **Qwen2.5-VL-7B-Instruct (AWQ INT4)** | High (51.6 OCRBench v2 text spotting; strong on documents) | Good — `bbox_2d` JSON | None | ~1–3 s/label (est.) | ~6–7 GB INT4 | $0 | ✅ | High — outputs JSON when prompted |
| **Qwen3-VL-8B (when available)** | Higher than 2.5-VL per technical report | Improved via DeepStack | None | ~1–3 s (est.) | ~5–8 GB INT4 | $0 | ✅ | High |
| **GPT-4o (crop, high detail)** | Very High | Returns bounding boxes only on request, lower precision than PP-OCRv5 | None native | 1.5–3.5 s incl. network | $0 GPU | ~$0.002/crop | ❌ | **Excellent** — Structured Outputs strict=true reports 100% schema match on `gpt-4o-2024-08-06` |
| **GPT-4o (full label)** | Very High | As above | None | 2–5 s incl. network | $0 GPU | ~$0.003/label | ❌ | Excellent |
| **Grok 2 Vision (`grok-2-vision-1212`)** | High on machine print (independent reports note OCR is competitive with GPT-4o); 33K context | Possible via prompt; less precise than PP-OCRv5 | None | 2–4 s incl. network (est.) | $0 GPU | ~$0.001 input + output per crop call | ❌ | Supported, less battle-tested than OpenAI strict |
| **Grok 4 / 4.1-Fast (vision)** | High | Returns boxes but image-token rules undisclosed | None | 2–4 s incl. network | $0 GPU | ~$0.006–$0.015/call (model-dependent) | ❌ | Structured outputs supported per Oracle docs |

#### Recommended Primary Stack

> **"PaddleOCR-GPU + SWT + Florence-2-large for cross-check, with GPT-4o-on-crop only as tiebreaker."**

**Pipeline shape (adaptive batching):**

1. **Per label, sync stage (target <2 s):**
   - Read image with Pillow → extract DPI via the layered contract in §9 → compute `mm_per_pixel`.
   - Run **PP-OCRv5 server detector + recognizer** on the full label → polygons + text + confidence.
   - Heuristic warning-region detector: filter PP-OCRv5 lines for the statutory phrase "GOVERNMENT WARNING" or "According to the Surgeon General" (string fuzzy match, e.g. RapidFuzz ratio ≥ 70).
   - Crop the warning block with 10% padding.
2. **Per label, sync stage (additional <1.5 s):**
   - Run **Florence-2-large `<OCR_WITH_REGION>`** on the warning crop to cross-check text and bbox.
   - Run **SWT on the warning crop**, sliced by PP-OCRv5's per-word polygons → compute mean stroke widths for words 1–2 ("GOVERNMENT WARNING") vs. words 3–N (rest of statement).
   - Decide bold/not-bold ratio using the §3 thresholds.
3. **Tiebreaker stage (only when local signals disagree):**
   - Trigger conditions: (a) PP-OCRv5 vs. Florence-2 text edit distance > 5%; (b) SWT ratio in the ambiguous band [0.85, 1.25]; (c) computed type height within ±10% of a §16.22(b) threshold; (d) PP-OCRv5 line confidence < 0.85.
   - Send the warning crop only (not full label) to **GPT-4o with `strict: true` JSON schema** producing the same extraction contract.
   - Compare GPT-4o's text + warning_block to PP-OCRv5's; if still ambiguous, surface to the human reviewer with all three signals visible.

**Latency budget on RTX 3090.** Step 1 + 2 typical end-to-end: **1.0–2.5 s for the first label** (cold cache; subsequent labels reuse warm models). Tiebreaker adds 1.5–3.5 s only when triggered. Comfortably inside the <5 s first-label target with a 1.5–3.5 s safety margin.

**Adaptive batching.** While a reviewer reviews label `i`, run PP-OCRv5 + SWT + Florence-2 on labels `i+1 … i+N` in parallel (PaddleOCR supports batch inference; Florence-2 batches naturally on a single 24 GB GPU at FP16). N ramps from 2 → 8 as the reviewer's per-label time stabilizes, capped by VRAM (PP-OCRv5 server + Florence-2-large + Qwen2.5-VL-7B-AWQ all loaded simultaneously is feasible at ~14–18 GB total — leaving headroom).

#### Fallback Stack (when local quality fails)

Trigger: any of (a) PP-OCRv5 text confidence < 0.7 on the warning region, (b) Florence-2 cross-check disagrees by > 10% edit distance, (c) decorative/scripted face flagged by SWT variance check (very high SWT variance within "GOVERNMENT WARNING" itself indicates the OCR isolated the wrong glyphs).

1. **Swap PP-OCRv5 for Qwen2.5-VL-7B-Instruct-AWQ INT4** with an explicit text-spotting prompt:
   `Output a JSON list of {"bbox_2d":[x1,y1,x2,y2],"text_content":"…"} for every text line in the image.`
   This is the documented OCRBench v2 prompt format that drives Qwen2.5-VL's 51.6 text-spotting score.
2. **If Qwen3-VL-8B is integrated**, swap that in instead — same prompt format, better recognition per the Qwen3-VL technical report (arXiv 2511.21631).
3. **For typography**, SWT remains the bold-detection tool; VLMs are not reliable bold detectors.
4. **Force the GPT-4o tiebreaker call** with both the full label and the crop, two separate calls — the full-label call gives layout context, the crop gives precision text. Reconcile in the JSON merger.
5. **If GPT-4o is unavailable / over budget**, route to **`grok-2-vision-1212`** with a structured-outputs JSON schema (OpenAI-compatible API at `https://api.x.ai/v1`). Note the 33K context cap: send the crop only, not the full label.

#### 10-Label Fixture-Set Spec

Each fixture is a labeled image plus an expected-result JSON. The set covers the §16.22 decision space and the visual-stack failure modes. (Fixtures should be synthesized for tests with no PII/trade-secret risk; pair each with ground-truth measurements derived from the source PDF or rendering pipeline.)

| # | Label class | Container size | DPI metadata | Resolution | Font / contrast scenario | What it tests | Expected outcome |
|---|---|---|---|---|---|---|---|
| 1 | **Wine, compliant baseline** | 750 mL (>237 mL ≤3 L) | EXIF 300 DPI present | 1500×2000 px | Clean sans-serif, black on white background near warning | End-to-end happy path | Pass: warning text exact match, bold ratio ~1.6, height ≥ 2 mm |
| 2 | **Spirits, compliant baseline** | 750 mL | PNG `pHYs` 300 DPI | 1500×2250 px | Serif body, black on cream | Confirms PNG pHYs reader path | Pass |
| 3 | **Malt beverage, compliant** | 12 oz (≤237 mL? — actually 355 mL, falls in middle tier) | JPEG JFIF 150 DPI | 1024×1536 px | Sans-serif on multicolor can art | Mid-DPI tier behavior + busy background | Pass: type ≥ 2 mm despite lower DPI |
| 4 | **Missing warning** | 750 mL wine | EXIF 300 DPI | 1500×2000 px | No warning block at all | Detect absence | Fail: `warning_block: null`, compliance_notes flag |
| 5 | **Undersized warning text** | 1.5 L wine (>237 mL ≤3 L tier, needs ≥2 mm) | EXIF 300 DPI | 1800×2400 px | Warning rendered at ~1.4 mm | Quantitative §16.22(b) check | Fail: `min_height_mm: 1.42`, `compliant_height: false` |
| 6 | **Non-bold prefix** | 750 mL spirits | EXIF 300 DPI | 1500×2000 px | "GOVERNMENT WARNING" rendered at same weight as body | §16.22(a)(2) check | Fail: SWT ratio ~1.0, `prefix_bold_decision: not_bold` |
| 7 | **Low-DPI / no-DPI ambiguity** | 750 mL wine | **No DPI metadata** (stripped JPEG) | 800×1067 px | Otherwise compliant | Forces fallback path; reference detection on UPC | DPI source = `reference_barcode`, height computation succeeds with ±5% uncertainty |
| 8 | **Decorative-font label** | 1 L spirits | EXIF 300 DPI | 1500×2200 px | Brand uses heavy script display face for "GOVERNMENT WARNING" stylized version (compliance violation) | OCR robustness + bold ambiguity | Probably fails OCR confidence threshold → tiebreaker triggered → GPT-4o or Grok call resolves; compliance_notes flag for reviewer |
| 9 | **Scan with skew** | 750 mL wine | TIFF 300 DPI | 1500×2000 px, ~5° rotation | Skewed scan typical of registry uploads | PP-OCRv5 + Florence-2 robustness; ensure deskew step | Pass after deskew; height measurement uncertainty < ±3% |
| 10 | **Container-size-edge case** | 50 mL (≤237 mL tier, needs ≥1 mm) | No DPI; assumed-300 fallback | 600×800 px | Miniature bottle, very small label | Tests the `assumed_300` path and the small-container threshold | Pass with `dpi_source: assumed_300`, height_mm ≈ 1.1 |

Across the 10 fixtures the coverage matrix is:
- **DPI present/absent**: 7 present (across EXIF/pHYs/JFIF/TIFF), 3 absent (#7 stripped, #10 absent, plus the assumed-300 path).
- **Container size**: ≤237 mL (#10), >237 mL ≤3 L (#1, 2, 3, 5, 6, 8, 9), >3 L (none — add an 11th if needed for the 3 mm tier).
- **Compliance outcomes**: 4 pass (#1, 2, 3, 9), 5 fail (#4 missing, #5 undersized, #6 non-bold, #7 ambiguous-DPI, #8 decorative-violation), 1 edge (#10).
- **Beverage class**: wine ×4, spirits ×3, malt ×1, plus 2 wine variants — re-balance if the production submission mix differs.
- **Visual stack stressors**: stylized fonts (#3, #8), low contrast (#3), skew (#9), low resolution (#7, #10), missing data (#4, #7), DPI absence (#7, #10).

Augment the fixture set with adversarial variants (stretched type that violates the "shall not be compressed" clause of §16.22(a)(3) — characters-per-inch table compliance — and contrast violations) once the baseline pipeline is green.

---

## Caveats

- **Latency numbers on RTX 3090 are estimated.** PaddleOCR's official benchmarks publish on Tesla T4 / V100 / A100; the report scales to RTX 3090 by relative throughput. Actual numbers must be measured on the team's WSL2 install (use PaddleOCR v3.2's fine-grained benchmark, which reports per-module timing). The same caveat applies to Florence-2 (Roboflow's "~1 s on T4" is the cited number) and Qwen2.5-VL-7B (Fullerton Health's "<2 s/document" is for a hybrid pipeline, not isolated VLM inference).
- **The 1.4–2.0× SWT ratio for bold/regular is empirical typography data, not a closed-form rule.** Some narrow display faces ("condensed bold") and some wide regulars can sit closer together; calibrate on real labels before committing to the 1.25 / 0.85 thresholds.
- **GPT-4o image-token cost figures depend on the precise scaling rules** (`detail: high`, 2048 max, 768 short side, 512×512 tiles) which OpenAI has kept stable since 2024 but are not contractually guaranteed. The ~$0.002/crop and ~$0.003/full-label numbers are at $2.50/M `gpt-4o` text input as of April 2026; prices have trended down historically. Verify against `developers.openai.com/api/docs/pricing` at integration time.
- **Grok image-token rules are not publicly tile-documented.** xAI publishes per-token rates and shows image-token consumption in the response `usage` object, but does not publish a deterministic OpenAI-style tile formula. Per-image cost on Grok must be measured empirically.
- **Qwen3-VL-8B-Instruct release status as of April 2026** is confirmed via the Qwen3-VL technical report (arXiv 2511.21631, "dense (2B/4B/8B/32B) and mixture-of-experts (30B-A3B/235B-A22B) variants") and the QwenLM/Qwen3-VL GitHub which lists 30B-A3B Instruct/Thinking + FP8 as released Oct 4, 2025, and 235B-A22B Sept 23, 2025. The 8B dense variant is part of the announced family; verify on Hugging Face that the 8B AWQ build is published before depending on it.
- **TTB does not publish a machine-readable §16.22 conformance benchmark.** The 10-label fixture set proposed here is the team's internal eval; a violation rate against the production registry stream should drive periodic recalibration of the SWT thresholds and OCR confidence cutoffs.
- **The "no FedRAMP path" constraint is honored** by keeping all primary vision compute local. The GPT-4o and Grok tiebreaker channels are optional and should be governed by an explicit policy switch (`enable_external_tiebreaker: bool`); if/when a FedRAMP-permissible inference path becomes available, that switch flips to a different vendor without changing the local stack.
- **Florence-2-large under MIT license**, **PaddleOCR under Apache-2.0**, **Qwen2.5-VL** under Tongyi Qianwen / Apache-2.0 (verify the specific weight license at integration), and **Qwen3-VL** licenses vary by size — confirm before redistributing fine-tuned weights.