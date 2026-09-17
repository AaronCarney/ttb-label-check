# TTB Label Check

Checks a photograph of an alcohol beverage label against the application filed for it, element by
element, and tells the reviewing agent which fields match, which do not, and which need a person to
look. The decision to approve or reject stays with the agent.

**The approach, the tools and the assumptions are in [docs/approach.md](docs/approach.md).**
How the requirements were derived from a brief that supplied none, the constraints nobody chose,
what is proven and what is not, and what changed while it was being built.

## Deployed URL

**https://ttb.aaroncarney.me**

The host is settled — Google Cloud Run, argued in [decision 0025](docs/decisions.md#0025) — and the
deploy is one command. Cloud Build builds the `Dockerfile` at the root of this repository from an
export of the current commit, and Cloud Run serves the image it produces, so nothing is built on a
developer's machine and an untracked file cannot reach the build:

```bash
scripts/deploy.sh --check                   # every check that needs no network; deploys nothing
TTB_GCP_PROJECT=your-project scripts/deploy.sh
```

That address is this project's own hostname rather than the one Cloud Run issues. A small Cloudflare
Worker in `edge/` answers it and forwards to the service, addressing the origin by its own hostname
because Cloud Run's front end routes on the Host header, and it signs each request with a Google ID
token minted from a key held as a Worker secret. [Decision 0028](docs/decisions.md#0028) argues why
the design closes the Cloud Run URL with IAM rather than hiding it — a request IAM denies is never
billed — and [0029](docs/decisions.md#0029) records the rate limit that was meant to sit beside it.
**Neither is the state of the deployed service, and the code says so where it is measured.** The
service is deployed with `TTB_PUBLIC=1` so that a reviewer can reach it, which grants the invoker
role to everyone: measured on 2026-09-17, the Cloud Run URL answers an uncredentialed request with
200, so the hostname above is the front door and not the only way in. The rate limit denies nothing
either. What actually bounds the meter is the two-instance cap in `scripts/deploy.sh`. The Worker
comment in `edge/src/index.js` carries both measurements. Deployed with `npx wrangler deploy` from
that directory; the key is never in this repository.

`--check` is what proves the repository is deployable without making it public: it runs every
precondition the deploy has that needs no network, and names any that fails. It runs as part of the
test suite.

### The five-second requirement is measured, and it is not met

R15 in [the requirements](specs/0001-label-verification/requirements.md) and NFR-1 in
[the PRD](docs/PRD.md) are one promise, and both mark it P0: 95 percent of single checks show
results within five seconds. **Measured on the deployed service on 2026-09-16, it comes in under
that.** Three runs, each posting a warm-up submission whose time is thrown away and then all 38 test
submissions one at a time:

| Address the run used | Inside five seconds |
| --- | --- |
| The Cloud Run URL, directly | 33 of 38 — 87% |
| `ttb.aaroncarney.me`, through the Worker | 34 of 38 — 89% |
| A local authenticated proxy, which adds a hop and inflates the figure | 27 of 38 — 71% |
| `ttb.aaroncarney.me`, with the service given eight cores instead of four | 35 of 38 — 92% |

The requirement is 95%. **The misses are narrow and they cluster:** on the two runs that describe
what a reviewer actually meets, every check that missed landed between 5.00 and 5.21 seconds, and
the fastest of them missed by two hundredths of a second. A fourth run earlier the same evening
passed this assertion outright, so the true share sits near the line rather than below it, and a
single figure would misrepresent it.

**Cores are not the lever.** Doubling the service to eight moved one check of thirty-eight, which is
smaller than the spread between two runs at the same size, so the figure above is not evidence that
more hardware fixes this. The service is back at the four cores
[decision 0025](docs/decisions.md#0025) argued from the free tier's limits, and the reading path
itself has never been tuned for speed.

The measurement runs against whatever URL it is given, and skips when there is none:

```bash
TTB_DEPLOY_URL=https://ttb.aaroncarney.me uv run pytest tests/test_deploy_healthz.py
```

`tests/test_deploy_healthz.py` is what produced every figure above.

Everything below runs today from a clone, which is the other half of the same deliverable.

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

It handles one label at a time through a web page, or a batch of them through an upload that streams
results back as each finishes. In a batch the first label is checked on its own and the rest run
behind it, which is the ordering rather than an accident of it: the reviewer gets a real result in
seconds instead of a progress bar, and starts working while the remainder runs. The batch then paces
itself against how fast they are actually reading, rather than racing ahead to compute results
nobody has asked for yet.

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

Then open <http://localhost:8000>. Upload a label image, fill in the application fields beside it,
and submit. To try the batch path, open `/batches`, or take the sample archive the page offers —
it is built from real label images shipped in this repository.

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
quotas and limits](https://docs.cloud.google.com/run/quotas), under *Request limits for Cloud Run*,
read 2026-09-17. Running locally there is no Cloud Run in the way, but the caps are enforced by the
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

**The measured figure is 93% branch coverage over `app/`**, measured 2026-09-17 from a run of the
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

Three stages, and the split between them is the design:

**1. Read.** An OCR engine finds text and its position on the image, and a parsing layer turns that
into seven fields — brand name, class/type, alcohol content, net contents, name and address, country
of origin, and the health warning — each carrying the box on the image it came from. The reader is
an interface with two implementations behind it, so the local engine and the hosted model are
swappable without anything downstream knowing which ran.

**2. Compare.** A rule pack decides. The rules are YAML, across a common pack and one per beverage
class, and each names a validator by string from a registry. A rule says what it checks, which
regulation it comes from, and what outcome each result maps to. Adding a check is a YAML edit, and
the reference tables the rules read (volume units, class/type designations, characters-per-inch
limits) are data files rather than code.

**3. Report.** Each check returns a verdict, a reason code, and a citation to the regulation it came
from, so a reviewer can see why and not just what. The result also carries the region of the image
the reading was taken from, and the interface deliberately does not draw it on the label: that box
is measured in the frame the reader worked in — the photograph shrunk to fit and sometimes turned
upright — and not in the photograph the page displays.

**No model decides a verdict.** A model may read a label — that is the part no deterministic code
can do — but the comparison is rules over the text it produced. The same label and the same
application give the same answer every time, with a citation attached. An earlier layer that sent
finished results to a language model for a second opinion was removed for exactly this reason
([decision 0009](docs/decisions.md#0009)).

**What an upload may be.** The service accepts **31.5 MB** in one request, **1.5 MB** for any single
image, **100** images in one batch, and refuses any image whose header declares more than
**50,000,000** pixels. Each number is derived from a constraint rather than picked, and
`app/api/limits.py` states the derivation beside it: the request cap sits just under Cloud Run's 32
MiB HTTP/1 request limit ([Cloud Run quotas and
limits](https://docs.cloud.google.com/run/quotas)) so the refusal comes from this service with a
message naming the file, rather than from Google with a message naming nothing; the per-image cap is TTB's own, since COLAs Online
refuses a label image over 1.5 MB and nothing larger can ever have been filed; 100 images of label
size is about 18 MB, inside the request cap, and the PRD's 300 submissions in ten minutes is three
such batches.

**What 100 images per batch is worth in practice.** The file count and the request cap only agree
while the images are small. A hundred files fit one request only if they average under **322.3 KB**;
above that the request cap is the real limit and the hundred is unreachable. At the 1.5 MB per-image
cap **20** fit one request — 21 of them come to 31.5 MB exactly, and the multipart framing around
each file is what tips it over. At the largest label in this project's own corpus, 547 KB, **59**
fit. The corpus median of about 184 KB is why a batch of ordinary labels does fit, and is where the
18 MB above comes from. A reviewer sending a hundred large files is refused by the request cap, by
name, and should send fewer. The arithmetic is `files_that_fit()` in `app/api/limits.py`; this
paragraph is held to it by `tests/test_readme_content.py`, not written out by hand. The pixel ceiling is the guard against a decompression bomb — a few kilobytes of PNG
can declare a 50,000 × 50,000 canvas, which no byte cap catches — and it is checked against the
file's header before anything is decoded. A refusal carries a reason code and a sentence saying
which file was refused and what the limit is.

**Almost nothing is kept, and what is kept is named.** There is no database and no COLA
integration. Batch state lives in the process and is dropped when the response is returned or the
server stops, and nothing the form collects reaches a log. Two things are written to a directory on
disk and swept after seven days. The uploaded label image, so the result page can still show it
after a restart or on a second worker. And, on a check run against a single label, the result
itself — because an override has to have something to amend, and a single label is in no batch to
hold it. That second file is stripped before it is written: the value read off the artwork, the
value the application declared, each finding's explanation, any model prose and the uploaded file's
name are blanked, leaving what an override actually amends — the dispositions, the confidences, the
rule ids, the CFR citations, the reason codes, the evidence boxes and the audit trail. One piece of
free text survives, a reviewer's own justification for an override, which is the agency's record of
its decision rather than the applicant's material. The PRD's C-2 asks for no retention at all; two
files on disk is still not that, and [decision 0018](docs/decisions.md#0018) says why and what a
real deployment would do instead.

**What a log may contain.** Log lines are an allow-list: only named fields are written, anything
else attached to a line is dropped, and the fields that could carry applicant material — the
application's contents, the image bytes, the text read off the label — are blanked by a second
pass. Both have tests. The name of the uploaded file counts as applicant material too, because it
is whatever the uploader typed and a file named after a person names that person. It reaches the
page as display text under its own name, and the identifier a log line correlates on is minted by
the app rather than built from it, so the two are never the same string. A test runs a person-named
file through both the refusal path and the ordinary path and reads what the real log handler
emits.

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

Measured on 2026-09-16 over the whole real corpus — all 30 labels in
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
| `brand` | the brand name the label carries | 16 of 30 |
| `class_type` | the class and type designation | 19 of 30 |
| `abv` | the stated alcohol content | 25 of 30 |
| `net_contents` | the stated net contents | 22 of 29 |
| `name_address` | the bottler's or importer's name and address | 22 of 30 |
| `origin` | the country of origin | 24 of 30 |
| `warning_present` | that the health warning is on the label at all | 30 of 30 |
| `warning_exact` | that the warning reads word for word as the regulation sets it | 14 of 30 |
| `warning_heading_caps` | that `GOVERNMENT WARNING:` is capitalised as required | 30 of 30 |

The figures are counts, not percentages, and the denominator differs between checks. One label
prints no net contents on any face, so `net_contents` is scoreable on 29 rather than 30: a check
the label itself cannot settle is left out rather than counted against the reader. Thirty labels
is a small denominator, and a percentage drawn from it would read as a precision this corpus does
not carry. See `docs/decisions.md#0027`.

**These figures are in-sample, and there is no held-out set.** The reader's heuristics — the
box-merge ratios, the gate that decides when to re-read a label rotated, the field patterns — were
tuned against these same 30 labels, and the table above scores them on the same 30. So each figure
is an upper bound on what the reader does with a label it has never seen, not an estimate of it.
Reserving a held-out split from 30 labels was judged worse than not having one: a ten-label test set
would leave both halves too small to measure anything, and the corpus is the whole of what this
project could source. The figure this matters most for is `warning_present`, 30 of 30, because that
is what licenses the one rule in the pack allowed to reject a label on the reader finding nothing —
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
  against by hash, so a change to the regulation is a deliberate edit and not a silent drift.
- **What is kept is kept for seven days and no longer.** Application data lives only as long as the
  request that carried it. On a single-label check the result is written to disk so a reviewer can
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
  labels and not others, it says on which it could not and sends that point to a reviewer. Where it
  could not be made correct at all, it is switched off in the rule pack rather than returning a
  verdict it has not earned, and it is named under Limitations. A wrong verdict on a real label is
  the one failure this product cannot have, and the two kinds of wrong are not equal. A false
  rejection lands on the applicant, who goes back round a filing process that takes weeks, and it is
  the error that would end a pilot. A false pass lands on the agent, who rules on every finding
  anyway and is the last check either way. So the design leans toward sending a doubtful point to a
  person, and the cost of that lean lands on the reviewer, as the extra items under Limitations.
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
| What changed and when? | [CHANGELOG.md](CHANGELOG.md) |

## Limitations

Checks this app does not make, and why. The first five each name the decision record that settled
them, and each is switched off in the rule pack rather than reporting a verdict it has not earned.
The sixth is different: those requirements were never decided on at all, which is the point of the
entry, so it cites nothing and nothing in the pack switches them off.

- **An upload with no application is read but not checked.** The beverage the application declares
  is what decides which rules apply, so a label submitted on its own is read and reported, and no
  check runs against it — including the government-warning checks, which every beverage shares but
  which are still written per beverage class. See `docs/decisions.md#0010`. For an agent this means
  the app is no use for a quick look at a label on its own: the application's values have to be
  entered before anything is checked.

- **The wording of an alcohol-content statement is not checked.** The app checks that a label states
  its alcohol content where the regulations require one, and that the figure on the label is the
  figure the application declared. It does not check that the statement is phrased as 27 CFR
  §4.36(b)(1), §5.65(b) and §7.65(b) require, because the reader returns the percentage it found and
  not the words the label printed. See `docs/decisions.md#0011`. A label stating the right figure
  in the wrong words passes this check, so the phrasing is still the agent's own read.

- **A country of origin is read only as the application's English name.** Customs marking rules also
  accept the country's name in the language of the country, an abbreviation that unmistakably
  indicates it, and the adjectival form — "HECHO EN MEXICO", "U.K.", "Irish" (19 CFR §134.45(b),
  (c)). The app does not read those, so an import that writes its origin one of those ways is sent
  to a reviewer rather than being matched or rejected. See `docs/decisions.md#0016`. On a batch of
  imports this is the main source of extra manual work — a compliant label lands in the review pile
  because the app cannot read the form it used, not because anything is wrong with it.

- **The health warning's typography and placement are not checked.** The app checks the warning's
  words, that "GOVERNMENT WARNING" is present, and that those two words are in capitals. It does not
  check that the warning sits on a contrasting background (27 CFR §16.22(a)(1)), its characters per
  inch (§16.22(a)(4)), its type height (§16.22(b)), or that it stands separate and apart from other
  information (§16.21). The first three need the colour of the ink or the physical scale of the
  label, and a photograph carries neither; separateness is visible in a photograph but no reader
  measures it yet. Each of those rules stays in the pack with its citation and the reason it is
  switched off, and a switched-off rule produces no finding at all, so a label is never passed or
  rejected on one. TTB says it does not routinely review
  labels for type size, characters per inch or contrasting background either. So the agent's eye is
  the only check on warning typography, exactly as it is today — the app neither helps here nor
  claims to. See `docs/decisions.md#0006` and `docs/decisions.md#0013`.

- **Bold type in the warning's heading is reported, not decided.** §16.22(a)(2) requires the heading
  in bold as well as in capitals. Bold weight is a stroke-width measurement on the heading's own
  region of the image, and the reader cannot always take it. Where it could not, the label goes to a
  reviewer on that point rather than being rejected for a boldness nobody measured. The capitals are
  read from the heading's text and are still decided. The cost is a steady trickle of review items
  on labels that are very likely fine. See `docs/decisions.md#0013`.

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
