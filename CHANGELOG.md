# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Opening a label in a batch shows its check results — every field, what was read from the label
  beside the application value, and the rule verdict with its reason code — in the same cards the
  single-label page uses. A label the app could not check says so and names the code recorded
  against it, rather than showing an empty panel. See `docs/PRD.md` FR-12.

### Fixed

- A browser batch upload containing a file that is not a PNG or JPEG now names that file, says what
  to do with it, and checks every other file in the set. It previously refused the whole submission
  and checked none of them. See `docs/decisions.md#0030`.

## [0.2.0] - 2026-09-16

### Added

- A label is read on this machine, with no outbound call, and that reader is the default. A second
  reader using a vision model sits behind the same interface. See `docs/decisions.md#0005`.
- Every declared element of an application — brand name, class and type, alcohol content, net
  contents, name and address, country of origin, and the health warning — is compared against what
  the label says, and each comparison states what counts as the same value.
- A grader can enter an application's details on the page and check a label against them.
- The README publishes what the on-machine reader actually reads, measured over all 30 real labels
  and their 56 face images: each of the nine checks separately, as a count of correct out of the
  labels that check is scoreable on. They are counts rather than percentages, because thirty labels
  is too small a denominator to state as one and because the denominator differs between checks.
  See `docs/decisions.md#0027`.

### Fixed

- A label stating its net contents in fluid ounces or pints is no longer rejected against an
  application recording millilitres. The customary figure a label prints is a rounded one — 375 mL
  is 12.68 fluid ounces, printed as 12.7 — so converting it back could never land on the
  application's number exactly, and four compliant labels were reported as failing. The check now
  asks what the label would print if it stated the application's figure in the label's own unit and
  to the label's own precision. Two numbers in the same unit are still compared exactly.
- The unit table now lists the spelled-out forms `fl ounce` and `fl ounces`, so a label reading
  `11.2 FL. OUNCES` converts instead of going to a reviewer as unreadable.
- A brand is compared against every name the application says the label may carry — the declared
  brand, the fanciful name, and each trade name the applicant marks "(Used on label)" — instead of
  against the brand-name field alone, and the finding names which of them matched. Three approved
  labels in the test corpus were being rejected for carrying a name their own application states in
  writing. The comparison also folds accents, as every other check already did, and a brand whose
  first letter disagrees goes to a reviewer instead of being rejected outright, because a stylised
  first letter is the most likely reading error. See `docs/decisions.md#0015`.
- A sharp, readable label photograph is no longer turned away as glare. The check counted bright
  pixels, which measures how light the label stock is rather than whether a hotspot destroyed any
  text, and it refused seven faces of five readable labels while passing the one fixture built with
  glare over its warning. Legibility is now judged by what the reader returned: an image no text is
  found on, at any rotation tried, is reported as unreadable. `GLARE` remains a term a reviewer can
  use, because a reviewer can see what the product cannot measure. See `docs/decisions.md#0026`.
- A brand printed over several lines — "Hop" over "Butcher" over "FOR THE WORLD" — is read as the
  one name it is, instead of as whichever line was largest. Type size is now measured across a line
  of text rather than along it, so a health warning set sideways up the edge of a label is no longer
  taken for the biggest type on it and handed back as the brand.
- A drink's ingredients are no longer reported as its country of origin. `DISTILLED FROM CORN` was
  read as a country named `corn`, because the word "from" was treated as introducing a place after
  any verb. It introduces a place only after "product" or "imported"; after a verb describing what
  was done to the drink, it introduces the material. A wrong country beside a field costs a reviewer
  more than an empty one, which sends them to look at the label.

### Changed

- The reader's accuracy is scored against what each label prints, transcribed from the label itself,
  rather than against the application the label was filed under. The two records routinely differ
  without either being a misreading, so the old comparison counted a correct reading as wrong.
- A label filed without a declared beverage is checked against nothing rather than against the
  spirits rules, and every reply now names the rule set that ran. See `docs/decisions.md#0010`.
- A country of origin the app cannot read goes to a reviewer instead of being rejected. The check
  reads the English name the application declares; the other forms customs marking rules accept — the
  country's own language, an abbreviation, the adjectival form — are not read, and a label using one
  of those was previously reported as failing. See `docs/decisions.md#0016`.
- The alcohol-content wording check no longer runs, with its reason recorded in the rule pack. The
  figure on the label is still compared with the figure the application declares; what is not checked
  is whether the statement is phrased the way the regulations require, because the reader returns the
  percentage it found and not the words the label printed. See `docs/decisions.md#0011`.
- The app loads the OCR models once for the process instead of once for every label, so a label no
  longer waits about a second for them, and the readiness check at `/healthz` warms the reader that
  serves submissions rather than one it discards.
- The bird's-eye view and the codemap in `ARCHITECTURE.md`, and the build, test and run commands in
  `CLAUDE.md`, describe the application as it now stands.

### Removed

- The optional layer that asked a language model for a second opinion on a finished rule result is
  gone, along with the two language-model SDK dependencies it needed and the development-only route
  that showed its raw calls. It was switched off by default and could not change a verdict: its
  output was discarded before it reached a rule result, and the channel that would have shown it to
  a reviewer was sealed. The reader that uses a vision model to turn a label photograph into fields
  is unaffected. See `docs/decisions.md#0009`.
- Installed dependencies and compiled Python are no longer tracked: `frontend/node_modules` and
  `__pycache__` are build output and are rebuilt from `uv.lock` and `pnpm-lock.yaml`.
- The telemetry block sent with each result no longer carries `orchestrator_duration_ms`. It timed a
  coordination step the app no longer performs, so it was always reported as zero, and nothing in
  the interface read it. The other three timings — total, per-rule and reading — are unchanged.

## [0.1.1] - 2026-09-15

### Fixed

- The rule engine reports a compliant label as compliant. Five defects together made that
  impossible, and each made a correct label fail: the engine looked up the application's declared
  value under the reader's field name only, so alcohol content, the government warning, the name and
  address and the country of origin were compared against nothing; the word-for-word warning check
  and the class-and-type check hashed and compared the reader's payload rather than the reading
  inside it; the warning heading was compared literally against a phrase written without the colon a
  compliant label carries; and the class-and-type check required the label's designation to equal a
  standard of identity rather than include one.
- The government-warning presence check now judges the warning, not the payload carrying it. A label
  with an empty warning used to pass it.

### Changed

- The health warning's four typography rules — contrasting background, characters per inch, type
  size and separate-and-apart — no longer run, each with its reason recorded in the rule pack. See
  `docs/decisions.md#0006`. `common.warning.heading_phrase` no longer runs as a duplicate of
  `common.warning.heading_caps_bold`.
- A class-and-type designation passes when it includes a recognised standard of identity as whole
  words, and both permitted spellings of "whisky" are accepted. See `docs/decisions.md#0007`.
