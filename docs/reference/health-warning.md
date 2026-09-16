# Government Health Warning: text and format rules

Source: 27 CFR 16.21 and 16.22, eCFR <https://www.ecfr.gov/current/title-27/section-16.21> and
<https://www.ecfr.gov/current/title-27/section-16.22> (text taken through the eCFR API,
`https://www.ecfr.gov/api/versioner/v1/full/2026-09-11/title-27.xml?part=16`). eCFR shows Title 27
current as of 2026-09-11; 16.22 was last amended by T.D. TTB-91, 76 FR 5477 (Feb. 1, 2011). Read
2026-09-15. Everything in quotation marks or code blocks below is verbatim.

## Where it goes, 16.21

"There shall be stated on the brand label or separate front label, or on a back or side label,
separate and apart from all other information, the following statement:"

## The text the app checks, 16.21

eCFR sets it as two paragraphs, breaking before "(2)":

```text
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects.
(2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
```

Joined with a single space it is 283 characters, all ASCII, with no double spaces (counted
2026-09-15 from the eCFR XML). Where a label breaks its lines is a layout choice; the regulation
fixes the words and their order.

## Format rules, 16.22 (verbatim)

- (a)(1) "All labels shall be so designed that the statement required by § 16.21 is readily legible
  under ordinary conditions, and such statement shall be on a contrasting background."
- (a)(2) "The first two words of the statement required by § 16.21, i.e., “GOVERNMENT WARNING,”
  shall appear in capital letters and in bold type. The remainder of the warning statement may not
  appear in bold type."
- (a)(3) "The letters and/or words of the statement required by § 16.21 shall not be compressed in
  such a manner that the warning statement is not readily legible."
- (a)(4) "The warning statement required by § 16.21 shall appear in a maximum number of characters
  (i.e., letters, numbers, marks) per inch, as follows:"

  | Minimum required type size for warning statement | Maximum number of characters per inch |
  |---|---|
  | 1 millimeter | 40 |
  | 2 millimeters | 25 |
  | 3 millimeters | 12 |

- (b) Size of type. The statement "shall be in script, type, or printing not smaller than":

  | Container | Minimum type size |
  |---|---|
  | 237 milliliters (8 fl. oz.) or less | 1 millimeter |
  | More than 237 milliliters (8 fl. oz.) up to 3 liters (101 fl. oz.) | 2 millimeters |
  | More than 3 liters (101 fl. oz.) | 3 millimeters |

- (c) "Labels bearing the statement required by § 16.21 which are not an integral part of the
  container shall be affixed to containers of alcoholic beverages in such manner that they cannot
  be removed without thorough application of water or other solvents."

## TTB guidance (not regulation)

- Distilled spirits page, <https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-health-warning>
  (last updated November 19, 2025): the warning "must appear as a continuous paragraph".
- Malt beverage page, <https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling/malt-beverage-health-warning>
  (last updated November 19, 2025): "It must appear as a continuous statement". Other information
  such as "contains sulfites" "may appear on the same line as the last sentence of the health
  warning statement as long as the information appears separate and apart".
- Neither page allows any variation in wording or punctuation.
- Form TTB F 5100.31 instructions, <https://ttb.gov/media/70320/download?inline=>: TTB "does not
  routinely review submitted labels for compliance with applicable requirements for mandatory label
  information regarding type size, characters per inch, or contrasting background."

## What an image check can and cannot see

From a photo alone the app can check the words, their order, that they run as one continuous
statement, the capitals of "GOVERNMENT WARNING" and, less reliably, its bold weight. Text after the
last sentence on the same line is allowed and is not part of the warning. Type height in
millimeters and characters per inch need the image's physical scale, which a photo does not carry;
those rules need the container size and a known scale, or a human. TTB itself does not routinely
review them.
