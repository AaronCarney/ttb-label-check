# Label extraction: which reader turns a label image into fields inside 5 seconds

Measured, and sources read, 2026-09-15.

**Answer.** `gemini-3.5-flash-lite` with a JSON schema reads a whole application in one call. It
covers front, back and neck images. The measured end-to-end time was 2.0 s at the median, and the
slowest was 2.8 s one at a time, or 4.7 s with 16 requests in flight. It returned the Government
Warning word for word on 12 of 13 real labels. The one miss is the risk that matters: on a label
whose warning drops a comma and a period, the model put them back. At paid rates it would cost about
$0.0011 per application. The prototype ran free. A local CPU OCR engine (RapidOCR) is the path
that works behind a firewall: 1.2 s median and 2.6 s worst, but with simple parsing it recovered the
warning exactly on only 6 of 13 labels. Used as a cross-check it adds what the model lacks. On the
7 labels where OCR and the model agreed, the model was right every time. The model's one error fell
among the 6 disagreements, and those are the labels to send to an agent. The Gemini API cannot be
reached through the agency firewall as described. The realistic production route is the same design
on Azure OpenAI in Azure Government, which is in FedRAMP High scope (vendor-reported) but was not
measured here. **Recommendation:** Gemini Flash-Lite plus a local OCR warning cross-check for the
prototype, behind an interface that can be pointed at Azure OpenAI. Local OCR alone is the fallback.

## Conditions

- Date: 2026-09-15, between 12:30 and 14:30 CDT.
- Machine: WSL2 Linux, 16 CPU cores, 15 GB RAM, no GPU, Python 3.12.
- Network: residential connection to the public Gemini API (`generativelanguage.googleapis.com`),
  free tier, no billing account.
- Software: `google-genai` 2.23.0, `rapidocr` 3.9.2 and `onnxruntime` 1.30.0.
- Labels: 13 approved applications from the TTB Public COLA Registry
  (https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do), approved 2026-08-01 to
  2026-08-05, plus one earlier approval:
  - wine: 4 (one imported from Italy, one from Spain);
  - malt beverage: 4 (including a keg collar);
  - spirits: 5 (one imported from Belize, one from Brazil).
- Images: 23 in all, 1 to 3 per application, from 531x802 to 3189x2126 px and 78 KB to 1.5 MB,
  sent at their original size. Seven applications have a separate back label carrying the warning.
- Timing: wall clock from reading the image files to parsed fields.
- Ground truth: each label was transcribed from its image, and the fields the scoring rests on were
  checked by eye against the image. That includes every warning that deviates from the standard text.

## What the registry gives as application data

