# Test labels with known answers, from the TTB Public COLA Registry

**Answer.** The TTB Public COLA Registry publishes every approved label application as a
public-domain record (CC0) with the label artwork attached. From it, `tests/fixtures/labels/` holds
30 real approved labels: 14 distilled spirits, 8 wine and 8 malt beverages, 14 of them imports.
Each is paired with the application fields it must match and the expected result of every check.
There are also 8 flawed variants derived from those labels. Each record gives the brand name,
fanciful name, class/type, origin, whether the product is domestic or imported, the product type,
and the applicant's name and address. Records filed on the current form (every label in this set)
no longer carry net contents or alcohol content, so both values were read from the label image and
are marked `read_from_label`. Three approved labels do not carry the 27 CFR 16.21 warning word for
word, so the set tests the exact-warning check on real labels as well as on variants.

## What the registry exposes

- **Scope and license.** The registry holds "COLAs issued from 1999 to present", with images
  usually online within 48 hours of approval, and needs no registration
  (https://www.ttb.gov/regulated-commodities/labeling/cola-public-registry). data.gov lists it as
  dataset `015-TTB-54`, access level public, license CC0 1.0
  (https://catalog.data.gov/dataset/ttb-public-cola-registry-view-the-details-of-a-specific-certificate-of-label-approval-cola).
- **Search.** `https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do` is an HTML form
  (POST to `publicSearchColasBasicProcess.do?action=search`) with these fields: date completed
  from/to, product or fanciful name, class/type code range, and origin code. Its manual says the
  date range may not exceed 15 years, that `%` is a wildcard, and that results are "limited to a
  maximum of 500 items", which can be saved as CSV (COLAs Online 3.11.3 Public COLA Registry User
  Manual, https://www.ttb.gov/system/files?file=images/pdfs/labeling_colas-docs/colas_ol_pcr_um.pdf,
  sections 3.4.1.1 and 3.4.6). Measured here, the live site shows 20 rows a page and reports
  "1 to 20 of 1000 (Total Matching Records: 2347)" for a Scotch search, so the display cap is now
  1,000. Each result row gives the TTB ID, permit number, serial number, completed date, fanciful
  name, brand name, origin code and description, and class/type code and description. The
  "completed" date moves when a record changes status, so a 2013 record surrendered in 2025 shows up
  in a 2025 search. Sorting by TTB ID descending
  (`publicPageBasicCola.do?action=sort&sortcol=ttbId&order=desc`) puts recent approvals first.
- **Class/type and origin codes.** The full class/type list is at
  https://ttbonline.gov/colasonline/lookupProductClassTypeCode.do?action=search&display=all.
  Codes used here: 141 bourbon, 142 rye, 150-153 Scotch, 166 American single malt, 170-172 Irish,
  200-219 domestic gin, 250-269 imported gin, 300-340 domestic vodka, 450-499 foreign rum,
  551-552 cognac, 600-629 domestic cordials and liqueurs, 977-978 tequila, 80 table red wine,
  80A rosé, 81 table white wine, 84 sparkling wine/champagne, 88 dessert/port/sherry wine,
  901 beer, 902 ale, 904 stout, 951 imported beer, 952 imported ale. Origin codes seen in records:
  50 Italy, 51 France, 5E Ireland, 5K Scotland, 81 Mexico, 4H Barbados; US states are 01-49.
- **Record, short view.**
  `viewColaDetails.do?action=publicDisplaySearchBasic&ttbid={TTB ID}` shows status, vendor code,
  serial number, class/type, origin, brand, fanciful name, application type, approval date, the
  permit holder's name and address, and a contact name. It has no images.
- **Record, form view.** `viewColaDetails.do?action=publicFormDisplay&ttbid={TTB ID}` renders
  TTB F 5100.31 as filed. The ticked boxes show source of product (Domestic or Imported) and type
  of product (Wine, Distilled Spirits, Malt Beverage). The form also carries the brand name
  (item 6), fanciful name (7), the applicant's name and address as on the permit, including any DBA
  "used on label" (8), grape varietals, wine appellation, the class/type description, status, and
  every label image with its type and "Actual Dimensions". On the older form edition, used for
  example by record 13231001000240 (approved 2013), items 12 and 13 hold net contents
  ("750 MILLILITERS") and alcohol content ("46.5"). On the current form, used for example by
  records 24322001000065 and 25005001000057 (2025) and by every record in this set, the item after
  grape varietals is "14. TYPE OF APPLICATION", and neither field appears.
- **Images.** Each image is `/colasonline/publicViewAttachment.do?filename={name}&filetype=l`,
  served as JPEG or PNG. Measured here, requests succeed only with ordinary browser headers
  (`Accept`) and the session cookie that the form view sets. A bare request got "Remote end closed
  connection without response". Image types are Brand (front) or keg collar, Back, Neck, Strip and
  Other. The type is the applicant's choice: in 5 of the 30 records the image tagged "Brand (front)"
  carries the mandatory text and warning, and the one tagged "Back" is artwork. Malt beverages are
  often filed as a single wraparound can or keg-collar image with no back.
- **Terms and rate limits.** The registry pages and the TTB page above state no rate limit and no
  bulk-access rule. Every registry page carries the Treasury system-use banner ("UNAUTHORIZED USE
  OF THIS SYSTEM IS STRICTLY PROHIBITED ... BY ACCESSING AND USING THIS COMPUTER YOU ARE AGREEING TO
  ABIDE BY THE TTB RULES OF BEHAVIOR"). The page footer says registry label images "may appear
  differently, with respect to type size, characters per inch and contrasting background, than
  actual labels on the container", and every record carries the qualification "TTB has not
  reviewed this label for type size, characters per inch or contrasting background." Measured
  here, `https://www.ttbonline.gov/robots.txt` returns no response (the connection closes). All
  collection for this set ran one request at a time, with a 2-second pause after each.
- **TLS.** Measured here, `www.ttbonline.gov` sends only its leaf certificate (issuer "Entrust OV
  TLS Issuing RSA CA 2"), so strict clients such as curl fail with "unable to get local issuer
  certificate". The fix used here keeps verification on: fetch the intermediate from the URL in the
  certificate's Authority Information Access field
  (http://crt.sectigo.com/EntrustOVTLSIssuingRSACA2.crt) and add it to the trust store.

## The warning text the set is scored against

27 CFR 16.21 (https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-16/subpart-C/section-16.21),
verbatim:

> GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic
> beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic
> beverages impairs your ability to drive a car or operate machinery, and may cause health
> problems.

27 CFR 16.22(a)(2) (https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-16/subpart-C/section-16.22):
"The first two words of the statement required by § 16.21, i.e., “GOVERNMENT WARNING,” shall
appear in capital letters and in bold type. The remainder of the warning statement may not appear
in bold type."

## How the set was chosen and verified

1. For each class bucket, one registry search over completed dates 01/01/2025 to 08/31/2026,
   sorted by TTB ID descending. Imports and domestic products were split on the origin description,
   and French and Italian wine used origin codes 51 and 50.
2. From each bucket, the first records that were status APPROVED, had a front image and (except
   malt beverages) a back image, had a brand name of 40 characters or fewer, and came from a permit
   holder not already used in that bucket. Fields were parsed from the live form view, and the front
   and back images downloaded from it.
3. Every image was read by eye: which image holds the warning, the alcohol content and net contents
   as printed, the class/type designation, the name and address line, and any origin statement.
   Small or sideways warnings were checked on magnified crops. Two records were dropped because
   neither downloaded image carried the warning (26236001000783 and 26236001000772, both on a neck
   or second back image), and three unreviewed malt and wine records were discarded to stay in the
   size budget.
4. `manifest.json` is built from the parsed registry fields and those readings. Each entry records
   the registry form and detail URLs, the image URLs and TTB image types, the class/type and origin
   codes, and the date verified.
5. Images were converted to JPEG at quality 88, capped at 2,800 px on the long side, which keeps
   warning text legible. Measured with `du -sh`, the folder is 13 MB across 64 files (60 label images,
6 variant images, the manifest and the script).

**Expected results.** Real labels were approved by TTB, so their field checks expect `pass`.
Where the label and the application differ in a way a reviewer should look at, the entry also
accepts `needs_review` and says why (for example, Black & White's label city is San Juan while the
application address is Guaynabo). Warning checks record what the label shows against the regulation
text, so an approved label can expect `warning_exact: false`. The manifest's `check_rules` block
states each rule. Bold type (16.22(a)(2)) is not scored.

## The 30 real labels

| TTB ID | Type | Brand (application) | Origin | What it tests |
|---|---|---|---|---|
| 26231001000662 | Spirits | LUCKY LUCY'S | Illinois | Mixed-case brand with a curly apostrophe; DBA on label |
| 26230001000540 | Spirits | BENT 301 | Maryland | Clean black-on-white; whole warning in bold |
| 26239001000079 | Spirits | TACONIC DISTILLERY | New York | Label's big brand is the DBA BONEFISH; application brand only in the producer line |
| 26236001000448 | Spirits | AVIATION | Illinois | DBA on label; serving-facts panel beside the warning |
| 26239001000081 | Spirits | TACONIC DISTILLERY | New York | Same pattern as the Taconic vodka, gin class |
| 26229001000513 | Spirits | SATVRNAL | Mexico | Import; hand-lettered front on a busy pattern |
| 26233001000189 | Spirits | FOURSQUARE | Barbados | Import; small back image; warning hyphenated at line ends |
| 26237001000107 | Spirits | JUAN LOBO | Mexico | Import; origin stated in Spanish ("HECHO EN MEXICO") |
| 26232001000404 | Spirits | BLACK & WHITE | Scotland | Import; label city differs from application address |
| 26231001000333 | Spirits | SALTIRE RARE MALT WHISKY COMPANY | Scotland | Import; very small warning; no "Product of" line |
| 26212001000085 | Spirits | TERRE ET BOIS DE PRADIÈRE | France | Import; warning set sideways and not word-for-word ("BEVERAGE IMPAIRS"); importer city misspelled |
| 26229001000034 | Spirits | BREVIS | New York | Warning not word-for-word ("RISKS OF BIRTH DEFECTS"); gold on navy |
| 26236001000210 | Spirits | LOST LANTERN | Oregon | Handwritten ABV; sideways net contents |
| 26218001000369 | Spirits | AODH | Ireland | Import; distilled in Ireland, bottled in India |
| 26233001000569 | Wine | PORTALUPI | California | Varietal (SANGIOVESE) as the class designation |
| 26233001000566 | Wine | UGLY SWEATER | California | Warning on the image tagged front; bottler name is neither applicant nor DBA |
| 26236001000716 | Wine | BEAR PATH | California | Heading not bold; varietal class |
| 26236001000652 | Wine | PATRIA | California | Script brand; white on orange |
| 26239001000132 | Wine | FABIO SIGNORELLI | Italy | Import; all mandatory text on one clean image |
| 26237001000196 | Wine | MARK WEST | California | Application class is dessert wine, label says PINOT NOIR; small images |
| 26239001000239 | Wine | DOMAINE DU GRAND TINEL | France | Import; space before the heading's colon |
| 26239001000331 | Wine | GAIFFE-BRUN | France | Import sparkling; ABV with a decimal comma (12,5%) |
| 26230001000420 | Malt | THE BRUERY | California | No bottler name or address on either image |
| 26242001000088 | Malt | ZHIGULEVSKOYE | Belarus | Import; back label spells the brand differently |
| 26239001000217 | Malt | FREISINGER | Germany | Import; net contents in US fl oz only |
| 26239001000279 | Malt | HOP BUTCHER FOR THE WORLD | Illinois | Single can wrap |
| 26240001000563 | Malt | OKTOBERFEST | Texas | Tiny warning over artwork |
| 26240001000454 | Malt | I HEARD CASSAROLE | Kentucky | Phone photo of a keg collar; handwritten fields; several keg sizes listed |
| 26240001000573 | Malt | SVYTURYS | Lithuania | Import; brand with a diacritic (ŠVYTURYS) |
| 26238001000795 | Malt | QALIO | Guatemala | Import; script logo reads as "Gallo" |

Each record's page is
`https://www.ttbonline.gov/colasonline/viewColaDetails.do?action=publicFormDisplay&ttbid={TTB ID}`.

## The flawed variants

`make_variants.py` builds them from the manifest (run `uv run --with pillow python make_variants.py`
in the folder). Output is deterministic.

| ID | Derived from | Change | Expected |
|---|---|---|---|
| var-heading-title-case | 26239001000132 | Warning repainted with the heading in title case ("Government Warning:") | heading caps fail; wording exact |
| var-warning-wording | 26239001000132 | "IMPAIRS" changed to "MAY IMPAIR" | warning exact fail |
| var-abv-mismatch | 26237001000107 | Application ABV 45%; label says 40% | ABV fail |
| var-brand-case-punctuation | 26231001000662 | Application brand "Lucky Lucys" against label "Lucky Lucy's" | brand pass |
| var-glare | 26236001000652 | White hotspot over part of the warning | as source; needs_review also accepted |
| var-skew | 26218001000369 | Rotated 12 degrees and sheared | as source; needs_review also accepted |
| var-low-light | 26236001000716 | Back darkened to 35%, noise added | as source; needs_review also accepted |
| var-blur | 26232001000404 | Back blurred, Gaussian radius 2.5 px | as source; needs_review also accepted |

## One-click samples for the deployed app

- **Distilled spirits: BENT 301 (26230001000540).** Black on white, every field legible, and a
  warning that matches exactly; a clean pass.
- **Wine: FABIO SIGNORELLI (26239001000132).** An import whose single image carries the brand,
  class, ABV, net contents, importer, origin and warning; a clean pass. Its two warning variants make
  natural failing companions.
- **Malt beverage: FREISINGER (26239001000217).** An import with a clear front and back, a stated
  origin and a legible warning; a clean pass.

## Limits of the set

- 30 real labels is enough to exercise every check, but too few for tight accuracy figures.
  Bourbon is one label: two candidate bourbons had the warning only on images not downloaded.
- Registry images are the artwork as filed, not photographs of bottles. One label (I HEARD
  CASSAROLE) is a real photo; glare, angle, low light and blur are otherwise simulated by the
  variants.
- Alcohol content and net contents are not in current registry records, so their application
  values were read from the labels. The ABV and net-contents checks on real labels therefore test
  extraction and matching, not a genuine mismatch; only `var-abv-mismatch` does that.
- Class/type matching of varietal names (SANGIOVESE, CHARDONNAY) against TABLE RED/WHITE WINE, and
  of LAGER against BEER, rests on judgement recorded in each entry, not on regulation text read for
  this file.
- Bold type, type size and contrast are not scored. TTB itself says it did not review type size or
  contrast on these records.
- I HEARD CASSAROLE's warning seems to end without a full stop; the photo is too coarse to be sure,
  so the entry accepts either answer.
- Two Taconic Distillery labels (vodka and gin) share an applicant and layout.
