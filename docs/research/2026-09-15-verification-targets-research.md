# Research Summary: Verification Targets for TTB COLA Verification Prototype

Filed 2026-09-15.

## TL;DR

- **The user's draft has at least one significant numeric error**: 27 CFR 5.65's distilled-spirits ABV tolerance is **±0.3 percentage points**, not ±0.15% — confirm and correct. 27 CFR 4.36 (wine) and 27 CFR 7.65 (malt beverages) values are as specified below; the user's premise that the 2022 "modernization" updated all three is partly wrong — **only parts 5 and 7 were modernized (T.D. TTB-176, eff. March 11, 2022); Part 4 (wine) was deferred**, so § 4.36 still carries its pre-modernization text (T.D. 6521 of 1960, as amended). The Government Warning text (16.21) and type-size tiers (16.22(b)) are confirmed verbatim.
- **TTB does not publish an official REST API or bulk download for the Public COLA Registry as of April 2026.** Data.gov lists two metadata-only entries (search page + per-record URL pattern) under **Creative Commons CCZero (CC0)**. The per-record URL pattern is `viewColaDetails.do?action=publicDisplaySearchBasic&ttbid={14-char TTB ID}`, not `publicDisplaySearchAdvancedAction.do`. The robots.txt at https://www.ttbonline.gov/robots.txt could not be retrieved by my tools and should be checked manually.
- **OpenAI's DALL·E 3 and the GPT-Image family (gpt-image-1, and current gpt-image-1.5/gpt-image-2) embed C2PA Content Credentials by default**, with no user opt-in needed; this has been continuous policy since Feb 2024 (DALL·E 3) and is documented for the GPT-image series as well. For ground-truth labeling of a ~250-case corpus, the literature strongly supports **double annotation with adjudication**, **Krippendorff's α ≥ 0.80** (≥ 0.667 only for tentative conclusions), use of **Label Studio / doccano / Prodigy** for small projects, and dataset documentation per **Gebru et al. (Datasheets for Datasets, 2018/2021 CACM)** and **Bender & Friedman (Data Statements, TACL 2018)**.

---

## Key Findings

### 1. ABV tolerance regulations

#### 27 CFR 4.36 — Wine (still pre-modernization text)
**Citation**: https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-4/subpart-D/section-4.36
**Authority history line in eCFR**: "T.D. 6521, 25 FR 13835, Dec. 29, 1960, as amended by T.D. ATF-275, 53 FR 27046, July 18, 1988…" — i.e., **the 2022 modernization (T.D. TTB-176) did not touch Part 4**; TTB has not finalized comparable wine-side amendments as of the eCFR current view.

Verbatim — § 4.36(b)(1) (direct ABV statement):
> "Except as provided in paragraph (c) of this section, a tolerance of 1 percent, in the case of wines containing more than 14 percent of alcohol by volume, and of 1.5 percent, in the case of wines containing 14 percent or less of alcohol by volume, will be permitted either above or below the stated percentage."

Verbatim — § 4.36(b)(2) (range statement):
> "[A] range of not more than 2 percent, in the case of wines containing more than 14 percent of alcohol by volume, and of not more than 3 percent, in the case of wines containing 14 percent or less of alcohol by volume, will be permitted between the minimum and maximum percentages stated, and no tolerances will be permitted either below such minimum or above such maximum."

Verbatim — § 4.36(c) (class-boundary prohibition; this is the "no class crossing" rule):
> "Regardless of the type of statement used and regardless of tolerances normally permitted in direct statements and ranges normally permitted in maximum and minimum statements, alcoholic content statements, whether required or optional, shall definitely and correctly indicate the class, type and taxable grade of the wine so labeled and nothing in this section shall be construed as authorizing the appearance upon the labels of any wine of an alcoholic content statement in terms of maximum and minimum percentages which overlaps a prescribed limitation on the alcoholic content of any class, type, or taxable grade of wine, or a direct statement of alcoholic content which indicates that the alcoholic content of the wine is within such a limitation when in fact it is not."

So a ±1% tolerance cannot push, e.g., a labeled 13.9% wine across the 14% class boundary, nor a 20.8% wine across the 21% boundary.

For wine **<7% ABV** (regulated under FDA + 27 CFR 24.257, not Part 4): tolerance is **±0.75%** ("alcohol content tolerance of plus or minus .75 percent by volume") per 27 CFR 24.257(a)(3).

