# LLM Orchestration Architecture for the TTB AI Label Verification Prototype

```
Project:        TTB COLA Label Verification Prototype
Topic:          T5 — AI/LLM Orchestration Architecture
Author:         Architecture Working Group
Status:         DRAFT — provisional sections explicitly flagged
Sister docs:    T3 (rule engine, NOT YET FINAL), T4 (vision, FINAL)
Cross-topic:    X-1, X-2, X-3 are deferred
Decisions
  honored:      The deterministic core (LLM orchestrates, does NOT decide pass/fail)
                Substitutability (production parity; cloud OK for prototype, swap-in path required)
                Rejection reasoning (every rejection carries structured reasoning: rule citation + evidence)
                The economics-and-policy test (every option carries economic AND federal-policy story)
                Federal cost-analysis conventions (A-94, GAO-20-195G)
```

## Primary External Sources (used inline)

- OpenAI Structured Outputs (announcement, August 2024) — https://openai.com/index/introducing-structured-outputs-in-the-api/ ; reference docs https://platform.openai.com/docs/guides/structured-outputs ; reproducibility cookbook https://cookbook.openai.com/examples/reproducible_outputs_with_the_seed_parameter
- Anthropic Tool Use docs — https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview ; advanced tool use https://www.anthropic.com/engineering/advanced-tool-use ; Messages API temperature note (`temperature` 0.0 "results will not be fully deterministic") — https://docs.anthropic.com/en/api/messages
- Google Vertex AI Function Calling — https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling
- Berkeley Function Calling Leaderboard (BFCL v3 / v4) — https://gorilla.cs.berkeley.edu/leaderboard.html ; ICML 2025 paper — https://proceedings.mlr.press/v267/patil25a.html
- XGrammar (Dong et al., arXiv:2411.15100) — https://arxiv.org/abs/2411.15100 ; project — https://github.com/mlc-ai/xgrammar
- llama.cpp GBNF grammar — https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- Outlines (dottxt-ai) — https://github.com/dottxt-ai/outlines ; Outlines-core — https://github.com/dottxt-ai/outlines-core
- vLLM Structured Outputs — https://docs.vllm.ai/en/latest/features/structured_outputs/ ; Tool Calling — https://docs.vllm.ai/en/latest/features/tool_calling/ ; v0.6.0 perf — https://blog.vllm.ai/2024/09/05/perf-update.html
- ReAct (Yao et al., arXiv:2210.03629) — https://arxiv.org/abs/2210.03629
- "Just Ask for Calibration" (Tian et al., EMNLP 2023, arXiv:2305.14975) — https://arxiv.org/abs/2305.14975
- NIST AI Risk Management Framework 1.0 (AI RMF) — https://www.nist.gov/itl/ai-risk-management-framework ; NIST AI 600-1 GenAI Profile — https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- OMB M-25-21 (April 3, 2025) "Accelerating Federal Use of AI" — https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf (rescinds M-24-10)
- OMB M-25-22 (April 3, 2025) "Driving Efficient Acquisition of AI" — https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf
- OpenTelemetry Semantic Conventions for Generative AI — https://opentelemetry.io/docs/specs/semconv/gen-ai/
- FedRAMP Marketplace — https://marketplace.fedramp.gov/ ; Google Cloud FedRAMP guidance ("Individual LLMs aren't independently authorized") — https://docs.cloud.google.com/architecture/fedramp-implementation-guide
- AWS Bedrock GovCloud (FedRAMP High + DoD IL4/5 for Claude 3.5 Sonnet v1, Claude 3 Haiku, Llama 3 8B/70B) — https://aws.amazon.com/about-aws/whats-new/2025/05/amazon-bedrock-models-fedramp-high-dod-il-4-5-govcloud/ ; commentary — https://aws.amazon.com/blogs/publicsector/accelerating-government-innovation-amazon-bedrock-models-get-fedramp-high-and-dod-il-4-5-approval-in-aws-govcloud-us/
- Llama 4 Scout/Maverick (Meta, April 5, 2025) — https://ai.meta.com/blog/llama-4-multimodal-intelligence/
- Qwen3 (April 29, 2025) — https://qwenlm.github.io/blog/qwen3/ ; technical report arXiv:2505.09388 — https://arxiv.org/abs/2505.09388 ; Qwen function-calling guide — https://qwen.readthedocs.io/en/latest/framework/function_call.html
- IBM Granite 3 / 4 (Apache 2.0, function-calling-tuned) — https://www.ibm.com/granite ; 3.0 announcement — https://www.ibm.com/new/announcements/ibm-granite-3-0-open-state-of-the-art-enterprise-models
- Microsoft Phi-4 (14B) — https://huggingface.co/microsoft/phi-4 ; Phi-4-Reasoning — https://huggingface.co/microsoft/Phi-4-reasoning
- Hermes 3 / 4 (Nous Research) — https://nousresearch.com/hermes3 ; arXiv:2408.11857 — https://arxiv.org/pdf/2408.11857 ; function-calling — https://github.com/NousResearch/Hermes-Function-Calling
- xLAM (Salesforce) — https://github.com/SalesforceAIResearch/xLAM ; dataset — https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k
- promptfoo — https://www.promptfoo.dev/docs/intro/ ; OpenAI Evals — https://github.com/openai/evals
- Thinking Machines / Horace He, "Defeating Nondeterminism in LLM Inference" (batch-invariance argument) — discussed at https://www.zansara.dev/posts/2026-03-24-temp-0-llm/ and https://mikulskibartosz.name/why-temperature-0-isnt-deterministic

---

# Q5.1 — Patterns for LLM-as-orchestrator vs. LLM-as-decider

The orchestrator is a **routing/disambiguation layer**, not a judge. The architecturally relevant patterns are: (a) function/tool calling, (b) structured-output / JSON-schema enforcement, (c) constrained generation, (d) RAG (lightly), and (e) single-shot vs multi-step agent designs.

The unifying claim, consistent with the deterministic core: for our 5 s SLA and "rule engine decides" posture, the right pattern is **single-shot tool-call with strict structured output and (where possible) grammar-constrained decoding, no chained reasoning**.

## (a) Function calling / tool use

Function calling is the canonical pattern when the LLM is supposed to translate a free-form prompt + structured context into a typed call against a developer-defined schema, but is *not itself* deciding the outcome of the surrounding workflow.

| Provider | Pattern | Determinism guarantees | Latency overhead | Replaceability |
|---|---|---|---|---|
| **OpenAI** Function Calling / Structured Outputs (`strict: true`) | JSON-schema-validated tool calls; with `strict: true`, OpenAI claims "100% reliability in our evals, perfectly matching the output schemas" using GPT-4o-2024-08-06+ (OpenAI announcement, Aug 2024). | Schema adherence guaranteed when `strict:true`; values still LLM-generated. Refusal field is separate. | Marginal — implemented at the constrained-decoding layer, not as a retry loop. | High: Pydantic/Zod schemas generate JSON Schema and are portable to Anthropic, Vertex, vLLM, Outlines, Instructor. |
| **Anthropic** `tool_use` | Schema in `tools[]`. Optional `strict: true` "to ensure Claude's tool calls always match your schema exactly" (Claude API docs). | Schema-matched output. Anthropic explicitly notes Messages API: temperature=0.0 "results will not be fully deterministic." | Very low — single round-trip; Claude returns `stop_reason: "tool_use"` content blocks. | High when wrapped behind a generic adapter; SDK API is similar to OpenAI shape. |
| **Google Gemini / Vertex** Function Calling | `function_declarations` in `tools[]`; `function_calling_config.mode = "ANY"` forces a call. | Returns structured FunctionCall part; not 100% schema-strict in all SDKs but Vertex SDK validates types. | Low; comparable to OpenAI. | Medium — Vertex AI also accepts OpenAI-compatible function-calling format on Gemini OpenAI-compatible endpoint. |
| **vLLM tool_calling** (open weights) | Per-model tool parser (`hermes`, `xlam`, `mistral`, `granite`, `qwen3_coder`, etc.) extracts tool calls from the model's free-text output; arguments are not schema-constrained at decode time unless paired with structured-outputs/XGrammar. | Soft — vLLM docs note "no schema-level constraint is applied during decoding, so arguments may occasionally be malformed." Pair with `--structured-outputs-config` for strict mode. | Sub-10 ms parser overhead; constrained decoding adds near-zero overhead with XGrammar. | High — same OpenAI-style API surface. |