The public record (form TTB F 5100.31) shows the brand name, fanciful name, applicant name and
address, class/type description, origin, type of product and each label's printed dimensions. It
does not show alcohol content or net contents
(https://www.ttbonline.gov/colasonline/viewColaDetails.do?action=publicFormDisplay&ttbid=26131001000310).
For those two fields the label itself is the only source.

## The labels are a real test of word-for-word checking

Three of the 13 approved labels print a warning that differs from the statutory text in 27 CFR 16.21
(https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-16/subpart-C/section-16.21). All
three were checked on the image:

- COLA 15078001000472 (Farmhouse Peachshine) prints "DRINK ALOHOLIC".
- COLA 25351001000893 (Reverence) has no colon after "GOVERNMENT WARNING", no comma after
  "GENERAL", and prints "BIRTH DEFECT." and "IMPAIR".
- COLA 22277001000091 (NZÙ) has no comma after "GENERAL" and no period after "DEFECTS".

## Latency

| Path | Setting | Requests | p50 | p95 | max |
|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | no thinking, 1 at a time | 13 | 2.03 s | 2.54 s | 2.75 s |
| `gemini-3.5-flash-lite` | 8 in flight | 52 | 1.52 s | 2.76 s | 3.18 s |
| `gemini-3.5-flash-lite` | 16 in flight | 104 | 1.47 s | 3.03 s | 4.68 s |
| `gemini-3.5-flash` | thinking `minimal`, 1 at a time | 13 | 3.06 s | 5.43 s | 6.54 s |
| `gemini-3.5-flash` | thinking `low`, 1 at a time | 13 | 2.98 s | 4.64 s | 8.08 s |
| RapidOCR, CPU | 1 at a time, with rotation retry | 13 | 1.18 s | 2.26 s | 2.60 s |
| RapidOCR, CPU | 8 processes | 52 | 4.75 s | 10.02 s | 11.74 s |
| Hybrid (model and OCR at once, one process) | 1 at a time | 13 | 1.53 s | 5.26 s | 5.28 s |

- **Batch throughput.** Flash-Lite finished 52 applications in 11.5 s and 104 in 14.3 s. At that
  rate, 300 would take about 45 s. RapidOCR in 8 processes finished 52 in 37.7 s, about 0.7 s each,
  but each request waited 5 to 12 s because every process ran ONNX Runtime threads on every core.
  Capping threads per process was not tried.
- **Load and first call.** The OCR engine takes 0.4 to 0.9 s to load, once per process.
- **Hybrid tail.** The hybrid's slow cases came from OCR, which took 5.2 s when it shared a process
  with the model call, against 1.4 to 1.8 s alone. The cause was not isolated. OCR belongs in its own
  process or pool, with a time limit.
- **Earlier OCR pass.** A first OCR pass without rotation retry ran at p50 0.81 s and p95 1.33 s,
  but it missed the sideways warnings.

## Accuracy against the verified values, 13 applications

Matching ignores case, punctuation and spacing for ordinary fields; ABV and net contents must match by
value. The warning must match exactly once whitespace is removed: case and punctuation count, and
spacing does not, because justified label type often closes word gaps. For OCR, brand, class and name
are scored as "the verified value appears in the OCR text", since plain OCR does not label fields.

| Field | Flash-Lite | Flash (minimal) | Flash (low) | RapidOCR + rules | Hybrid |
|---|---|---|---|---|---|
| Brand | 12 | 12 | 12 | 12 | 12 |
| Class/type | 13 | 13 | 12 | 11 | 13 |
| Alcohol content | 13 | 13 | 13 | 10 | 13 |
| Net contents | 11 | 13 | 13 | 11 | 12 |
| Name and address | 11 | 11 | 11 | 8 | 10 |
| Country of origin | 13 | 13 | 13 | 13 | 13 |
| Warning word for word | 12 | 12 | 12 | 6 | 10 |
| "GOVERNMENT WARNING" in capitals | 13 | 13 | 13 | 10 | 13 |
| Heading bold (of 12 judgeable) | 9 | 10 | 10 | not attempted | 9 |

**What the misses were:**

- **Warning (all Gemini settings).** The only miss was NZÙ. The models added the missing comma and
  period back, so the model can quietly correct a label that should fail.
- **Warning (Gemini, deviations kept).** All three models kept "ALOHOLIC" and every Reverence
  deviation.
- **Bold.** The models said "bold" for three headings set in the same heavy face as the rest of the
  warning. A model's bold judgement is not reliable enough to reject a label on its own.
- **Name and address.** Flash-Lite returned a retailer's "bottled exclusively for" line instead of
  the importer on the Belize rum. Two other misses were an address given without its "Imported by"
  prefix, or with extra lines, where the scoring was strict.
- **Net contents.** Flash-Lite read "1 PINT" as "I PINT" once, and gave "16 FL OZ" without "1 Pint"
  once.
- **Brand.** One miss is a scoring artefact: the model joined the brand and the fanciful name.
- **OCR warning.** Its failures were layout, not reading:
  - sideways text on 2 labels;
  - a two-column keg collar;
  - justified text with a barcode beside it;
  - accents invented on 2 labels ("PREGNÁNCY", "ÀLCOHOLIC").
- **Hybrid.** Using the OCR warning in place of the model's made the result worse: 10 of 13 instead
  of 12.

## The cross-check

Comparing the model's warning with the OCR warning, after stripping accents and whitespace:

- **Agreement.** The two agreed on 7 of 13 labels, and the model was right on all 7.
- **Disagreement.** On the other 6, a person should check the warning. This group holds the model's
  one error (NZÙ, where OCR read the punctuation correctly) and the deviating Reverence label.
- **Result.** Nothing slipped through. On this set the cost is 6 of 13 labels sent for a second look.

## Cost per application

Measured tokens per application are 1,807 input on average (all images together, default media
resolution) and 214 to 225 output. The per-token prices are vendor-reported
(https://ai.google.dev/gemini-api/docs/pricing):

- `gemini-3.5-flash-lite` at $0.30 input and $2.50 output per million tokens: about **$0.0011**.
- `gemini-3.5-flash` at $1.50 and $9.00, where output includes thinking: about $0.0047 with thinking
  `minimal`, and about $0.0072 with `low` (274 thinking tokens on average).
- The free tier charges nothing for either model (same page).
- RapidOCR has no per-call cost; it uses CPU time only.

## Free-tier limits

- **Published limits.** Google does not publish free-tier limits in its documentation. It says
  they can be seen in AI Studio (https://ai.google.dev/gemini-api/docs/rate-limits).
- **What was observed.** 184 Flash-Lite calls were made on 2026-09-15, including 104 in 14 s.
  None was refused or rate-limited. The daily cap is not known, so a 300-label batch on the free tier
  is unverified.
- **Data use.** On the free tier, "Google uses the content you submit ... to provide, improve, and
  develop Google products". Also, "Human reviewers may read, annotate, and process your API input and
  output", and "Do not submit sensitive, confidential, or personal information to the Unpaid
  Services" (https://ai.google.dev/gemini-api/terms). Paid use is not used to improve products (same
  page). Public registry labels are fine for this. An agency's unreleased applications are not.

## Behind the agency firewall

The IT notes say outbound traffic to many domains is blocked, and that the agency runs on Azure after
a FedRAMP process. Each option would need the following.

| Option | Needs outbound to | Government authorization (vendor-reported) |
|---|---|---|
| RapidOCR, local | Nothing at run time. The three default models (PP-OCRv6 small detection and recognition, a mobile orientation classifier) are inside the `rapidocr` 3.9.2 wheel. Other model choices download from `modelscope.cn` on first use, so the files must be bundled. | Not applicable: runs on the agency's own hosts. |
| Gemini API (as measured) | `generativelanguage.googleapis.com` | None for this API. |
| Gemini on Vertex AI | Google Cloud, US multi-region endpoint | Generative AI on Vertex AI is FedRAMP High, IL2, IL4 and IL5 for Google models that support US multi-region endpoints, "including most Generally Available Gemini models". Flash and Flash-Lite are not named (https://docs.cloud.google.com/docs/security/compliance/fedramp-dod-compliance-scope; https://docs.cloud.google.com/docs/security/compliance/deploy-gemini-gov). |
| Azure OpenAI in Azure Government | The agency's own Azure Government endpoint | Azure OpenAI is in scope for FedRAMP High, DoD IL2, IL4 and IL5 (workload isolation) in Azure Government, and FedRAMP High and IL2 in Azure commercial (https://learn.microsoft.com/en-us/azure/azure-government/compliance/azure-services-in-fedramp-auditscope, tables last updated February 2026). |
| Azure AI Document Intelligence | The agency's Azure endpoint, or none in a disconnected container | Same audit-scope page: FedRAMP High, IL2, IL4 and IL5 (workload isolation) in Azure Government. |
| Claude Haiku 4.5 | Anthropic API, or Bedrock, Vertex AI or Microsoft Foundry | Anthropic's own FedRAMP Marketplace entry reads "Not yet certified" (https://www.fedramp.gov/marketplace/products/FR2633053633/). GovCloud availability of Haiku 4.5 is contradictory in AWS's own pages; see below. |
| OpenAI API (direct) | `api.openai.com` | None found; the government route for these models is Azure OpenAI. |

## Options not measured here (no key), vendor-reported

**Azure OpenAI in Azure Government**
(https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-gov,
dated 2026-09-01):

- **Models.** `gpt-4.1`, `gpt-4.1-mini` and `gpt-4o` accept image input with structured outputs.
  They are offered as Standard (regional) deployments in `usgovarizona` and `usgovvirginia`.
- **Newer models.** `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` and `gpt-5.1` also accept images.
  They are offered as Data Zone Standard.
- **Unknowns.** Latency and Azure Government prices are not stated there and were not measured.

**Azure AI Document Intelligence:**

- **Price.** The Read model costs $1.50 per 1,000 pages (East US), about $0.0015 per image;
  prebuilt and layout models cost $10 per 1,000
  (https://prices.azure.com/api/retail/prices?$filter=productName%20eq%20%27Azure%20Document%20Intelligence%27%20and%20armRegionName%20eq%20%27eastus%27).
- **Free tier.** 500 pages a month, 1 request per second, and only the first 2 pages of a document
  (https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits).
- **Connected containers.** Read and Layout run in containers, but a connected container still
  reports billing to Azure. Read needs 8 cores and at least 10 GB of memory
  (https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/containers/install-run).
- **Disconnected containers.** These need Microsoft's approval and an upfront commitment plan
  (https://learn.microsoft.com/en-us/azure/ai-services/containers/disconnected-containers).
- **Fit.** It returns text and layout, not these label fields, so the field parsing problem seen with
  local OCR remains.
- **Latency.** No vendor latency figure was found.

**Claude Haiku 4.5**
(https://platform.claude.com/docs/en/models/haiku-4-5/overview):

- **Model and retirement.** The model ID is `claude-haiku-4-5-20251001`. Its retirement is stated
  as "not sooner than October 15, 2026".
- **Price.** $1 input and $5 output per million tokens
  (https://platform.claude.com/docs/en/about-claude/pricing).
- **Image tokens.** A 2000x1500 image is resized to 1269x952 and counts as 1,564 tokens
  (https://platform.claude.com/docs/en/build-with-claude/vision). That puts one image plus 300
  output tokens at about $0.0031.
- **Structured outputs.** Supported
  (https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
- **AWS GovCloud: covered.** AWS's compliance page lists Claude Haiku 4.5 as in GovCloud FedRAMP
  scope (https://aws.amazon.com/compliance/services-in-scope/FedRAMP/amazon-bedrock-models/).
- **AWS GovCloud: not listed.** AWS's region table lists no Haiku 4.5 in the GovCloud regions
  (https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html).
  Availability there is therefore unconfirmed.

**OpenAI small vision models**
(https://developers.openai.com/api/docs/pricing):

- **Prices per million tokens (input and output).**
  - `gpt-5-mini`: $0.25 and $2.00.
  - `gpt-4.1-mini`: $0.40 and $1.60.
  - `gpt-5.6-luna`: $0.20 and $1.20.
- **Image tokens.** Images are counted in 32-pixel patches, capped at 2,500 patches at high detail
  (https://developers.openai.com/api/docs/guides/images-vision).
- **Cost per label.** One 1500x2000 image plus 300 output tokens comes to about $0.0014 on
  `gpt-5-mini` and about $0.0021 on `gpt-4.1-mini`.
- **Features.** Structured outputs are supported
  (https://developers.openai.com/api/docs/models/gpt-5-mini).
- **Latency.** Not stated.

## Recommendation and the risk to the 5-second budget

- **Primary, prototype.** `gemini-3.5-flash-lite` with a response schema, sending every image of an
  application in one request. In parallel, a local RapidOCR pass reads the warning. If the two
  warnings agree, the result stands. If they disagree, the warning is marked for the agent to check
  by eye. The model must be called through one small interface so the same code can use Azure
  OpenAI in Azure Government, the route that fits the agency's firewall and FedRAMP boundary.
- **Why primary.** It was the fastest and among the most accurate options measured, cost nothing
  here, and costs about $0.0011 per application at paid rates. `gemini-3.5-flash` was no more
  accurate on these labels and had a tail over 5 s.
- **Fallback.** Local RapidOCR alone, for when no model endpoint is reachable. It stays inside the
  budget at 2.6 s worst serially, and brand, class, ABV and net contents can be checked as "the
  application's value appears on the label". The warning cannot be confirmed automatically on about
  half the labels, so those must show "check the warning by eye" and not "pass".
- **Measured risk, Flash-Lite.** Flash-Lite never exceeded 5 s in 169 timed requests. Its worst was
  4.68 s with 16 in flight, and 2.75 s one at a time.
- **Measured risk, other paths.**
  - Gemini Flash with thinking reached 6.5 s and 8.1 s.
  - OCR run in the same process as the model call reached 5.3 s.
  - OCR run across 8 processes on 16 cores reached 11.7 s per request.
- **Not measured.** This is one network, one afternoon, and the free tier. Azure OpenAI latency is
  unmeasured, and so is the free-tier daily cap. The deployed app needs its own timed check against a
  real label.
