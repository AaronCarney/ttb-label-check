# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), except that a release heading carries no
date: the release's git tag records when it was cut. Versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `uv run python -m eval.corpus_check` runs every real corpus label through the production evaluator,
  rule pack and disposition, with only the OCR replaced by frozen readings, and prints what the
  product reports: match, mismatch or needs review per label and per check, the reason code behind
  each mismatch and review, and how many checks it settled without a person. Today all 30 approved
  labels come out 0 match, 9 mismatch, 21 needs review. Of the 11 mismatches, 2 are genuine: those
  labels' warnings differ from 27 CFR 16.21 by a word. `tests/test_corpus_outcomes.py` pins every
  outcome and lists each of the other 9 with its cause.

- `uv run python -m eval.corpus_check --registry` runs the fetched Public COLA Registry records through
  the same production path, from each record's front and back images, and `--freeze` first runs the
  OCR on every image with no frozen reading. On 98 bourbon records nothing was tuned on: 0 match, 63
  mismatch, 35 needs review; 74.1% of checks settled without a person. Of the 88 mismatched checks, 3
  are warnings that genuinely differ from 27 CFR 16.21, 8 are warnings printed only on an image the
  upload does not take, and 77 are the product reading the label wrong, including a new cause: a
  mash-bill grain percentage read as the alcohol content (`docs/decisions.md#0051`).

- `uv run python -m eval.fetch_registry_corpus` fetches an application's record and every label image
  from the Public COLA Registry, for a list of TTB IDs, into `eval/data/` (not committed). The registry
  now answers plain HTTP with a bot-defence challenge, so it drives a real browser and fetches each
  image from inside the record's page, one record at a time with a pause between them. A stopped run
  resumes where it stopped.

- The regulation a finding rests on is in the product, beside the finding. Pressing a citation fills
  a column with the wording of the section it names — reserved, so it fills in place rather than
  covering what a reviewer is comparing it against, and reached from a chip that is a button, so
  keyboard and pointer reach it alike and nothing appears on hover. The product holds all 24
  sections its 43 citations name, across 27 CFR and 19 CFR. `docs/decisions.md#0034` had refused
  this because filling the panel meant typing regulation text into a compliance tool with no test
  that could check it against the regulation; the wording is now fetched from the eCFR's own API by
  `uv run python -m tools.fetch_cfr` and committed with the issue date, the retrieval date and a
  hash, and `TTB_CHECK_ECFR=1 uv run pytest tests/test_cfr_corpus_matches_ecfr.py` re-fetches every
  section and compares it character for character. Nothing is fetched while the service runs. A
  citation the parser cannot read whole shows as not held rather than as a guess at a section, which
  is the other half of what 0034 refused. See `docs/decisions.md#0046`.

- A batch of labels is now checked against the applications filed for them. The engine always did
  this, but the only bulk path a reviewer could reach carried images and nothing else, so every
  comparison rule reported that it had nothing to compare and the page showed a column of **Not
  checked** beside **Expected (empty)** — the half of the job the brief is about. The applications
  travel as one CSV, a row per label, carrying the same ten fields the single-label form asks for
  and joined to the images by filename. The form takes that file in a field of its own or among the
  images, because a reviewer who unzips the sample pack and selects everything sends it through the
  image picker. A row's own beverage type beats the form's select, so a pack of wines, beers and
  spirits is one batch; a label the CSV has no row for is still read and still checked for what
  every label must carry; and two rows for one label are refused rather than resolved, because at
  300 labels the failure a reviewer cannot see from the page is not "no application" but "the wrong
  one". See `docs/decisions.md#0043`.
- The downloadable sample pack carries both halves. `/batches/sample.zip` now ships
  `applications.csv` beside the images — the application really filed for each label, taken from the
  registry record — so the pack a reviewer downloads exercises the comparison instead of
  demonstrating its absence.
