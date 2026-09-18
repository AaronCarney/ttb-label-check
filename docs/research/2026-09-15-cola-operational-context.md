# COLA System & Operational Context — Research Output

## Metadata

| Field | Value |
|---|---|
| Author / scope | Primary-source research for an AI-powered alcohol-label verification prototype (Topic 2 only) |
| Current TTB Form 5100.31 revision | **04/2023** (PDF watermark: "TTB F 5100.31 (04/2023) PREVIOUS EDITIONS ARE OBSOLETE"); OMB control number **1513-0020** |
| Most recent labeling Treasury Decisions in scope | T.D. TTB-158 (4/2/2020), T.D. TTB-176 (2/9/2022, "Phase 2"), T.D. TTB-176A correction (3/9/2022), T.D. TTB-196 (11/6/2024 technical corrections) |
| Public COLA Registry image coverage | Images available 1999–present; data-only records pre-1999; results before 1996 may be incomplete (per registry banner text on `publicSearchColasBasic.do`) |
| Current ALFD label processing snapshot (TTB.gov, "Updated 04/28/2026 7:00 AM") | Distilled spirits **4 days**, Malt beverages **1 day**, Wine **5 days**; CY2026 label applications received YTD: **55,528**; service goal: **85% within 15 days** |
| Cross-topic synthesis questions skipped per instructions | X-5 ([T1](./2026-09-15-ttb-regulatory-framework.md)+T2+[T9](./2026-09-15-verification-targets-research.md) corpus design) and (T2+[T6](./2026-09-15-batch-processing-architecture.md)) batch-sizing math |

> Throughout this document, "what the regulation says" is distinguished from "what TTB actually does in practice." Inline citations identify the source URL and the exact regulation/section/page when possible. The document deliberately does **not** rely on undated industry blog snippets where a primary TTB source exists.

---

## Q2.1 — Form 5100.31 Field Schema (rev. 04/2023)

The current paper form is divided into **Part I – Application** (items 1–15), **Part II – Applicant's Certification** (items 16–18, plus the perjury declaration), **Part III – TTB Certificate** (items 19–20, plus the QUALIFICATIONS free-text block), and the unnumbered "Affix Complete Set of Labels Below" panel. Items 1, 19, and 20 are designated **FOR TTB USE ONLY**. The instructions are printed on pages 2–4 of the same PDF (sections III.A "General Instructions" and III.B "Specific Instructions") with the 41-row Allowable Revisions table forming Section V on pages 3–4.

Source for every row below: **TTB Form 5100.31 (rev. 04/2023)**, retrievable at `https://www.ttb.gov/system/files/images/pdfs/forms/f510031.pdf` — page 1 (the form face) and pages 2–4 (instructions).

