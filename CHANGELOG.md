# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-09-17

### Added

- A label is now checked as a whole label rather than as one photograph of it. A COLA is filed with
  every face of a label, and a label's mandatory elements are spread across its panels — the
  government warning is most often printed on the back. Every face supplied is read, the readings are
  merged into one verdict, and each finding keeps the face it was read from. On a real approved
  bourbon this is the difference between a government warning nobody looked for and one that is found
  and passes all three of its checks.

- A browser batch upload can now say that two files are two faces of one label, by naming them
  `anything-front.jpg` and `anything-back.jpg`. The two are checked together as one label instead of
  as two labels that each fail what the other carries. Any other filename is one label on its own, so
  nothing changes for a reviewer who names their files differently, and the batch upload page states
  the convention. The downloadable sample set now ships both faces of every sample label that has
  two, named the way the upload reads them back.

- Every result now shows how long the check took, on both the single-label page and the batch
  detail panel. The number has been on the envelope since `metrics` was added and was reachable
  only through the raw-JSON drawer, which is off unless `DEV_MODE` is set. Two cases get their own
  wording rather than a bare number: an answer served from the result cache says so, because those
  milliseconds are what returning the stored answer cost and not what checking the label cost; and
  a check the runaway guard stopped says it was stopped, because its time is how far it got.

- Opening a label in a batch shows its check results — every field, what was read from the label
  beside the application value, and the rule verdict with its reason code — in the same cards the
  single-label page uses. A label the app could not check says so and names the code recorded
  against it, rather than showing an empty panel. See `docs/PRD.md` FR-12.

### Changed

- The four sample labels on the landing page are described by what checking them actually does, and
  two of the four are different labels. Every description was false: the one offered as "a bourbon
  where everything matches" comes back with five points for a reviewer, and the one offered to show
  that a brand typed without its apostrophe still matches is the same two photographs as the bourbon
  and returns the same findings. No label in the set passes outright, so none is offered as one. The
  four now offered are a wine with a single review point, an imported wine whose country-of-origin
  check passes, a beer that prints no bottler name and address and is flagged for it, and a warning
  reworded to be rejected.

- A GOVERNMENT WARNING heading whose boldness the app measured is no longer rejected for it. The
  heading's boldness is a stroke-width measurement on a photograph, and a sweep of all 38 corpus
  labels found the number moves with the photograph rather than with the type: the labels are all
  TTB-approved and so all required to be bold, yet they measured from 0.111 to 0.508, and one label
  measured 0.111 from a clean photograph and 0.261 from a blurred copy of the same printing. At the
  shipped cut, 18 of the 28 labels the app measured confidently were being called "not bold" — every
  one of them a rejection of a label TTB had approved. Those labels now go to a reviewer on that
  point instead. The heading's words and its capitals are read from the heading's own characters and
  still reject. See `docs/decisions.md#0037` and
  `docs/research/2026-09-17-heading-bold-ratios.md`.

- The accessibility conformance level the product commits to is WCAG 2.0 Level A and AA — the level
  Section 508 requires, and the level the automated scan has always checked. It was previously stated
  as WCAG 2.2 AA, which no test here could hold: of the two criteria that level was chosen for, one
  (2.4.11 Focus Not Obscured) has no automated rule in axe-core at all. The later criteria the UI is
  built to, including reflow at 320 pixels, are kept and tested without being claimed as a level. See
  `docs/decisions.md#0031`.

### Removed

- The CFR citation on a field card is text rather than a button. It was a button that did nothing:
  the handler behind it was never supplied on either surface, and the panel it was meant to open
  would have had to show the wording of the section, which this product holds for one of the 43
  citations its rules carry. The region overlay that would have drawn each reading's box on the
  label image is removed for the same reason — the boxes are in the reader's downscaled, sometimes
  rotated pixel space, and the only image the page can show is the original upload. See
  `docs/decisions.md#0034`.

### Fixed

- A government warning printed beside something else is no longer rejected for what its neighbour
  says. The reader assembled the statement from every line at the heading's height — a band across
  the whole label — so a keg's tapping instructions, a state deposit line, an importer's web address
  and a Mexican producer number were each read into the warning, and the word-for-word comparison
  then rejected a statement the label prints correctly. The warning is now read as the column of
  text under its own heading. Measured over the 38 shipped labels, rejections for a warning that is
  in fact correct fell by six, and fields the band used to swallow — net contents, class and type —
  are readable again on three more. A label that really prints the wrong words still fails: one in
  the set prints "the RISKS of birth defects" where the regulation fixes "the risk". See
  `docs/decisions.md#0038` for the one reading this traded away.

