# ttb-label-check

## What it is

## Getting started

## Status

Planning. Nothing is built yet.

## Limitations

Checks this app does not make, and why. Each entry names the decision record that settled it, and a
check listed here is switched off in the rule pack rather than reporting a verdict it has not earned.

- **The wording of an alcohol-content statement is not checked.** The app checks that a label states
  its alcohol content where the regulations require one, and that the figure on the label is the
  figure the application declared. It does not check that the statement is phrased as 27 CFR
  §4.36(b)(1), §5.65(b) and §7.65(b) require, because the reader returns the percentage it found and
  not the words the label printed. See `docs/decisions/0011`.

- **A country of origin is read only as the application's English name.** Customs marking rules also
  accept the country's name in the language of the country, an abbreviation that unmistakably
  indicates it, and the adjectival form — "HECHO EN MEXICO", "U.K.", "Irish" (19 CFR §134.45(b),
  (c)). The app does not read those, so an import that writes its origin one of those ways is sent
  to a reviewer rather than being matched or rejected. See `docs/decisions/0016`.

- **The health warning's typography and placement are not checked.** The app checks the warning's
  words, that "GOVERNMENT WARNING" is present, and that those two words are in capitals. It does not
  check that the warning sits on a contrasting background (27 CFR §16.22(a)(1)), its characters per
  inch (§16.22(a)(4)), its type height (§16.22(b)), or that it stands separate and apart from other
  information (§16.21). The first three need the colour of the ink or the physical scale of the
  label, and a photograph carries neither; the fourth is visible in a photograph but no reader
  measures it yet. Each of those four rules stays in the pack and reports that the measurement was
  not taken, so a label is never passed or rejected on one. TTB says it does not routinely review
  labels for type size, characters per inch or contrasting background either. See
  `docs/decisions/0006` and `docs/decisions/0013`.

- **Bold type in the warning's heading is reported, not decided.** §16.22(a)(2) requires the heading
  in bold as well as in capitals. Bold weight is a stroke-width measurement on the heading's own
  region of the image, and the reader cannot always take it. Where it could not, the label goes to a
  reviewer on that point rather than being rejected for a boldness nobody measured. The capitals are
  read from the heading's text and are still decided. See `docs/decisions/0013`.