**Bottom line for T5.** The orchestrator must consume structured fields from the vision layer ([T4](./2026-09-15-ocr-vision-architecture.md) ExtractedField envelopes) and emit a typed JSON answer for the rule engine ([T3](./2026-09-15-rule-engine-architecture.md)) to consume. Function calling is conceptually cleanest, but for our use case the "tool" has only one operation (e.g., `disambiguate_brand_match`); using **structured output via JSON schema with `strict: true`** is functionally equivalent and slightly cheaper. We treat them as the same pattern.

## (b) Structured-output / JSON-schema enforcement

Structured Outputs (OpenAI, Aug 2024 / GPT-4o-2024-08-06+) generalizes function-calling: a `response_format` of `{type: "json_schema", json_schema: {...}, strict: true}` constrains the entire response to a schema. OpenAI: "Structured Outputs ensure schema adherence" (vs. older `json_mode`, which only ensured *valid JSON*, not schema match).

Open-source equivalents:

- **Outlines** (dottxt-ai) — finite-state-automaton-based constrained decoding from a Pydantic model or JSON schema; "no overhead during inference" (Outlines docs); used by vLLM, TGI, LoRAX, SGLang internally. Outlines-core is the Rust port (HF + dottxt).
- **Instructor** — Pydantic + retry wrapper (post-hoc validation, not decode-time constraint).
- **Guidance / LMQL** — programmatic constraint with templating.
- **vLLM Structured Outputs** — supports `json`, `regex`, `choice`, `grammar`, `structural_tag` via XGrammar/Outlines/llguidance backends.
- **llama.cpp grammars (GBNF)** — `--json` flag plus `json-schema-to-grammar` converter.
- **XGrammar** — context-free-grammar engine with adaptive token-mask cache; near-zero overhead in JSON generation; integrates with vLLM, MLC, llama.cpp.

| Mechanism | Determinism vs. soft prompt | Latency overhead | Federal/on-prem fit |
|---|---|---|---|
| Soft-prompted JSON ("respond in JSON") | Low — frequent malformed output; ~5–15% schema violations even on big models | None | OK but unsafe |
| OpenAI `strict:true` Structured Outputs | High — schema-adherent (vendor-claimed 100%) | None | Cloud-only path; mirror w/ Outlines on swap |
| Anthropic `tool_use` w/ `strict: true` | High | None | GovCloud Bedrock path |
| Outlines / XGrammar / llama.cpp GBNF | High — guarantees structural validity by construction | Near-zero (XGrammar reports near-zero per-token overhead) | Native fit; runs anywhere |

**Recommendation:** Use schema-strict structured outputs in both the cloud prototype path AND the on-prem path. The schema travels with the prompt template; only the backend changes.

## (c) Constrained generation (token-level)

**XGrammar** (Dong et al., arXiv:2411.15100, NeurIPS / ICML 2025) — context-free grammar execution via byte-level pushdown automaton + adaptive token-mask cache split into context-independent (precomputable) and context-dependent (runtime) portions. Reported speedups of up to 100× over prior CFG-constrained decoding and "near-zero overhead structure generation in end-to-end LLM serving." Integrated into vLLM and MLC-LLM, supporting Llama, Qwen, DeepSeek, Phi, Gemma.

**llama.cpp GBNF** — grammar files (BNF-like) describing the legal output language; the sampler masks illegal tokens at each step. JSON-Schema → GBNF conversion is supported but only for a subset of JSON Schema. Caveat from llama.cpp docs: "the grammar trick doesn't 100% guarantee valid JSON, because there's always a chance the model runs out of tokens before completing." Mitigation: set `max_tokens` high and use the JSON-array root pattern with closure-aware stopping.

**vLLM guided decoding** — `guided_json`, `guided_regex`, `guided_choice`, `guided_grammar` parameters; backend `auto` selects XGrammar/Outlines/llguidance per request. Vendor-neutral OpenAI-style API.

Latency/quality trade-offs:

- Constrained decoding **does not slow inference meaningfully** (XGrammar paper; Outlines docs corroborate). It can sometimes *speed up* generation via "coalescence" — deterministic spans skip the model entirely.
- Quality concern: forcing a token can occasionally trap the model into a low-probability path where the *next* unconstrained span suffers. Mitigation: include schema descriptions in the prompt, never rely on schema as the sole source of intent.

**For T5:** primary path uses cloud structured-outputs; on-prem path uses vLLM + XGrammar.

## (d) Retrieval-augmented patterns (RAG)

Per the deterministic core, the deterministic rule engine owns regulatory citations (e.g., 27 CFR §16.21 warning text, §16.22 typography rules, T.D. TTB-158 ABV tolerances). RAG is therefore **not in scope** as a primary pattern. Two narrow uses are theoretically defensible:

1. *Prior-COLA precedent retrieval* — finding past TTB decisions that resemble the current borderline case. Stretch goal; depends on TTB providing a corpus.
2. *Reasoning-text enrichment* — retrieving the canonical regulation text to include verbatim in the natural-language explanation. Better solved by a static citation table.

**Recommendation:** No RAG in the prototype. Revisit only if [T3](./2026-09-15-rule-engine-architecture.md) produces a "needs-precedent-search" disposition.

## (e) Multi-step agents vs. single-shot routing

ReAct (Yao et al., 2210.03629) and its descendants (LangGraph, AutoGen, CrewAI) interleave Thought → Action → Observation across multiple LLM calls. This is *the wrong shape* for a 5-second SLA, deterministic-decider system:

- Each ReAct step adds a full LLM round-trip (TTFT 200–800 ms each on Haiku/Flash, several seconds on self-hosted 7–8B at low concurrency).
- Multi-step reasoning *is itself the decision-making* function we explicitly forbid.
- Auditability is harder: which step's output drove which downstream effect?

**Decision:** *Single-shot, single-tool* call per orchestration task. If the task requires more than one piece of information, build a richer prompt up front with all needed structured inputs already attached (the orchestrator works on already-extracted ExtractedField envelopes — no exploration is needed). LangGraph and AutoGen are explicitly out of scope for the prototype.

| Pattern | Latency | Determinism | Auditability | Replaceability |
|---|---|---|---|---|
| Single-shot tool-call w/ structured output | ✅ ≤ 1 LLM call | High (schema + temp=0) | High — one input, one output | High |
| ReAct / multi-step agent | ❌ N LLM calls | Lower (compounding randomness) | Per-step trace required | Medium |
| Multi-agent (LangGraph/CrewAI/AutoGen) | ❌ Even worse | Lowest | Hardest | Lowest |

---

# Q5.2 — Model-selection criteria framework

We do not name a winning model. We define the criteria a candidate must satisfy, with evidence.