- The deployed service no longer makes its first visitor wait. Cloud Run scales to zero, so an idle
  instance was reclaimed and whoever arrived next paid a container start plus an OCR model load —
  36.48 seconds to first byte, measured, against 0.14 seconds warm. A cron trigger on the edge
  Worker now calls `/api/health` every five minutes with the invoker token, keeping the loaded
  instance alive. See `docs/decisions.md#0042`.
- Every check writes one log line when it finishes: the outcome, the reason code behind it and how
  long it took, under the evaluation's id. A check that succeeded used to log nothing. Nothing from
  the application or the label is on the line.

### Changed

- An import on which no country-of-origin statement was read goes to a reviewer under
  `ORIGIN.PRESENCE.NOT_READ`, which says the reader may have missed it or the label may state the
  country in a form 19 CFR 134.45 accepts and the check does not read. It used to fail, and reached
  review only because the confidence floor caught the failure, under a code that named no element.
  The origin check never reports a mismatch; `ORIGIN.PRESENCE.MISSING` stays as a code a reviewer
  can apply. On the corpus three findings change code and no outcome moves
  (`docs/decisions.md#0059`).

- The bold check measures the heading's strokes against the warning's own body, which 27 CFR
  16.22(a)(2) requires to be regular, instead of against a fixed cut that followed the photograph
  rather than the type. A heading at least 1.125 times as heavy as its body passes. One measured and
  not clearly heavier goes to a reviewer under a new code, `WARNING.STYLE.BOLD_NOT_CLEAR`, and
  `WARNING.STYLE.BOLD_NOT_MEASURED` now means only that the weight could not be measured: the type
  too small, the photo too blurred, or too little of the warning read. A measured weight still never
  rejects a label. Checks settled without a person rise from 77.6% to 80.4% on the corpus and from
  72.4% to 75.2% on the held-out registry labels, where 6 labels now match; no check moves toward a
  mismatch (`docs/decisions.md#0058`).

- The brand check now searches every line read on every face for the application's brand and the
  trade names it marks as used on the label, instead of comparing only the text set in the largest
  type. A name found is a match, and the result card shows the line it was found on, with its box
  and face. A name found nowhere goes to a reviewer under `BRAND.IDENTIFY.UNCERTAIN`, and the check
  never reports a brand mismatch; `BRAND.NAME.MISMATCH` stays as a code a reviewer can apply. On the
  corpus, labels move from 9 mismatch and 21 needs review to 7 and 23. On the 98 held-out registry
  labels the 41 brand mismatches become 33 matches and 8 reviews, and labels move from 0 match, 63
  mismatch and 35 needs review to 5, 39 and 54 (`docs/decisions.md#0052`).

- The reader's replay suite now covers every real label in the corpus, 58 of its 62 images, and
  merges a label's faces with the product's own merge instead of a front-first merge of its own.
  With the product's merge it shows what the old merge hid: on three labels the net contents come
  from a barrel size or the Serving Facts panel, not the bottle's size on the front. Four frozen
  readings had drifted from what today's reader returns on the same image; all 56 are re-frozen
  from the current reader, and every check the reader misses is listed with its cause.

- One system, and a check of one label is a batch of one. The product had two ways in — a page for a
  single label and a page for a folder of them — which meant two upload forms, two result layouts
  and two paths through the engine for the same job, and a reviewer had to decide which one their
  submission was before they could start. `GET /` is now the only form, `POST /` always starts a
  batch and answers 303 to `/batch/{id}`, and the results page opens the first result the moment it
  lands, so a reviewer checking one label waits no longer than before and a reviewer checking three
  hundred reads the first while the rest run. `GET /batches`, the bulk page's URL, redirects there
  permanently rather than 404ing, because it is the address the deployed service has been handing
  out. Two costs come with it, both accepted: the service checks one batch at a time
  (`docs/decisions.md#0041`), so a reviewer submitting one label while a 300-label batch runs is now
  refused and told to wait, where before the single-label path was never refused; and a reviewer
  holding two unsuffixed photographs of one label must tick **These images are all faces of one
  label**, because filename pairing cannot read two phone photographs. See
  `docs/decisions.md#0045`.

