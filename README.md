# TTB Label Check

Checks a photograph of an alcohol beverage label against the application filed for it, element by
element, and tells the reviewing agent which fields match, which do not, and which need a person to
look. The decision to approve or reject stays with the agent.

**The approach, the tools and the assumptions are in [docs/approach.md](docs/approach.md).**
How the requirements were derived from a brief that supplied none, the constraints nobody chose,
what is proven and what is not, and what changed while it was being built.

## What it is

TTB's compliance agents review roughly 150,000 label applications a year, and most of each review is
matching: does the brand name printed on the artwork say what the application says, is the alcohol
content the declared one, is the Government Health Warning present and word for word. A simple
application takes five to ten minutes by eye. In peak season importers file hundreds at once.

The requirements came from the four people in the brief, answered one at a time rather than
averaged. The agent with 28 years in the job said "you need judgment", so nothing auto-rejects and
anything the app cannot settle comes back with its best answer and a flag asking the agent to
confirm it. The reviewer eight months in said it has to be exact, so the warning is compared word
for word and a check that cannot be measured is visibly switched off rather than silently skipped.
The deputy director wanted speed and batches, so results stream back as each one finishes. IT said
don't do anything crazy, and the answer was to build nothing they have to operate.

This app does the matching. You give it an application's declared values and the label images filed
with it; it reads the label, compares the two, and returns one verdict per element with the rule and
the regulation behind it. Every verdict is an answer, **match** or **mismatch**, which the interface
labels Pass and Fail. Where the app cannot honestly decide an element, the answer is its best guess
and carries a **Needs review** flag and a Confirm button; where it is sure, the answer stands with
nothing to confirm ([decision 0065](docs/decisions.md#0065)).

There is one way in and one way it works: a form that takes one label or three hundred, and a
results page that streams verdicts back as each label finishes. A submission of one label is a batch
of one, checked by the same path as a submission of three hundred. The first label is checked on its
own and the rest run behind it, which is the ordering rather than an accident of it: the reviewer
gets a real result in seconds instead of a progress bar, and starts working while the remainder
runs. The batch then paces itself against how fast they are actually reading, rather than racing
ahead to compute results nobody has asked for yet.

## Deployed URL

**https://ttb.aaroncarney.me**

Google Cloud Run, 4 vCPU and 4 GiB, one instance reading one image at a time, scaling to zero
([decisions 0025](docs/decisions.md#0025) and [0048](docs/decisions.md#0048)). That address is this
project's own hostname, not the one Cloud Run issues: a Cloudflare Worker in `edge/` answers it,
signs each request with a Google ID token and forwards it, and the Cloud Run URL itself answers an
uncredentialed request with 403, so the hostname is the only way in
([decision 0028](docs/decisions.md#0028)). The same Worker pings `/api/health` every five minutes,
which keeps the instance holding the loaded OCR models from being reclaimed and a visitor from
paying the 36-second cold start ([decision 0042](docs/decisions.md#0042)).

The deploy is one command, and it builds from an export of the committed revision rather than from
anyone's working tree:

```bash
scripts/deploy.sh --check                   # every check that needs no network; deploys nothing
TTB_GCP_PROJECT=your-project scripts/deploy.sh
```

How the service is provisioned, how its address is closed with IAM, how the keep-warm was measured
and what a deploy refuses to ship are in [docs/operations.md](docs/operations.md). None of it is
needed to run the app; [Getting started](#getting-started) is.

### The five-second requirement is measured, and it is not met

R15 in [the requirements](specs/0001-label-verification/requirements.md) and NFR-1 in
[the PRD](docs/PRD.md) are one promise, and both mark it P0: 95 percent of single checks show
results within five seconds of pressing check. Measured on the deployed service of version 0.4.0,
from the moment a check is submitted to the moment its result reaches the page, sending every face
of each label: **15 of 37 checks inside five seconds in one run and 16 of 37 in a second run
minutes later** — 41% and 43% against a requirement of 95%. The median check took 5.60 and 5.46
seconds; the slowest took 10.72. Nothing was stopped early and nothing was answered out of the
cache. Thirty-six checks returned all seven fields; the thirty-seventh is the deliberately blurred
sample, which the quality gate turns away.

**Most of the wait is reading the images.** Of the median check, reading its images took 4.57 and
4.35 seconds, and submitting, opening the results page and receiving the result over its stream
0.62 and 0.58. The 33 submissions carrying a back made 11 and 12 of 33 inside the budget, median
6.27 and 6.01 seconds; the four with only a front made 4 of 4, median 3.35 and 3.04. The back is
worth its cost: the government warning is printed on the back of 20 of the 30 corpus labels, so a
check that skipped it would be faster and wrong.

**The reader got slower in 0.4.0.** The build before it made 23 and 33 of 37, with reading at 3.33
and 3.09 seconds for the median check. Version 0.4.0 carries the reader fixes listed in
`CHANGELOG.md`, and the median read is about 1.3 seconds longer.

**The first measurement of the day found a defect instead.** The service ran one request at a time
on up to two instances, and a check's results stream held its instance for as long as the check
ran, so the next request started a second instance that did not hold the batch; the reviewer was
shown no result. Two runs lost 25 and 34 of their 37 checks this way. The service now runs one
instance taking several requests ([decision 0048](docs/decisions.md#0048)), and both runs above
answered all 37.

**Three levers have been tried, and none of them closes it.** Doubling the service to eight cores
moved one check of thirty-eight, so it is back at the four cores
[decision 0025](docs/decisions.md#0025) argued from the free tier's limits. Reading both faces at
once was measured rather than assumed: one read already keeps 3.7 of 4 cores busy, and reading a
label's two faces at once took **16% longer** than reading them in turn, so the serialisation stays
([decision 0047](docs/decisions.md#0047)). The reading path itself has been tuned three times
already. What is left is making a single read cheaper.

**Nothing here is tuned to make the number look better.** The earlier runs of 87%, 89%, 71% and 92%
were taken on superseded code and on a harness that counted a check the evaluation guard had blanked
as a slow one, which is why they are quoted as history rather than as figures
([decision 0035](docs/decisions.md#0035)).

The measurement runs against whatever URL it is given, and skips when there is none:

```bash
TTB_DEPLOY_URL=https://ttb.aaroncarney.me uv run pytest tests/test_deploy_healthz.py
```

`tests/test_deploy_healthz.py` is what produced every figure above. Each run writes its rows to
`artifacts/deploy-latency/`, naming for every check what came back as well as how long it took.

Everything below runs today from a clone, which is the other half of the same deliverable.

## Getting started

You need [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer. Nothing else — **no API key, no
account, and no outbound network call.** The reader that turns a photograph into text runs inside
the process, and its models are installed with the dependencies.

```bash
git clone https://github.com/AaronCarney/ttb-label-check.git
cd ttb-label-check
uv sync
uv run task demo
```

Then open <http://localhost:8000>, or the deployed URL above, and follow the steps below. The first
label after the app starts is slower than the rest: the OCR models are read off disk once, on first
use, and kept for the life of the process.

### Checking one label

1. Press **Label images** and pick the photographs of the label. Pick the back as well as the front:
   the government warning is usually on the back, and a front on its own is checked for a warning
   that is not on it. To pick more than one file, hold **Ctrl** (**Cmd** on a Mac) while you click.
2. If the files are not named `something-front` and `something-back`, tick **These images are all
   faces of one label**. Otherwise each photograph is checked as a label of its own.
3. Choose the **Beverage type**. It is the one field you must fill in.
4. Type the other fields as the application states them. A field left empty is not compared, and
   the label is still checked for what every label must carry.
5. Press **Check**. The results page opens, and the result appears on it as soon as it is ready.

If something is wrong with the upload, the page comes back with a message at the top saying what
to fix, and what you typed is still filled in.

### Reading the result

The top of the result shows the label's answer, **Pass** or **Fail**. Below it, one card per field
shows what the app read on the label (**Extracted**), what the application says (**Expected**), its
answer for that field, and a sentence saying why.

- **Pass or Fail on its own** means the app is sure. There is nothing to do.
- **Pass or Fail with a *Needs review* flag** is the app's best guess. Look at the photograph. If
  the guess is right, press **Confirm Pass** or **Confirm Fail**. If it is wrong, press **This
  result is wrong**, then the other answer. The top of the result counts how many fields are left
  to confirm. Where the app had nothing to go on either way, the guess is Fail, because a label the
  agent cannot read is sent back for a better image.
- **Not checked** means the app did not check that field, so it has no answer to confirm.
- **Needs better photo** means the photograph cannot be read. **Copy message** copies a note to send
  the applicant asking for a new one.

One Fail fails the whole label. Each finding names the regulation it rests on; press the citation to
read that section beside the result.

### Correcting a result

Any field's answer can be changed. Press **This result is wrong** on its card; under *It should
be:*, press the answer it should have. That is two clicks, and no reason has to be typed. The card
then says *Corrected by the reviewer*, and the label's answer and the batch table follow. To undo a
correction, correct the field back to what it was; both corrections stay on the record.

To hold back the whole label rather than one field, press **O** while a result is showing. Type the
first letters of a reason code (for example `BR` for the brand), pick the code with the arrow
keys, and press **Enter** to save it. This can fail a label or send it back to review; it cannot
pass a label that has a failed field. **Esc** closes it.

### Checking many labels at once

**To try it with no labels of your own**, press the **Download a 10-label sample** link on the
entry page. It holds real approved labels and `applications.csv`, one row per label holding the
application actually filed for it. Unzip it, open the unzipped folder in the **Label images**
picker, press **Ctrl+A** (**Cmd+A** on a Mac) to pick every file, and press **Check**. The CSV among
the images is read as the applications, so nothing has to be typed and every label is checked
against its own application. A CSV can also go in the separate **Applications CSV (optional)**
picker. A batch with no CSV is still read and still checked for what every label must carry, and
says so.

With more than one label, a table lists them as they finish, and the first one opens below it.
Click a row, or move to it with **Tab** and press **Enter**, to open that label. Press **Sort by
Position** or **Sort by Disposition** at the top of a column to sort by it; press it again to
reverse the order. One upload takes up to 100 files, and one batch runs at a time.

**To supply your own applications**, write the same CSV: a `filename` column, then
`beverage_type`, `brand_name`, `fanciful_name`, `class_type`, `alcohol_content`, `net_contents`,
`applicant_name_address`, `source_of_product`, `origin` and `wine_appellation` — the same ten fields
the form asks for. `filename` joins on the image name, with or without its extension and with or
without a `-front`/`-back` suffix, so one row covers both faces of a label. Columns of your own are
ignored rather than refused. Two rows naming one label are refused: at 300 labels the failure you
cannot see from the page is not a missing application but the wrong one.

What one upload may carry, and where each cap comes from, is in [How it works](#how-it-works). The
application enforces the caps itself, so a local run refuses exactly what the deployed one refuses.

### Running the tests

```bash
uv run pytest
```

**Two groups skip themselves rather than fail, and a clean run does not mean they ran.** The
accessibility, keyboard and reflow tests drive a real browser: they need [pnpm](https://pnpm.io/) on
`PATH` to build the front-end island and Playwright's browsers installed
(`uv run playwright install chromium`). Without pnpm the whole group skips, silently, and the suite
still reports green — so a run on a machine without it proves nothing about the interface. The
deploy measurement skips the same way without `TTB_DEPLOY_URL`. Everything else runs from a clone
with nothing but `uv sync`.

With pnpm and Playwright installed, that group runs the accessibility scan over every screen the
product serves, and treats a check the scanner could not decide as a failure rather than a pass.
Section 508 also asks for a conformance review by a person, and that has not been run;
`docs/approach.md` says what the scan settles and what it does not.

### Linting, formatting and type checking

Three commands, and all three are expected to pass before a commit:

```bash
uv run ruff check          # lint
uv run ruff format --check # formatting, without rewriting anything
uv run mypy                # types, over app/
```

`uv run ruff format` without `--check` writes the formatting instead of reporting it, and
`uv run ruff check --fix` applies the fixes ruff considers safe. Each tool's configuration lives in
`pyproject.toml` with the reasoning next to it. mypy checks `app/`; tightening it is separate, later
work.

Coverage comes with the suite:

```bash
uv run pytest --cov            # branch coverage over app/
```

**The measured figure is 95% branch coverage over `app/`**, from a run of the whole suite bar the
three tests marked slow; the lowest-covered module is the rule-pack loader at 82%. It is reported
rather than gated, because a threshold set before anyone had measured the real number shapes the
suite to the threshold rather than to the product.

### The container path

Same app, one command, if you would rather not install anything:

```bash
docker compose up demo
```

It serves the same <http://localhost:8000> and needs no secrets either.

### What is pinned, and what is not

Every Python dependency resolves from `uv.lock`, hash for hash, and the container installs from it
frozen. The built front-end bundle is committed, and `tests/test_island_build_clean.py` rebuilds it
and fails if the result differs — that test is in the pnpm-gated group above, so it is the pipeline
rather than a local run that holds the bundle to its source. The OCR models ship inside the
installed package; nothing is downloaded when the app runs.

Two things are **not** pinned, and you should see them named rather than find them: the container's
base image is a moving tag rather than a digest, and the system packages it installs — along with
the `uv` that installs everything else — carry no versions. The Python layer is reproducible; the
layer underneath it is not.

### Using a hosted reader instead

There is a second reader that sends label crops to a hosted vision model. It is off by default and
is not needed for anything in this README:

```bash
export VISION_MODE=cloud
export OPENAI_API_KEY=sk-...
uv run task demo
```

It is expected to read harder images more accurately, and that expectation is the vendor's rather
than ours: every accuracy figure here came from the on-machine reader, and the hosted one has never
been scored against the corpus, though `eval.read_accuracy --reader cloud` would do it. It costs a
few hundred dollars a year of inference at TTB's volume, computed from published rates rather than
measured. `.env.example` lists every environment variable the app reads.

## How it works

Three stages. `ARCHITECTURE.md` maps the directories; `app/services/evaluator.py` is the eight steps
one check runs, in order.

**1. Read.** An OCR engine finds text and its position; a parsing layer turns that into seven fields,
each carrying the box it came from. Every face of a label is read and the readings are merged into
one set of fields, each taken from the face that read it best — a COLA is filed with every face, and
the government warning is usually on the back. Two files whose names end `-front` and `-back` on one
stem are one label; the applications arrive as one CSV joined to the images by the same filename
([decision 0043](docs/decisions.md#0043)).

**2. Compare.** A rule pack decides, in YAML, across a common pack and one per beverage class. A rule
names the validator it calls, the regulation it comes from, and what outcome each result maps to.
Adding a check is a YAML edit, and the tables the rules read are data files rather than code.

**3. Report.** Each check returns a verdict, a reason code and a citation, so a reviewer sees why and
not just what. The citation opens: pressing it fills a column beside the finding with the wording of
the section, which the product holds for all 24 sections its rules cite, fetched once from the eCFR
and committed with a hash. Nothing is fetched while the service runs
([decision 0046](docs/decisions.md#0046)). A settled result stands until the agent says it is
wrong: each field card carries a *This result is wrong* button, the label's result then follows the
corrected fields by the same rule, and the audit trail keeps each correction
([decision 0064](docs/decisions.md#0064)). A result flagged *Needs review* also carries a Confirm
button, and confirming it is recorded the same way ([decision 0065](docs/decisions.md#0065)).

**No model decides a verdict.** A model may read a label — no deterministic code can — but the
comparison is rules over the text it produced, so the same label and application give the same
answer every time. A layer that sent finished results to a language model for a second opinion was
removed for that reason ([decision 0009](docs/decisions.md#0009)).

**What an upload may be.** **31.5 MB** in one request, **1.5 MB** per image, **100** images in a
batch, and nothing whose header declares more than **50,000,000** pixels. Each is derived rather
than picked, beside its derivation in `app/api/limits.py`: the request cap sits under Cloud Run's
32 MiB limit so the refusal names the file; the per-image cap is TTB's own, since COLAs Online
refuses a label image over 1.5 MB; the pixel ceiling catches a decompression bomb no byte cap does.

**What 100 per batch is worth in practice.** A hundred files fit one request only if they
average under **322.3 KB**. At the 1.5 MB per-image cap **20** fit; at the largest label in this
project's corpus, 547 KB, **59** fit. A reviewer sending a hundred large files is refused by name and should
send fewer. `tests/test_readme_content.py` holds this paragraph to `files_that_fit()`.

**Almost nothing is kept.** No database and no COLA integration. Batch state lives in the process
and is dropped when the next batch starts. Two things reach disk and are swept after seven days —
the uploaded image, and each result stripped of everything an override does not amend
([decision 0018](docs/decisions.md#0018)). Log lines are an allow-list with applicant material
blanked by a second pass, and both have tests.

## Tools, and why each one

| Tool | What it does here | Why this one |
|---|---|---|
| FastAPI + Uvicorn | HTTP, the server-side page shells, and the batch event stream | Async server-sent events for batch progress, and Pydantic request and response models for free |
| Pydantic v2 | Every envelope, rule definition and settings object | One schema layer for the YAML loader, the API and the config, so a malformed rule pack fails at load rather than mid-review |
| Jinja2 + a React island | Pages are server-rendered; one bundled component tree handles the result page's interactive parts and the live batch table | The keyboard path for overruling a finding and a batch page that fills in as results stream back need real client state; the rest does not, and the built bundle ships in the repository so no Node is needed to run this |
| RapidOCR on ONNX Runtime | The default reader, on CPU | Ships its own models in the wheel, so a clone needs no download, no key and no GPU |
| RapidFuzz | Brand-name similarity scoring | The brand check needs a graded score, not a yes or no, because a dropped apostrophe is not a different product |
| PyYAML | Loads the rule packs and reference tables | The rules are data a compliance reader should be able to read |
| uv | Dependency resolution and the lockfile | One locked environment, reproducible from a single binary |
| pytest | The suite | The default in this ecosystem, and no alternative was weighed |

Those are conventional picks, and the column above gives the criterion that settled each. The
choices that had a real alternative are architectural, and each was decided against a named one: a
server-rendered page with a small interactive island **over a full client-side application**,
because only two parts need real client state and a build step on the reviewer's machine is a
barrier to running this at all; a directory of files **over both an embedded database**, which
answers no question the files do not, **and object storage**, which needs an account, a key and an
outbound call the clone cannot make; a processor-only reader shipped with the code **over a design
that only calls a hosted model**, which cannot run where this product is for, **and over picking a
reader per image at run time**, which adds moving parts for an accuracy gain nobody has measured.
`docs/approach.md` argues each at length.

The optional hosted reader calls a hosted OpenAI vision model, pinned to a dated snapshot so two
runs of the same label agree. `.env.example` names the snapshot in force.

## Reading accuracy

Measured over the whole real corpus — all 30 labels in
`tests/fixtures/labels` and their 56 face images — with the default on-machine reader (`local`).
Every figure below came from that run. Reproduce it with:

```bash
uv run python -m eval.read_accuracy
```

The harness scores the reader against the transcription in that corpus's manifest, which records
what each label prints, and reports each check separately rather than one blended figure, because
the checks fail in different ways and an average hides that.

| Check | What it asks | Correct of scoreable |
| --- | --- | --- |
| `brand` | the brand name the label carries | 17 of 30 |
| `class_type` | the class and type designation | 19 of 30 |
| `abv` | the stated alcohol content | 27 of 30 |
| `net_contents` | the stated net contents | 23 of 29 |
| `name_address` | the bottler's or importer's name and address | 22 of 30 |
| `origin` | the country of origin | 25 of 30 |
| `warning_present` | that the health warning is on the label at all | 30 of 30 |
| `warning_exact` | that the warning reads word for word as the regulation sets it | 20 of 30 |
| `warning_heading_caps` | that `GOVERNMENT WARNING:` is capitalised as required | 30 of 30 |

The figures are counts, not percentages, and the denominator differs between checks. One label
prints no net contents on any face, so `net_contents` is scoreable on 29 rather than 30: a check
the label itself cannot settle is left out rather than counted against the reader. Thirty labels
is a small denominator, and a percentage drawn from it would read as a precision this corpus does
not carry. See `docs/decisions.md#0027`.

**These figures are in-sample.** The reader's heuristics — the box-merge ratios, the gate and
screen that decide when to re-read a label rotated, the field patterns — were tuned against these
same 30 labels, and the table above scores them on the same 30. So each figure is an upper bound on
what the reader does with a label it has never seen, not an estimate of it. The held-out labels in
[Outcomes on real labels](#outcomes-on-real-labels) carry no transcription to score a reader
against, so they measure verdicts rather than this table. The figure this matters most for is
`warning_present`, 30 of 30, because that is what licenses the one rule in the pack allowed to
report a mismatch because the reader found nothing — `rules/common/health_warning.yaml` says so
where the licence is granted. On the held-out labels the reader missed a warning printed on a face
it was given 3 times in 98; each of those read some of the warning's words, so each goes to a
reviewer rather than coming back a mismatch.

None of this is a verdict. The reader's output goes to a human reviewer who approves or rejects
every finding, so a reading the reader is unsure of is returned as unsure rather than guessed at.
The largest remaining gaps are recognition limits on display type — handwritten script brands and
stylised capitals — and elements the detector splits across several text boxes, which truncates a
designation like `BOURBON WHISKEY` to `BOURBON`.

## Outcomes on real labels

What a reviewer receives, measured on the production path: the real face merge, rule engine and
verdict, with only the OCR replayed from recorded readings. Two sets, reported apart. The corpus is
the 30 labels above, which every change was measured on. The held-out set is 98 bourbon records from
TTB's public COLA Registry (53 approved, 42 surrendered, 3 expired) that nothing was tuned on
([decision 0051](docs/decisions.md#0051)) until the last decision below. Every one was accepted by
TTB, so each mismatch the product reports was read against the label images by eye.

```bash
uv run python -m eval.corpus_check              # the corpus
uv run python -m eval.corpus_check --registry   # the held-out set
```

The held-out records, their readings and the alcohol content and net contents read off their images
are not in the repository, so that second figure cannot be reproduced from a clone;
`eval/fetch_registry_corpus.py` fetches the records.

| | Corpus, before | Corpus, now | Held-out, before | Held-out, now |
|---|---|---|---|---|
| Labels: match / mismatch / needs review | 0 / 9 / 21 | 0 / 2 / 28 | 0 / 63 / 35 | 6 / 11 / 81 |
| Checks: match / mismatch / needs review | 350 / 11 / 94 | 365 / 2 / 88 | 998 / 88 / 379 | 1,090 / 11 / 364 |
| Checks with a clear result, match or mismatch | 79.3% | 80.7% | 74.1% | 75.2% |

"Before" is the product until the reader and rules were reworked to tell a reading error from a
label defect ([decisions 0052 to 0063](docs/decisions.md#0052)). On the held-out set that took the
mismatches the product caused from 77 to none. The 11 held-out mismatches now are 3 warnings that
genuinely differ from 27 CFR 16.21 and 8 warnings printed only on a neck or strip image the upload
does not take. On the corpus, both mismatches are genuine warning differences.

The held-out figure after the last of those decisions ([0063](docs/decisions.md#0063)) is not a
clean held-out measurement. That decision sends a difference to a reviewer when it could be a
misread: a word no dictionary holds, several words lost or moved, a warning whose words were read
but not found, a proof one "1" away from twice the ABV. Those kinds of signal were found by reading
the held-out failures, and the corpus also supports the word-list rule with misreads such as
"ORINK", "HEAILTH" and "ALCOHOIC".

A clear result is not a check decided without a person: the agent still reviews every label. The
share barely moved because a wrong mismatch is a clear result too: most of them became matches and
the rest go to a reviewer, so what changed is how many clear results are right. The most common reasons a check goes to a person are a field the reader did not find, a
name and address it could not match, a class designation it could not confirm, and a heading whose
bold weight it could not establish.

## Assumptions

The brief's technical requirements are a single sentence, and it says nothing about speed, batch
sizes, error handling, retention or who uses this. Each item below is a gap the brief left and a
call we made in it, stated as our call rather than as a finding.

- **The application is right and the label is what is being checked.** Where the two disagree, the
  app reports a mismatch on the label; it never assumes the application is the error. Two checks
  never report a mismatch, because the reader cannot show which text is the element: a brand not
  found on the label, and an import whose origin statement was not read. Both go to a person.
- **The application names the beverage type**, and that is what selects the rule pack. A label
  submitted with no application is read but not checked, because nothing says which rules apply.
- **A submitted photograph is meant to be legible.** Making a poor photograph readable is out of
  scope; where the app cannot read a field it says so rather than guessing at one. How well it
  tells a poor photograph from a good one is a separate question, and an open one.
- **The warning text is fixed.** 27 CFR 16.21's wording is pinned as a committed asset and compared
  against by hash, so a change to the regulation is a deliberate edit and not a silent drift. The
  same bargain covers the sections the citation panel shows, in `assets/cfr/`: they were fetched
  from the eCFR once and committed, and `TTB_CHECK_ECFR=1 uv run pytest
  tests/test_cfr_corpus_matches_ecfr.py` re-fetches every one and compares it character for
  character. Nothing runs that on a schedule, so the corpus is as current as the last time somebody
  ran it — the manifest says which issue of each title is held.
- **What is kept is kept for seven days and no longer.** Application data lives only as long as the
  request that carried it. Every check's result is written to disk so a reviewer can
  overrule a finding on it, stripped of every value it read and every value the application
  declared. The uploaded label image is written the same way, so the result page survives a restart.
  Both are a demo's bargain rather than a production one: the labels this ships are public TTB COLA
  Registry images, and a real deployment would hold an applicant's material inside the agency's
  boundary, encrypted, and drop it the moment the result had been read
  ([decision 0018](docs/decisions.md#0018)).
- **The agency's own plumbing sets three constraints, and none was treated as negotiable.** No
  integration with COLA or any other TTB system; outbound traffic blocked at the firewall, which is
  why the default reader ships its models rather than calling anything; and nothing new for IT to
  operate, which is why there is no database, no queue and no service to run beside the app. All
  three came from the systems administrator in the brief.

## Trade-offs

- **A narrow core that works, over broad coverage that does not.** Where a check can be made on some
  labels and not others, it reports needs review on the labels where it could not. Where it could
  not be made correct at all, it is switched off in the rule pack rather than returning a verdict it
  has not earned, and it is named under Limitations. The product reports; the agent rules on every
  finding and makes the decision. The two kinds of wrong result are still not equal. A false match
  is the one the requirements rule out (`docs/PRD.md` S-2), because a label the product calls clean
  is the one the agent has least reason to look at hard. A false mismatch costs the agent time and,
  repeated, teaches them to discount every mismatch the product reports. So the design reports needs
  review on a doubtful point rather than guessing either way, and the cost of that lean lands on the
  agent, as the extra items under Limitations.
- **Determinism over capability.** Rules decide, models only read. The cost is that anything needing
  judgement beyond a scored comparison goes to a person rather than being resolved automatically.
- **Local CPU reading by default, accuracy second.** The hosted reader is expected to be better on
  hard images, on the vendor's word rather than on a run of ours. It is not the default, because a
  reviewer should be able to clone and run this with no account, and the firewall the brief
  describes would block the call anyway. What that costs is the display-type recognition limit named
  under Reading accuracy.
- **State in memory, except what a result page and an override need.** A server restart loses an
  in-flight batch and the reviewer re-uploads. Two things are written down: the label image, because
  a result page that cannot show the label it is describing is not a result page, and a single
  label's result, because an override has to have something to amend. Both are kept for seven days
  and no longer ([decision 0018](docs/decisions.md#0018)).
- **A brand differing only in punctuation or spacing is a match, not a question.** "Os" against
  "O's" passes at any length, with the difference named in the finding, rather than sending every
  dropped apostrophe to a person. It cannot tell the rare punctuation change that alters a name's
  meaning. Any other difference sends the app searching every line it read for the declared name,
  and a name it cannot find goes to a person. What it buys and what it costs are argued in
  [decision 0017](docs/decisions.md#0017) and [decision 0052](docs/decisions.md#0052). The search
  has a cost of its own: a brand that is a common phrase, such as "CASK STRENGTH", is found wherever
  the phrase is printed.

## What the brief asked for

The seven label elements the brief lists, and where each is answered. Which regulation sets a check
depends on the beverage: wine comes from 27 CFR part 4, distilled spirits from part 5, malt
beverages from part 7, the health warning from part 16, and an import's origin marking from 19 CFR
part 134. The sections below are the wine pack's; the spirits and malt packs carry the parallel
sections of parts 5 and 7, and every rule states its own citation, which is why `rules/` can be read
on its own.

| Element | Status | Regulation | Where the check lives |
|---|---|---|---|
| Brand name | Checked — the label is searched for the application's brand and trade names; found is a match, not found goes to a person, never a mismatch | §4.32(a)(1), §4.33 | `rules/wine/wine.yaml`, `rules/spirits/spirits.yaml`, `rules/malt/malt.yaml` |
| Class/type designation | Checked — matched against the application and against the designation tables; for spirits, also against the standards of identity | §4.32(a)(2), §4.34; spirits Subpart I | `rules/tables/wine_designations.yaml`, `rules/tables/malt_designations.yaml`, `rules/spirits-deep.yaml` |
| Alcohol content | Checked — format, and the figure against the application; for spirits, a stated proof against twice the label's own ABV. Required-or-not follows the beverage class | §4.32(b)(1), §4.36; proof §5.1, §5.65(b)(1)(i) | the three class packs |
| Net contents | Checked — compared as a quantity, with units converted before comparing | §4.32(b)(2), §4.37 | `rules/tables/volume_units.yaml` |
| Name and address | Checked — applicant or declared trade name, plus city and state | §4.32(a)(3), §4.35 | the three class packs |
| Country of origin | Checked for imports, against the application's English country name. The other forms customs accepts are a named limitation | §4.35(e), 19 CFR §134.45 | the three class packs |
| Government Health Warning | Checked — present, word for word against the pinned text, heading in capitals, heading boldness measured where it can be. The typography rules are switched off, because a photograph does not carry what they measure | §16.21; typography §16.22 | `rules/common/health_warning.yaml`, `assets/warnings/govt_warning_16_21.txt` |

Both deliverables:

| Deliverable | Status |
|---|---|
| Source code repository — all source, a README with setup and run instructions, and documentation of approach, tools and assumptions | This repository, this file, and [docs/approach.md](docs/approach.md) |
| Deployed application URL — a working prototype Treasury can access and test | Live at https://ttb.aaroncarney.me. See "Deployed URL" above |

## Where to look next

**To see it work,** follow Getting started above and check one label against an application with a
field deliberately wrong. The answer on each field, the *Needs review* flag, the citation under each finding and the label image
beside the readings are the whole product in one screen.

**To read the code,** open `rules/` first. Verdicts are decided there, in YAML, and every check
names the regulation behind it — so you can see everything this app enforces without reading any
Python. `ARCHITECTURE.md` maps every directory the repository ships in one table, and `app/services/evaluator.py` is the
eight steps one check runs through, in order.

**To judge whether it works,** `tests/fixtures/labels/` is the answer key: 30 real approved labels
with a transcription of what each one prints and the verdict each check should return. The brief
suggested generating test labels; we used real ones instead, because a generated label only proves
the reader can read what we drew. `uv run python -m eval.read_accuracy` scores the reader against
it and reproduces every figure in Reading accuracy above.

| Question | Document |
|---|---|
| How was this approached, and what was assumed? | [docs/approach.md](docs/approach.md) |
| What is this supposed to do, and for whom? | [docs/PRD.md](docs/PRD.md) |
| How is it put together? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Why was it done this way and not another? | [docs/decisions.md](docs/decisions.md) |
| What does the regulation actually say? | [docs/reference/](docs/reference/) |
| How is the service run and redeployed? | [docs/operations.md](docs/operations.md) |
| What changed and when? | [CHANGELOG.md](CHANGELOG.md) |

## Limitations

Checks this app does not make, and what each costs the agent using it. Where a decision record
settled the limit it is cited; in all of these the app reports no verdict it has not earned.

- **An upload with no application is read but not checked.** The declared beverage is what decides
  which rules apply, so a label submitted alone is read and reported and nothing is checked against
  it — the government-warning checks included (`docs/decisions.md#0010`). The app is no use for a
  quick look at a label on its own.

- **An alcohol statement in a form the regulations do not print is reported as needs review.** No
  pattern can list every phrasing 27 CFR §4.36(b), §5.65(b) and §7.65(b) permit, so a statement
  outside the printed forms is reported as needs review rather than as a mismatch
  (`docs/decisions.md#0011`). Eight of the 30 approved corpus labels land there. A compliant label
  can reach the review pile over its wording.

- **A country of origin is read only as the application's English name.** Customs marking rules
  also accept the country's own language, an unmistakable abbreviation and the adjectival form
  (19 CFR §134.45(b), (c)); the app reads none of them and reports needs review
  (`docs/decisions.md#0016`). An import on which no origin statement is read at all also goes to a
  person, under a code of its own, rather than failing (`docs/decisions.md#0059`). None of it means
  anything is wrong with the label.

- **The health warning's typography and placement are not checked.** Contrasting background,
  characters per inch, type height and standing separate and apart (27 CFR §16.22(a)(1), (a)(4),
  (b), and §16.21) need ink colour or physical scale, which a photograph does not carry. Each stays
  in the pack switched off with its citation, and a switched-off rule produces no finding, so no
  label is passed or failed on one (`docs/decisions.md#0006`, `docs/decisions.md#0013`). TTB says it
  does not routinely review labels for these either.

- **Bold type in the warning's heading can pass or go to a person, never fail.** §16.22(a)(2)
  requires the heading bold and the rest of the statement not, so the app measures the heading's
  stroke against the statement's own body on the same photo; 1.125 times as heavy or more is bold.
  Approved headings measured as low as 0.988, inside the range of regular type, so a heading not
  clearly heavier goes to a person rather than failing, as does one too small or too blurred to
  measure. On the corpus 16 headings pass and 14 go to a person (`docs/decisions.md#0058`). A body
  printed bold, which the same section forbids, is not checked.

- **Five more requirements have no check at all, disabled or otherwise.** Mandatory wording must be
  readily legible on a contrasting background, stand separate and apart, be similarly conspicuous
  across a designation's words, and meet a minimum type height (27 CFR §§4.38, 5.52, 5.53, 5.141(d),
  7.52, 7.53); and the warning's letters must not be compressed past ready legibility
  (§16.22(a)(3)). None appears in any rule pack. Most would have been switched off like the
  typography above, but they were absent rather than decided, and this entry is the record of that.
  A label can come back with every check passed and none of these five looked at.

- **A photo the app refuses to read is checked against nothing.** Detail below a Laplacian variance
  of **50.0** reads as too low a resolution and a high-frequency ratio below **0.3** as motion blur;
  either ends the evaluation before any rule, so **no compliance rule runs** and the result comes
  back carrying the legibility reason code and no field readings. Both numbers are this project's
  own line, set against this corpus and derived from nothing TTB publishes. A photo on which the
  reader finds no text at all stops the label the same way, and the result names the photo to
  retake (`docs/decisions.md#0062`).

- **A rotated re-read can decline to fire, and the result does not say that it did.** A sideways
  government warning is found by reading the label again at 90° and 270°, and that read is the
  expensive part, so it runs only when no heading was found upright, the box shapes look sideways,
  and the sideways strips read like the warning or read too poorly to rule it out
  (`docs/decisions.md#0054`). When it declines and none of the warning's wording was read either,
  the label is reported as carrying no warning, and only the server log says a re-read was turned
  down. A missing warning is a §16.21 mismatch, so that silence decides labels. A label photographed
  upside down is the same gap.

- **Every item of a JSON `POST /batches` request is refused, so that endpoint checks nothing.** It
  expects the server to find an image from a `label_id`, and there is no image store, so every item
  returns `ENGINE.INPUT.LABEL_IMAGE_MISSING` and the batch reports zero labels checked
  (`docs/decisions.md#0020`). The path that works is `POST /`, which carries the files and is what
  the form uses.