| Criterion | Push toward smaller (3B–8B) | Push toward larger (14B–70B+) | Evidence |
|---|---|---|---|
| **Capability** (function calling, structured output) | Tool-tuned 7–8B models score ≥ 0.70 on BFCL v3 (e.g., xLAM-7B-fc-r matched GPT-4 on BFCL; Qwen2.5/3 7B–8B routinely > 0.65). Single-tool single-call disambiguation is well within reach of 3–8B if tool-tuned. | Multi-tool selection, ambiguity over many fields, complex schemas with `oneOf`. | BFCL leaderboard — https://gorilla.cs.berkeley.edu/leaderboard.html ; xLAM paper https://github.com/SalesforceAIResearch/xLAM |
| **Latency budget** | 7–8B at INT4 on a single L4/A10G hits 80–150 TPS on vLLM with TTFT 70–200 ms — comfortably inside our ~1 s budget. | 70B even on 4×H100 yields TTFT 200–500 ms and 30–60 TPS; tight on our budget. | vLLM v0.6 perf — https://blog.vllm.ai/2024/09/05/perf-update.html ; Ori benchmarks — https://www.ori.co/blog/benchmarking-llama-3.1-8b-instruct-on-nvidia-h100-and-a100-chips-with-the-vllm-inferencing-engine |
| **Cost** | Self-hosted 7–8B amortizes well: a single L4/A10G handles tens of concurrent labels at sub-cent / call. | 70B requires 2–4× A100/H100 for production, $$$. Cloud 70B per-token cost is also higher. | — |
| **Self-hosting feasibility (substitutability)** | 7–8B at Q4 GGUF fits on consumer-grade GPUs (16 GB) and even high-end CPUs — frictionless for federal swap. | 70B requires multi-GPU or aggressive quant; non-trivial in air-gapped enclaves. | LocalLLM VRAM tables — https://localllm.in/blog/ollama-vram-requirements-for-local-llms |
| **Determinism** | Smaller models often have less batching pressure on shared infra, so batch-invariance holds more often (caveat: applies only when self-hosted with a known batch policy). | Hosted large models inherit provider's batch scheduling — provider-side nondeterminism we can't control. | Thinking Machines / Horace He on batch-invariance |
| **Trust posture (FedRAMP High / IL4/5/6)** | Llama 3 8B & Llama 3 70B are FedRAMP High + IL4/5 in Bedrock GovCloud (May 2025). Self-hosted Qwen / Phi / Granite inherit FedRAMP from the underlying compute (per Google Cloud guidance: "Individual LLMs aren't independently authorized under FedRAMP"). | Frontier hosted models have a longer authorization tail; some are not yet FedRAMP-authorized in their gov tier. | AWS — https://aws.amazon.com/about-aws/whats-new/2025/05/amazon-bedrock-models-fedramp-high-dod-il-4-5-govcloud/ ; FedRAMP Marketplace — https://marketplace.fedramp.gov/ |

**Framework rule:** start at the smallest model that hits ≥ 0.85 BFCL "Simple" / "Multiple" subscore on the orchestration tasks defined in Q5.5. Scale up only if golden tests fail. Do not select on raw MMLU.

**Determinism caveats (cite both Anthropic and OpenAI):**

- **Anthropic Messages API** explicitly: temperature 0.0 "results will not be fully deterministic" (Anthropic docs).
- **OpenAI** offers a `seed` parameter and `system_fingerprint`: same seed + same params + same fingerprint → "mostly deterministic" — "There is a small chance that responses differ even when request parameters and system_fingerprint match" (OpenAI cookbook). Azure OpenAI mirrors this language. Determinism is *not guaranteed* by any major API.
- The deeper cause is **batch non-invariance**: GPU reduction kernels execute in different orders depending on the batch the request is co-served with, producing tiny floating-point differences that can flip argmax (Horace He / Thinking Machines analysis). Floating-point non-associativity alone is *not* the primary cause — kernel batch shape is.

**Implication:** even a perfectly seeded, temperature-0 system is "mostly deterministic." This must be documented in the audit posture (Q5.4) rather than silently assumed.

---

# Q5.3 — Self-hostable model survey (April 2026)

All entries are open-weight models that can be deployed on-prem or in a FedRAMP-High / IL4-IL5 enclave. We mark each on (a) parameter sizes, (b) license, (c) function-calling/structured-output capability, (d) BFCL or equivalent, (e) GPU memory at common quants, (f) inference framework support.

| Family | Sizes | License | FC / SO support | BFCL (where reported) | VRAM @ Q4_K_M (8 K ctx) | Frameworks |
|---|---|---|---|---|---|---|
| **Llama 3.1 / 3.3** | 8B, 70B, 405B | Llama 3 Community | Native tool template (vLLM `--tool-call-parser llama3_json`); strong | Llama 3.1 405B Instruct ≈ 0.885 (self-reported); 8B ≈ 0.65–0.72 | 8B: ~5 GB; 70B: ~42 GB | vLLM, TGI, TRT-LLM, llama.cpp, Ollama, SGLang |
| **Llama 4 Scout / Maverick** (Apr 5, 2025; MoE) | Scout 17B-active / 109B-total (16 experts); Maverick 17B-active / 400B-total (128 experts) | Llama 4 Community License (EU restriction; >700M MAU = special license) | Strong; native tool calling | Released too recently for canonical BFCL v4 result at time of writing; Maverick reports MMLU-Pro 80.5 | Scout: single H100 with int4; Maverick: H100 host | vLLM, TGI, TRT-LLM (day-one); on Bedrock and watsonx.ai |
| **Qwen 2.5** | 0.5/1.5/3/7/14/32/72B | Apache 2.0 (most); 72B is research-only-ish | Strong tool use; Hermes-style template baked in | Qwen2.5-72B-Instruct ≈ 0.74; 7B/14B in 0.55–0.68 range | 7B: ~4.7 GB; 14B: ~8.3 GB; 32B: ~21 GB; 72B: ~45 GB | vLLM, TGI, TRT-LLM, llama.cpp, SGLang |
| **Qwen 3** (Apr 29, 2025) | 0.6/1.7/4/8/14/32B + MoE 30B-A3B / 235B-A22B | Apache 2.0 | Excellent — Qwen team reports BFCL v3 = 70.8 on 235B; thinking/non-thinking modes | 70.8 (235B-A22B); 8B/14B reportedly competitive with prior 32–72B | 8B: ~5 GB; 14B: ~8 GB; 30B-A3B (MoE): ~17 GB at Q4 | vLLM, TGI, llama.cpp, SGLang (`--tool-call-parser qwen3_coder` / `hermes`) |
| **Mistral 7B / Mixtral 8×7B / 8×22B** | 7B / 47B-total-13B-active / 141B-total-39B-active | Apache 2.0 | Native function calling on Mixtral-Instruct-v0.3+; vLLM `mistral` parser | Mistral-7B weak (~0.45); Mixtral-8x22B-Instruct ~0.68 | 7B: ~5 GB; 8×7B: ~26 GB Q4; 8×22B: ~80 GB Q4 | vLLM, TGI, llama.cpp, mistral-inference |
| **Gemma 2 / Gemma 3** | 2/9/27B (G2); 1/4/12/27B (G3); FunctionGemma 270M | Gemma license (commercial-permissive but Google retains policy clause) | FunctionGemma is purpose-built for tool-calling, edge-sized | FunctionGemma not on BFCL leaderboard; G3-27B competitive | 9B: ~6 GB; 27B: ~17 GB | vLLM, TGI, llama.cpp, SGLang |
| **Phi-4 (14B)** + Phi-4-mini / Phi-4-Reasoning / Phi-4-Multimodal | 14B + minis | MIT | Function calling supported via prompting; not natively tool-tuned | Phi-4 strong on reasoning, MMLU/MATH; BFCL not officially listed by Microsoft | 14B: ~9 GB Q4 | vLLM, TGI, llama.cpp |
| **IBM Granite 3.x / 4** | 2B, 8B, 3B-A800M MoE, 1B-A400M MoE; Granite 4 family in late 2025 | Apache 2.0 | **Tool-call-tuned**; IBM published own BFCL-equivalent benchmarks showing 3.0 8B leading peer dense models on tool calling | IBM internal evals; growing community presence | 8B: ~5 GB Q4 | watsonx, vLLM, TGI, NIM, Ollama |
| **DeepSeek-V3 / R1** | V3 671B-A37B MoE; R1 reasoning | MIT (V3); MIT/derivative (R1) | Tool calling supported but R1 reasoning may emit `<think>` text that complicates parsing | V3 ~0.40 on τ-bench airline / retail; not as strong as Llama 4 Scout for tool use | Out of single-host range without aggressive quant | vLLM, SGLang |
| **Hermes 3 / Hermes 4** (Nous Research) | 8B/70B/405B (Hermes 3 on Llama 3.1); Hermes 4.3 36B (ByteDance Seed base) | Apache 2.0 (Hermes 4) | **Purpose-tuned tool calling** with `<tool_call>` tags; vLLM/SGLang have `hermes` parser | Strong on Hermes-style FC tasks; multiple community evals | 8B: ~5 GB Q4; 70B: ~42 GB | vLLM, TGI, llama.cpp |
| **Watt-Tool / xLAM (Salesforce)** | xLAM-1B/7B/8x7B/8x22B-fc-r; xLAM-2-70b-fc-r | CC-BY-NC-4.0 (research) | Purpose-built for FC; vLLM `xlam` parser | xLAM-7B-fc-r ≈ GPT-4 on BFCL; xLAM-2-70b-fc-r 56.2% on τ-bench (vs Llama 3.1 70B 38.2%) | 7B: ~5 GB | vLLM, TGI |