- Every check's result is kept for seven days, not only a single label's. The result is what an
  override amends, and it used to be written only when a check ran outside a batch — so with every
  check now a batch, it is written for every label. It is stripped before it is written exactly as
  before: every value read off the artwork and every value the application declared is blanked.

- The landing page no longer offers four curated labels as buttons, each with a sentence describing
  what checking it would show. A tour of the product is not the product, and one of those sentences
  asserted an outcome the engine explicitly refuses to assert: it said of a beer that *"Neither
  photograph of this beer shows a bottler's name and address, and the check says so"*, where the
  check says *"The reader did not find a name and address on this label, so this check was not made.
  That is not a finding that the label lacks it: compare the label against the application
  yourself."* The demonstration is the sample pack now, dropped
  into the same form a reviewer's own labels go through. What those sentences explained is in
  `README.md` and `docs/approach.md`. `POST /samples/{sample_id}`, which checks one shipped label
  against its filed application, is unchanged.
- The app checks the wording of a label's alcohol statement. A statement in one of the forms its
  beverage class's section gives — §4.36(b) for wine, §5.65(b) for spirits, §7.65(b) for malt
  beverages, with the abbreviations and parentheses those sections allow — passes, and any other
  statement goes to a reviewer at warn severity, so the check never rejects a label. Of the 30
  approved labels in the fixture corpus, 27 statements pass and 3 go to a reviewer. See
  `docs/decisions.md#0011`.

### Fixed

- The bold check measures the heading's letters on a label that prints its warning light on a dark
  panel. It used to measure the ground around the letters, which is wide, so those headings passed
  as bold whatever their type. 53 of 220 heading crops are printed this way. The checks that passed
  for that reason now go to a reviewer. `uv run python -m eval.remeasure_headings` renews the heading
  measurement in every frozen reading from its image. See `docs/decisions.md#0057`.

- Every mismatch and every needs review now carries a reason code, and the code agrees with the
  outcome: a code for a label defect arrives only with a mismatch, and a code for a question the
  product could not settle only with a needs review. `uv run python -m eval.corpus_check` reports any
  check that breaks this, and the corpus test holds it at zero. See `docs/decisions.md#0056`.

- A government warning the reader misread is no longer reported as a wrong warning. Where the
  statement's words are read but its "GOVERNMENT WARNING" heading is not, the three warning checks
  go to a reviewer under `WARNING.HEADING.NOT_READ` instead of reporting the warning missing. A thin
  glyph added or dropped inside a word ("HEAILTH"), text after the statement's last words, and a
  lookalike beside a swapped mark ("(I]" for "(1)") go to a reviewer with each spot named, never to
  a match. The warning block ends at "health problems" even when those words are misread, and a
  heading read as "GOVERNMENTWARNING" counts as the heading's two words. On the 30 corpus labels,
  labels with a mismatch go from 4 to 3; on the 98 held-out labels, mismatched checks go from 33 to
  28, and no check on either set moved toward a mismatch. See `docs/decisions.md#0055`.

- The audit trail keeps every rule's reason code. Where two rules reported the same code, the
  record kept it for the last rule only, and the others read as sent to a reviewer for no stated
  reason. 76 checks across both label sets had lost their code this way. The reviewer's field cards
  were not affected.

- A government warning printed sideways in small type is read again on its side instead of being
  reported missing. The check that decides whether to read a label again on its side counted a strip
  read as noise as proof the strip was not the warning; a strip read that poorly now counts as unread.
  And where the first rotation reads only the warning's heading, the other rotation is read too and
  the more complete warning is kept. The corpus does not move; on the 98 held-out labels seven faces
  now read their warning, and mismatched checks fall from 38 to 33. See `docs/decisions.md#0054`.

