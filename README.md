# TTB Label Check

Checks a photograph of an alcohol beverage label against the application filed for it, element by
element, and tells the reviewing agent which fields match, which do not, and which need a person to
look. The decision to approve or reject stays with the agent.

## Deployed URL

Not up yet; the URL goes here when it is published.

The host is settled — Google Cloud Run, argued in [decision 0025](docs/decisions.md#0025) — and the
deploy is one command. Cloud Build builds the `Dockerfile` at the root of this repository from an
export of the current commit, and Cloud Run serves the image it produces, so nothing is built on a
developer's machine and an untracked file cannot reach the build:

```bash
scripts/deploy.sh --check                   # every check that needs no network; deploys nothing
TTB_GCP_PROJECT=your-project scripts/deploy.sh
```

`--check` is what proves the repository is deployable without making it public: it runs every
precondition the deploy has that needs no network, and names any that fails. It runs as part of the
test suite.

### The five-second requirement is not verified

R15 in [the requirements](specs/0001-label-verification/requirements.md) and NFR-1 in
[the PRD](docs/PRD.md) are one promise, and both mark it P0: 95 percent of single checks show
results within five seconds. **No run has confirmed it, and this file publishes no figure for it.**

Speed belongs to the machine doing the reading, and this prototype is built to read on the deployed
service rather than on a developer's computer, so a number measured here would describe the wrong
hardware. The service is not up, so the measurement has not been taken.

The check itself is written and waiting. `tests/test_deploy_healthz.py` posts every test submission
to the deployed single-check route one at a time, throws away the first as a cold start, and asserts
the share that came back inside five seconds. It skips while there is no URL and runs the moment
there is one:

```bash
TTB_DEPLOY_URL=<the URL the deploy printed> uv run pytest tests/test_deploy_healthz.py
```

Everything below runs today from a clone, which is the other half of the same deliverable.

## What it is

TTB's compliance agents review roughly 150,000 label applications a year, and most of each review is
matching: does the brand name printed on the artwork say what the application says, is the alcohol
content the declared one, is the Government Health Warning present and word for word. A simple
application takes five to ten minutes by eye. In peak season importers file hundreds at once.

This app does the matching. You give it an application's declared values and the label images filed
with it; it reads the label, compares the two, and returns one verdict per element with the rule and
the regulation behind it. Three outcomes only — **match**, **mismatch**, or **needs review**, which
the interface labels Pass, Fail and Needs review — and the third is a real answer, used wherever the
app can see the element but cannot honestly decide it.

It handles one label at a time through a web page, or a batch of them through an upload that streams
results back as each finishes.

## Getting started

You need [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer. Nothing else — **no API key, no
account, and no outbound network call.** The reader that turns a photograph into text runs inside the
process, and its models are installed with the dependencies.

```bash
git clone https://gitlab.com/aaroncarney1/ttb-label-check.git
cd ttb-label-check
uv sync
uv run task demo
```

Then open <http://localhost:8000>. Upload a label image, fill in the application fields beside it,
and submit. To try the batch path, open `/batches`, or take the sample archive the page offers —
it is built from real label images shipped in this repository.

The first label is slower than the rest: the OCR models are read off disk once, on first use, and
kept for the life of the process.

### The container path

Same app, one command, if you would rather not install anything:

```bash
docker compose up demo
```

It serves the same <http://localhost:8000> and needs no secrets either.

### Using a hosted reader instead

There is a second reader that sends label crops to a hosted vision model. It reads harder images
more accurately and costs money per label. It is off by default and is not needed for anything in
this README:

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
the reading was taken from; the interface does not draw that region on the label yet.

**No model decides a verdict.** A model may read a label — that is the part no deterministic code
can do — but the comparison is rules over the text it produced. The same label and the same
application give the same answer every time, with a citation attached. An earlier layer that sent
finished results to a language model for a second opinion was removed for exactly this reason
([decision 0009](docs/decisions.md#0009)).

**Nothing is kept.** Batch state lives in the process and is dropped when the response is returned or
the server stops. There is no database and no COLA integration.

## Tools, and why each one

| Tool | What it does here | Why this one |
|---|---|---|
| FastAPI + Uvicorn | HTTP, the server-side page shells, and the batch event stream | Async server-sent events for batch progress, and Pydantic request and response models for free |
| Pydantic v2 | Every envelope, rule definition and settings object | One schema layer for the YAML loader, the API and the config, so a malformed rule pack fails at load rather than mid-review |
| Jinja2 + a React island | Pages are server-rendered; one bundled component tree handles the image-and-evidence area | The interactive part needs real keyboard semantics over bounding boxes; the rest does not need a client framework, and the built bundle ships in the repository so no Node is needed to run this |
| RapidOCR on ONNX Runtime | The default reader, on CPU | Ships its own models in the wheel, so a clone needs no download, no key and no GPU |
| RapidFuzz | Brand-name similarity scoring | The brand check needs a graded score, not a yes or no, because a dropped apostrophe is not a different product |
| PyYAML | Loads the rule packs and reference tables | The rules are data a compliance reader should be able to read |
| uv | Dependency resolution and the lockfile | One locked environment, reproducible from a single binary |
| pytest | The suite | — |

The optional hosted reader calls a hosted OpenAI vision model, pinned to a dated snapshot so two
runs of the same label agree. `.env.example` names the snapshot in force.

## Reading accuracy

**Not published yet, on purpose.** This project puts no number in front of a reviewer that a run on
this machine did not produce, and the reading-accuracy run has not happened.

The harness is written and committed. It scores the reader against the real labels in
`tests/fixtures/labels`, using the transcription in that corpus's manifest as the answer key:

```bash
uv run python -m eval.read_accuracy
```

It reports each check separately rather than one blended figure, because the checks fail in
different ways and an average hides that. The figures go here when the run lands.

## Assumptions

- **The application is right and the label is what is being checked.** Where the two disagree, the
  app reports a mismatch on the label; it never assumes the application is the error.
- **The application names the beverage type**, and that is what selects the rule pack. A label
  submitted with no application is read but not checked, because nothing says which rules apply.
- **A submitted photograph is meant to be legible.** Making a poor photograph readable is out of
  scope; where the app cannot read a field it says so rather than guessing at one. How well it
  tells a poor photograph from a good one is a separate question, and an open one.
- **The warning text is fixed.** 27 CFR 16.21's wording is pinned as a committed asset and compared
  against by hash, so a change to the regulation is a deliberate edit and not a silent drift.
- **Nothing sensitive is stored.** Images and application data live only as long as the request that
  carried them, which keeps the prototype clear of retention and PII obligations it is not built to
  meet.
- **No integration with COLA or any other TTB system**, which was an explicit constraint from the
  systems administrator in the brief.

## Trade-offs

- **A narrow core that works, over broad coverage that does not.** Where a check can be made on some
  labels and not others, it says on which it could not and sends that point to a reviewer. Where it
  could not be made correct at all, it is switched off in the rule pack rather than returning a
  verdict it has not earned, and it is named under Limitations. A wrong verdict on a real label is
  the one failure this product cannot have.
- **Determinism over capability.** Rules decide, models only read. The cost is that anything needing
  judgement beyond a scored comparison goes to a person rather than being resolved automatically.
- **Local CPU reading by default, accuracy second.** The hosted reader is better on hard images. It
  is not the default, because a reviewer should be able to clone and run this with no account.
- **State in memory.** A server restart loses an in-flight batch and the reviewer re-uploads. A
  prototype that stores nothing is easier to trust than one that stores label images.
- **Scored brand matching rather than exact matching.** A punctuation difference scores just below
  identical and passes, with the score shown, rather than sending every dropped apostrophe to a
  person. What it buys and what it costs are argued in
  [decision 0017](docs/decisions.md#0017).

## What the brief asked for

The seven label elements the brief lists, and where each is answered:

| Element | Status | Where |
|---|---|---|
| Brand name | Checked — scored against the application's brand, fanciful and trade names | `rules/wine/wine.yaml`, `rules/spirits/spirits.yaml`, `rules/malt/malt.yaml` |
| Class/type designation | Checked — matched against the application and against the designation tables; for spirits, also against the standards of identity | `rules/tables/wine_designations.yaml`, `rules/tables/malt_designations.yaml`, `rules/spirits-deep.yaml` |
| Alcohol content | Checked — format, and the figure against the application. Required-or-not follows the beverage class | the three class packs |
| Net contents | Checked — compared as a quantity, with units converted before comparing | `rules/tables/volume_units.yaml` |
| Name and address | Checked — applicant or declared trade name, plus city and state | the three class packs |
| Country of origin | Checked for imports, against the application's English country name. The other forms customs accepts are a named limitation | the three class packs |
| Government Health Warning | Checked — present, word for word against the pinned 27 CFR 16.21 text, heading in capitals, heading boldness measured where it can be. The typography rules are switched off, because a photograph does not carry what they measure | `rules/common/health_warning.yaml`, `assets/warnings/govt_warning_16_21.txt` |

Both deliverables:

| Deliverable | Status |
|---|---|
| Source code repository — all source, a README with setup and run instructions, and documentation of approach, tools and assumptions | This repository and this file |
| Deployed application URL — a working prototype Treasury can access and test | Host settled and the deploy is one command; standing the service up is the owner's to authorise. See "Deployed URL" above |

## Where to look next

| Question | Document |
|---|---|
| What is this supposed to do, and for whom? | [docs/PRD.md](docs/PRD.md) |
| How is it put together? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Why was it done this way and not another? | [docs/decisions.md](docs/decisions.md) |
| What does the regulation actually say? | [docs/reference/](docs/reference/) |
| What changed and when? | [CHANGELOG.md](CHANGELOG.md) |

## Limitations

Checks this app does not make, and why. Each entry names the decision record that settled it, and a
check listed here is switched off in the rule pack rather than reporting a verdict it has not earned.

- **An upload with no application is read but not checked.** The beverage the application declares
  is what decides which rules apply, so a label submitted on its own is read and reported, and no
  check runs against it — including the government-warning checks, which every beverage shares but
  which are still written per beverage class. See `docs/decisions.md#0010`.

- **The wording of an alcohol-content statement is not checked.** The app checks that a label states
  its alcohol content where the regulations require one, and that the figure on the label is the
  figure the application declared. It does not check that the statement is phrased as 27 CFR
  §4.36(b)(1), §5.65(b) and §7.65(b) require, because the reader returns the percentage it found and
  not the words the label printed. See `docs/decisions.md#0011`.

- **A country of origin is read only as the application's English name.** Customs marking rules also
  accept the country's name in the language of the country, an abbreviation that unmistakably
  indicates it, and the adjectival form — "HECHO EN MEXICO", "U.K.", "Irish" (19 CFR §134.45(b),
  (c)). The app does not read those, so an import that writes its origin one of those ways is sent
  to a reviewer rather than being matched or rejected. See `docs/decisions.md#0016`.

- **The health warning's typography and placement are not checked.** The app checks the warning's
  words, that "GOVERNMENT WARNING" is present, and that those two words are in capitals. It does not
  check that the warning sits on a contrasting background (27 CFR §16.22(a)(1)), its characters per
  inch (§16.22(a)(4)), its type height (§16.22(b)), or that it stands separate and apart from other
  information (§16.21). The first three need the colour of the ink or the physical scale of the
  label, and a photograph carries neither; separateness is visible in a photograph but no reader
  measures it yet. Each of those rules stays in the pack with its citation and the reason it is
  switched off, and a switched-off rule produces no finding at all, so a label is never passed or
  rejected on one. TTB says it does not routinely review
  labels for type size, characters per inch or contrasting background either. See
  `docs/decisions.md#0006` and `docs/decisions.md#0013`.

- **Bold type in the warning's heading is reported, not decided.** §16.22(a)(2) requires the heading
  in bold as well as in capitals. Bold weight is a stroke-width measurement on the heading's own
  region of the image, and the reader cannot always take it. Where it could not, the label goes to a
  reviewer on that point rather than being rejected for a boldness nobody measured. The capitals are
  read from the heading's text and are still decided. See `docs/decisions.md#0013`.