- A label whose reading reported no heading weight at all was rejected as though the app had
  measured the heading and found it not bold. Both readers drop the weight from the reading when
  they cannot measure it, and the rule read that silence as a measurement of "not bold" against a
  rule that rejects. It now goes to a reviewer, which is what the rule was always documented to do.

- A hand-built fixture carrying an empty style report (`heading_styles: null`) crashed the whole
  rule run with an `AttributeError` rather than being judged on the heading text it did carry.

- A browser batch upload containing a file that is not a PNG or JPEG now names that file, says what
  to do with it, and checks every other file in the set. It previously refused the whole submission
  and checked none of them. See `docs/decisions.md#0030`.
- A check that runs long now shows what it finished instead of an empty page. The guard that stops a
  runaway evaluation used to sit at exactly the five seconds the latency requirement measures, and
  firing it threw away work already done — including a label the reader had finished reading — so the
  same label could answer completely or blankly on a difference of fifty milliseconds. A stopped
  check now returns the readings and rule results it completed, says in the audit trail why the rest
  is missing, and reports the time it actually spent. The guard is 30 seconds and is a runaway guard,
  not a latency target. See `docs/decisions.md#0035`.
- A label whose class or type is followed by punctuation is no longer reported as not carrying that
  class. The check that looks for a standard of identity inside a longer designation split the text
  on spaces alone, so `STRAIGHT BOURBON WHISKEY, 40% ALC/VOL` yielded `whiskey,` and
  `BLENDED WHISKEY.` yielded `whiskey.`, neither of which equals `whiskey`. A word now ends at
  punctuation as well as at a space. The effect a reviewer saw was a spurious note on a label that
  plainly states its class; the rule is `spirits.class_type.matches_soi` at warn severity, so no
  label was refused over it. The whole-word guarantee is unchanged and now has tests: `Gin` still
  does not match inside `VIRGINIA`, and a multi-word standard of identity must still appear in its
  own order.

### Performance

- A label is read again sideways only where its sideways text reads as the government warning. The
  reader used to decide that from the shape of the text it found, which fires on a barcode or a
  net-contents line printed up an edge as readily as on a warning: over the project's 62 corpus
  images, four were read twice more at 90 and 270 degrees and one of those four carried a warning.
  The strips are now read where they lie first, which costs about 10 ms against about 440 ms for
  reading the whole label again. The slowest corpus read fell from 1345 ms to 463 ms on a
  development machine, and the label whose warning the re-read recovers still reads it. See
  `docs/decisions.md#0036`.

### Documentation

- The limitations list now names the one endpoint that cannot check anything. A batch submitted as
  JSON to `POST /batches` carries references to labels rather than the images themselves, there is
  no store to resolve a reference in, and so every item of such a batch comes back refused. The
  behaviour was decided and recorded; what was missing was the entry telling a reader before they
  rely on it. The batch path that works is `POST /batches/upload`.

- Three statements that the code had overtaken are corrected. `docs/approach.md` said the pipeline
  does not gate the deploy — `scripts/deploy.sh` reads GitLab for the pipeline belonging to the
  exact commit it would ship and refuses anything short of `success`. Decision 0031 said the
  accessibility scan misses `/batches` — a third case now scans it, and the record says so inline
  rather than being rewritten. The registry description of `ENGINE.WORKER.UNHANDLED` named only the
  SSE stream-end path, and a per-label failure has carried the code on that item's own envelope
  since the refusal work.

- What reaches the Cloud Run URL directly is restated from a fresh measurement. The README and the
  edge Worker's own comment both said the origin answers an uncredentialed request with 200,
  measured while the service was deployed open. Measured 2026-09-17 at 22:30 UTC it answers 403:
  `roles/run.invoker` is granted to the Worker's service account and to nobody else, which is the
  design decision 0028 argues for, and `ttb.aaroncarney.me` still answers 200. Both places now say
  so, and both say it is a measurement rather than a fixed property, because the deploy script sets
  it either way.

## [0.2.0] - 2026-09-16

### Added

- A label is read on this machine, with no outbound call, and that reader is the default. A second
  reader using a vision model sits behind the same interface. See `docs/decisions.md#0005`.
- Every declared element of an application — brand name, class and type, alcohol content, net
  contents, name and address, country of origin, and the health warning — is compared against what
  the label says, and each comparison states what counts as the same value.
- A reviewer can enter an application's details on the page and check a label against them.
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