- The alcohol content and net contents are no longer read from a volume or percentage that is about
  something else. A percentage followed by an ingredient ("75% CORN", "at least 30% wheat") or set as
  a labelled row ("WHEAT: 30%") is not read as the alcohol content, and when two faces are joined a
  statement printed with the alcohol words is kept over a bare percentage, however cleanly the bare
  one was read. A volume in a Serving Facts panel, one a sentence mentions ("IN 53 GALLON CHARRED",
  "under 15 gallons"), or the size of a barrel or cask is not read as the net contents. A table row
  "PROOF: 96" is no longer read as the figure before it. On the 30 corpus labels the three wrong
  net-contents mismatches are gone (7 labels with a mismatch become 4); on the 98 held-out labels
  mismatched checks fall from 47 to 38 and no check moved toward a mismatch. See
  `docs/decisions.md#0053`.

- A spirits label's stated proof is checked against its own ABV. The brief requires a proof to be
  twice the alcohol by volume, and nothing checked it: the local reader dropped the proof, no rule
  named it, and joining a label's faces kept one alcohol reading, so a proof on the other face was
  lost too. Both readers now find every proof figure on the label with one deterministic finder, and
  the figures from all faces are kept. Only a proof on the ABV statement's line or the next can
  reject; a figure elsewhere, one that looks rounded ("86" beside 42.8%), one above 200, or a proof
  with no ABV read goes to a reviewer. A range in a class name ("80-89 PROOF") and a strength at
  distillation or barrel entry are not read as the bottle's proof. See `docs/decisions.md#0050`.

- A brand that differs from the application only in punctuation or spacing is a match whatever its
  length, and the finding says what differs. It was scored, so the answer depended on how long the
  name was: "Stones Throw" against "Stone's Throw" passed, and "Os" against "O's" was rejected as a
  different brand. A mark that stands for a word or a thing ("&", "#", "@", "%"), and a mark between
  two digits, stay part of the name. See `docs/decisions.md#0017`.

- A check no longer loses its results to a second instance. The service took one request at a
  time on up to two instances, and a check's results stream held its instance for as long as the
  check ran, so the next request — the keep-warm ping, the page's own fetches, the next check —
  started a second instance, which answered the results stream with 404 because the batch was held
  by the first. The reviewer was shown nothing. The service now runs one instance taking up to
  sixteen requests at a time; reads stay one at a time behind the reader's lock. The upload size
  check no longer switches Pillow's process-wide decompression-bomb guard off while it reads a
  header, which was safe only at one request at a time. See `docs/decisions.md#0048`.

- The deploy latency test measures the page as it now is. It still posted the old single-label
  form and read the result out of the response page, so after one page replaced the single-label
  and batch forms three of its five checks failed against a working service. It now posts a label's
  faces as one label and times the check to the result arriving on the batch's stream. Its summary
  no longer counts a submission the service refused as a check inside the budget. The published
  figure is re-measured on it: 23 of 37 and 33 of 37 checks inside five seconds across two runs,
  medians 4.19 and 3.73 seconds, against a requirement of 95 percent.

- A reviewer can send the back of the label. `POST /` had accepted a second image since the
  multi-face work, but the page offered one file input, so no reviewer could send one — and the
  government warning is printed on the back of 20 of the 30 corpus labels, so the product's one
  entry point reported a warning missing that the label carries. The form takes the faces of a label
  together and says why the back matters. The five-second measurement sends what the page
  sends, and the number it returns is published: 18 of 37 checks and 21 of 37 inside five seconds
  across two runs on the deployed service, against a requirement of 95 percent, where a front-only
  run of the same set made 35 of 37. See `docs/decisions.md#0044`.