**License caveat for federal:** Apache 2.0 (Granite, Qwen 2.5/3 most sizes, Mistral 7B, Mixtral, Hermes 4) is the cleanest path for federal procurement. Llama 3 / Llama 4 community licenses are widely deployed under federal contracts (e.g., Bedrock GovCloud's IL4/5 authorization explicitly includes Llama 3 8B and 70B), but legal review must verify the EU/MAU clauses for the specific agency. xLAM's CC-BY-NC-4.0 is **not** suitable for federal production.

## Quantization & accuracy

| Quant | Bit-width | Typical perplexity loss | Use case |
|---|---|---|---|
| BF16 / FP16 | 16 | Baseline | Production default when VRAM permits |
| Q8_0 (GGUF) | ~8 | < 1% | Indistinguishable from FP16 in eval |
| Q5_K_M (GGUF) | ~5 | ~2% | Good for borderline VRAM |
| Q4_K_M (GGUF) | ~4 + 6-bit on sensitive layers | ~3–5% | Standard local default |
| AWQ INT4 | 4 | Comparable to Q4_K_M | vLLM-friendly |
| GPTQ INT4 | 4 | Slightly worse than AWQ | vLLM/TGI |
| EXL2 | variable | Similar to GPTQ | exllama |
| INT8 (bitsandbytes) | 8 | Near-lossless | Single-GPU experimentation |

For an *orchestrator* doing brand-name disambiguation and short structured-JSON output, Q4_K_M is empirically fine on Llama 3.1 8B / Qwen3 8B / Phi-4 / Granite 8B. We recommend **Q5_K_M** as the production-baseline self-hosted quant (~5 GB VRAM for an 8B) and Q4_K_M only on memory-pressed environments. Validate with the golden-test harness (Q5.4).

## Inference frameworks

| Framework | Strengths | Notes for federal |
|---|---|---|
| **vLLM** | Continuous batching, PagedAttention, OpenAI-compatible API, structured outputs (XGrammar), tool-call parsers; ~12,500 TPS Llama 3.1 8B BF16 on H100 (vendor); 2.7× throughput over v0.5.x; widely benchmarked. | Production-grade. Deployable in GovCloud VPC. |
| **llama.cpp** | CPU + GPU + Apple Silicon; GGUF; native GBNF grammar; small footprint. | Excellent for air-gapped / disconnected. Single-process default; production usually wraps in `llama-server`. |
| **HF TGI** | Production server; OpenAI-compatible; tool calling. | Mature; widely deployed. |
| **NVIDIA TensorRT-LLM** | Highest throughput on Hopper/Blackwell; trickier to manage. | Best raw speed; needs NV stack. |
| **SGLang** | RadixAttention; ~29% higher throughput on H100 vs vLLM for Llama 3.1 8B (16,200 vs 12,500 TPS) on shared-prefix workloads. | Strong choice for multi-turn; less battle-tested. |
| **Ollama** | Dev convenience; not for production. | Demo / local-dev only. |

## Hardware tiers and latency expectations

| GPU class | Memory | Recommended models | TPS for 8B Q4/BF16 |
|---|---|---|---|
| L4 (24 GB) | 24 | 8–14B INT4 | 80–130 TPS |
| A10G (24 GB) | 24 | 8–14B INT4 | 80–140 TPS |
| A100 40 GB | 40 | 8B BF16, 32B INT4 | 200–500 TPS BF16 |
| A100 80 GB | 80 | 70B INT4, 8B BF16 | 300–1,500 TPS BF16 |
| H100 80 GB | 80 | 70B BF16 (TP=4), 8B BF16 | ~12,500 TPS Llama 3.1 8B |
| CPU-only (AVX-512) | system RAM | up to 7B Q4 | 5–15 TPS |

## Federal posture: how a self-hosted open-weight model gets authorized

Per Google Cloud's FedRAMP guidance, "Individual LLMs aren't independently authorized under FedRAMP" — instead, the underlying compute (GovCloud VM, K8s, Vertex AI) is authorized and the LLM **inherits** authorization through the boundary. Practical paths:

1. **Bedrock GovCloud (FedRAMP High + IL4/5):** Llama 3 8B/70B + Claude 3 Haiku and Claude 3.5 Sonnet v1 are model-card-listed (May 2025). Newer models (Llama 4, Claude 3.7+, Claude 4.x) are not yet authorized at IL4/5 on the GovCloud boundary — verify FedRAMP Marketplace at deployment time.
2. **Azure OpenAI Government / Azure Government:** GPT-4o family available with FedRAMP High; Azure AI Foundry hosts open-weight models on FedRAMP-authorized infra.
3. **Vertex AI on Google Cloud (FedRAMP High):** Gemini Flash/Pro plus Model Garden open weights (Llama, Qwen, Gemma) inherit GCP's FedRAMP boundary.
4. **Self-hosted on agency-owned infra:** any open-weight model runs inside the agency's existing ATO; the LLM itself is software, not a service. This is the air-gapped path.

---

# Q5.4 — Prompt determinism and replay (federal audit)

Federal audit posture is governed by:

- **NIST AI RMF 1.0 (NIST AI 100-1)** — Govern / Map / Measure / Manage functions. The Manage function explicitly requires documentation, model cards, and traceable decision provenance.
- **NIST AI 600-1 (Generative AI Profile, July 26, 2024; updated April 8, 2026)** — translates AI RMF into 200+ actions across 12 GAI risk categories including confabulation, data integrity, and value chain transparency.
- **OMB M-25-21** (April 3, 2025) — *rescinds and replaces M-24-10*. Establishes "high-impact AI" minimum risk-management practices including pre-deployment testing, AI impact assessments, ongoing monitoring, and waiver tracking. CAIO authority retained but is reframed as "change agent and AI advocate."
- **OMB M-25-22** (April 3, 2025) — procurement; requires monitoring rights and incremental evaluation.
- **GSA AI guidance** and the agency-level compliance plans for M-25-21 (December 26, 2025 deadline; many published Q1 2026).

The TTB COLA verifier is unlikely to be **rights-impacting** in M-25-21's strict sense (it is not "principal basis" for an action affecting an individual's rights — applicants can appeal; the human reviewer remains the decider). It may be **safety-/program-impacting** in TTB's internal taxonomy. Either way, the prudent baseline is to satisfy the high-impact practices.

## Versioned prompts

- **Prompt-as-code.** All prompts live in the repository (`prompts/orchestrator/v1.2/brand_match_disambiguation.j2`), are git-tracked, code-reviewed, and tagged with semantic versions.
- **Prompt registry.** Tools — Langfuse (open-source, self-hostable), PromptLayer, Helicone, LangSmith — provide evaluation and trace-binding. For federal posture we recommend Langfuse self-hosted, since data must remain inside the FedRAMP boundary.
- **Effect on reproducibility:** prompt_version becomes a first-class log field. Any change to the prompt is a new version; old version is archived; replays are deterministic-against-version.