#### 27 CFR 5.65 — Distilled spirits (post-modernization)
**Citation**: https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-5/subpart-E/section-5.65
**Source line**: "T.D. TTB-176, 87 FR 7579, Feb. 9, 2022, unless otherwise noted." Effective **March 11, 2022**.

Verbatim — § 5.65(c) Tolerances:
> "A tolerance of plus or minus 0.3 percentage points is allowed for actual alcohol content that is above or below the labeled alcohol content."

**Correction to user's draft**: The tolerance is **±0.3 percentage points**, not ±0.15%. The Federal Register preamble for T.D. TTB-176 expressly notes that the modernization "expanded" the distilled-spirits tolerance to ±0.3 (the prior pre-2022 § 5.37(b) tolerance was ±0.15% for spirits at or below 100° proof). Cite eCFR for the current value.

Section 5.65 itself does not include explicit "cannot mislead about proof" language inside the tolerance subsection; misleading-proof prohibitions are handled via the general misleading-labeling rules in **Subpart H of Part 5** (e.g., § 5.122 false/misleading; § 5.65(b) requires ABV with proof permitted only if in the same field of vision).

#### 27 CFR 7.65 — Malt beverages (post-modernization)
**Citation**: https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-7/subpart-E/section-7.65
**Source line**: T.D. TTB-176, 87 FR 7579, Feb. 9, 2022. Effective March 11, 2022.

Verbatim — § 7.65(a) (when the statement is required):
> "Alcohol content and the percentage and quantity of the original gravity or extract may be stated on any malt beverage label, unless prohibited by State law. When alcohol content is stated, and the manner of statement is not required under State law, it must be stated as prescribed in paragraph (b) of this section."

So for malt beverages, ABV is **optional federally** but defers to State law — some States require it, some prohibit it, and TTB COLA verification logic must therefore not flag a missing ABV as non-compliant unless State context is known.

Verbatim — § 7.65(b)(2) (rounding):
> "For malt beverages containing one half of one percent (0.5 percent) or more alcohol by volume, statements of alcohol content must be expressed to the nearest one-tenth of a percentage point, subject to the tolerance permitted by paragraph (c) of this section. For malt beverages containing less than 0.5 percent alcohol by volume, alcohol content may be expressed either to the nearest one-tenth or the nearest one-hundredth of a percentage point, and such statements are not subject to any tolerance."

Verbatim — § 7.65(c) Tolerances:
> "Except as provided by paragraph (d) of this section, a tolerance of 0.3 percentage points will be permitted, either above or below the stated alcohol content, for malt beverages containing 0.5 percent or more alcohol by volume. However, any malt beverage that is labeled as containing 0.5 percent or more alcohol by volume may not contain less than 0.5 percent alcohol by volume, regardless of any tolerance."

Additional asymmetric constraints in 7.65(d)–(f): "low alcohol"/"reduced alcohol" requires <2.5% (no tolerance permitted to push above 2.5%); "non-alcoholic" requires <0.5% (no tolerance); "alcohol free" requires 0.0% (no tolerance).

**Modernization note for citation accuracy**: T.D. TTB-176 (Feb 9, 2022; eff. March 11, 2022) reorganized and modernized **only Parts 5 and 7**. The corresponding wine modernization (Part 4) was deferred. So when citing post-2022 text, only §§ 5.65 and 7.65 carry the new TTB-176 source line; § 4.36 still cites T.D. 6521 (1960) and T.D. ATF-275 (1988).

---

### 2. 27 CFR 16.21 / 16.22 — Health Warning Statement
**Citation**: https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-16
**Source**: T.D. ATF-294, 55 FR 5421, Feb. 14, 1990, as amended (T.D. 372, 61 FR 20723, May 8, 1996; T.D. TTB-91, 76 FR 5477, Feb. 1, 2011, etc.). Authority: 27 U.S.C. 205, 215, 218.

#### § 16.21 — Mandatory text (verbatim)
> "There shall be stated on the brand label or separate front label, or on a back or side label, separate and apart from all other information, the following statement:
> GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems."

Note the structure: "GOVERNMENT WARNING:" (with colon) is followed by two numbered clauses on the same continuous line; TTB explicitly requires it appear "as a continuous statement" per its labeling FAQs (https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling/malt-beverage-health-warning).

