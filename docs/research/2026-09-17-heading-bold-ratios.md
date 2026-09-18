# Heading boldness over the label corpus

**What was asked.** `WIDTH_HEIGHT_RATIO_BOLD_MIN` in `app/vision/heading_measure.py` decides whether
the GOVERNMENT WARNING heading is bold, and until this measurement it was the one corpus-fitted
number in the product that could reject a label outright. It was set at 0.25 against PIL's default
bitmap font, and its own comment said an empirical re-tune against real labels was still owed. This
is that re-tune.

**How.** `eval/heading_bold_ratios.py`, over the warning-carrying face of every label in
`tests/fixtures/labels/manifest.json`, through the reader's own `look()` so the crop is the frame
production measures. Run on the development box under the six-thread OCR budget with a
two-second pause per image; 38 faces in 103.7 s.

**The ground truth is the approval.** Every label in the corpus carries `registry.status: APPROVED`
and §16.22(a)(2) requires the heading in bold, so the whole population should measure above the cut.
This is a one-sided test: it cannot show the cut is too low, only whether it is too high.

## What was found

The 28 real labels that measured confidently ran **0.1114 to 0.5079**, median
**0.1995** — a 4.6x spread across a population that
is uniformly bold, where the difference between bold and regular type is nearer 1.5x. Two more
labels did not measure at all and go to a reviewer either way.

**At 0.25, 18 of the 28 confidently-measured approved labels came out "not
bold"** and would have been rejected.

No cut repairs this. The distribution is continuous, with no gap to put a threshold in:

| Cut | Called bold |
| --- | --- |
| 0.10 | 28 / 28 |
| 0.15 | 17 / 28 |
| 0.20 | 14 / 28 |
| 0.22 | 12 / 28 |
| 0.25 | 10 / 28 |  <- shipped
| 0.28 | 7 / 28 |
| 0.30 | 6 / 28 |
| 0.35 | 1 / 28 |
| 0.40 | 1 / 28 |

## Why the measurement does not work

The corpus answers this without anyone taking TTB's approvals on trust, because it contains the same
printing photographed two ways:

| Image | Ratio | Note |
| --- | --- | --- |
| `ttb-26232001000404` | 0.1114 | the label as photographed |
| `var-blur` | 0.2613 | *the same image*, Gaussian-blurred at 2.5 px |
| `ttb-26236001000716` | 0.1200 | the label as photographed |
| `var-low-light` | 0.1200 | the same image darkened to 35% — unchanged |
| `var-glare` | 0.5548 | a white hotspot over the warning; highest ratio in the corpus |

Blur moves the same type 2.3x, across the cut. Glare moves it to the top of the corpus. Blur and
glare thicken strokes against a background Otsu then thresholds differently, and the ratio follows
the photograph rather than the typeface.

## What was done

`docs/decisions.md#0037`: a measured weight may send a label to a reviewer and may never reject it.
The words and the capitals are read from the heading's own characters and still reject. The
threshold is kept at 0.25 rather than lowered, because once it chooses only between passing a label
and reviewing one, a low cut buys a quieter queue by passing headings nobody checked.

## Every label measured

Real labels, sorted by ratio:

| Label | Face | Ratio | Verdict at 0.25 |
| --- | --- | --- | --- |
| `ttb-26232001000404` | back | 0.1114 | **not bold** |
| `ttb-26239001000132` | front | 0.1161 | **not bold** |
| `ttb-26236001000448` | back | 0.1170 | **not bold** |
| `ttb-26237001000107` | back | 0.1189 | **not bold** |
| `ttb-26236001000716` | back | 0.1200 | **not bold** |
| `ttb-26218001000369` | back | 0.1318 | **not bold** |
| `ttb-26230001000540` | back | 0.1328 | **not bold** |
| `ttb-26242001000088` | back | 0.1365 | **not bold** |
| `ttb-26239001000217` | back | 0.1420 | **not bold** |
| `ttb-26239001000331` | front | 0.1445 | **not bold** |
| `ttb-26229001000513` | back | 0.1482 | **not bold** |
| `ttb-26212001000085` | front | 0.1591 | **not bold** |
| `ttb-26238001000795` | back | 0.1875 | **not bold** |
| `ttb-26236001000210` | back | 0.1947 | **not bold** |
| `ttb-26233001000189` | back | 0.2043 | **not bold** |
| `ttb-26239001000239` | front | 0.2119 | **not bold** |
| `ttb-26231001000333` | back | 0.2211 | **not bold** |
| `ttb-26229001000034` | back | 0.2214 | **not bold** |
| `ttb-26233001000566` | front | 0.2546 | bold |
| `ttb-26236001000652` | front | 0.2578 | bold |
| `ttb-26230001000420` | back | 0.2795 | bold |
| `ttb-26233001000569` | back | 0.2953 | bold |
| `ttb-26239001000079` | back | 0.3272 | bold |
| `ttb-26240001000573` | front | 0.3298 | bold |
| `ttb-26231001000662` | back | 0.3334 | bold |
| `ttb-26240001000563` | front | 0.3444 | bold |
| `ttb-26237001000196` | back | 0.3480 | bold |
| `ttb-26239001000081` | back | 0.5079 | bold |
| `ttb-26239001000279` | front | not measured | not measured |
| `ttb-26240001000454` | front | not measured | not measured |

Variants, reported apart. `var-heading-title-case` has its heading repainted, so its stroke width is
the repainting's and not an approved label's; it is excluded from the population above.

| Label | Face | Ratio | Verdict at 0.25 |
| --- | --- | --- | --- |
| `var-heading-title-case` | front | 0.1374 | **not bold** |
| `var-warning-wording` | front | 0.1278 | **not bold** |
| `var-abv-mismatch` | back | 0.1189 | **not bold** |
| `var-brand-case-punctuation` | back | 0.3334 | bold |
| `var-glare` | front | 0.5548 | bold |
| `var-skew` | back | 0.1318 | **not bold** |
| `var-low-light` | back | 0.1200 | **not bold** |
| `var-blur` | back | 0.2613 | bold |