## Versioned models (snapshot pinning)

Vendor snapshot conventions:

- **OpenAI** — `gpt-4o-2024-08-06` is a pinned snapshot; `gpt-4o` (no date) is a floating alias that can rotate. OpenAI also exposes `system_fingerprint` per response — use it as a log field.
- **Anthropic** — `claude-3-5-sonnet-20241022`, `claude-haiku-4-5-20251001` are snapshots; `claude-3-5-sonnet-latest` is floating. Use snapshot IDs only.
- **AWS Bedrock** — `anthropic.claude-3-5-sonnet-20240620-v1:0` is a pinned model ID; cross-region inference profiles add an additional version dimension.
- **Azure OpenAI** — deployment IDs decouple model version from app code; pin via Foundry deployment configuration; record `system_fingerprint`.
- **Vertex AI** — `gemini-2.5-flash-001` style snapshot IDs.

**Risk: silent deprecation.** Floating aliases will return different bytes after a vendor model push. Snapshot IDs are themselves end-of-life'd on a schedule (OpenAI typically 6–12 months notice). The audit log must record the snapshot ID *as observed* (from response headers / system_fingerprint) and the deployment must monitor vendor deprecation announcements.

## Logging structured per inference

Every orchestrator call emits a structured log conforming to OpenTelemetry Semantic Conventions for GenAI (`gen_ai.*` attributes; spec at https://opentelemetry.io/docs/specs/semconv/gen-ai/). Required fields per call:

```json
{
  "ts": "2026-09-13T13:14:15.123Z",
  "trace_id": "...",
  "span_id": "...",
  "label_review_id": "tt-2026-0492130",
  "task": "brand_name_fuzzy_disambiguation",
  "prompt_version": "1.4",
  "schema_version": "1.0",
  "rule_set_version": "TTB-rules-2026.04",
  "gen_ai.system": "azure_openai_gov",
  "gen_ai.request.model": "gpt-4o-2024-08-06",
  "gen_ai.response.model": "gpt-4o-2024-08-06",
  "gen_ai.system_fingerprint": "fp_abc123",
  "gen_ai.request.temperature": 0.0,
  "gen_ai.request.seed": 42,
  "gen_ai.request.max_tokens": 200,
  "input_hash": "sha256:...",
  "output_hash": "sha256:...",
  "output_parsed_valid": true,
  "latency_ms": 612,
  "ttft_ms": 198
}
```

Inputs and outputs are NOT recorded by default at the span level (privacy/PII), per OpenTelemetry guidance: "OpenTelemetry instrumentations SHOULD NOT capture them by default, but SHOULD provide an option for users to opt in." Federal deployments will typically *opt in* to opaque content references (hash + reference to a separately access-controlled audit store) rather than inline content, to satisfy FOIA/discovery without inflating telemetry volume.

## Temperature and sampling decisions

Standing rule: **temperature = 0, top_p = 1, seed pinned to a constant per-task** (record it). Document the residual non-determinism in the SSP / model card:

> "The orchestrator LLM is configured for maximum determinism (temperature 0, top_p 1, fixed seed, snapshot-pinned model). The provider does not guarantee bit-identical outputs across invocations: OpenAI documentation states 'There is a small chance that responses differ even when request parameters and system_fingerprint match'; Anthropic documentation states 'even with temperature of 0.0, the results will not be fully deterministic.' The technical cause is batched-inference non-invariance on parallel hardware. The system mitigates the impact via (a) structured-output schema validation that rejects malformed responses, (b) the deterministic rule engine which is the sole decider, and (c) golden-test regression that detects material drift."

## Test harness / prompt regression

- **Golden-set harness.** A labeled dataset of representative inputs (≥ 100 borderline brand-name pairs, ≥ 50 OCR-disambiguation cases, ≥ 50 reasoning-text generation cases) with expected structured outputs. CI runs prompts against the pinned model snapshot and asserts equivalence of structured fields (not free text).
- **Tools.** *Promptfoo* (declarative YAML + CI integration; recommended for the federal red-teaming requirement; OpenAI acquired but remains MIT/open-source). *OpenAI Evals* (reference harness). *LangSmith* (proprietary, ecosystem-tied). *DeepEval* (pytest integration). *Anthropic Console eval* (Anthropic-specific).
- **Recommendation:** promptfoo as primary CI gate (declarative, model-agnostic, supports red-teaming), combined with a deepeval-based pytest layer for richer assertions. Self-host the dashboard.
- **Pass criteria.** Every PR that changes a prompt or model snapshot must run the harness; merge requires schema-match ≥ 100% and structured-field equivalence ≥ 95% on the golden set, with deviations reviewed.

## Federal AI traceability expectations

- AI RMF "Manage 4.1" — mechanisms to monitor and document risks; "Manage 4.2" — actionable plans.
- NIST AI 600-1 — actions for "Information Integrity" and "Value Chain Transparency" map to versioned prompts, snapshot pinning, and log retention.
- OMB M-25-21 — "minimum risk management practices" must include AI impact assessments, ongoing monitoring, and *human-in-the-loop or human review* for high-impact AI. The deterministic rule engine + agent review loop satisfies the human review requirement; documentation of the orchestrator's role belongs in the AI Use Case inventory entry.

---

# Q5.5 — Concrete orchestration task inventory (PROVISIONAL — pending [T3](./2026-09-15-rule-engine-architecture.md))

Each candidate task is filtered against the rule **"is there a deterministic alternative at acceptable cost?"** If yes → exclude.

## Task 1. Fuzzy brand-name match disambiguation (borderline cases)

**Status:** SURVIVES filter (conditionally).

**Why deterministic alone is insufficient:** STONE'S THROW vs. Stone's Throw is *not* a borderline case — case-fold + apostrophe-strip + Levenshtein/Jaro-Winkler in [T3](./2026-09-15-rule-engine-architecture.md) solves it. The genuine borderline is similarity in the **0.85–0.95** band: e.g., "Black Mountain Brewing" (label) vs "Black Mtn. Brewing Co." (COLA application), or applicant name on COLA = "Old Forge Distillery LLC" vs label = "Old Forge Distillery." Token-set + abbreviation expansion handles many; ambiguous remainders benefit from LLM judgment.

**Input contract:** `(brand_a, brand_b, similarity_score, normalized_a, normalized_b, deterministic_decision: enum{match, no_match, borderline})`. Only invoked when `deterministic_decision == borderline`.

**Output contract (JSON Schema, single-shot, schema-strict):**
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["match", "confidence", "reasoning"],
  "properties": {
    "match": {"type": "boolean"},
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "reasoning": {"type": "string", "maxLength": 400}
  }
}
```

**Prompt design (high-level):** zero-shot, structured. Tell the model: "Two strings A and B were both pre-processed to normalized forms A' and B'. Determine whether they refer to the same alcoholic-beverage brand. Do not consider regulatory rules — only string identity. Respond per schema."

**Fallback if model fails:** route to "needs review" with a `reason: orchestrator_uncertain` annotation. Never auto-fail.

## Task 2. Natural-language reasoning text generation (per rejection reasoning)

**Status:** SURVIVES filter, but **template-first, LLM-as-enrichment-only**.

**Default path (deterministic):** the rule engine emits a structured rejection code (e.g., `R_WARNING_TEXT_MISMATCH_0001`) plus structured evidence (regex diff, OCR confidence, bounding box). A human-curated template library (one template per code) renders deterministic English explaining the rejection. Citations to 27 CFR §16.21 etc. are baked into the templates.

**LLM enrichment path (rare):** for novel rejection conditions or cases where evidence does not fit a template (e.g., multi-rule interaction), the LLM is invoked to *paraphrase the structured evidence*, never to introduce new rules. Strictly bounded.

**Input contract:** `(rejection_code, regulation_citation, evidence_blob)`.

**Output contract:**
```json
{
  "type": "object", "additionalProperties": false,
  "required": ["reasoning_text"],
  "properties": {
    "reasoning_text": {"type": "string", "minLength": 30, "maxLength": 600}
  }
}
```

**Hard rule:** the rule citation in the output is **copied** from input, never generated. Post-validation step: assert the cited regulation IDs in the output exactly match the input set (regex check). On mismatch → fall back to template.

## Task 3. OCR disambiguation under low confidence with multiple plausible readings

**Status:** SURVIVES filter — *narrow scope*.

**Deterministic alternative:** if Vision returns a single best extraction with high confidence, no LLM. If Vision returns low confidence and *one* plausible reading, route to "needs better photo." If Vision flags multiple plausible readings *and* a contextual cue resolves them (e.g., "the bottler address city — is it 'Burlington' or 'Burlingame'? Application data says VT"), the LLM has a clear and bounded job.

**Input contract:** `(field_name, candidate_readings: [{text, confidence}], context: {application_data_for_field, surrounding_extracted_fields})`.

**Output contract:**
```json
{
  "type": "object", "additionalProperties": false,
  "required": ["chosen_text", "confidence", "abstain"],
  "properties": {
    "chosen_text": {"type": ["string", "null"]},
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "abstain": {"type": "boolean"},
    "reasoning": {"type": "string", "maxLength": 300}
  }
}
```

If `abstain == true` or `confidence < threshold` → "needs better photo" / "needs review."

## Task 4. Beverage-class detection / conflict surfacing

**Status:** PROVISIONAL (depends on the class-depth scope call). If class-depth lands in scope, this becomes a conflict-flagging task: LLM compares label content (extracted classy phrases like "Distilled Spirits Specialty," "American Whisky," "Light Beer") with the COLA-application class field, and emits a structured "conflict / no-conflict" with explanation. Output never blocks pass/fail — it surfaces to the agent. **Deferred until the class-depth scope call resolves.**

## Task 5. Panel-tag mismatch arbitration

**Status:** EXCLUDED — *no LLM*.

The deterministic alternative ("flag and surface to agent") is acceptable. Vision's "applicant tagged this Back but it looks like Front" is already a low-priority flag that does not block; the agent visually verifies in milliseconds. LLM adds latency and gives no upside.

## Task 6. Warning-text near-match arbitration (§16.21)

**Status:** EXCLUDED in primary path; **CAVEATED** as future enhancement.

§16.21 is exact-match ("word-for-word") by policy. OCR errors create *near-matches*. The right deterministic response is: high-confidence OCR match → pass; high-confidence OCR mismatch → fail with rule citation; low-confidence OCR → "needs better photo" (so a human re-photos and the OCR re-runs). This avoids ever asking an LLM to opine on whether a warning-text deviation "is real" — that opinion is dangerously close to deciding the rule.

**If [T3](./2026-09-15-rule-engine-architecture.md)'s confidence model later proves the "needs better photo" rate is unacceptable**, a narrowly-scoped LLM task could be added: input = the detected text and the canonical text + per-character OCR confidence; output = `{is_ocr_artifact: bool, abstain: bool}`. We recommend deferring this task and revisiting only with empirical data from the [T3](./2026-09-15-rule-engine-architecture.md) confidence calibration (Q3.5).

## Final task list (orchestrator MVP)

| # | Task | LLM invoked? | Default fallback |
|---|---|---|---|
| 1 | Brand-name borderline disambiguation | Yes (only when [T3](./2026-09-15-rule-engine-architecture.md) says `borderline`) | needs review |
| 2 | Reasoning-text enrichment for novel cases | Rarely; templates first | template |
| 3 | OCR multi-reading disambiguation | Yes (only when ≥ 2 plausible readings + clear context) | needs better photo |
| 4 | Beverage-class conflict (depends on the class-depth scope call) | Provisional | n/a |
| 5 | Panel-tag arbitration | No | n/a |
| 6 | Warning-text near-match | No (deferred) | needs better photo |

> **PROVISIONAL.** This list narrows further once [T3](./2026-09-15-rule-engine-architecture.md)'s per-field confidence thresholds ([T3](./2026-09-15-rule-engine-architecture.md) Q3.5) are finalized. Tasks 1 and 3 may be merged into a single "field disambiguation" tool with a `field_kind` discriminator if [T3](./2026-09-15-rule-engine-architecture.md)'s threshold structure makes that cleaner.

---

# Q5.6 — Per-task prompt and output design

For each surviving task we provide: prompt skeleton, JSON Schema, validation, malformed-output behavior. **The orchestrator's structured output NEVER includes a final pass/fail.**

## Task 1 — Brand-name borderline disambiguation

**Prompt template (high-level):**
```
[SYSTEM]
You are a deterministic string-comparison helper. You compare two brand names that
have already been normalized (case-folded, punctuation-stripped, abbreviations expanded).
You decide whether they refer to the same brand. You do NOT decide regulatory pass/fail.
You respond ONLY with a JSON object matching the provided schema.