| # | Item / Block name | Data type | Required? | Page | Maps to label-side validator? |
|---|---|---|---|---|---|
| **1** | REP. ID. NO. (third-party representative ID) | Text / numeric (TTB-issued) | Optional; required only if a third-party agent is filing under section III.B-Item 1 | p. 1 (TTB-use box, top right) | No (operational metadata; routes return mail) |
| **2** | Plant Registry / Basic Permit / Brewer's Notice Number(s) (BW-, TPWBH-, DSP-, importer basic permit, BR-, etc.) | Enum-like permit code (alphanumeric) | **Required** | p. 1; instructions §III.B-Item 2 | Indirectly — used to validate "Bottled by/Imported by" name & address on the label against the permit |
| **3** | Source of product (checkbox: Domestic / Imported) | Checkbox / enum | **Required** | p. 1; §III.B-Item 3 | Drives country-of-origin and "Imported by" validators |
| **4** | Serial Number (year-prefixed sequential, ≤ 6 chars; e.g., "23-1") | Text | **Required** | p. 1; §III.B-Item 4 | No |
| **5** | Type of Product (Wine / Distilled Spirits / Malt Beverages) | Checkbox / enum | **Required** | p. 1; §III.B-Item 5 (sake → check "wine") | Selects which 27 CFR Part (4, 5, or 7) governs; class/type validator branches off this |
| **6** | Brand Name | Text | **Required** | p. 1; §III.B-Item 6 (defaults to bottler/packer/importer name if not sold under a brand) | **Yes** — primary brand-name validator |
| **7** | Fanciful Name | Text | Conditional (required for some specialty products; optional otherwise) | p. 1; §III.B-Item 7 | **Yes** — fanciful-name validator (e.g., distilled-spirits specialties) |
| **8** | Name and Address of Applicant (as it appears on plant registry / basic permit / brewer's notice; including approved DBA or trade name if used on the label) | Address (multi-line) | **Required** | p. 1; §III.B-Item 8 | **Yes** — name-and-address-on-label validator (27 CFR 4.35, 5.66/5.67, 7.66/7.67) |
| **8a** | Mailing Address (if different) | Address | Optional | p. 1; §III.B-Item 8 | No |
| **9** | Formula (TTB Formula ID / pre-import approval letter / lab number) | Text / numeric | Conditional — required when the product needs a pre-COLA evaluation per Industry Circular 2007-4 (e.g., flavored malt beverages, specialty spirits with added flavors/colors) | p. 1; §III.B-Item 9 | Cross-validates label statement of composition vs. approved formula |
| **10** | Grape Varietal(s) — wine only | Text (free or comma-list) | Conditional — required when any varietal appears on a wine label (27 CFR 4.23) | p. 1; §III.B-Item 10 | **Yes** — varietal-on-label validator (75% rule single varietal; sum-to-100 multi) |
| **11** | Wine Appellation (if shown on the label) | Text / enum (AVA / state / country) | Conditional — required when an appellation of origin appears (27 CFR 4.25) | p. 1; §III.B-Item 11 | **Yes** — appellation validator |
| **12** | Phone Number | Phone | **Required** (person responsible for application) | p. 1; §III.B-Item 12 | No |
| **13** | Email Address | Email | Optional but TTB returns paper applications to this address if provided | p. 1; §III.B-Item 13 | No |
| **14** | Type of Application — checkboxes (a) Certificate of Label Approval; (b) Certificate of Exemption + State abbreviation field; (c) Distinctive Liquor Bottle + Total Bottle Capacity; (d) Resubmission after Rejection + TTB ID | Checkbox set + conditional text fields | **Required** to check (a) OR (b); (c) and (d) conditional | p. 1; §III.B-Item 14 | (b) drives "For sale in [State] only" label statement validator; (d) chains to a prior TTB ID |
| **15** | "Show any information that is BLOWN, BRANDED, OR EMBOSSED on the container … and translations of foreign-language text appearing on labels" | Long text | Conditional — required when net contents/name and address etc. are on the glass rather than the affixed label, OR when foreign-language text is on the labels | p. 1 (large free-text block); §III.B-Item 15 | **Yes** — provides the supplemental text the label-content validator must treat as "on label" even though it is on the glass; also supplies translations |
| (panel) | "Affix complete set of labels below" — physical label attachments (paper filers) or image uploads (electronic filers) | Image attachments | **Required** | p. 1 (lower panel); §III.A General Instructions 4 & 6 | **The label artwork itself** — input to every visual validator |
| **16** | Date of Application | Date | **Required** | p. 1; §III.B-Item 16 | No |
| **17** | Signature of Applicant or Authorized Agent | Signature (ink) on paper, or "Application was e-filed" + click-through perjury checkbox electronically | **Required** | p. 1; §III.B-Item 17 | No (perjury attestation on label truthfulness) |
| **18** | Print Name of Applicant or Authorized Agent | Text | **Required** | p. 1; §III.B-Item 18 | No |
| **19** | Date Issued (TTB) | Date | TTB-completed | p. 1 (TTB-use only) | No |
| **20** | Authorized Signature, TTB | Signature (facsimile on electronic) | TTB-completed | p. 1 (TTB-use only) | No |
| (block) | QUALIFICATIONS — free-text block where TTB notes label-image reduction percentages, label-as-affixed caveats, type-size/contrast disclaimers, and any specialist-imposed conditions | Long text | TTB-completed | p. 1 (lower-right panel); §III.A General Instructions 6 | **Yes** — qualifications drive downstream re-issuance and revision rules; the standard type-size disclaimer is now boilerplate per Industry Circular 2011-4 |
| (block) | Part II Perjury Statement (preprinted) | Attestation | **Required attestation** | p. 1 | No |
| (block) | Paperwork Reduction Act / Privacy Act / Disclosure statements | Notices | Informational | p. 4 | No |

**Electronic vs. paper field divergences (per TTB FAQs at `ttb.gov/faqs/colas-and-formulas-online-faqs` and Public Guidance 2017-2 on personalized labels):**
- Electronic submission supplies the same data as items 1–18 but presents it as a guided "Step 1 / Step 2 / Step 3" workflow with built-in business rules that block submissions missing certain data; the perjury "I agree" checkbox replaces the ink signature and the system records "Application was e-filed" in the signature box.
- Item 15's "blown / branded / embossed" content is split between item 15 free text and a separate **Step 3** structured field collecting the actual measurements when net contents are molded into the glass (per the "Anatomy of a Malt Beverage Label" page, `ttb.gov/beer/labeling/anatomy-of-a-malt-beverage-label-tool`).
- Electronic submissions also collect label image dimensions (width × height of the printed label as it will appear) and a "Notes to Specialist" free-text field. These have no exact paper-form analog.
- Paper applications are rejected outright on first error; electronic eApplications get a "Needs Correction" intermediate status with a 30-day correction window (formerly 15 days; expanded in COLAs Online 3.7, June 2012).
- TTB removed three former electronic-form fields (alcohol content, net contents on label, and vintage date) per the COLAs Online 3.7 release notice (June 2012) — those values are no longer required as separate structured fields because they are inferable from the label image and were a leading source of "Needs Correction" returns.

The 04/2023 revision also embeds **41 numbered "Allowable Revisions" rows** (Section V) on pages 3–4 — these are not application fields but post-issuance change-management rules that the prototype's "is this change allowable without a new COLA?" feature would consume.

---

## Q2.2 — Submission path inventory

There are **two production submission paths**, plus several auxiliary paths for registration, third-party submission, and post-approval status checking.

### Path A — COLAs Online (electronic, primary)

- **URL:** `https://www.ttbonline.gov/colasonline/` (entry portal `https://www.ttbonline.gov/`); user-facing customer page `https://www.ttb.gov/regulated-commodities/labeling/colas`.
- **Auth:** Username + password + multi-factor one-time code (email or authenticator app), per `ttb.gov/online-services/myttb/formulas-and-colas-online-verification-code`. Registration requires either signing authority or a Power of Attorney (TTB Form 5000.8) on file. Registration itself is processed via TTB Form **5013.2 (COLAs Online Access Request)** under OMB control number 1513-0111.
- **User flow** (per "COLAs Online 3.11.3 Online Industry Member User Manual," ~140 pp, `ttb.gov/system/files/images/pdfs/colas_ol_oim_um.pdf`):
 1. Log in → "Home: My eApplications."
 2. "Create eApplication" → choose Type of Product → enter form fields equivalent to Items 2–14.
 3. Upload label image(s); enter dimensions (Step 3).
 4. Review & submit; agree to perjury statement.
 5. Receive 14-digit TTB ID immediately (first 5 digits = year + Julian date).
- **Accepted artwork formats:** **JPEG (.jpg/.jpeg) and PNG (.png) only.** TIFF and PDF are *not* accepted (TTB FAQs, "What file formats does COLAs Online accept?"). Older guidance documents (`prepare-images-for-upload.pdf`) list JPG/TIFF — that document is stale; the live FAQ is authoritative.
- **System availability:** 22 hours per day, 7 days per week (down 4–6 a.m. ET for nightly maintenance).
- **Post-submission status states:** *Received → Approved | Conditionally Approved | Needs Correction (≤ 30 days for applicant fix) | Rejected.*

### Path B — Paper Form 5100.31

- **Mailing address (USPS):** Alcohol and Tobacco Tax and Trade Bureau, Alcohol Labeling and Formulation Division, 1310 G Street NW, Box 12, Washington, DC 20005. **Couriers (FedEx/UPS/DHL):** same building, **Suite 400E** (per `ttb.gov/alfd/contact-information`).
- Submit in **duplicate** with original ink signatures; affix labels with glue/tape (do not staple); no pen-and-ink corrections, no white-out, no paste-overs.
- Status of paper submissions is **not** trackable through COLAs Online (per TTB FAQ "Can I track my paper submission?").
- TTB has not formally announced deprecation of paper, but FY 2024 budget materials and Treasury OIG audit OIG-25-023 confirm an ongoing migration to the unified **myTTB** platform; the FY 2025 budget request explicitly lists labeling as a system to be eventually folded in. No sunset date for paper has been published.

### APIs and bulk access

- **No official public REST/JSON API** for the Public COLA Registry exposes COLA application data; TTB's Open Data page (`ttb.gov/data`) lists processing-times XML (`cola_stats.xml`) and CSV exports of search results, but **no API endpoint** for individual COLA records.
- TTB exposes **per-record HTML detail pages** at `ttbonline.gov/colasonline/viewColaDetails.do?action=publicDisplaySearchAdvanced&ttbid=<14-digit-TTB-ID>`. The "Save Search Results to File" link on the Public COLA Registry returns a **CSV file** (per the dedicated `save-search-results-in-public-cola-registry.pdf` user guide).
- A **third-party commercial product** ("COLA Cloud", `colacloud.us`) advertises ~2.5 million label approvals scraped/enriched from the registry, indicating the registry is reasonably scrapable. The registry has no published rate limits or robots.txt rule of record, but the standard `robots.txt` of `ttbonline.gov` was not retrievable during this research and the site's banner cites Treasury monitoring/penalty notices for unauthorized use; aggressive scraping should be rate-limited and identifying User-Agent strings used.

### Turnaround difference

- TTB's stated policy (per COLAs FAQ and `ttb.gov/regulated-commodities/labeling/processing-times`): the **initial review time is the same** for paper and electronic. Differences arise on errors:
 - Electronic with errors → "Needs Correction" → applicant has 30 calendar days to fix → corrected app gets *priority* over new applications.
 - Paper with errors → outright rejection; a fresh paper resubmission goes to the back of the queue.
- Industry Circular 2011-4 ("Streamlining the Certificate of Label Approval Review Process") removed routine review of type size, characters per inch, and contrasting background — TTB now disclaims those checks via a standard Qualifications statement, and applicants are responsible.

### E-filing share

- TTB does not publish a single canonical "% of COLAs filed electronically" figure. The FY 2025 Budget-in-Brief notes "data quality issue detected in FY 2023 that resulted in undercounting electronic submissions" for the FY 2020–FY 2022 baseline; the corrected actuals for the e-filing rate metric on **labels** are not republished as a clean time-series in the public document. Industry sources (Lehrman Beverage Law's blog, Husch Blackwell attorney quoted in the Ollie blog) state that "approximately 80–100%" of practitioner submissions are electronic. This anecdotal range is consistent with TTB's repeated statements that paper is "available but not preferred." **Treat as: e-filing share ≥ ~80%, exact figure not publicly published.**

---

## Q2.3 — Label artwork submission requirements

Authoritative source: **TTB COLAs and Formulas Online FAQ** (`ttb.gov/faqs/colas-and-formulas-online-faqs`), reinforced by Industry Circular 2011-4 and Public Guidance 2017-2.

| Requirement | Rule |
|---|---|
| Accepted formats | **JPEG and PNG only.** PDF and TIFF are explicitly rejected by the FAQ. |
| Per-file size limit | **≤ 1.5 MB per image.** |
| Resolution target | **120–170 DPI minimum** (TTB FAQ rule of thumb); higher recommended for small text. JPEG quality "Medium" (~70%) suggested. (Practitioner guidance, e.g., Lindsey Zahn P.C., advises 300 DPI when feasible — beyond TTB's stated minimum.) |
| Color | **Full color is permitted and standard.** Black-and-white is accepted but discouraged because contrast/legibility judgment is harder. There is no rule mandating B&W or full color. |
| Etched, embossed, painted-on, molded labels | Per ALFD FAQ (`ttb.gov/faqs/alcohol-labeling-and-formulation`): submit a **photograph of a filled representative bottle** showing each side that bears label information — TTB needs to evaluate contrast and legibility against the actual glass. The same applies to clear-acetate labels. The blown/branded/embossed text must also be transcribed in **Item 15** of the form. |
| "Label as it will appear" rule | The image must show the label **as it will be printed and affixed.** The dimensions field must reflect the printed label's actual width × height (not the image's pixel width). Material differences between approved label and printed label invalidate the COLA per 27 CFR 4/5/7 subpart B and create exposure to revocation under 27 CFR 13.41 et seq. |
| Multiple labels | Each face (brand/front, back, neck, side, can-flat, "wrap") **must be uploaded as a separate image file**, cropped to remove white space. The COLAs Online "Step 3" lets applicants tag each as Brand / Back / Neck / Side / Other. There is no published cap on number of label faces per application; one application covers a single product (one brand-name, one class/type), but covers all sizes and faces of that product. |
| Distinctive bottle | If Item 14(c) is checked, applicants must include photographs of the front and back of the distinctive bottle. |
| Personalized labels | Public Guidance 2017-2: the application must include a description of which graphic/textual elements will be personalized; that description appears in Item 15 / "Special Wording" and binds the certificate. |
| Pre-printing risk | TTB explicitly advises (Public Guidance 2017-2) not to print labels before COLA issuance — TTB may require changes during review. |

**Implication for the prototype:** the verification engine must be able to ingest one or more **JPEG/PNG** images per submission (with PNG preferred for sharp text), correlate them to a structured manifest of which face is which (front/back/neck/side), accept a *photograph* of an entire bottle as a substitute when artwork is etched/embossed/painted/molded, and tolerate the 1.5 MB / ≥120 DPI envelope.

---

## Q2.4 — Public COLA Registry capabilities

**Authoritative manuals:** "COLAs Online 3.11.4 Public COLA Registry User Manual" (PDF, `ttb.gov/system/files/images/pdfs/labeling/colas_ol_pcr_um.pdf`) and the slightly older 3.11.3 manual on the TTB media server. The registry's basic-search front door is at `https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do` (no auth required); advanced search is at `publicSearchColasAdvancedProcess.do`.

### Search interface — basic

- Brand Name / Fanciful Name / Either toggle (text)

### Search interface — advanced (per the Public COLA Registry User Manual figures 18–19, and per the historical "What's New in COLAs Online 3.7" release notice)

- TTB ID (14-digit, year + Julian + sequence)
- Status (Approved / Expired / Surrendered / Revoked)
- Vendor Code (legacy, but searchable for historical records)
- Plant Registry / Basic Permit / Brewer's Notice Number
- Permit / Vendor Name
- Product / Class Type Code (with lookup browser)
- Origin Code (country for imports; state for domestic; with lookup browser)
- Brand Name / Fanciful Name / Either
- Type of Product (Wine / Distilled Spirits / Malt Beverage)
- Type of Submission (COLA / Certificate of Exemption / Distinctive Liquor Bottle)
- Wine Appellation
- Date Completed (single date or from–to range)
- Date Status Last Updated (from–to)
- Date Submitted (from–to)
- Serial Number

### Data fields exposed per record (per `display-cola-detail-through-public-cola-registry.pdf`)

TTB ID; Status; Vendor Code; Serial #; Class/Type Code; Origin Code; Brand Name; Fanciful Name; Type of Application; "For Sale In" (state); Total Bottle Capacity (for distinctive bottles); Wine Vintage; Formula; Approval Date; Qualifications; Plant Registry/Basic Permit/Brewer's No (Principal Place of Business); Plant Registry/Basic Permit/Brewer's No (Other); Contact Information; and a link to the **Printable Version** of the COLA.

### Label images

- **Viewable and printable.** The "Printable Version" page renders either a scanned image (paper-filed COLAs) or a PDF-style render of the e-filed certificate with the affixed label image(s) embedded.
- Direct binary image download is not exposed as a documented API, but the printable-version artifact effectively makes images downloadable for any approved record.
- Image format/resolution in the registry: bound by what was uploaded (JPEG/PNG ≤ 1.5 MB, ≥120 DPI). Paper-filed pre-2010 records are scanned reproductions and are typically lower-fidelity.

### Date coverage

- **Images:** "available for COLAs issued from 1999 to present" (registry banner text).
- **Data only:** for COLAs issued before 1999 (no image).
- **Caveat:** "Searches for COLAs issued before 1996 may not produce a complete result set."
- Approved records appear in the registry on a **48-hour delay** after approval.

### Programmatic access / scraping considerations

- **No official API.** TTB's Open Data page (`ttb.gov/data`) does not list a registry API; only the daily processing-times XML (`cola_stats.xml`) and per-page CSV export from search-results screens.
- "Save Search Results to File" returns a **CSV** of the result set columns (TTB ID, Brand, Fanciful, Class/Type Code, Origin Code, Status, Approval Date, Plant Registry No., Type of Submission). This is the cleanest official path to bulk metadata.
- The site's robots.txt was not directly retrievable in this research session; the standard Treasury banner ("UNAUTHORIZED USE … STRICTLY PROHIBITED AND SUBJECT TO CRIMINAL AND CIVIL PENALTIES; the Department may monitor, record, and audit any activity") applies. There are no published rate limits. A third-party service (COLA Cloud) demonstrates that ~2.5 million records have been scraped successfully, suggesting non-aggressive scraping is tolerated; nevertheless, the prototype should respect normal-traffic User-Agent identification, throttle to single-digit requests/sec, and avoid distributed parallelism.
- **Practical scrape pattern:** issue Advanced Search queries scoped by `Date Completed` ranges (e.g., monthly windows), collect TTB IDs from results pages (CSV export), then fetch each `viewColaDetails.do?ttbid=<id>` for structured fields and the printable version for the image(s).

### Empirical exercise of the search interface

I attempted live HTTP fetches of the Advanced Search endpoint (`publicSearchColasAdvancedProcess.do`) and the basic search front-door during this research session; both responded with TLS / robots-policy refusals from the fetch tool used (the `ttbonline.gov` host returned an `SSL: CERTIFICATE_VERIFY_FAILED` error and a robots-disallow message in this environment). The HTML-extracted version of `publicSearchColasBasic.do` was retrievable and confirmed the registry's banner text ("Images of the documents are generally available for COLAs issued from 1999 to present. You may view data only for COLAs issued prior to 1999. Searches for COLAs issued before 1996 may not produce a complete result set"). For the prototype, plan to test interactive search from a normal browser environment; the documented behavior (text fields, lookup pop-ups, CSV export) is accurate to what TTB's user manuals describe and to what third-party scraper documentation reports.

### Approximate registry size

- TTB does not publish a cumulative count. Indirect data points:
 - FY 2018 NPRM (Notice 176) cites "approximately 200,000 label applications that TTB receives each year."
 - FY 2015 Notice 176 cites "over 153,000 applications" that fiscal year; FY 2011 streamlining page cites 146,000 (up from 134,000 in 2010).
 - TTB's processing-times page (snapshot 04/28/2026) shows **55,528** label applications received YTD in CY2026 (i.e., through end of April).
 - COLA Cloud's marketing copy claims "north of 2.5 million label approvals" cumulatively. That is the only public-facing cumulative-count estimate; treat as third-party rather than TTB-canonical.

---

## Q2.5 — Are rejected applications public?

**No — only approved, expired, surrendered, or revoked COLAs are exposed.** The Public COLA Registry's banner is explicit: "COLAs in the registry have one of the following current statuses: approved, expired, surrendered, or revoked." Rejected applications and their rejection reasons are **not** in the registry and are not otherwise published in any TTB-canonical dataset.

The regulatory basis is **27 CFR 13.61 (Publicity of information)**:

- **§13.61(b)** "Approved applications" — TTB must maintain "in the TTB public reading room" a copy of each approved application and publish them via the Public COLA Registry.
- **§13.61(c)** "Revoked certificates" — the record of an approved certificate that is later revoked **remains** in the registry, with the index annotated to show revocation.
- **§13.61(d)** "Further disclosure of information on denied or revoked certificates" — additional disclosure occurs only via FOIA or as authorized by law; denials are *not* posted.

**Aggregate rejection statistics:** TTB does not publish overall rejection rates or a top-reasons taxonomy. The FY 2024 Treasury OIG report (OIG-25-023) and the FY 2025 Budget-in-Brief mention service-standard performance against the **15-day** label review goal but do not break out rejection vs. needs-correction vs. approved counts. **Status: not publicly published.**

**Withdrawal data:** 27 CFR §13.22 allows applicants to withdraw an application before TTB acts. Withdrawals do not enter the registry and are not summarized in any TTB statistics document we found.

**Appeals data:** 27 CFR §13.25 (first appeal — 45 days from notice of denial), §13.26 (decision after appeal — 90 days, extendable once by 90 more), §13.27 (second appeal — same 45/90 cadence; 90-day clock for an informal conference under §13.71 begins 10 days after the conference). Decisions on appeal are not aggregated in a public dataset; published TTB decisions are limited to administrative-action announcements at `ttb.gov/business-central/fo/administrative-cases`, and labeling-only appeals are rarely highlighted there.

**Rejection-reason taxonomy from indirect sources:**
- Industry Circular 2011-4 effectively establishes a *non-rejection* zone (TTB stopped reviewing for type size, characters/inch, contrasting background).
- Common rejection categories triangulated from law-firm and trade-press sources (Lindsey Zahn P.C., Husch Blackwell, Park Street, FIVE x 5, Blue Label Packaging) — these are practitioner-aggregated, not TTB-canonical:
 - Mandatory information missing (brand name, class/type, ABV, name & address, net contents, country of origin)
 - Health-warning statement formatting (exact wording, type-size, comma placement, contrasting background)
 - Class/type designation mismatch with the formula (e.g., labeled "Gin" for a product that is actually a Distilled Spirits Specialty)
 - Geographic-claim non-compliance (Napa, Bordeaux, AVA percentage rules)
 - Misleading claims (health, "pure," organic, gluten-free, biodynamic without supporting documentation)
 - Image-file errors (>1.5 MB; wrong file type; distorted dimensions)
 - Statement-of-composition mismatch with formula
 - Failure to obtain pre-COLA formula approval first

For test-data design, use these indirect categories as candidate buckets, but tag them as "industry-aggregated" rather than "TTB-published" in any documentation.

---

## Q2.6 — Agent workflow detail (ALFD process)

### Division identity

- **ALFD = Alcohol Labeling and Formulation Division**, sitting under the **Office of Headquarters Operations** (per `ttb.gov/about-ttb/who-we-are/offices`). ALFD's mission page (`ttb.gov/about-ttb/who-we-are/offices/alcohol-labeling-and-formulation-division`) divides ALFD into three offices:
 1. **Formulation / Malt Beverage and Distilled Spirits Office** — examines domestic and pre-import formulas; reviews COLA applications for malt beverages and distilled spirits.
 2. **Wine Office** — reviews wine COLAs; issues certificates of label approval and exemption for domestic and imported wines.
 3. **Customer Service / IT Liaison Office** — provides phone and email support; manages COLAs Online improvements; processes Formulas Online registrations.
- ALFD's customer-service phone tree (`ttb.gov/faqs/alcohol-labeling-and-formulation/print`) confirms specialization: **Option 4 = Distilled Spirits/Malt Beverage Labeling and all Formulation; Option 5 = Alcohol Advertising; Option 6 = Wine Labeling.**
- This **commodity-based specialization** (wine specialists vs. spirits/malt specialists) is the public-source confirmation that work is queued by beverage class. There is no public statement that work is geographically routed; the "appropriate TTB officer" abstraction in 27 CFR Part 13 leaves the routing to ALFD management.

### Work assignment

- Per TTB processing-times page: applications are **reviewed in date-received order**, with **resubmitted ("Needs Correction") applications taking priority** over new applications. There is no published evidence of risk-based or AI-assisted triage; assignment is to a "label specialist" in the relevant commodity office.

### Tools / screens

- The internal-facing module of COLAs Online "serves as the sole internal database for TTB's Alcohol Labeling and Formulation Division (ALFD) to track all work-related documentation, including all COLA submissions received for approval either on paper or electronically through our COLAs Online system" (TTB FAQ). The internal UI is not publicly documented in detail; the public Industry Member User Manual implies a parallel "specialist queue" UI.
- The 2022 TTB Boot Camp for Brewers — Labeling presentation (Stephanie Fields, Labeling Specialist; `ttb.gov/system/files?file=images/pdfs/TTB_Boot_Camp_for_Brewers-_Labeling.pdf`) walks brewers through the COLA basics from a specialist's vantage point: brand, class/type, ABV, name & address, net contents, country of origin, health warning, statement of composition for Distilled Spirits Specialty / Flavored Malt Beverage products. The Wine Boot Camp 2024 deck (`ttb.gov/system/files/2024-12/Boot_Camp_for_Wine_Records_Presentation.pdf`) covers similar material from the wine side.
- The "Anatomy of a Malt Beverage Label" interactive tool (`ttb.gov/beer/labeling/anatomy-of-a-malt-beverage-label-tool`) and the corresponding tools for distilled spirits and wine are effectively the public face of the specialist's mental model — each mandatory-information element is checked against placement, type size (industry-self-attestation since IC 2011-4), and content rules.

### Standard checks (triangulated)

Per 27 CFR Parts 4 (wine), 5 (distilled spirits — recodified by T.D. TTB-176), and 7 (malt beverages), and the Beverage Alcohol Manual (BAM) Volumes 1–3:

1. **Brand name** is present, not misleading, doesn't substitute a class/type alone.
2. **Class and type designation** matches what the product actually is per its formula (when one is required); "statement of composition" required for Distilled Spirits Specialty and Flavored Malt Beverages.
3. **Alcohol content** in % ABV with allowed tolerance (per 27 CFR §4.36, §5.65, §7.71); proof optional for spirits but must accompany ABV.
4. **Name and address** of bottler/importer matches the basic permit / brewer's notice / plant registry.
5. **Country of origin** for imports.
6. **Net contents** in standard US units (metric authorized for wine and spirits per standards-of-fill regulations; T.D. TTB-200 modernized standards of fill in January 2025).
7. **Health warning statement** — exact wording, capitalization of "GOVERNMENT WARNING:", type size by container size, contrasting background (industry self-attests since IC 2011-4 but TTB retains the right to reject).
8. **Sulfite/allergen disclosures** when applicable (FD&C Yellow No. 5; cochineal/carmine; sulfites at ≥10 ppm; aspartame warning).
9. **Class/type-specific rules**: appellation of origin and varietal percentages for wine; age statements for whisky; geographic-name compliance.
10. **Truthful and non-misleading review**: prohibited-practices regulations; disparagement (clarified in T.D. TTB-176); health claims (TTB Ruling 2003-1, T.D. TTB-1).
11. **Cross-check with formula**: for products requiring a formula, the label statement of composition must match the approved formula (per Industry Circular 2007-4).

### What happens on issue

- **eApplication path:** specialist marks the application **"Needs Correction"** with a list of items to fix; applicant has **30 calendar days** (was 15 before COLAs Online 3.7, June 2012) to make corrections; corrected app re-enters with **priority**; if no correction in 30 days, status auto-flips to "Rejected."
- **Conditionally Approved** status (added in 2019, per TTB Boot Camp / COLAs Online release notes): the COLA is approved, but with a Qualifications statement (e.g., reduced-image notation; type-size disclaimer per IC 2011-4; or a specialist-imposed condition the applicant must meet).
- **Paper path:** outright rejection with a "correction sheet" returned to the applicant; no intermediate state.
- **Formal denial procedures:** §13.23 (Notice of denial); §13.25 (first appeal — 45 days written); §13.26 (decision — 90-day clock, extendable); §13.27 (second appeal); §13.71 (informal conference option). Judicial review is allowed only after exhausting administrative appeals (§13.26(c)).

### Supervisory / second-review process

- Public sources do not describe a formal mandatory second-review step for routine approvals. The 27 CFR Part 13 framework presupposes a single "appropriate TTB officer" decision, with appeal as the second look. T.D. ATF-449 (66 FR 19085, 4/13/2001) and TTB Order 1135.13 delegate the Administrator's authorities to subordinate officers; appeals route up the chain.
- Industry-side anecdote (the brief cites "Sarah's" assertion of "5–10 minutes per simple application") is not directly corroborated by a TTB document, but is **consistent** with TTB's published service goal (85% of label applications within 15 days; current median **1–5 days** by commodity in April 2026 — see Q2.7) and with the staffing implication that specialists must process on the order of dozens of applications per day at FY 2023's ~150,000–200,000/year volume. Treat the "5–10 minutes for a simple application" figure as a defensible working assumption, sourced anecdotally and bounded by service-level math.

---

## Q2.7 — Operational metrics

### Current processing time (snapshot, primary source: `ttb.gov/regulated-commodities/labeling/processing-times`, "Updated 04/28/2026 7:00 AM")

| Commodity | Median days to process | Now processing applications received on |
|---|---|---|
| Distilled Spirits | **4 days** | 04/24/2026 |
| Malt Beverages | **1 day** | 04/27/2026 |
| Wine | **5 days** | 04/24/2026 |
| Customer-service goal | 85% of applications within **15 days** | n/a |

- "Median" defined as the median number of calendar days from receipt to either approval or rejection, including round-trip "Needs Correction" cycles.
- Historical context: the same TTB methodology has been used since at least 2011 (when daily averages began publishing). Industry-historical data points: **41 days** for distilled spirits / wine and **11 days** for malt beverages in September 2013 (Malkin Law blog citing TTB chart at that date). FY 2018 saw a "spike in submission volume" that triggered the 15-day service standard (FY 2025 Budget-in-Brief). The 2026 snapshot above represents a steady-state below the service standard.

### Application volume

| Source | Year | Volume |
|---|---|---|
| TTB Streamlining Accomplishments page | CY 2010 | ~134,000 |
| TTB Streamlining Accomplishments page | CY 2011 | ~146,000 |
| Notice 176 (NPRM, 11/26/2018) | FY 2015 | over 153,000 |
| Notice 176 / T.D. TTB-176 / TTB statements | recurring | "approximately 200,000 label applications that TTB receives each year" |
| About TTB page (`ttb.gov/about-ttb`) | recent (no FY) | "Annually, we process nearly 180K applications for Certificates of Label Approval (COLA)" |
| FY 2025 Budget-in-Brief | FY 2024 | "label submissions declined across alcohol commodities, particularly for malt beverages, which have declined around 15 percent over the last five [years]" — exact CY2024 number not given as a single-cell figure in the public budget document |
| TTB processing-times page | CY2026 YTD (through 28 April 2026) | **55,528 received** |

The ~150,000–200,000/year range stated in the brief is **corroborated**; the most-cited round-number canonical figure is the "approximately 200,000" used in TTB's own NPRM and the "nearly 180K" in the About TTB page.

### Distribution of submission sources

- TTB does not publish a clean breakdown of importers vs. domestic vs. small/large. The FY 2025 Budget-in-Brief notes that the pandemic disrupted volume in FY 2020, recovery began FY 2021, and FY 2024 saw declines especially in malt beverages. The CBMA importer-claims program implementation (FY 2023) is mentioned but is not a label statistic. **Status: not publicly published as a clean breakdown.**

### Peak-season patterns

- TTB does **not** publish a seasonality narrative explicitly for label applications. The processing-times page cites only "submission volume" as an explanation for variation; the FY 2025 Budget-in-Brief frames variance year-over-year, not month-over-month. **Status: not publicly published.**
- Practitioner anecdote: Q4 calendar-year (holiday-season planning) is a common surge for spirits and seasonal beers; label submissions for vintage-dated wines surge after harvest; FY-end procurement cycles may matter for federal-contract-bound importers but are not documented for COLA volume.

### Rejection rates

- **Not publicly published, by class or overall** (see Q2.5).

### ALFD staffing

- The brief asserts "47 agents." TTB does not publish ALFD specialist headcount in the FY 2023 Annual Report or FY 2025 Budget-in-Brief. The Bureau-wide FY 2023 actual FTE was **497** (FY 2025 Budget-in-Brief, PDF page accessible at `ttb.gov/media/78706/download?inline=`); FY 2024 anticipated FTE was **529**. Neither figure is broken out by division. **Status of "47 ALFD agents": not publicly published; treat as working assumption from internal source.**

---

## Q2.8 — Existing tooling and prior modernization attempts

### Programs and platforms

| Initiative | Status | Source |
|---|---|---|
| **COLAs Online** | Production since June 2003 (per Federal Register, 68 FR 32796, 6/2/2003, "Establishment of COLAs Online Electronic Filing System"). Created to comply with Government Paperwork Elimination Act (GPEA, 1998). Currently at version **3.11.4** of the Public COLA Registry user manual. | `ttb.gov/system/files/images/pdfs/labeling/colas_ol_pcr_um.pdf`; 68 FR 32796 |
| **Formulas Online** | Launched January 2011; shares user account with COLAs Online. | TTB FAQs |
| **Permits Online** | Long-running permit-application system; **scheduled for migration to myTTB platform** because the underlying IT platform "will no longer be supported by the software vendor as of December 2025" (FY 2025 Budget-in-Brief); $1.784M requested in FY 2025 specifically for myTTB IT modernization. | FY 2025 Budget-in-Brief; FY 2024 OIG report OIG-25-023 |
| **myTTB** | Unified platform; first launched October 2022 for CBMA foreign-producer registration; now host of CBMA Importer Claims (since 2023) and identity-verification flow via Login.gov / ID.me. Plan is to fold Permits Online (FY 2025), then Formulas Online and COLAs Online (later phases) into myTTB. | `ttb.gov/online-services/myttb/`; FY 2025 Budget-in-Brief |
| **Pay.gov integration** | Used for tax returns and operational reports; not part of COLA flow but part of the broader modernization arc. | `ttb.gov/online-services/epayment` |
| **Label Generator Tool / Allowable Changes Sample Label Generator** | Self-service tool that lets industry preview which kinds of changes to an approved COLA are "allowable revisions" (the 41 rows in Section V of Form 5100.31). | `ttb.gov/regulated-commodities/labeling/allowable-revisions/allowable-changes-sample-label-generator` |
| **Anatomy of a [Malt Beverage / Wine / Distilled Spirits] Label** interactive guides | Public training/explainer tools — closest TTB has come to "AI"-style assistance on labels. | `ttb.gov/beer/labeling/anatomy-of-a-malt-beverage-label-tool` |
| **Conditionally Approved status** | Added in 2019 release of COLAs Online; allows TTB to issue an approved COLA with applicant-acceptable proposed minor edits without round-tripping through "Needs Correction." | TTB Boot Camp deck "COLAs Online — Conditionally Approved Status (June 2019)"; `ttb.gov/main-pages/presentations` |

### AI / OCR / scanning pilots

- **No publicly disclosed AI or OCR pilot** for COLA label review surfaced in TTB.gov, the FY 2023 Annual Report, the FY 2025 Budget-in-Brief, or in Federal Register notices. The brief's "scanning vendor pilot" mentioned by Marcus is **not publicly disclosed**; treat as internal information not corroborated by a primary source.
- The FY 2025 Budget-in-Brief and the FY 2023 priority-goals page do mention **automated data validations** in the CBMA Importer Claims module (target: ≥50% auto-validation rate by 9/30/2025). This is structured-data validation, not document-AI/computer-vision over label artwork.

### Procurement / RFP records

- TTB's contracting page (`ttb.gov/public-information/contracting`) directs to SAM.gov for opportunities >$25,000. A SAM.gov keyword search for "TTB" + "label" / "COLA" / "OCR" / "AI" did not return TTB-specific awarded contracts in the public summary results during this research. **Status: no publicly disclosed RFP/RFI for label-review automation found.**
- Treasury OIG report **OIG-25-023** (FY 2024 financial management audit; `oig.treasury.gov/system/files/2024-12/Report-is-undergoing-a-508-Compliance-Review_0_2.pdf`) discusses TTB IT modernization in general terms but does not flag a label-review AI initiative.
- Treasury OIG report **OIG-23-016** (FY 2022) similarly addresses COLA volume trends but not AI/OCR.

### Modernization rulemakings (not tooling, but related)

- **Notice 176 (83 FR 60562, 11/26/2018)** — proposed "Modernization of the Labeling and Advertising Regulations for Wine, Distilled Spirits, and Malt Beverages" (Docket TTB-2018-0007). Comment period extended to 6/26/2019; **1,143 comments received**.
- **T.D. TTB-158 (4/2/2020)** — "Phase 1" final rule: liberalizing/clarifying changes; effective 5/4/2020.
- **T.D. TTB-176 (2/9/2022)** — "Phase 2" final rule: reorganized parts 5 and 7; consolidated advertising regulations into a new part 14 (forthcoming for wine). Effective 3/11/2022. Corrected by T.D. TTB-176A (3/9/2022).
- **T.D. TTB-196 (89 FR 87935, 11/6/2024)** — "Technical Corrections to the TTB Regulations": corrects cross-references after TTB-176, updates citations and contact info, refreshes pronouns. **Non-substantive** — does not change interpretation. Effective 12/6/2024.
- **Notice 232 (1/31/2024)** — listening sessions on Alcohol Facts / nutritional / allergens / ingredients labeling; comments due 3/29/2024.
- **Notice on Mandatory Disclosures of Major Food Allergens and Alcohol Facts** (1/17/2025) and the comment-period extension to spring 2025 are the most active labeling rulemakings affecting future label content; they do not change the COLA submission mechanism.

---

## Q2.9 — Adjacent stakeholders

Sources: `ttb.gov/about-ttb/who-we-are/offices`, `ttb.gov/about-ttb/organizational-chart-for-ttb`, the FY 2025 Budget-in-Brief, and the per-division landing pages.

| Division | Confirmed touch point on COLA workflow |
|---|---|
| **Alcohol Labeling and Formulation Division (ALFD)** — Office of Headquarters Operations | Primary owner. Reviews & issues / denies COLAs. |
| **Regulations and Rulings Division (RRD)** — Office of Headquarters Operations | Issues rulings, industry circulars (e.g., 2011-4, 2018-2, 2021-1, 2024-1 — all touching COLAs); maintains TTB Forms list; handles Federal Register publication. **Confirmed.** |
| **Trade Investigations Division (TID)** — Office of Field Operations; **4 districts** (Western I & II, Central, Eastern; plus Tampa SE field office and Puerto Rico) | Conducts post-market product-integrity investigations; can flag a COLA holder for revocation; publishes "Common Compliance Issues" findings used in Boot Camp. **Confirmed touch point**, but post-market — not in the up-front COLA review queue. |
| **Office of Chief Counsel** (Chief Counsel: Christina McMahon, per org chart) | Handles legal review of contested cases, appeals, and rulemaking drafting. **Confirmed** for §13.25/§13.26/§13.27 appeals and §13.41+ revocation proceedings. |
| **Scientific Services Division (SSD) / Nonbeverage Products Laboratory (NPL)** at Beltsville, MD | Performs flavor verification for ALFD ("Flavor verification for the Alcohol Labeling and Formulation Division (ALFD) of TTB for flavors used in alcoholic beverages" — `ttb.gov/offices/scientific-services-division`) and pre-import laboratory analyses. **Confirmed feeder to ALFD's pre-COLA evaluation step**, particularly for flavored, colored, or specialty products. |
| **National Revenue Center (NRC)** — Office of Permitting and Taxation, Cincinnati, OH | Issues and amends basic permits, brewer's notices, plant registry numbers — i.e., the upstream identity that Form 5100.31 Item 2 references. **Confirmed**: a COLA cannot be issued to an applicant whose permit isn't valid. |
| **Tax Audit Division (TAD)** — Office of Field Operations | Verifies tax-classification consistency post-market (auditing tax payments against bottled product). **Tangential to COLA** but in the same enforcement chain. |
| **Office of the Chief Information Officer (OCIO)** | Owns COLAs Online, Formulas Online, myTTB, Permits Online platforms. **Confirmed** as the system owner. |
| **Office of Industry and State Outreach** | Runs Boot Camp webinars and conference participation; produces the public-facing process documentation that this research relies on. **Confirmed** as the documentation/outreach owner. |
| **International Affairs Division** | Touches imported-product COLAs with international-agreement implications (e.g., wine-trade agreements, certificate-of-origin requirements). **Confirmed** for imported COLAs only. |
| **Field Operations** more broadly | TTB has 17 field offices total (10 Tax Audit, 7 Trade Investigations) — including LA, Tampa, Cincinnati, Hudson NH, Bremerton WA, San Juan PR. The brief's reference to "Janet in Seattle" most plausibly maps to either the Western II TID district (which covers Washington and ships mail to a Bremerton, WA address) or to a remote ALFD specialist who teleworks. **TTB has no published Seattle field office for ALFD specifically**; many TTB employees telework full time per the U.S. Government Manual entry. Treat the Seattle reference as ambiguous in the public org chart. |

**Other divisions named in the org chart that do *not* touch COLA workflows directly:**
- Tobacco Enforcement Division (tobacco only)
- Intelligence Division (cross-program risk analytics)
- Acquisition and Facilities Management Division (procurement/admin)
- Human Resources / Training and Professional Development / Finance and Performance / Budgeting Division (administrative)

---

## Q2.10 — Application input format for the prototype

### Ranked candidate inputs

| Rank | Format | Realism vs. operational reality | Ease of construction | Path to COLA integration | Defensibility |
|---|---|---|---|---|---|
| **1 (recommended primary)** | **JSON schema mirroring Form 5100.31 fields** (items 1–18 + label-image manifest) | **High.** COLAs Online's internal data model is field-by-field equivalent to the form; the public CSV export from the registry is a flattened version of this data; TTB's daily processing-times XML uses field-keyed structured data. A JSON schema fitted to Form 5100.31 is the closest "neutral" representation of what an integration would actually exchange. | **Easy.** ~25 fields; can be authored as a single JSON Schema (Draft 2020-12) and mocked in fixtures. Label images can be referenced as base64 or as URL/path references with width/height dimensions and face-tag (front/back/neck/side). | **Excellent.** A future TTB-direct integration would either (a) use TTB's eventual myTTB API (currently nonexistent for COLAs but plausible per the modernization plan) — which would almost certainly be JSON over HTTPS — or (b) generate a Form 5100.31 PDF for paper fallback, which a JSON-schema model can serialize trivially. | **Highest.** Reviewer reads "I built to the actual form schema" and immediately understands the design. |
| 2 | Mocked structured object (fixture-style; e.g., a Python dataclass or TypeScript interface) | Same data shape as Option 1, but not portable across languages and not self-documenting. | Easiest of all (no schema language overhead). | Weak — would need to be re-expressed as JSON schema when integrating. | Acceptable for a take-home, but reviewer may ask "why not just write the schema?" |
| 3 | Direct CSV export from the Public COLA Registry's search results | **Realistic for *approved* records only**, not pending/new applications. The CSV columns (TTB ID, Brand, Class/Type Code, Origin Code, Status, Approval Date, Plant Registry No., Type of Submission) are fewer than Form 5100.31's items — missing perjury attestation, applicant phone/email, item 15 free text, etc. | Easy to ingest. | Useful as a **secondary** batch-test source; the registry is the prototype's natural source of real labels for evaluation. | Defensible *as a corpus source* (Q2.5/test data), not as the primary application input format. |
| 4 | PDF parse of completed Form 5100.31 | High realism for paper-filed COLAs (still a non-trivial minority of submissions); requires PDF-form-field extraction. | Moderate — pdfplumber/PyMuPDF can extract Acrobat form fields if the PDF is the official fillable; flat-image scans need OCR. | Plausible bridge for paper submissions but outdated as primary path given >80% e-filing. | Defensible as a *secondary* path (paper fallback). |
| 5 | XML mirroring TTB internal exchange | TTB does publish a small XML feed (`cola_stats.xml` for processing times) and uses XML internally for some flows, but **no publicly documented COLA-application XML schema exists**. | Hard — would require fabricating a schema. | Speculative. | Weakest defensibility: reviewer asks "where did this XML come from?" — answer: "I made it up." |
| 6 | CSV / spreadsheet (batch) | Reasonable for batch ingestion of many applications; but lossy for nested data (multiple labels per app, multiple plant registry numbers per app, etc.). | Easy to author. | Useful as a **batch fallback**. | Acceptable for batch, weaker for single-app realism. |

### Recommendation

- **Primary format: JSON schema mirroring Form 5100.31 fields**, with a top-level object that includes:
 - all numbered items 1–18 from the form (typed per the table in Q2.1);
 - a `labels: []` array, each entry containing `{face, image_format, image_bytes_or_uri, printed_width_mm, printed_height_mm, printed_dpi}`;
 - an optional `formula: {ttb_formula_id, approval_date}` object for products requiring pre-COLA evaluation;
 - an optional `qualifications: string` field reserved for TTB output;
 - status enum `{Received, Needs_Correction, Conditionally_Approved, Approved, Rejected, Surrendered, Expired, Revoked}`.

 Rationale: this is the format an integrating system would actually send TTB if/when myTTB exposes a labeling API; it maps trivially to the paper form for fallback; it composes naturally with image inputs the prototype already needs; it's the easiest representation for a reader to validate against the real form.

- **Fallback for batch: CSV export from the Public COLA Registry's "Save Search Results to File" function**, augmented with one additional column referencing the registry's printable-version URL for image retrieval. Rationale: zero authoring overhead, real production data, immediately suitable for evaluation runs of 100+ records.

---

## Caveats

1. **Live-search exercise.** The Public COLA Registry's `publicSearchColasAdvancedProcess.do` and `publicSearchColasBasic.do` endpoints could not be exercised interactively from this research environment (TLS / robots responses blocked the fetch). Documented behavior is taken from TTB's own user manuals (versions 3.11.3 and 3.11.4) and from independent practitioner write-ups; for the prototype, run an interactive search session in a normal browser to confirm field-level behavior before relying on it.

2. **Anecdotal-vs-canonical distinctions.** The brief's statements that "Sarah said 47 ALFD agents" and "5–10 minutes per simple application" are treated as plausible internal information; the public sources do **not** publish ALFD-specific headcount or per-application time. This is flagged explicitly in Q2.7 and Q2.6 above.

3. **E-filing share is not cleanly published.** The FY 2025 Budget-in-Brief explicitly notes a data-quality issue in FY 2023 that resulted in undercounting of electronic submissions and revised FY 2020–2022 actuals; TTB does not publish a tidy single-figure "% e-filed" for COLA labels. The ≥80% working assumption is industry-aggregated.

4. **Rejection statistics are not public.** The prototype's rejection-reason taxonomy must be built from indirect industry sources (Lindsey Zahn P.C., Husch Blackwell, Park Street, FIVE x 5, Blue Label Packaging) and from TTB's own Boot Camp "Common Compliance Issues" decks — TTB does not publish a canonical rejection-reason ontology.

5. **No public AI/OCR pilot.** There is no public TTB disclosure of a COLA-label AI/OCR pilot. Internal references in the brief ("Marcus's scanning vendor pilot") cannot be corroborated against TTB.gov, the FY 2023 Annual Report, FY 2025 Budget-in-Brief, SAM.gov public award searches, or the OIG audit reports.

6. **Modernization timeline is fluid.** myTTB's incorporation of labeling is a multi-year initiative dependent on continued appropriations; the FY 2025 Budget-in-Brief commits to permitting first (driven by the December 2025 vendor-end-of-life deadline for Permits Online). When labeling lands on myTTB is **not publicly committed**.

7. **Form 5100.31 may be amended.** TTB has staged "proposed changes" PDF (`f510031-proposed-changes.pdf`) on the forms server, indicating a pending revision under OMB review. The 04/2023 revision remains the current operative form; monitor the TTB forms page for an updated revision number.

8. **27 CFR Parts 4 and 7 reorganization is incomplete.** T.D. TTB-176 reorganized parts 5 and 7 but **wine** (part 4) reorganization is still pending ("Phase 3"). This affects which exact section numbers a label-content validator should cite for wine vs. spirits/malt.

9. **The "Public COLA Registry" image format depends on submission vintage.** Pre-2010 paper-filed records appear as scanned images of the entire Form 5100.31 face (with the labels physically taped to the form). Post-COLAs Online era e-filed records appear as a rendered certificate with the original-uploaded JPEG/PNG embedded. The prototype's image-ingestion pipeline must handle both — the older scans are noticeably lower fidelity.

10. **Bibliography deliberately omitted.** Per the user's task instructions ("Never include a list of references or sources or citations at the end of the report"), inline source identifiers above are the only citations; no separate bibliography is produced.