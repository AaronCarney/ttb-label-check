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
anything the app cannot settle comes back labelled unsettled. The reviewer eight months in said it
has to be exact, so the warning is compared word for word and a check that cannot be measured is
visibly switched off rather than silently skipped. The deputy director wanted speed and batches, so
results stream back as each one finishes. IT said don't do anything crazy, and the answer was to
build nothing they have to operate.

This app does the matching. You give it an application's declared values and the label images filed
with it; it reads the label, compares the two, and returns one verdict per element with the rule and
the regulation behind it. Three outcomes only — **match**, **mismatch**, or **needs review**, which
the interface labels Pass, Fail and Needs review — and the third is a real answer, used wherever the
app can see the element but cannot honestly decide it.

There is one way in and one way it works: a form that takes one label or three hundred, and a
results page that streams verdicts back as each label finishes. A submission of one label is a batch
of one, checked by the same path as a submission of three hundred. The first label is checked on its
own and the rest run behind it, which is the ordering rather than an accident of it: the reviewer gets a real result in
seconds instead of a progress bar, and starts working while the remainder runs. The batch then paces
itself against how fast they are actually reading, rather than racing ahead to compute results
nobody has asked for yet.

## Deployed URL

**https://ttb.aaroncarney.me**

Google Cloud Run, 4 vCPU and 4 GiB, one request at a time, scaling to zero
([decision 0025](docs/decisions.md#0025)). That address is this project's own hostname, not the one
Cloud Run issues: a Cloudflare Worker in `edge/` answers it, signs each request with a Google ID
token and forwards it, and the Cloud Run URL itself answers an uncredentialed request with 403, so
the hostname is the only way in ([decision 0028](docs/decisions.md#0028)). The same Worker pings
`/api/health` every five minutes, which keeps the instance holding the loaded OCR models from being
reclaimed and a visitor from paying the 36-second cold start
([decision 0042](docs/decisions.md#0042)).

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
results within five seconds. Measured on the deployed service on 2026-09-20, sending every face of
each label the way the page now sends them: **18 of 37 checks inside five seconds in one run and 21
of 37 in a second run minutes later** — 49% and 57% against a requirement of 95%. The median check
took 5.01 and 4.38 seconds; the slowest took 9.01. The requirement is missed by a wide margin, and
the margin is the back of the label.

**What changed.** Until 2026-09-19 the page offered one file input, so the measurement posted one
image. The government warning is printed on the back of 20 of the 30 corpus labels, so a front-only
check reported a warning missing that the label carries — a fast wrong answer. The page now takes a
front and a back, the measurement sends both, and the faces are read one after another, so the
second face costs roughly what the first one costs.

Both halves of that are visible inside the same runs. The 33 submissions carrying a back came in 14
and 17 inside the budget, median 5.55 and 4.95 seconds. The four that have only a front came in 4
of 4, median 2.39 and 2.74 seconds. Against the previous deployed commit, which could only be sent
fronts, the whole set measured 35 of 37 inside five seconds — 94.6%, median 2.90. That number was
real and it is not a number about this product: it describes a submission the page no longer makes
and an answer that was wrong about the warning on 19 of 29 real labels.

Nothing was stopped early, nothing was answered out of the cache, and every check returned all
seven fields, in both runs. These are slow checks, not blank ones.

**Reading both faces at once will not close it, and that is measured rather than assumed.** The
two faces are read one after another, and a running copy reads one image at a time: it holds a
single OCR engine, and a second read waits for the first to finish (`app/vision/local.py`). Reading
both faces at once therefore means lifting that serialisation rather than merely asking for both
together. One read already keeps 3.7 of 4 cores busy, so there is nothing idle for a second read to
take. One label's two faces read at once took **16% longer** than read one after the other: it
lengthens the wait it was meant to shorten. Over a queue of labels it is 11 to 16% faster per
image, and it buys that with the slowest single image — 1.10 seconds as built against 1.92 or 3.45
— and with memory, 658 MB against 911 or 1267 MB of the service's 4 GiB. The serialisation stays
([decision 0047](docs/decisions.md#0047)). What is left is making a single read cheaper. Those
figures were taken on the development box, which is about four times faster than the deployed
service: the comparison between shapes carries over, the seconds do not
(`docs/evidence/2026-09-20-read-scaling.json`).

**Nothing here is tuned to make the number look better.** The earlier runs of 87%, 89%, 71% and 92%
were taken on superseded code and on a harness that counted a check the evaluation guard had
blanked as a slow one, which is why they are quoted as history rather than as figures
([decision 0035](docs/decisions.md#0035)).

**Cores are not the lever.** Doubling the service to eight cores moved one check of thirty-eight,
which is smaller than the spread between two runs at the same size. The service is back at the four
cores [decision 0025](docs/decisions.md#0025) argued from the free tier's limits.

The measurement runs against whatever URL it is given, and skips when there is none:

```bash
TTB_DEPLOY_URL=https://ttb.aaroncarney.me uv run pytest tests/test_deploy_healthz.py
```

`tests/test_deploy_healthz.py` is what produced every figure above. Each run writes its rows to
`artifacts/deploy-latency/`, naming for every check what came back as well as how long it took.

Everything below runs today from a clone, which is the other half of the same deliverable.

## Getting started

You need [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer. Nothing else — **no API key, no
account, and no outbound network call.** The reader that turns a photograph into text runs inside the
process, and its models are installed with the dependencies.

```bash
git clone https://github.com/AaronCarney/ttb-label-check.git
cd ttb-label-check
uv sync
uv run task demo
```

Then open <http://localhost:8000>. Upload the front of a label and, if the label has one, its back
— the government warning is usually printed on the back, so a front on its own is checked for a
warning that is not on it. Fill in the application fields beside the images and submit.

**To try it with no labels of your own**, follow the **Download a 10-label sample** link on the
entry page. It is built from real approved labels shipped in this repository, and
it carries `applications.csv` beside the images: one row per label, holding the application that was
actually filed for it. Unzip the pack and select the whole unzipped folder in the label-images
picker — the CSV among the images is read as the applications, so nothing has to be typed and no
second gesture is needed. Every label then comes back checked against its own application, which is
what the product is for; a batch of images with no CSV is still read and still checked for what
every label must carry, and says so.

**To supply your own applications**, write the same CSV: a `filename` column, then
`beverage_type`, `brand_name`, `fanciful_name`, `class_type`, `alcohol_content`, `net_contents`,
`applicant_name_address`, `source_of_product`, `origin` and `wine_appellation` — the same ten fields
the form asks for. `filename` joins on the image name, with or without its extension
and with or without a `-front`/`-back` suffix, so one row covers both faces of a label. Columns of
your own are ignored rather than refused. Two rows naming one label are refused: at 300 labels the
failure you cannot see from the page is not a missing application but the wrong one.

The first label is slower than the rest: the OCR models are read off disk once, on first use, and
kept for the life of the process.

**What an upload may be, and why the request cap is the size it is.** One request may carry
**31.5 MB** in total, any single image up to **1.5 MB**, and a batch up to **100** images. The request
total is the host's constraint rather than this service's choice: Cloud Run refuses an HTTP/1
request larger than 32 MiB before the application is reached, and when Google refuses it the reply
is Google's own error page, which names neither the limit nor the file that broke it. This
service's cap therefore sits just under the platform's, so the refusal you get is ours and it tells
you which file to fix. Google's published quota is *"Maximum HTTP/1 request size: 32 MiB per
request. Limit applies if using HTTP/1 server. No limit if using HTTP/2 server"* — [Cloud Run
quotas and limits](https://docs.cloud.google.com/run/quotas), under *Request limits for Cloud Run*.
Running locally there is no Cloud Run in the way, but the caps are enforced by the
application in both places, so a local run refuses exactly what the deployed one refuses.

### Running the tests

```bash
uv run pytest
```

**Two groups skip themselves rather than fail, and a clean run does not mean they ran.** The
accessibility, keyboard and reflow tests drive a real browser: they need
[pnpm](https://pnpm.io/) on `PATH` to build the front-end island and Playwright's browsers
installed (`uv run playwright install chromium`). Without pnpm the whole group skips, silently, and
the suite still reports green — so a run on a machine without it proves nothing about the
interface. The deploy measurement skips the same way without `TTB_DEPLOY_URL`, as the section above
says. Everything else runs from a clone with nothing but `uv sync`.

**With pnpm and Playwright installed, that group runs and holds the accessibility scan.** It covers
every screen the product serves, and it treats a check the scanner could not decide as a failure rather than a pass, so an undecidable
result cannot read as a clean one. One check is exempt, and only because somebody reviewed it and
wrote down what they found; an undecided check nobody has looked at still fails. Six result-page cases once
failed it on colour contrast below the AA threshold, and the layout test once failed at a 320-pixel
viewport on a 27-pixel overflow; both were ours and both are fixed. What a machine cannot settle it
does not settle: Section 508 asks for a conformance review as well as an automated scan, and that
review has not been run. `docs/approach.md` says what the scan does and does not settle for the
Section 508 claim.

### Linting, formatting and type checking

Three commands, and all three are expected to pass before a commit:

```bash
uv run ruff check          # lint
uv run ruff format --check # formatting, without rewriting anything
uv run mypy                # types, over app/
```

`uv run ruff format` without `--check` writes the formatting instead of reporting it, and
`uv run ruff check --fix` applies the fixes ruff considers safe.

Coverage comes with the suite:

```bash
uv run pytest --cov            # branch coverage over app/
```

**The measured figure is 93% branch coverage over `app/`**, measured from a run of the
whole suite bar the two slow performance tests. It is reported, not gated: no `fail_under` is set,
because a threshold chosen before anyone had measured the real number is how a suite gets shaped to
the threshold rather than to the product. The lowest-covered module is the rule-pack loader at 82%.

Two modules used to report 0% and neither was untested: `app/rules/__main__.py` and
`app/vision/__main__.py` are command-line entry points, the suite drives both in a subprocess, and
coverage measures only the process it starts in. That made the figure wrong in the direction that
does harm — a 0% reads as "nobody tests this" and points effort at the one place that does not need
it. The suite now turns on coverage's subprocess measurement for whoever runs it, so the two report
82% and 87% from the tests that were always exercising them.

Each tool's configuration lives in `pyproject.toml` with the reasoning next to it: which lint rules
are switched on beyond ruff's default and what each one has already caught here, why the line length
is 100 rather than ruff's 88, why markdown is excluded from both the linter and the formatter, and
why the type checker starts permissive. mypy checks `app/`; tightening it is separate, later work.

### The container path

Same app, one command, if you would rather not install anything:

```bash
docker compose up demo
```

It serves the same <http://localhost:8000> and needs no secrets either.

### What is pinned, and what is not

Every Python dependency resolves from `uv.lock`, which carries a hash for every artefact it pins,
and the container installs from it frozen — nothing is re-resolved at build time, so the image gets the versions this
repository was tested against. The built front-end bundle is committed, and
`tests/test_island_build_clean.py` rebuilds it and fails if the result differs from the committed
copy. That test is in the pnpm-gated group above, so it is the pipeline rather than a local run that
holds the bundle to its source. The OCR models ship inside the
installed package; nothing is downloaded when the app runs.

Two things are **not** pinned, and you should see them named rather than find them: the container's
base image is a moving tag rather than a digest, and the system packages it installs — along with
the `uv` that installs everything else — carry no versions. The Python layer is reproducible; the
layer underneath it is not.

### Using a hosted reader instead

There is a second reader that sends label crops to a hosted vision model. It is expected to read
harder images more accurately, and that expectation is the vendor's rather than ours — every
accuracy figure in this README came from a run of the on-machine reader, and the hosted one has
never been scored against the corpus, though `eval.read_accuracy --reader cloud` would do it. Its
cost is a few hundred dollars a year of inference at TTB's volume, computed from published rates
rather than measured here. It is off by default and is not needed for anything in this README:

```bash
export VISION_MODE=cloud
export OPENAI_API_KEY=sk-...
uv run task demo
```

`.env.example` lists every environment variable the app reads, with what each one does.

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
([decision 0046](docs/decisions.md#0046)).

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
| `origin` | the country of origin | 24 of 30 |
| `warning_present` | that the health warning is on the label at all | 30 of 30 |
| `warning_exact` | that the warning reads word for word as the regulation sets it | 20 of 30 |
| `warning_heading_caps` | that `GOVERNMENT WARNING:` is capitalised as required | 30 of 30 |

The figures are counts, not percentages, and the denominator differs between checks. One label
prints no net contents on any face, so `net_contents` is scoreable on 29 rather than 30: a check
the label itself cannot settle is left out rather than counted against the reader. Thirty labels
is a small denominator, and a percentage drawn from it would read as a precision this corpus does
not carry. See `docs/decisions.md#0027`.

**These figures are in-sample, and there is no held-out set.** The reader's heuristics — the
box-merge ratios, the gate and screen that decide when to re-read a label rotated, the field
patterns — were
tuned against these same 30 labels, and the table above scores them on the same 30. So each figure
is an upper bound on what the reader does with a label it has never seen, not an estimate of it.
Reserving a held-out split from 30 labels was judged worse than not having one: a ten-label test set
would leave both halves too small to measure anything, and the corpus is the whole of what this
project could source. The figure this matters most for is `warning_present`, 30 of 30, because that
is what licenses the one rule in the pack allowed to report a mismatch because the reader found nothing —
`rules/common/health_warning.yaml` says so where the licence is granted. A reviewer weighing these
numbers should read them as what the reader does on labels like the ones it was built against.

None of this is a verdict. The reader's output goes to a human reviewer who approves or rejects
every finding, so a reading the reader is unsure of is returned as unsure rather than guessed at.
The largest remaining gaps are recognition limits on display type — handwritten script brands and
stylised capitals — and elements the detector splits across several text boxes, which truncates a
designation like `BOURBON WHISKEY` to `BOURBON`.

## Assumptions

The brief's technical requirements are a single sentence, and it says nothing about speed, batch
sizes, error handling, retention or who uses this. Each item below is a gap the brief left and a
call we made in it, stated as our call rather than as a finding.

- **The application is right and the label is what is being checked.** Where the two disagree, the
  app reports a mismatch on the label; it never assumes the application is the error.
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
- **Scored brand matching rather than exact matching.** A punctuation difference scores just below
  identical and passes, with the score shown, rather than sending every dropped apostrophe to a
  person. What it buys and what it costs are argued in
  [decision 0017](docs/decisions.md#0017).

## What the brief asked for

The seven label elements the brief lists, and where each is answered. Which regulation sets a check
depends on the beverage: wine comes from 27 CFR part 4, distilled spirits from part 5, malt
beverages from part 7, the health warning from part 16, and an import's origin marking from 19 CFR
part 134. The sections below are the wine pack's; the spirits and malt packs carry the parallel
sections of parts 5 and 7, and every rule states its own citation, which is why `rules/` can be read
on its own.

| Element | Status | Regulation | Where the check lives |
|---|---|---|---|
| Brand name | Checked — scored against the application's brand, fanciful and trade names | §4.32(a)(1), §4.33 | `rules/wine/wine.yaml`, `rules/spirits/spirits.yaml`, `rules/malt/malt.yaml` |
| Class/type designation | Checked — matched against the application and against the designation tables; for spirits, also against the standards of identity | §4.32(a)(2), §4.34; spirits Subpart I | `rules/tables/wine_designations.yaml`, `rules/tables/malt_designations.yaml`, `rules/spirits-deep.yaml` |
| Alcohol content | Checked — format, and the figure against the application. Required-or-not follows the beverage class | §4.32(b)(1), §4.36 | the three class packs |
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
field deliberately wrong. The three outcomes, the citation under each finding and the label image
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

Checks this app does not make, and why. The first five each name the decision record that settled
them, and in each the app reports no verdict it has not earned.
The sixth is different: those requirements were never decided on at all, which is the point of the
entry, so it cites nothing and nothing in the pack switches them off.

The next two are different again. They are not checks the app declines to make, but two places where
it stops short of judging a label and the envelope does not fully say so. Both are in the reading,
before any rule is reached.

The last one is different from all of them: it is not about a check at all, but about an endpoint
that cannot check anything.

- **An upload with no application is read but not checked.** The beverage the application declares
  is what decides which rules apply, so a label submitted on its own is read and reported, and no
  check runs against it — including the government-warning checks, which every beverage shares but
  which are still written per beverage class. See `docs/decisions.md#0010`. For an agent this means
  the app is no use for a quick look at a label on its own: the application's values have to be
  entered before anything is checked.

- **An alcohol statement in a form the regulations do not print is reported as needs review.** The app passes
  a statement in one of the forms 27 CFR §4.36(b), §5.65(b) and §7.65(b) give for its beverage
  class, and reports needs review for any other statement rather than a mismatch: no pattern can list
  every phrasing those sections permit, and none of them says how the figure is written. Of the 30
  approved labels in the fixture corpus, 3 print a statement reported as needs review — two malt
  labels that leave out the colon §7.65(b) prints in "Alcohol by volume: percent", and one wine
  label that writes its figure with a decimal comma. A label whose statement the reader does not
  return in full is reported as needs review too. See `docs/decisions.md#0011`. For an agent this means a
  compliant label can land in the review pile over its alcohol wording.

- **A country of origin is read only as the application's English name.** Customs marking rules also
  accept the country's name in the language of the country, an abbreviation that unmistakably
  indicates it, and the adjectival form — "HECHO EN MEXICO", "U.K.", "Irish" (19 CFR §134.45(b),
  (c)). The app does not read those, so an import that writes its origin one of those ways is
  reported as needs review rather than as a match or a mismatch. See `docs/decisions.md#0016`. On a batch of
  imports this is the main source of extra manual work — a compliant label lands in the review pile
  because the app cannot read the form it used, not because anything is wrong with it.

- **The health warning's typography and placement are not checked.** The app checks the warning's
  words, that "GOVERNMENT WARNING" is present, and that those two words are in capitals. It does not
  check that the warning sits on a contrasting background (27 CFR §16.22(a)(1)), its characters per
  inch (§16.22(a)(4)), its type height (§16.22(b)), or that it stands separate and apart from other
  information (§16.21). The first three need the colour of the ink or the physical scale of the
  label, and a photograph carries neither; separateness is visible in a photograph but no reader
  measures it yet. Each of those rules stays in the pack with its citation and the reason it is
  switched off, and a switched-off rule produces no finding at all, so no label is reported as a
  match or a mismatch on one. TTB says it does not routinely review
  labels for type size, characters per inch or contrasting background either. So the agent's eye is
  the only check on warning typography, exactly as it is today — the app neither helps here nor
  claims to. See `docs/decisions.md#0006` and `docs/decisions.md#0013`.

- **Bold type in the warning's heading is reported, never decided.** §16.22(a)(2) requires the
  heading in bold as well as in capitals. Bold weight is a stroke-width measurement on the heading's
  own region of the image, and a sweep of all 38 corpus labels
  (`eval/heading_bold_ratios.py`) found the measurement is not good enough to call any label a mismatch on. The
  labels are all TTB-approved and so all required to be bold, yet the ratio ran 0.111 to 0.508 across
  them, and one label measured 0.111 from a clean photograph and 0.261 from a blurred copy of the
  same printing. At the 0.25 cut, 18 of the 28 labels it measured confidently came out "not bold".
  So a heading that does not measure as bold is reported as needs review rather than a mismatch,
  whether the measurement failed or simply came back low. The capitals are read from the heading's
  text and are still decided: a heading not in capitals is a mismatch. The cost is a large share of review items on
  labels that are very likely fine — on this corpus, most of them. See `docs/decisions.md#0037` and
  `docs/decisions.md#0013`.

- **Five more requirements have no check at all, disabled or otherwise.** A label's mandatory
  wording must be readily legible on a contrasting background, must stand separate and apart from
  other information, must be similarly conspicuous across the words of a designation, and must meet
  a minimum type height (27 CFR §§4.38, 5.52, 5.53, 5.141(d), 7.52, 7.53); and the health
  warning's letters must not be compressed so far that it stops being readily legible
  (§16.22(a)(3)). None of those appears in any rule pack. Most would have ended up switched off
  like the typography above — legibility and conspicuousness are judgements rather than
  measurements, and type height needs the label's physical scale, which a photograph does not carry
  — but they were absent rather than decided, and this entry is where that is put on the record.
  For an agent the consequence is the same as for the typography above, and it is silent: a label
  can come back with every check passed and none of these five looked at, so the agent's own eye is
  the only thing standing between a badly set label and an approval.

- **A photo the app refuses to read is checked against nothing.** Before any rule runs, the app
  measures the image and can turn it away: detail below a Laplacian variance of **50.0** reads as too
  low a resolution, and a high-frequency ratio below **0.3** reads as motion blur. Either one ends
  the evaluation there — **no compliance rule runs** against that label, and the result comes back
  as a review item carrying the legibility reason code and no field readings at all. The refusal
  itself is on the record: the reason code reaches the audit trail as its own entry. What is not on
  the record is that both numbers are this project's own line, set against this corpus, derived from
  nothing TTB publishes. So for an agent, *needs a better photo* is as much a statement about where
  this app stops as about the photograph — a label just the wrong side of either number has not been
  judged by anything, and the only way to find out whether it is compliant is to look at it.

- **A rotated re-read can decline to fire, and nothing records that it did.** A government warning
  printed sideways is found by reading the label again at 90° and 270°. That second read is the
  expensive part of a reading, so it runs only when three things are true at once: no heading was
  found in the upright pass, the box shapes look sideways, and the sideways strips themselves read
  like the warning. When either of the last two declines, the label is read upright only and reported
  as carrying no government warning — and no part of the result says a re-read was considered and
  turned down. Since a missing warning became a §16.21 mismatch rather than needs review, that
  silence now decides labels rather than just delaying them. A label photographed fully upside down
  is a known gap of the same kind: no rotation covers 180°, and its boxes are horizontal, so the
  sideways test does not fire for it either.

- **Every item of a JSON `POST /batches` request is refused, so that endpoint checks nothing.** It
  takes references to labels — a `label_id` and the application's values — and says the server will
  find the image. There is no image store for it to find one in, so every item comes back as a
  refusal carrying `ENGINE.INPUT.LABEL_IMAGE_MISSING` and the batch reports zero labels checked. The
  alternative to refusing was to run the reader and the rules over a stand-in and report a verdict
  about something that is not the label, which would be worse. The path that works is `POST /`,
  which carries the files themselves, and it is what the form uses. See `docs/decisions.md#0020`. For an agent this means the JSON endpoint is usable only for
  its shape — the batch id, the queue, the SSE stream — and never for an answer about a label.