[USER]
brand_a: "{{brand_a}}"
brand_a_normalized: "{{brand_a_norm}}"
brand_b: "{{brand_b}}"
brand_b_normalized: "{{brand_b_norm}}"
similarity_jaro_winkler: {{score}}

Question: do brand_a and brand_b refer to the same alcoholic-beverage brand?
```

**JSON Schema:** as in Q5.5 Task 1.

**Validation:**
1. Schema-valid JSON.
2. `confidence` ∈ [0,1].
3. `reasoning` non-empty if `match` is null/abstain.

**Malformed-output behavior:**
- 1st failure → retry once with a corrective prefix: `"Your previous response did not match the required schema: {schema}. Please produce only the JSON object."`
- 2nd failure → emit `{"task":"brand_disambiguation","disposition":"needs_review","reason":"orchestrator_could_not_produce_structured_response"}` to the rule engine.

## Task 2 — Reasoning-text enrichment

**Prompt skeleton:**
```
[SYSTEM]
You produce a short, neutral, factual paraphrase of structured rejection evidence.
You may quote regulation IDs ONLY from the provided list — never introduce new ones.
You do not assert pass/fail. You produce 1–3 sentences.

[USER]
rejection_code: "{{code}}"
regulation_citations: {{citations}}
evidence: {{evidence_json}}
```

**Schema:** `{ "reasoning_text": string }`

**Validation:**
- All regulation IDs in output ⊆ input citations (regex `27\s*CFR\s*\u00a7?\s*\d+\.\d+` extraction + set inclusion).
- `len(text) ∈ [30, 600]`.
- No imperatives ("must", "shall reject"); blocklist regex.

**Fallback:** templated rendering of the rejection code.

## Task 3 — OCR disambiguation

**Prompt skeleton:**
```
[SYSTEM]
You choose among OCR candidate readings for one field on an alcohol label.
You may use the provided application context only as a tiebreaker.
You may abstain. You do NOT decide pass/fail.

[USER]
field_name: "{{field_name}}"
candidates:
  - text: "{{c1.text}}", ocr_confidence: {{c1.conf}}
  - text: "{{c2.text}}", ocr_confidence: {{c2.conf}}
context:
  application_value: "{{appl_value}}"
  surrounding_fields: {{surroundings_json}}