The "**separate and apart from all other information**" placement language is in 16.21 itself (quoted above). Applies to alcoholic beverages ≥0.5% ABV.

#### § 16.22(a) — Boldface/capitalization (verbatim)
> "(a) Legibility. (1) All labels shall be so designed that the statement required by § 16.21 is readily legible under ordinary conditions, and such statement shall be on a contrasting background.
> (2) The first two words of the statement required by § 16.21, i.e., 'GOVERNMENT WARNING,' shall appear in capital letters and in bold type. The remainder of the warning statement may not appear in bold type.
> (3) The letters and/or words of the statement required by § 16.21 shall not be compressed in such a manner that the warning statement is not readily legible.
> (4) The warning statement required by § 16.21 shall appear in a maximum number of characters (i.e., letters, numbers, marks) per inch, as follows: …" [a max-CPI table follows by container size]

Key test rules: (i) "GOVERNMENT WARNING" must be **ALL CAPS + BOLD**; (ii) the **rest of the statement must NOT be bold**; (iii) contrasting background; (iv) not compressed.

#### § 16.22(b) — Type size by container size (verbatim)
> "(1) Containers of 237 milliliters (8 fl. oz.) or less. The mandatory statement required by § 16.21 shall be in script, type, or printing not smaller than 1 millimeter.
> (2) Containers of more than 237 milliliters (8 fl. oz.) up to 3 liters (101 fl. oz.). The mandatory statement required by § 16.21 shall be in script, type, or printing not smaller than 2 millimeters.
> (3) Containers of more than 3 liters (101 fl. oz.). The mandatory statement required by § 16.21 shall be in script, type, or printing not smaller than 3 millimeters."

Tier summary for test cases:
| Container size | Min type height |
|---|---|
| ≤ 237 mL (8 fl oz) | 1 mm |
| > 237 mL and ≤ 3 L (101 fl oz) | 2 mm |
| > 3 L (101 fl oz) | 3 mm |

§ 16.22(c): non-integral labels must be water-resistant ("cannot be removed without thorough application of water or other solvents").

---

### 3. TTB Public COLA Registry — programmatic access (April 2026)

- **No official REST API or bulk download.** TTB's Open Data page (https://www.ttb.gov/data) lists the COLA Registry only as searchable HTML; the data.gov entries describe HTML access points, not downloadable datasets. Third-party scraping services (e.g., colacloud.us) explicitly market themselves as filling the gap because "Bulk access doesn't exist." — corroborating that TTB has not shipped one as of late 2025/early 2026.
- **Data.gov record IDs / metadata** (verified at catalog.data.gov on Feb 12, 2025 metadata-update; no newer):
  - "TTB Public COLA Registry – View the details of a specific Certificate of Label Approval" — Identifier `015-TTB-54`. Homepage URL: `https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do`. **License: Creative Commons CCZero (CC0)** — `https://creativecommons.org/publicdomain/zero/1.0/`. Public access level: public. **The user's prior CC0 citation is correct.**
  - "TTB Public COLA Registry Search and Download – Extract data about COLAs that meet specified search criteria" — same publisher (TTB / Treasury), HTML-only resource pointing to the same search URL.