- A result card says what the rule matched. A card read `Found: {'brand_name': 'Rossastro'}` against
  `Expected: FABIO SIGNORELLI` under a **Pass** pill: the found value was a Python dict, and the
  expected value named only the application's brand field while the rule had matched the fanciful
  name the same application declares. The card now shows the words the label prints, and a check
  that passed on something other than the application's literal value says so — the designation
  found inside a longer one, the figure behind two differently worded quantities, the name located
  in the applicant block. The card also shows the rule that set its pill rather than whichever rule
  ran first, so a "Needs review" card no longer carries a silent **Pass** verdict from an unrelated
  check.
- The government warning check no longer reports a mismatch when the only differences are ones the
  reader is known to misread on a correct label: an accent on a letter, `(I)` for `(1)`, `O` for `D`,
  or one punctuation mark. It reports needs review and names each difference. A warning that shows
  "surgeon general" with a lower-case S or G is no longer a match. See `docs/decisions.md#0040`.
- The reader reads the alcohol content from the percentage printed with the alcohol words, and a
  figure starts at the start of a number. On a spirits label that prints "100% GRAIN NEUTRAL SPIRITS"
  above "40% ALC/VOL" it read 0, and on a wine label that lists its grape blend above the statement
  it read the first grape's share. Both now read the statement. The reader also returns a statement
  that puts the words first, "ALC. BY VOL. 5%", whole. The README's `abv` figure is 27 of 30, up
  from 25.
- Memory no longer grows with every batch. The service checks one batch at a time: while one is
  being checked, a second upload, from the page or from `POST /batches`, is refused with a 409 that
  says how far the running batch has got. Starting a batch drops the finished one, each label's image
  is let go once it is checked, and the request-size guard no longer holds a second copy of the
  upload. See `docs/decisions.md#0041`.
- A batch's anomaly advisory, which warns when many labels in a row fail for the same reason, now
  counts a check that ran out of time as a timeout. It used to count it under the rule-pack
  selection, the first line of the label's trail.
- `eval.read_accuracy --sleep` pauses after each image the reader reads, so a label with several
  faces gets a pause between every face, and the seconds it reports per label leave the pause out.

## [0.3.1]

### Fixed

- The reader no longer turns upright lines of the government warning upside down. Its line
  orientation check flipped a line whenever it was 90% sure the line was inverted, and on real labels
  it was wrong often enough that a correctly printed warning read as noise and was rejected. It now
  flips a line only when it is 99.9% sure. The sideways cognac's warning goes from 227 characters
  wrong to exactly what the label prints. Measured over the 38 shipped labels, rejections for the warning's wording fell from
  18 to 15, and no label is newly rejected on anything. Three labels gain a point for a reviewer,
  where the reader now reads a line it used to garble and picks the wrong one for class and type or
  for name and address. See `docs/decisions.md#0039`.

- A government warning is no longer rejected because the reader lost the space between two words.
  The comparison ignored spacing by collapsing runs of spaces, which cannot restore a space that is
  missing, so a reading of `IMPAIRSYOUR` rejected a label that prints `IMPAIRS YOUR`. Spaces are now
  removed from the comparison entirely. Every letter, digit and punctuation mark still has to match
  in order, and the shipped label that prints "the RISKS of birth defects" is still rejected.

- `uv run python -m eval.read_accuracy`, the command the README's reading accuracy figures come
  from, crashed on its first label. It still built a label as one image after a label came to carry
  its faces, and no test ran that step. It now builds a one-face label, and
  `tests/test_read_accuracy_reads.py` holds it.

### Changed

- The README's reading accuracy figures are re-measured after the fixes above. The warning now
  reads word for word on 20 of the 30 labels, up from 14; brand is 17, up from 16, and net
  contents 23 of 29, up from 22. Every other check is unchanged.

## [0.3.0]

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
  measured while the service was deployed open. Measured since, it answers 403:
  `roles/run.invoker` is granted to the Worker's service account and to nobody else, which is the
  design decision 0028 argues for, and `ttb.aaroncarney.me` still answers 200. Both places now say
  so, and both say it is a measurement rather than a fixed property, because the deploy script sets
  it either way.

## [0.2.0]

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

## [0.1.1]

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