```

**Schema:** as Q5.5 Task 3.

**Validation:**
- `chosen_text` ∈ candidate texts, OR `abstain == true`.
- `confidence` ∈ [0,1].

**Malformed:** retry-once → "needs review."

---

# Q5.7 — Confidence calibration (PROVISIONAL — needs [T3](./2026-09-15-rule-engine-architecture.md) Q3.5)

LLM self-reported (verbalized) confidence is well-known to be miscalibrated. Tian et al. ("Just Ask for Calibration," EMNLP 2023, arXiv:2305.14975) found that on RLHF-tuned models like ChatGPT/GPT-4/Claude, **verbalized** probabilities are often *better-calibrated* than the model's conditional token probabilities (sometimes halving expected calibration error) — but still systematically miscalibrated, especially in the high-confidence tail. Subsequent work (Xiong et al. 2024; "Calibrating Verbalized Probabilities," 2410.06707) confirms verbalized confidence is reasonable as a *signal* but not a *probability*.

**Design principles (orchestrator side, not waiting on [T3](./2026-09-15-rule-engine-architecture.md)):**

1. **Prefer agreement over magnitude.** Treat the LLM's `match: bool` (or `chosen_text` selection) as the primary signal. Use `confidence` as a soft tiebreaker only.
2. **Use the LLM as a tie-breaker for the rule engine's borderline band.** Outside the borderline band, the rule engine doesn't ask the LLM at all.
3. **Aggregate confidences as MIN, not product.** Final disposition confidence:
   ```
   composite = min(vision.overall_conf, rule_engine.conf, llm.conf_or_1.0)
   ```
   Multiplicative aggregation is over-confident on dependent inputs and biased toward optimism. Min-aggregation is conservative — the right posture for a federal high-stakes path.
4. **Threshold values come from [T3](./2026-09-15-rule-engine-architecture.md).** [T3](./2026-09-15-rule-engine-architecture.md) Q3.5 must publish: the borderline-band low/high for each field, the "needs review" composite-confidence threshold, and the rejection-eligible composite threshold. Until then, every threshold here is symbolic.
5. **Calibration monitoring.** Log composite, LLM, vision, rule-engine confidences and the agent's eventual override decision; compute Expected Calibration Error monthly. If LLM verbalized confidence is empirically uncorrelated with agent agreement, drop it from the composite (use only vision + rule-engine).

> **PROVISIONAL.** Quantitative thresholds and the precise function form pending [T3](./2026-09-15-rule-engine-architecture.md) Q3.5.

---

# Q5.8 — Latency and cost budget (PROVISIONAL — needs [T3](./2026-09-15-rule-engine-architecture.md) Q3.9, [T4](./2026-09-15-ocr-vision-architecture.md) Q4.5)

## Budget arithmetic (5 s SLA)

| Stage | Best | Typical | Worst |
|---|---|---|---|
| Vision ([T4](./2026-09-15-ocr-vision-architecture.md) §4.7.1; K=3 parallel) | 1.0 s | 2.0 s | 3.0 s |
| Rule engine ([T3](./2026-09-15-rule-engine-architecture.md)) | 30 ms | 60 ms | 100 ms |
| Orchestrator LLM (if invoked) | 250 ms | 700 ms | 1500 ms |
| Logging / structured-output validation / network | 50 ms | 100 ms | 200 ms |
| **Total** | ~1.3 s | ~2.9 s | ~4.8 s |

The orchestrator's headroom is **~1.5–2 s in the worst case, ~2–3 s typical**. We size the per-task budget as ≤ 1500 ms hard timeout; ≤ 700 ms target for short tasks.

## Candidate orchestrator latencies

**Cloud (per artificialanalysis.ai measurements + provider docs, April 2026):**

| Model | TTFT (median) | Output speed | Notes |
|---|---|---|---|
| Claude 4.5 Haiku (Non-reasoning) | 0.65–0.74 s | 90.9–104.7 TPS | Best Haiku-class TTFT in measurements; FedRAMP via Bedrock GovCloud (model-version pending IL4/5 verification) |
| Claude 3.5 Haiku | 1.18–1.93 s | 50–95 TPS | IL4/5-authorized in Bedrock GovCloud as of May 2025 |
| GPT-4o-2024-08-06 (cloud) | 0.4–0.7 s | 80–140 TPS | Azure OpenAI Gov FedRAMP High |
| GPT-4o-mini | 0.3–0.5 s | 100–200 TPS | Azure OpenAI Gov |
| Gemini 2.5 Flash / Flash-Lite | 0.3–0.6 s | 100–200 TPS | Vertex AI Gov supports IL4 |

**Self-hosted (vLLM benchmarks):**

| Setup | Model | TTFT | TPS |
|---|---|---|---|
| 1× H100 80 GB BF16 | Llama 3.1 8B | ~70–80 ms | ~12,500 (max throughput); ~80–150 single-stream |
| 1× A100 80 GB BF16 | Llama 3.1 8B | ~100–150 ms | ~80–200 single-stream |
| 1× L4 24 GB INT4 | Llama 3.1 8B / Qwen3-8B / Phi-4 | ~150–250 ms | ~40–80 single-stream |
| 4× H100 BF16 | Llama 3.3 70B | ~200–500 ms | ~30–60 single-stream |
| CPU AVX-512 (HB-176) | Llama 3.1 8B | ~1+ s | 5–15 |

## Per-task latency targets

| Task | Output tokens | TTFT-dominated? | Target | Hard timeout |
|---|---|---|---|---|
| 1. Brand fuzzy disambiguation | ≤ 100 | Yes | 300–700 ms | 1000 ms |
| 2. Reasoning enrichment | ≤ 300 | Mixed | 700–1500 ms | 1500 ms |
| 3. OCR disambiguation | ≤ 80 | Yes | 300–700 ms | 1000 ms |

**Single-shot only.** Never chain LLM calls inside one label review.

## Per-call cost budget

Cost-per-call shapes operating economics ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md) owns full TCO) and the FedRAMP-tier choice (the economics-and-policy test). Order-of-magnitude per-orchestration-call at ~1.5K input / 200 output tokens:

| Path | Per call | Notes |
|---|---|---|
| Claude 3.5 Haiku (Bedrock GovCloud, FedRAMP High + IL4/5) | ~$0.0021 | $0.80 / $4.00 per M tokens |
| Claude 4.5 Haiku (Bedrock — verify IL4/5 at deploy) | ~$0.0021 | $1.00 / $5.00 per M tokens |
| GPT-4o-2024-08-06 (Azure OpenAI Gov, FedRAMP High) | ~$0.0058 | $2.50 / $10.00 per M tokens |
| GPT-4o-mini (Azure OpenAI Gov) | ~$0.00035 | $0.15 / $0.60 per M tokens |
| Gemini 2.5 Flash (Vertex Gov) | ~$0.00050 | $0.30 / $2.50 per M tokens |
| Self-hosted 8B (single L4 on FedRAMP-High infra) | ~$0.00006–0.00015 | Dominated by GPU-hour ($0.50–1.00/hr) at typical concurrency |

**Per label-review:** at most ~2 LLM calls. Worst-case cloud ≈ $0.005–0.012; self-hosted ≈ $0.0002–0.0005. Against TTB's ~150,000 apps/year (Sarah's interview): cloud ≈ $750–1,800/yr; self-hosted ≈ $30–75/yr (compute only). Both negligible vs. labor savings ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md) owns that math).

**Implication for the economics-and-policy test.** Cost is *not* a binding constraint at this scale — at 150K labels/year the LLM line item rounds to noise on either path. The decision driver is therefore **federal-policy posture and procurement vehicle availability** ([T7](./2026-09-15-federal-deployment-compliance.md)), not unit cost. Per federal cost-analysis conventions, [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) will express these in OMB A-94 / GAO-20-195G–conformant ranges.

> **PROVISIONAL.** Vendor pricing as of April 2026; self-hosted figures assume reasonable utilization on shared GPU infra. Final budget allocations require [T3](./2026-09-15-rule-engine-architecture.md) Q3.9 and [T4](./2026-09-15-ocr-vision-architecture.md) Q4.5 cross-topic synthesis (X-1, deferred).

---

# Q5.9 — Failure-mode handling

Per-task failure semantics (consistent across the orchestrator):

| Failure | Response |
|---|---|
| **Low self-reported confidence** (`< threshold`) | route to "needs review"; do *not* attempt second LLM call. For Task 6 (warning-text, future) and other high-stakes tasks: default to "needs review" even at moderate confidence. |
| **Malformed structured output** | schema validator catches → retry once with corrective prefix `"Your previous response did not match the schema: {schema}. Please correct and respond again."` → on second failure: "needs review" with reason `orchestration_layer_could_not_produce_structured_response`. |
| **Hard timeout** | per-task timeout (1000–1500 ms) → cancel → "needs review" with reason `orchestration_timeout`. |
| **Refusal / non-answer** | same as malformed: retry once with corrective prefix → "needs review." |
| **Model-side outage / 5xx** | Circuit breaker (e.g., Hystrix-style: open after N consecutive errors) → fall back to deterministic-only path; mark all currently-borderline cases as "needs review" until breaker clears (recovery probe every 30 s). |
| **Schema-valid but business-invalid** (e.g., `chosen_text` ∉ candidates) | Treat as malformed; retry once → "needs review." |
| **Constrained decoding emits truncated JSON** (rare with grammar-bounded; happens if `max_tokens` exhausted before close-brace) | Retry with higher `max_tokens` once → "needs review." |

**Invariant:** the system **NEVER** auto-rejects on orchestrator failure. The deterministic safe-failure mode is "needs review," not "fail." This is non-negotiable per the deterministic core and aligns with NIST AI 600-1's "Govern 6.2 — Maintain procedures and resources to ensure that any incidents are handled."

---

# Q5.10 — Cross-application consistency

LLM outputs can drift on near-identical inputs (same brand, different vintage; same SKU with refreshed artwork). Mitigations:

1. **Temperature = 0, top_p = 1, fixed seed, snapshot-pinned model.** Necessary but not sufficient (per Q5.4). Provider-side batch non-invariance still applies.
2. **Session-only canonicalized cache.** Within a single review session, cache the orchestrator's structured output keyed on `sha256(canonicalized_input)`. Same input within the session → same answer, deterministically. The prototype has no persistent storage; cross-application caching is therefore out of scope for the prototype.
3. **Document the limitation.** "The prototype cannot guarantee that two label reviews of the same applicant + same product, submitted on different days, will receive the same orchestrator-generated reasoning text or borderline disambiguation, due to the prototype's no-persistent-storage constraint." Reviewers will see this if it occurs.
4. **Production design (out of scope but architected for):**
   - Persistent **decision cache** keyed on (canonical_input_hash, prompt_version, model_snapshot, schema_version).
   - "This case has been seen before" pre-check shown to the agent with a link to the prior decision.
   - Operator-visible cache trail (cache hit, miss, drift detected).
   - When prompt_version or model_snapshot rotates, all cache entries are invalidated; an audit-grade "cache reason" log shows the bust event.

> **PROVISIONAL.** Cross-application consistency in the production version requires the persistent-storage workstream that the prototype is explicitly gap-listed on. This is a known and accepted limitation.

---

# Cross-Topic Synthesis Questions

- **X-1 (Latency budget end-to-end across [T3](./2026-09-15-rule-engine-architecture.md), [T4](./2026-09-15-ocr-vision-architecture.md), T5):** DEFERRED.
- **X-2 (Confidence composition across vision/rule/LLM):** DEFERRED — design principles given in Q5.7; numeric thresholds depend on [T3](./2026-09-15-rule-engine-architecture.md) Q3.5.
- **X-3 (Decision provenance and audit envelope):** DEFERRED.

---

# Summary Recommendations

1. **Adopt single-shot tool-call / structured-output as the only orchestration pattern.** No ReAct, no LangGraph, no multi-step agents.
2. **Use schema-strict structured outputs everywhere** (OpenAI `strict:true`, Anthropic `tool_use strict:true`, vLLM + XGrammar / Outlines on swap-in path).
3. **Constrained decoding via XGrammar** on the on-prem path; near-zero overhead and 100% structural validity.
4. **Restrict orchestrator scope to three MVP tasks** (brand-name borderline, reasoning enrichment, OCR multi-reading); explicitly exclude warning-text arbitration and panel-tag arbitration.
5. **Always min-aggregate confidence** across vision/rule/LLM; never multiply.
6. **Pin model snapshot strings**, never floating aliases; record `system_fingerprint` per call.
7. **Set temperature = 0, seed = constant, top_p = 1** and *document* residual non-determinism in the SSP / model card per OpenAI and Anthropic guidance.
8. **Log per OpenTelemetry GenAI semantic conventions**, with `prompt_version`, `model_version`, `rule_set_version`, `input_hash`, `output_hash`, `latency_ms`, `ttft_ms` mandatory.
9. **Promptfoo + golden-set CI gate** for prompt regression; deepeval for richer Python-side assertions.
10. **Self-hostable model framework, not a single model.** Front-runners: Llama 3.1 8B (Bedrock GovCloud authorized), Qwen3 8B / 14B (Apache 2.0, strong BFCL, on-prem ready), IBM Granite 3.x / 4 8B (Apache 2.0, federally friendly, FC-tuned). Hermes 3 / 4 and xLAM as tool-tuned alternatives (xLAM CC-BY-NC-4.0 NOT for federal production).
11. **Hard fail-safe:** the orchestrator never auto-rejects. All failure modes route to "needs review." The rule engine is the only decider per the deterministic core.
12. **Federal posture:** primary path = Azure OpenAI Gov / AWS Bedrock GovCloud (FedRAMP High + IL4/5); swap-path = vLLM-hosted open-weight model inside the agency ATO boundary, inheriting FedRAMP from the underlying compute. Both paths must be validated against the same golden test suite before promotion.
13. **OMB compliance:** treat the system as potentially high-impact under M-25-21 even if rights-impacting status is unclear; document the AI Use Case for the inventory; satisfy the "minimum risk-management practices" floor.
14. **Cite primary regulation text from a static citation table**, never from LLM generation. Post-validate that any regulation citation the LLM emits is exactly drawn from the input set.
15. **Cost is not the driver at TTB scale.** At 150K labels/year, LLM cost (cloud or self-hosted) is negligible; choose path on policy posture and procurement vehicle ([T7](./2026-09-15-federal-deployment-compliance.md)), not unit economics.

---

# Open Questions / Research Gaps

- **OQ-T5-1.** What are [T3](./2026-09-15-rule-engine-architecture.md)'s exact per-field borderline-band thresholds (Q3.5)? Without them, the orchestrator's invocation policy cannot be finalized.
- **OQ-T5-2.** Will TTB authorize use of cloud foundation models for the prototype, or must we go straight to a self-hosted variant for any non-public data? Affects model-selection priority order.
- **OQ-T5-3.** Should we prefer Claude 3.5 Sonnet (already FedRAMP+IL4/5 in Bedrock GovCloud) over GPT-4o or Gemini for the cloud prototype path, given Claude's currently broader gov authorization footprint? Awaiting procurement guidance.
- **OQ-T5-4.** Does Llama 4 Scout/Maverick have an IL4/5 path on Bedrock GovCloud yet? As of April 30, 2026, only Llama 3 8B/70B is confirmed. Re-check Marketplace at deployment time.
- **OQ-T5-5.** Empirical calibration of LLM verbalized confidence on our specific golden set — must be measured before relying on Q5.7 composite for any threshold.
- **OQ-T5-6.** Promptfoo vs. self-hosted Langfuse: which combination satisfies the agency's SSP for prompt-registry and audit retention? Decision deferred to security architect.
- **OQ-T5-7.** Cross-application consistency in production requires persistent storage; awaiting product decision on whether the production system gets a decision cache (currently a known limitation).
- **OQ-T5-8.** Is task 4 (beverage-class detection) in or out? Depends on the class-depth scope call.
- **OQ-T5-9.** OMB M-25-21 / M-25-22 implementation: is the TTB CAIO's "high-impact AI" classification of this prototype Yes or No? If Yes, additional pre-deployment testing and waiver-tracking obligations apply. CAIO determination required.
- **OQ-T5-10.** Snapshot-deprecation calendar: which model snapshot strings have ≥ 12 months of guaranteed availability? Needed to pin operationally and avoid forced regression cycles.