- **URL patterns** (confirmed from TTB's own "Display COLA Detail Through the Public COLA Registry" PDF and the data.gov entry):
  - **Search entry point**: `https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do` (Basic Search)
  - **Per-record/detail URL**: `https://www.ttbonline.gov/colasonline/viewColaDetails.do?action=publicDisplaySearchBasic&ttbid=XXXXXXXXXXXXXX` where the 14-character value is the COLA's TTB ID.
  - The "Advanced Search" page exists but the canonical single-record link uses `viewColaDetails.do`. The user's draft URL `publicDisplaySearchAdvancedAction.do` does not match the documented per-record pattern; correct it to the `viewColaDetails.do?action=publicDisplaySearchBasic&ttbid=…` form.
- **robots.txt at https://www.ttbonline.gov/robots.txt**: I was unable to fetch this file with my tools (the host returns a permissions error to my fetcher and search engines do not surface the file contents). **Recommendation: verify by direct curl/browser fetch and quote in your document.** Do not rely on prior assumptions about its content.

---

### 4. DALL·E 3 / GPT-Image — C2PA behavior in 2026

- **DALL·E 3** has embedded C2PA Content Credentials in all images generated via ChatGPT and the OpenAI API since **February 2024** (rolled out to mobile by Feb 12, 2024). Source: OpenAI Help Center, "C2PA in ChatGPT Images" (https://help.openai.com/en/articles/8912793-c2pa-in-chatgpt-images), and OpenAI's May 7, 2024 blog post "Understanding the source of what we see and hear online" (https://openai.com/index/understanding-the-source-of-what-we-see-and-hear-online/).
- **GPT-Image-1** (released April 2025) and successor models embed C2PA metadata by default. Microsoft's Azure OpenAI documentation states: "Content Credentials are automatically applied to all generated images from DALL·E and GPT-image-1 series models" (https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/content-credentials).
- **GPT-4o native image generation** (the model behind ChatGPT image generation rolled out March 2025) also embeds C2PA: "All generated images come with C2PA metadata, which will identify an image as coming from GPT-4o" (OpenAI announcement page for "Introducing 4o Image Generation").
- **Behavior**:
  - Images via the API carry a manifest signed back to OpenAI's certificate, identifying the model.
  - Images generated through ChatGPT carry an additional manifest indicating the ChatGPT-application surface (dual-provenance lineage).
  - Edits update the manifest with action records.
  - **Caveat OpenAI itself emphasizes**: "Metadata like C2PA is not a silver bullet … it can easily be removed either accidentally or intentionally" — most social-media platforms and screenshots strip it. For your verification prototype, presence of a valid C2PA manifest is high-precision evidence of AI origin; absence is not evidence of human origin.

---

### 5. Ground-truth labeling protocols for a ~250-case evaluation corpus

Authoritative sources and the practitioner consensus:

**Single vs. double annotator with adjudication.** Standard NLP/CV practice for evaluation corpora where human judgment is required is **double annotation followed by adjudication** (a third expert reviews disagreements), not single annotation. This is the protocol used in canonical NLP gold standards (e.g., i2b2/n2c2 clinical NLP shared tasks, OntoNotes, ACE) and is endorsed in domain-specific corpus construction papers (e.g., Roberts et al., "Building Gold Standard Corpora for Medical NLP," PMC3540456; the Dutch ADE corpus paper in *Language Resources and Evaluation*, 2025). The combination of **iterative annotation guideline refinement + double annotation + adjudication** is repeatedly cited as producing the highest-quality labels for small expert-annotated corpora.

**Inter-annotator agreement (IAA) thresholds.** From Krippendorff (Content Analysis, 4th ed., 2019; reiterated by Hayes & Krippendorff, 2007), the canonical thresholds are:
- **α ≥ 0.800** — reliable; standard target for publishable evaluation data.
- **0.667 ≤ α < 0.800** — only for "tentative conclusions"; treat as a warning sign.
- **α < 0.667** — discard; redesign the schema or retrain annotators.

For Cohen's κ on categorical labels, Landis & Koch (1977) interpret 0.61–0.80 as "substantial" and 0.81–1.00 as "almost perfect"; Artstein & Poesio (Computational Linguistics, 2008) recommend treating κ ≥ 0.80 as a working target for computational linguistics. For a 250-case evaluation corpus with binary or low-cardinality labels, target **κ or α ≥ 0.80**, report 95% bootstrap CIs, and explicitly document any items where adjudication was required.

**Tooling for small (~250-case) corpora.**
- **Label Studio** (Heartex; open-source) — most flexible across modalities (text/image/audio), supports role-based workflows, ML backend integration, and is the most common choice when teams need both text and image annotation in one tool. Suitable for COLA work because labels include both the JPG/PDF artifact and structured fields.
- **doccano** — open-source, lightweight; ideal when the task is purely text classification, NER, or sequence labeling on a small corpus. Has a basic REST API; quality control (IAA dashboards, adjudication UI) is limited and is typically computed offline.
- **Prodigy** (Explosion / spaCy) — commercial; best when active learning will materially reduce annotation cost. Per-seat licensing.
- **INCEpTION** — strong adjudication and IAA support; favored by linguistic-resource projects.
- **Plain CSV/Google Sheets** — defensible for ~250 simple binary judgments by a small team, but lacks audit trails, version history of guideline changes, and structured disagreement capture; not recommended once you double-annotate.

For a 250-case corpus across heterogeneous COLA artifacts (label image + structured metadata), **Label Studio is the most commonly recommended choice**.

**Annotation guideline documentation — primary sources to cite.**
- **Gebru, T., Morgenstern, J., Vecchione, B., Wortman Vaughan, J., Wallach, H., Daumé III, H., & Crawford, K. (2018/2021). "Datasheets for Datasets."** First arXiv version 1803.09010 (March 2018); FAccT/FAT* 2018 workshop paper; final published version: *Communications of the ACM*, 64(12): 86–92 (Dec. 2021). Provides the canonical questionnaire across motivation, composition, collection process, preprocessing, uses, distribution, and maintenance. URL: https://arxiv.org/abs/1803.09010 ; https://cacm.acm.org/research/datasheets-for-datasets/
- **Bender, E. M., & Friedman, B. (2018). "Data Statements for Natural Language Processing: Toward Mitigating System Bias and Enabling Better Science."** *Transactions of the Association for Computational Linguistics (TACL)*, 6: 587–604. DOI: 10.1162/tacl_a_00041. URL: https://aclanthology.org/Q18-1041/ . Updated **Schema Version 2 (2023)** appears in McMillan-Major, Bender, & Friedman, *ACM Journal on Responsible Computing*, 1(1) (March 2024), DOI 10.1145/3594737. Schema V3 (current) is maintained at https://techpolicylab.uw.edu/data-statements/ (UW Tech Policy Lab).
- Companion practice — **Mitchell et al. (2019), "Model Cards for Model Reporting,"** FAT* 2019 — documents the *model* alongside the dataset; pairs naturally with datasheets/data statements.

For a TTB COLA verification eval corpus, a defensible documentation bundle is: (1) a **Datasheet for Datasets** describing how the 250 cases were sampled from the Public COLA Registry; (2) a **Data Statement** describing label-language characteristics and any annotator demographics; (3) an **annotation guideline document** (versioned, with examples and edge cases) cited in the Datasheet's "Collection Process" section; (4) reported **Cohen's κ or Krippendorff's α with 95% CI**, plus a confusion matrix of pre-adjudication disagreements.

---

## Caveats

- **§ 4.36 currency**: The eCFR shows § 4.36 has not been amended by the 2022 modernization rulemaking; the most recent amendment cited in the eCFR source line for Subpart D dates back decades. If TTB issues a Part 4 modernization final rule after this document is filed, recheck § 4.36.
- **27 CFR 5.65 user error**: Your draft figure of "±0.15%" is the **pre-2022** distilled-spirits tolerance from the old § 5.37(b). Update to **±0.3 percentage points** with citation to T.D. TTB-176 (87 FR 7526; eff. March 11, 2022) and quote § 5.65(c) directly from eCFR.
- **TTB COLA URL pattern**: Replace any reference to `publicDisplaySearchAdvancedAction.do` for per-record links — that is not the canonical permalink. Use `viewColaDetails.do?action=publicDisplaySearchBasic&ttbid={TTB_ID}`. The advanced search form does exist but is a UI page, not a per-record endpoint.
- **ttbonline.gov/robots.txt could not be retrieved** by the research tools available. You must verify and quote it manually from a browser/curl. Do not rely on speculation about its contents in a strategy document.
- **No official TTB API** as of April 2026: do not cite api.data.gov for COLA data; data.gov merely catalogs the HTML access points. Any programmatic access strategy must therefore document scraping rate limits, robots.txt compliance, and the CC0 license that applies to the underlying public-record data.
- **C2PA absence is not provenance evidence**: OpenAI's own help-center text explicitly warns that screenshots and most social-media uploads strip metadata. Frame test cases accordingly: "C2PA present + verifies → AI-origin (high confidence)"; "C2PA absent → unknown."
- **IAA thresholds are conventions, not laws**: Krippendorff's 0.80/0.667 values come from his own textbook and are widely adopted but explicitly described in the methods literature (PMC6245899) as not universally appropriate. For a regulatory-compliance evaluation corpus where false-negative costs are high, justify your threshold choice rather than citing 0.80 by default.
- **Sample-size sufficiency**: Per Krippendorff's tables (via ATLAS.ti documentation), reaching α ≥ 0.80 at p = 0.05 with two coders and a 4-class label generally requires ≥139 jointly coded items; 250 cases is therefore adequate to *measure* IAA reliably for binary-to-quaternary schemas, but tighter for multi-class or rare-class labels. Power-analyze your specific schema.