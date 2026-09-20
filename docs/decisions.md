# TTB Label Check — Decision Document

**Settled forks and their rationale. Nothing else.** One entry per fork: what was chosen, what was
rejected by name, and the concrete constraint that decided it.

Status and released changes go in `CHANGELOG.md`. Requirements go in `docs/PRD.md`, and changes to
the PRD's approved text in `docs/PRD-decisions.md`. Mechanism and layout go in `ARCHITECTURE.md`.
Dated findings go in `docs/research/`. Regulation text the app checks goes in `docs/reference/`.

**This document governs nothing.** It records why the project went one way instead of another, for
someone asking "why was this done like this?". Cite the constraint an entry records, or the document
that governs — never an entry itself as the reason something must be done. Where an entry and a
governing document disagree, the governing document wins and the entry is a stale record to date and
correct.

Consolidated out of sixteen separate files under `docs/decisions/`. The entry numbers
are the numbers those files carried, so an
existing citation to `docs/decisions/0011` is entry 0011 here and links resolve as
`docs/decisions.md#0011`.

**Older entries use "reject" loosely.** Where an entry says a check rejects a label, read that the
check reports mismatch at the rule pack's `reject` severity; where it says a label goes or is sent to
a reviewer, read that the check reports needs review. The product decides nothing: it reports match,
mismatch or needs review, and the agent, who reviews every label, decides (`docs/PRD.md` SC-1, FR-11).

When a decision changes, add a dated entry below the original. Do not edit the original away; the
superseded reasoning is what makes the change legible later.

---

<a id="0001"></a>
## 0001. Semantic versioning

**Chosen.** The project's version follows Semantic Versioning 2.0.0 and reads `MAJOR.MINOR.PATCH`,
starting at `0.0.0`. Once a stack is chosen the version lives in that stack's package manifest.

**Rejected.** *Calendar versioning* (`YYYY.MM.N`) — it dates a release but cannot say whether
anything that worked before has stopped working, which is the question a reviewer asks of a new
version. *No version* — dates and commit hashes cannot mark a release point that someone discussing
the work can name.

**Because** every change needs a number that says whether it breaks something that worked before,
and Semantic Versioning is the scheme whose positions carry that meaning.

<a id="0002"></a>
## 0002. Stakeholder priority depends on the phase

**Evidence:** the brief, `specs/0001-label-verification/PRD.md`.

**Chosen.** Four people in the brief shape what the prototype does. While it is a prototype their
asks weigh in this order, and the weights are what settle it when two asks pull against each other:

1. **Sarah Chen, Deputy Director of Label Compliance — 100%.** She sponsors the work, decides
   whether it goes further, and set its firmest limits: results in about 5 seconds, a tool her
   73-year-old mother could figure out with "no hunting for buttons", and batch uploads of 200–300
   labels. The batch ask is also Janet's, of the Seattle office, named but not interviewed.
2. **Dave Morrison, senior compliance agent of 28 years — 90%.** Whether agents take the tool up
   turns on reactions like his. He asks for judgement on trivial differences ("STONE'S THROW" on the
   label against "Stone's Throw" in the application) and for a tool that does not make his work
   harder.
3. **Jenny Park, junior compliance agent of 8 months — 80%.** She names the strictest check — the
   warning word for word with "GOVERNMENT WARNING:" in capitals and bold — and the hardest input,
   photos taken at angles, in bad light or with glare, which she herself places as possibly out of
   scope.
4. **Marcus Williams, IT Systems Administrator — 70%.** His limits bind any production path more
   than the prototype: no COLA integration, nothing sensitive stored, outbound traffic blocked to
   many domains. For the prototype he asks only "Just don't do anything crazy."

In production the order changes: Marcus and the IT leadership above him become the deciders, through
FedRAMP, authority to operate and PII review, and Dave's informal influence counts for less. The
prototype is built for the first order and records how it would meet the second.

**Rejected.** *Weighing all four equally* — it hides whose asks decide whether the prototype goes
further. *A power-and-interest grid alone* — it files Dave as low power although adoption turns on
senior agents like him, and it gives Marcus most weight in the phase where he asked for least.

**Because** the brief states each of these in the stakeholders' own words: Sarah's three asks, which
it sets in bold; Dave's "You need judgment"; Jenny's "It has to be **exact**"; and Marcus's "for a
prototype? Just don't do anything crazy."

<a id="0003"></a>
## 0003. How build choices are judged

**Chosen.** Every build choice — scope, extraction, stack, host — is judged by these criteria in
this order. A choice that fails an earlier criterion is out, however well it does on a later one.

1. **It meets the firmest asks, measured on the deployed prototype with real labels.** Results
   within about 5 seconds per label (Sarah); the warning checked word for word with its heading in
   capitals and bold (Jenny); trivial differences judged as the same value (Dave). Vendor figures
   and fake labels do not count as evidence.
2. **A working core comes first.** The label elements common to all three beverage types are checked
   before any one type is checked in depth, and batch upload is part of the core.
3. **Every result can be checked by the agent.** It shows which element, what was read, what was
   expected and which rule applied. Where the prototype cannot tell, it says "needs review" rather
   than guess.
4. **Anyone can use it unaided.** A public URL with no sign-in, sample labels one click away, and a
   README that is enough to run it.
5. **It fits Marcus's limits and has a path through the firewall.** Every outbound service is named,
   and the part that calls an outside service can be replaced by one running inside the agency's
   network without a rewrite. Each option states what it would cost at the agency's volume and what
   federal authorization it would need.
6. **It is the smallest thing that meets 1 to 5 in the time left.** Nothing is built only for show.
7. **It is free or cheap.** No money goes on anything merely cosmetic.

What the README and the results claim is limited to what was measured, and says under what
conditions.

**Rejected.** *Engineering merit alone* — for a federal agency, cost and authorization can overturn
an engineering pick, and leaving them to a later review lets the design assume away limits it did not
know about. *Weighted scores summed across criteria* — a strong score on cost could then buy back a
missed 5-second limit, and the brief's own account of a failed pilot shows that a slow tool is
abandoned whatever else it does well.

**Because** of stakeholder priority ([0002](#0002)) and the brief's line that "a working core
application with clean code is preferred over ambitious but incomplete features".

<a id="0004"></a>
## 0004. The prototype runs locally from a clone, and also deploys

**Chosen.** The product is built to run on a reviewer's own machine first: a clone, one install step
and one command to start, with everything it needs contained in the repository. It needs no account,
no API key and no outbound network call to do its job. Deployment is a thin layer over that same app
— a container image and a start command — so a public URL is a short step at the end rather than a
separate build. Both are delivered; they are separate deliverables, not alternatives.

**Rejected.** *Deployed only, with the README pointing at the URL* — it leaves deliverable 1's
"setup and run instructions" unmet, and "attention to requirements" is one of the six evaluation
criteria. *Local only, with deployment left as a stated limitation* — it leaves deliverable 2 unmet
and fails the reviewer who wants to test the prototype without installing anything. *Building for
the host first and making local work follow* — hosted-first designs acquire dependencies on the
host's storage, secrets and networking, and the agency firewall is precisely the constraint this
product has to survive.

**Because** the brief's Deliverables section lists "README with setup and run instructions" under the
repository and "Deployed Application URL — Working prototype we can access and test" as a second
item; and the owner instructed that this version runs locally with a cloud option if
time allows, and that "everything we include [is] contained within the app itself if possible to make
installing simple".

<a id="0005"></a>
## 0005. Two readers behind one interface, local by default

**Evidence:** `docs/research/2026-09-15-extraction.md`.

**Chosen.** Reading a label image into fields is one replaceable component behind one interface, with
two implementations:

- **A local CPU OCR engine, shipped in the app and used by default.** It needs no key and makes no
  outbound call, so a clone runs and checks labels out of the box, and the product works inside a
  network that blocks outbound traffic.
- **A hosted vision model, used when a key is present**, enabled by an environment variable. Where
  it is available it reads more accurately; where it is not, the product still works.

Neither reader decides anything. Rules decide; the reader reports what it saw with a confidence, and
the product says "needs review" where the reader is unsure.

**Open point.** Measured on 13 real labels, the hosted model returned the government
health warning word for word on 12 of 13 and the local engine with simple parsing on 6 of 13. The
warning must be checked exactly, so the local reader's parsing has to close that gap, and the shipped
accuracy figure is whatever the evaluation run measures once it has.

**Rejected.** *Hosted model only* — fastest to good accuracy and what the measurement favours, but a
product that cannot run without an outbound call cannot run in the environment it is for, and a clone
would be unusable without an account and a key. *Local engine only* — fully self-contained and it
satisfies the firewall constraint completely, but at 6 of 13 on the exact warning it does not yet meet
the check the brief is most explicit about, and committing to it alone removes the evidence that a
better reader exists. *Choosing the reader per request at run time, by content* — more moving parts
to explain and to test, for an accuracy gain nobody has measured; the interface leaves it available
later.

**Because** the brief's IT interview states that outbound traffic is blocked to many domains and an
earlier pilot lost features to blocked endpoints, the owner instructed that everything be "contained
within the app itself", and [0003](#0003) criterion 5 requires that the part calling an outside
service be replaceable by one running inside the agency's network without a rewrite.

**Measured.** Hosted model 2.03 s median, 2.75 s worst, one at a time, on 13 real applications; local
CPU OCR 1.18 s median, 2.60 s worst. Per-field accuracy for both is tabulated in the research file.

<a id="0006"></a>
## 0006. The health warning's typography rules are out of scope

**Extended by** [0013](#0013), which settles what these rules answer instead.

**Chosen.** Four rules in the health-warning pack are switched off, each carrying the reason in its
own `notes` field:

| Rule | What it checks | Citation |
|---|---|---|
| `common.warning.contrasting_bg` | The warning sits on a contrasting background | §16.22(a)(1) |
| `common.warning.cpi_max` | Characters per inch, against the §16.22(a)(4) table | §16.22(a)(4) |
| `common.warning.type_size_min` | Minimum type size | §16.22(b) |
| `common.warning.separate_apart` | The warning is separate and apart from other information | §16.21 |

The app checks the warning's words and their order, that "GOVERNMENT WARNING" is present, and that
those first two words are in capitals and bold. It does not check contrast, characters per inch, type
height or isolation. The README states this as a limitation.

A fifth rule, `common.warning.heading_phrase`, is switched off as redundant rather than out of scope:
it asked for evidence named `warning_heading` that no reader produces, so it never ran, and
`common.warning.heading_caps_bold` already checks the same two words along with the capitals and bold
weight §16.22(a)(2) requires.

**Why three of the four cannot be measured from the only input the app has.** Type height and
characters per inch are physical measurements: §16.22(b) sets the minimum in millimetres keyed to
container size — 1 mm at 237 mL or less, 2 mm up to 3 L, 3 mm above — and turning pixels into
millimetres needs the image's physical scale, which a photograph does not carry
(`docs/reference/health-warning.md`, "What an image check can and cannot see"). `type_size_min` as
written compares a point value against a fixed 2.0 and ignores container size altogether, so a pass
from it does not mean what its citation says. Contrast needs the colour of the text and of the
surface behind it, sampled at the warning's exact position, and no reader reports either.
`separate_apart` is different: isolation is a relationship between blocks on the page and a
photograph does carry it, so that rule is unbuilt rather than unbuildable.

The deciding fact is that TTB does not check these itself. The instructions to Form TTB F 5100.31 say
TTB "does not routinely review submitted labels for compliance with applicable requirements for
mandatory label information regarding type size, characters per inch, or contrasting background"
(`docs/reference/health-warning.md`, TTB guidance). A prototype that rejects labels on three measurements the agency does not routinely review would be
wrong about the job.

**Rejected.** *Leave them enabled* — each reads a key no reader emits, so each returns a failure on
every label, compliant ones included; enabled, these four make every submission a rejection. *Pass
when the measurement is absent* — this reports a check as made and passed when nothing was measured,
the exact failure the project set out to avoid: a document or a screen claiming a check the code only
stubbed.
*Build the measurements* — contrast needs colour sampling at the warning's position and the other two
need a known physical scale, meaning container size plus a fiducial or a calibration step in the
upload; that is a larger piece of work than the brief asks for, and the brief's own account of the
warning is Jenny's — the words exactly, with "GOVERNMENT WARNING:" in capitals and bold, which is what
`verbatim` and `heading_caps_bold` check.

**Because** a check that cannot be made must not be reported as made. Between failing every label and
claiming a measurement that never happened, the honest third option is to not run the rule and to say
so in the README.

<a id="0007"></a>
## 0007. A class-and-type designation includes its standard of identity

**Chosen.** The class-and-type rules pass when the label's designation **includes** a recognised class
or type as a run of whole words, not when it equals one. The validator `enumerated_match` takes a
`match_mode` parameter: `exact` stays the default, and the four class-and-type rules set
`contains_designation` — `spirits.class_type.present`, `spirits.class_type.matches_soi`,
`wine.class_type.present`, `malt.class_type.present`. Each list also gains the spellings that appear
on real labels; §5.143(b) permits "whisky" or "whiskey", so both are listed for every whisky entry.

**Why.** A label does not carry a bare standard of identity. It carries the standard with the
qualifiers the regulation permits around it:

| On the label | The standard it declares |
|---|---|
| KENTUCKY STRAIGHT BOURBON WHISKEY | bourbon whisky |
| CALIFORNIA TABLE WINE | table wine |
| INDIA PALE ALE | ale |

Checked by equality against a list of bare standards, every one of those fails. The three qualifier
kinds are all required or permitted by the regulations the rules cite: the state of distillation must
appear adjacent to the designation for the named whisky types (§5.66(f)), and "straight" is part of
the standard itself (§5.143). Whole words, not substrings — a substring test would find "gin" inside
"Virginia" and pass a wine as a spirit.

**Rejected.** *List the full designations* — every state of distillation crossed with straight,
bottled-in-bond and single-barrel, crossed with both spellings of whisky; the list would run to
thousands of entries and would still miss the next one. *Match the last word only* — "KENTUCKY
STRAIGHT BOURBON WHISKEY" ends in "whiskey", which is a class, so the shallow rule would pass, but the
deep rule asks for the type, bourbon whisky, and the last word alone cannot tell bourbon from rye.
*Normalise spellings in Python* — a whisky/whiskey equivalence in the validator puts a fact about the
regulation in code, where the rule pack is the place for it.

**Because** rules decide and a reader only reports, so a rule has to be right about what the
regulation asks. The regulation asks for a designation that declares a recognised standard of
identity, not for a label that repeats the standard's name and nothing else.

<a id="0008"></a>
## 0008. The alcohol-content tolerance rules are out of scope

**Chosen.** Five rules are removed from the pack, with the validators and reason codes that served
only them:

| Rule | Citation |
|---|---|
| `spirits.alcohol.tolerance_band` | 27 CFR §5.65(c) |
| `wine.alcohol.tolerance_band` | 27 CFR §4.36(b)(1) |
| `wine.alcohol.no_class_boundary_cross` | 27 CFR §4.36(c) |
| `malt.alcohol.tolerance_band` | 27 CFR §7.65(c) |
| `malt.alcohol.floor_05` | 27 CFR §7.65(c) |

Gone with them: the `abv_band`, `abv_class_boundary_check` and `abv_hard_floor` validators, the
`abv_actual_pct` field on `ExpectedValue`, and the `CROSSES_CLASS_BOUNDARY` and `BELOW_HARD_FLOOR`
reason codes.

`ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND` **stays in the registry as reviewer vocabulary**, emitted by
no rule. The reviewer console offers it in the override picker and `app/api/overrides.py` refuses any
code the registry does not list, so removing it would make that override fail. A reviewer holding a
laboratory figure the application does not carry is exactly the person who should be able to record
this, which the automatic check could never do.

What stays is every alcohol-content check this product can make: that the label states one where the
application declares one, that the statement is in a permitted format, and that the number on the
label is the number the application declared.

**Why.** Each of those five rules compares the alcohol content **printed on the label** against the
alcohol content **in the bottle**, and that second number comes from laboratory analysis. This
application is given an image of a label and a copy of the application form. It never sees the liquid,
so the figure the rules need does not exist anywhere in its inputs and cannot be obtained from them.
The regulations are real and the tolerances are stated correctly; the rules are simply not answerable
from what a label checker is given.

Keeping them was not neutral. `ExpectedValue.abv_actual_pct` was declared and never written, so all
three validators took their "no value" branch and returned a failure on every label. All five rules
were `severity: reject`, and `compute_disposition` turns any non-warn failure into `fail`. Both
readers emit an alcohol observation even when they find none, so the rules ran every time. The result
was that **no label of any beverage type could be reported as a match** — the exact outcome this
product exists to avoid. The unit tests did not catch it because each supplied `abv_actual_pct` itself
through a test helper, checking arithmetic the product could never reach.

**Rejected.** *Populate `abv_actual_pct` from the application* — the application declares the labeled
value, the other side of the same comparison; comparing a number against itself makes the rule pass on
every label, as wrong as failing on every label and harder to notice. *Lower the severity to `warn`* —
it routes every label to a human reviewer with a reason code naming a discrepancy nobody measured,
converting a false rejection into a false alarm. *Leave the rules in and mark them disabled* — a
disabled rule still reads as a capability in the pack, and a reviewer would reasonably believe the
tolerance is checked. *Accept a laboratory figure as an optional input* — no such field exists on the
TTB Public COLA Registry record the application form is modelled on, and the brief supplies a label
image and an application, not an analysis.

**Cost, stated.** A label whose stated alcohol content differs from the product's true alcohol content
is not detected here, and the README names this as a limitation. Detecting it needs an input this
product is not given.

<a id="0009"></a>
## 0009. The model reasoning layer is removed; the model reader stays

**Chosen.** The optional layer that sent a finished rule result to a language model for a second
opinion is deleted: `app/orchestrator/` and its three tasks, the component that merged the model's
note back into a rule result, the predicate that decided when to call it, and the schema the model
answered in. The `openai` and `anthropic` SDK dependencies go with it, and so does the
development-only route meant to show the model's raw calls.

**The reader that uses a hosted vision model stays** (`app/vision/cloud.py`, [0005](#0005)). It is a
different thing and it is what the brief's AI requirement is about: it turns a photograph of a label
into fields, the step no deterministic code can do. Removing a reasoning layer does not remove the
model from the product.

**Why.** The layer could not change a verdict, by construction, and was switched off by default. Four
independent facts, each verified in the code before deletion:

1. **Its output was discarded.** The merge step matched the model's notes to rule results by rule
   identifier, and neither backend ever set one, so every note arrived unattributable and was dropped.
2. **Even a matched note was cosmetic.** The merge step wrote only to a free-text `message` field, and
   was forbidden by contract from touching the outcome, the severity or the reason code — the three
   values a verdict is made of.
3. **The channel that would have shown it to a reviewer was sealed.** The envelope builder hard-codes
   the field-card's AI suggestion block to "not present".
4. **It was off.** The master switch defaulted to false.

Nothing in `docs/PRD.md` requires it and no decision asks for it. It was 644 lines of subsystem plus
roughly twenty test files, reaching into eighteen files elsewhere — configuration, dependency wiring,
the evaluator, the health check, the metrics timeline. That reach is the cost: every one of those
files had to be read and understood by anyone changing the app, to sustain a layer that provably did
nothing.

**Rejected.** *Turn the switch on and make the layer count* — that means letting a model influence a
compliance verdict, giving up the property that the same label gives the same answer with a citation
attached, to buy a second opinion nobody asked for. *Leave it switched off and untouched* — dead code
is not free; it misleads a reader about what the product does, has to be kept importable, its tests
have to keep passing, and two SDK dependencies stay in the install for a path that never executes.
*Keep the interface and delete the implementations* — the same dead weight in fewer lines, still
suggesting a capability that is not there.

**Because** determinism decided it: a checker that must show a reviewer why it reached a verdict is
worth more than one that consults a model and then ignores the answer.

**Consequence.** The deterministic path is unchanged — every check, verdict and reason code is exactly
what it was. One trace remains on purpose: the per-evaluation telemetry block carries a duration field
for this layer and now always reports zero. It is a required field on the response envelope that the
frontend and the recorded response fixtures both read, so removing it costs a schema change, a
frontend change and a rewrite of every fixture, in exchange for one integer. It stays until something
else changes that schema.

<a id="0010"></a>
## 0010. A label filed without a beverage class is checked against nothing

**Chosen.** **The application decides which rules run, and where it names no beverage, no rule runs.**
An upload that arrives without an application — the drop-zone on the landing page accepts one — is no
longer checked against the distilled-spirits rules. It is checked against nothing. The reply still
carries what the reader read off the label, and its audit trail carries one row saying no rule set
could be chosen:

    rule_id:      ENGINE.RULE_PACK.NOT_SELECTED
    disposition:  needs_review
    evidence_ref: rule_pack/none

**Every reply names the rules that produced it**, whether or not any ran. Where the application does
name a beverage the same row reads `ENGINE.RULE_PACK.SELECTED`, `not_applicable`,
`evidence_ref: rule_pack/wine` — meaning the wine rules together with the ones that apply to every
beverage. The row is written before the label is read, so a reply cut short by an unreadable image or
by the five-second limit carries it too.

**Why.** *The reader's own answer is not evidence.* Both readers tag every reading they produce
`spirits` — `app/vision/local.py:211,242` and `app/vision/cloud.py:265,314` — because nothing on a
bottle reliably distinguishes a wine from a spirit and nothing ever
asked them to try. Until now `app/services/evaluator.py` replaced that tag only when the application
named a beverage, so a wine label filed without an application inherited `spirits` and was checked against the
spirits rules. That is the one failure this product cannot have: the spirits rules include the
standards of identity — `spirits.class_type.matches_application` asks whether the designation on the
label is one of the classes Part 5 Subpart I defines. A wine label reading `TABLE WHITE WINE` is not,
so the app would have reported a compliant wine label as failing a rule that never applied to
it — a rejection manufactured out of a guess nobody made.

*Nothing in the rule model can express "whatever the beverage is".* Every rule declares
`applies_to_classes`, and `app/rules/yaml_engine.py:123` selects a rule only where a reading's class is
in that list. The eight health-warning rules in `rules/common/health_warning.yaml` list all three
beverages and every other rule lists exactly one — checked across all five rule files —
so the warning rules are already independent of the beverage in substance. What stops them running is the
mechanism: `FieldObservation.beverage_class` is a required three-valued field
(`app/schemas/extracted.py:61`) with no way to say "not stated", so a reading has to claim a beverage before any rule will look at it, including the eight
that do not care which. Making those eight run without a beverage means changing the reading model,
the rule model, the loader, the engine and the health-warning rule file. That is the right fix and it
is not this one. Until it lands, an upload with no application gets no health-warning check.

**Rejected.** *Refuse the upload outright, with a 400 and "pick the beverage type"* — the form already
marks the field required (`app/ui/templates/single.html:35`), and
`app/services/application_form.py:152` already refuses a form that fills in any other application
field without it; rejected because two tests deliberately accept an image on its own,
`tests/test_ui_application_fields.py::test_an_image_on_its_own_still_evaluates` and the end-to-end test
named below, so the product has already decided that an image alone is a
thing a reviewer may submit; turning it away is a larger product change than the defect warrants and it
removes the reading as well as the checks. *Run the beverage-independent rules anyway, by tagging the
reading with a fixed beverage and discarding every beverage-specific result* — this keeps the
health-warning check on the image-only path, which is the strongest argument for it, but the tag would
be a claim the product cannot support: the reading and every result built from it would carry
`beverage_class: spirits` into the audit trail for a label nobody classified. Fixing a defect whose
shape is "the audit trail states a beverage nobody declared" by restating it more quietly is not a fix.
*Run the rules once per beverage and keep the results common to all three* — exact, and it needs no
fixed tag, since a rule that applies to every beverage produces the same `rule_id` in all three runs;
rejected for the same reason, because the readings still have to carry a beverage in each run and the
results kept still carry whichever one was picked. It also runs the spirits standards-of-identity
checks against a wine label three times over to throw the answers away.

**Because** a reply that names no rules is honest about what it did not do. A reply built on a beverage
nobody declared is not, and the reviewer reading it has no way to tell. No reply is better than a wrong
one here: a guess that is right two times in three is worse than an honest refusal, because a reviewer
cannot tell the two thirds from the third.

**Cost, stated.** An image on its own no longer gets the checks that need no application — that the
label carries a brand, a class, a net-contents statement, and the §16.21 government warning. It gets
the reading and a statement that nothing was checked. This is a loss on the demonstration path, where
a reviewer drops in an image to see the app work, and it is the brief's most prominent single
requirement that is lost. It is recovered in full by giving the rule model a way to say "applies
whatever the beverage is", which is recorded for the consolidation pass with the five files it touches.

**One test states the behaviour this replaces** and now fails:
`tests/test_ui_end_to_end_comparison.py::test_without_an_application_nothing_is_compared_and_the_label_is_still_checked`
asserts that an image-only upload still runs the comparison rules and has them opt out. With no
beverage named, no comparison rule can be selected to opt out. The test is in another lane's files and
is handed to the consolidation pass with the replacement stated.

<a id="0011"></a>
## 0011. The alcohol-content format check is switched off until the reader returns the label's wording

**Chosen.** Three rules are switched off, each carrying the reason in its own `notes` field:

| Rule | What it checks | Citation |
|---|---|---|
| `spirits.alcohol.format` | The alcohol statement is in a permitted form | §5.65(b) |
| `wine.alcohol.format` | The alcohol statement is in a permitted form | §4.36(b)(1) |
| `malt.alcohol.format` | The alcohol statement is in a permitted form | §7.65(b) |

The rules stay in their packs with their citations and their regex, and
`app/rules/_validators/format_check.py` stays registered as `regex_match`. Nothing is deleted. The
README states the gap as a limitation. What still runs on alcohol content is every check this app can
make from what it is given: that a label carries a statement where one is required
(`spirits.alcohol.present`, `wine.alcohol.present_or_table`, `malt.alcohol.conditional_required`) and
that the number on the label is the number the application declared
(`*.alcohol.matches_application`).

**Why.** The rule never sees the label's wording, so it cannot judge the label's wording.
`format_check.py:17-36` takes the reader's alcohol observation — a percentage and a unit — and builds
the sentence `f"alcohol {pct}{unit} by volume"` from it; line 49 hands that construction to the regex
and line 61 matches it. The string being tested is one the validator wrote itself, in the canonical
form the pattern is designed to accept. Both readers supply the number and not the text:
`app/vision/local.py:597-605` parses `_ABV_RE` down to `{"abv_pct": float, "unit": "%"}` and discards
the matched characters. Two wrong verdicts follow:

- **A number read means a pass, whatever the label printed.** `_ABV_RE` matches a bare percentage, so
  a label whose only alcohol statement is `12.5%` — with none of the wording §5.65(b) requires —
  yields `12.5`, which the validator renders as `alcohol 12.5% by volume`, which matches. Across the
  38 labels in the fixture manifest the rule passed every one.
- **No number read means a rejection, at `severity: reject`.** When the reader places no alcohol
  figure the projection returns the empty string and line 61 short-circuits to `FAIL`. For spirits the
  statement is mandatory (§5.63(a)(3)), so the rejection at least aims at a real requirement — but it
  aims at a formatting question the rule never asked, and it fires whenever the reader could not place
  a statement the label carries. For wine and malt the statement is often not required at all:
  §4.36(a) makes it optional at or below 14% alcohol where "table wine" or "light wine" appears on the
  brand label, and §7.63(a)(3) requires it for a malt beverage only where the alcohol comes from added
  nonbeverage ingredients. On those labels a lawful silence is a hard reject.

A check that passes whatever it is shown, and rejects when it is shown nothing, carries no information
about the label either way.

**Rejected.** *Leave the rules enabled* — they return a verdict they have not earned in both
directions; a wrong rejection on a compliant label is the one failure this product cannot have, and a
pass that reports an unmade check is the failure [0006](#0006) already refused. *Repair the projection here* — the repair needs the reader to return the label's alcohol
statement as printed, a change to `app/vision/local.py` and `app/vision/cloud.py`, whose work is
gathered in one pass against frozen OCR output and whose proof cannot be made without an OCR run; the
switch-off is what can be landed honestly now, and the repair is written down where the reader work is
planned.
*Delete the rules, as [0008](#0008) deleted the tolerance rules* — the two cases differ: a tolerance
rule compares the label against the liquid, which exists nowhere in this app's inputs, whereas the
format check compares the label against a regex and the label's own text is in the image the app
already has. This check is unbuilt, not unbuildable, and deleting it would throw away a correct rule
and its citation. *Lower the severity to `warn`* — it sends every
label whose alcohol statement the reader could not place to a human, with a reason code naming a
formatting defect nobody examined, converting a false rejection into a false alarm, which
[0008](#0008) rejected for the same reason. *Pass when nothing was read* — this reports the format as checked and
correct on a label the app never looked at, the same claim of an unmade check that [0006](#0006)
refused for contrast and type size. *Delete `format_check.py` along with the
rules* — `app/rules/loader.py:211` refuses startup when any rule names a validator the registry does
not carry, and it makes that check for disabled rules too; a switched-off rule still names
`regex_match`, so the validator stays.

**Because** a check that cannot be made must not be reported as made. Between a rule that passes
everything and a rule that rejects compliant labels, the honest option is to not run it and to say so
in the README.

**Consequence.** The app does not check the form of words a label uses to state its alcohol content,
and the README names this as a limitation. The check returns when the reader returns the alcohol
statement as the label prints it — verbatim, as a string, alongside the parsed percentage rather than
instead of it. Until then `format_check.py`'s projection is what it has always been: a restatement of
the reader's numbers, not a reading of the label.

**Amended — each class's pattern takes the forms its own section prints, and anything else goes to a
reviewer.**

Both readers return the alcohol statement as the label prints it, under `alc_text`, and
`regex_match` matches the rule's pattern against that text. The three rules run at `severity: warn`.
A statement the pattern matches passes. A statement it does not match, or one the reader could not
place, goes to a reviewer under `ALCOHOL_CONTENT.FORMAT.NEEDS_REVIEW`. No statement is rejected.

| Rule | Forms it passes |
|---|---|
| `spirits.alcohol.format` | The three forms §5.65(b)(2)(i) lists — "Alcohol ____ percent by volume", "____ percent alcohol by volume", "Alcohol by volume ____ percent." — with a statement of proof after it, §5.65(b)(1)(i) |
| `malt.alcohol.format` | The three forms §7.65(b)(3)(i) lists, the third with the colon it prints: "Alcohol by volume: percent." |
| `wine.alcohol.format` | "Alcohol __ % by volume" and the range "Alcohol __ % to __ % by volume", §4.36(b)(1) and (b)(2); and, as the "similar appropriate phrase" those paragraphs allow, the other two word orders, the third with or without a colon, each with a figure or a range |

Each pattern takes the abbreviations its section allows — "alc", "%", "/" for "by", "vol", with or
without a period — and parentheses around any word or symbol. §5.65(b)(3) and §7.65(b)(4) say the
forms "must appear as shown" apart from those abbreviations, so a malt statement of the third form
without its colon goes to a reviewer.

A pattern cannot list every statement the regulations permit. §5.65 and §7.65 allow other
representations alongside the statement, such as alcohol by weight; §4.36 allows any similar
appropriate phrase; and none of the three sections says how the figure is written. A statement in a
form the pattern does not list is a reviewer's judgement, not a defect.

Over the 30 approved labels in the fixture manifest, 27 statements pass. Three go to a reviewer: two
malt labels, `ttb-26238001000795` and `ttb-26240001000454`, print the third form without its colon,
and one wine label, `ttb-26239001000331`, writes its figure with a decimal comma.

**Evidence:** `rules/spirits/spirits.yaml`, `rules/wine/wine.yaml`, `rules/malt/malt.yaml`,
`app/rules/_validators/format_check.py`, `tests/rules/_validators/test_format_check.py`,
`tests/fixtures/labels/manifest.json`, `docs/reference/label-elements.md`.

<a id="0012"></a>
## 0012. A class-and-type designation the app cannot place goes to a reviewer, not to a rejection

**Chosen.** **No rule rejects a label because its class-and-type designation is absent from a list.**

| Rule | Before | Now |
|---|---|---|
| `wine.class_type.present` | `enumerated_match` against a five-entry list | `presence_check` on the `class_type` field |
| `spirits.class_type.present` | `enumerated_match` against a ten-entry list | `presence_check` on the `class_type` field |
| `malt.class_type.present` | `enumerated_match` against an eight-entry list | `presence_check` on the `class_type` field |
| `spirits.class_type.matches_soi` | `severity: reject` | `severity: warn`, on a list completed to Part 5 Subpart I's own classes and named types |

The `*.class_type.matches_application` rules are unchanged in shape: `designation_match` already
returns needs-review at warn severity where neither side names a recognised class. Two facts about the
regulations move into decision tables, which is where a fact about the law belongs rather than inside a
rule's parameters: `rules/tables/wine_designations.yaml` (new) pairs `Champagne` with `Sparkling Wine`
in both directions, and `rules/tables/malt_designations.yaml` places thirteen styles within the class
`Beer`, with `malt.class_type.matches_application`'s `recognised_classes` carrying all thirteen plus
`Beer` itself so no table entry is unreachable. The validator works out which class each side names
from `recognised_classes` before it consults the table, so a designation only the table knows would
never fire. `Rose Wine` comes off wine's recognised list.

**Why.** *An allow-list is the wrong instrument for the question `present` asks.* The three citations
those rules carry — §4.32(a)(2), §5.63(a), §7.63(a)(2) — each require a designation to appear on the
label. They do not require it to be one of a short set. Checking presence against a list answers a
different and harder question, and gets the easy one wrong whenever the list is short.

*The list can never be complete, and every gap in it was a hard rejection of a compliant label.*
§4.34(b) lets a wine be designated by a grape variety name, a semi-generic geographic name or a
geographic distinctive name **in lieu of** a class and type, and the prime grape names in §4.91 alone
run to several hundred. Part 5 Subpart I lets a distilled spirit with no standard of identity be
designated by a fanciful name alongside a truthful statement of composition, so no list of standards
can cover what may lawfully appear. Driving the engine over the transcribed readings in
`tests/fixtures/labels/manifest.json` — all real, all TTB-approved — produced thirteen failing verdicts
on approved labels before these changes, every one at reject severity:

| Designation on the label | Rule reporting it | Cause |
|---|---|---|
| `Cognac XO / Cognac Petite Champagne` | `spirits.class_type.present`, `.matches_soi` | Cognac on neither list |
| `CRÈME DE CASSIS LIQUEUR` | `spirits.class_type.present`, `.matches_soi` | Liqueur on neither list |
| `PEATED OREGON AMERICAN SINGLE MALT WHISKEY` | `spirits.class_type.matches_soi` | Qualified whiskey designation |
| `SANGIOVESE`, `CHARDONNAY`, `GEWURZTRAMINER`, `PINOT NOIR` | `wine.class_type.present` | §4.34(b) varietal designations |
| `ROSE WINE`, `WHITE RHONE WINE / CHATEAUNEUF-DU-PAPE` | `wine.class_type.present` | Colour and geographic designations |

After the changes the same run reports none of them, and no verdict anywhere off the outcome the
manifest records.

*Where the app genuinely cannot place a designation, "a reviewer should look" is the true answer, and
the engine already has a shape for it.* `designation_match` returns `INSUFFICIENT_EVIDENCE` at warn
severity on that branch, and the country-of-origin comparison was settled the same way.
`spirits.class_type.matches_soi` now says the same thing: it passes what Subpart I names, and sends
what it does not recognise to a human rather than rejecting the label.

*Champagne and Rose Wine, measured against the CFR text.* Both were on
`wine.class_type.matches_application`'s recognised list, and whether either belonged there is a
measurement, not a judgement. Champagne belongs, and listing it alone was
not enough: §4.21(b)(2) makes champagne a type of sparkling light wine and §4.34(a) says the type
designation "champagne" "may appear in lieu of the class designation 'sparkling wine'", and
§4.24(b)(2) additionally lists it among the semi-generic names, so a label reading CHAMPAGNE and an
application reading SPARKLING WINE name the same wine. With Champagne merely
listed and nothing recording the equivalence, `designation_match` saw two recognised classes that
differ and returned a rejection — turning a substitution the regulation expressly permits into a
rejected label. The decision table records the equivalence both ways, because the regulation offers
the two designations as alternatives rather than as a general and a specific term. Rose Wine does not
belong and is removed: §4.21(a)(4) puts "pink (or rose) wine" beside
"red wine", "amber wine" and "white wine" as ways of designating the colour of a Class 1 grape wine. It
is a colour inside a class, not a class. Removing it changes no verdict, because every designation
carrying "rose wine" also carries "wine", which is listed, so both sides already agree at that class.

**Rejected.** *Extend the `present` allow-lists until they agree with each other* — the smallest change
and it fixes the two spirits labels, but it leaves the cause in place — the next lawful designation
nobody listed is still a rejection — and it cannot fix wine at all, where the lawful set is several
hundred grape names plus the semi-generic and geographic lists.
*Carry every lawful designation* — thousands of entries, needing maintenance against §4.91 and Subpart
I, and still a rejection engine for whatever it missed; [0007](#0007) rejected the same idea for the
qualifiers around a standard of identity. *Keep `matches_soi` at reject severity and grow its list* —
same defect in a rule whose subject makes it worse, since Subpart I's fanciful-name route means an
unlisted designation is not evidence of anything wrong. *Put the Champagne equivalence in the rule's
parameters rather than a decision table* — the equivalence is a fact about §4.34(a), not about how this
rule is configured, and a reader checking the rule against the regulation should find it in one place
with its citation; the malt pack already carries its class-and-style equivalences this way. *Drop the `present` rules altogether, since `matches_application` also looks at the
designation* — they answer different questions; `present` is the §4.32(a)(2) requirement that the label
carry a designation at all, and an application that declares no class makes `matches_application`
inapplicable, so with `present` gone a label with no designation would pass.

**Because** a wrong rejection of a real, approved label is the one failure this product cannot have.
Where the app cannot place what a label says, the honest verdict is that a reviewer should look — never
that the label is wrong.

<a id="0013"></a>
## 0013. The health-warning checks answer only what they measured

**Extends** [0006](#0006), which put four of these checks out of scope. That
entry said which checks are not made; this one says what they answer instead, and settles three further
questions: what "the same words" means when a printer's spacing differs, what a boldness nobody could
measure is worth, and what happens to a rule that duplicates another.

**Chosen.**

**1. The four checks this product cannot make answer `insufficient_evidence` at warn severity**, under
a reason code that names the missing measurement. All four now name one validator, `unmeasurable`:

| Rule | What it checks | Citation | Reason code |
|---|---|---|---|
| `common.warning.contrasting_bg` | The warning sits on a contrasting background | §16.22(a)(1) | `WARNING.LEGIBILITY.CONTRAST_NOT_MEASURED` |
| `common.warning.cpi_max` | Characters per inch, against the §16.22(a)(4) table | §16.22(a)(4) | `WARNING.TYPE_SIZE.CPI_NOT_MEASURED` |
| `common.warning.type_size_min` | Minimum type height | §16.22(b) | `WARNING.TYPE_SIZE.HEIGHT_NOT_MEASURED` |
| `common.warning.separate_apart` | The warning is separate and apart from other information | §16.21 | `WARNING.PLACEMENT.ISOLATION_NOT_MEASURED` |

Each rule stays in the pack with its citation and `notes`, and each stays `disabled: true`, so none
adds a finding to a label today. What changed is what they say the moment anyone switches one on. The
four bodies that used to back them — `contrast_ratio_check.py`, `cpi_lookup.py`, `type_size_check.py`
and the `layout_isolation_check` half of `layout_check.py` — are deleted. Each compared against a
payload key no reader emits, so each returned a rejection on every label, compliant ones included.

**2. `type_size_check` is deleted rather than left switched off.** It compared a point value against a
fixed 2.0, while §16.22(b) sets the minimum in millimetres keyed to container size — 1 mm at 237 mL or
under, 2 mm up to 3 L, 3 mm above — so a pass from that comparison did not mean what its own citation says. Code whose answer is wrong in a way its citation
hides is worse than no code: a later reader trusts it. The §16.22(a)(4) decision table stays, at
`decision_table_ref` on the CPI rule, because it is the regulation's own three rows rather than an
implementation of anything.

**3. The verbatim comparison ignores letter case, spacing and a line break that splits a word. It does
not ignore punctuation.** `common.warning.verbatim` keeps reject severity: once case and spacing are out
of the comparison, a mismatch means the words differ, and §16.21 fixes the words. The canonical form
both the loader and the validator use is, in order:

    nfkc → ascii_quotes → join_line_break_hyphens → drop_whitespace → casefold

Spacing is removed rather than collapsed. Collapsing runs of spaces left a gap the reader lost —
`IMPAIRSYOUR` for `IMPAIRS YOUR` on `ttb-26239001000217` — rejecting an approved label for spacing,
which this point says is not compared ([0039](#0039)).

**4. `common.warning.heading_phrase` is deleted, not switched off.** It asked for evidence named
`warning_heading` that no reader produces, and `common.warning.heading_caps_bold` already checks the
same two words together with the capitals §16.22(a)(2) requires. `equality_match`, the validator it was
the only user of, is deleted with it.

**5. A boldness the reader could not measure is not a rejection.** `heading_style_check` decides the
heading's words and capitals first, from the heading's own text, and still rejects when either is wrong.
Where the payload reports `heading_bold_measured_confident: false`, the rule answers
`insufficient_evidence` at warn severity under `WARNING.STYLE.BOLD_NOT_MEASURED`, which the rule
declares in its own `parameters`. `app/vision/heading_measure.py` no longer falls back to measuring the lower half of the whole image when
it has no heading box: a measurement taken somewhere else is not a measurement of the heading.

**Why, on the four unmeasurable checks.** A check that cannot be made has three possible answers and
only one of them is honest. Passing claims a requirement was met that nobody looked at. Failing rejects
a compliant label for the product's own blindness — which is exactly what the deleted implementations
did. Insufficient evidence says what happened: the label goes to a reviewer on that point, with a
sentence naming the measurement nobody could take, and is never rejected on it. [0006](#0006)
established that these are out of scope; leaving four separate bodies of unreachable code switched off
left four traps, because switching one on produced a wrong verdict rather than a missing one.

**Why, on case and spacing.** The answer key settles it. `tests/fixtures/labels/manifest.json`'s own
`check_rules.warning_exact` reads, verbatim:

> Same words, numbers and punctuation as 27 CFR 16.21. Letter case, spacing, line breaks and hyphens
> that split a word at a line end are ignored; the heading's capitals are scored separately by
> warning_heading_caps.

Five labels in that manifest prove each half of it, and they are why the pipeline is shaped the way it
is. `ttb-26231001000662` prints `GOVERNMENT WARNING  :`, doubles the space after two commas and sets the
whole body in capitals — approved, and marked `warning_exact: true`. `ttb-26237001000107` prints
`(1)ACCORDING` with no space at all, also `true`, so "ignore spacing" cannot mean "collapse runs of
spaces" because there is no run to collapse; whitespace on both sides of a punctuation mark is removed
instead, which makes `WARNING  :`, `WARNING :` and `WARNING:` one string. `ttb-26231001000333` breaks
`PREG-\nNANCY` across two printed lines, also `true`. `ttb-26240001000454` ends `HEALTH PROBLEMS"`
instead of `PROBLEMS.` and is marked `false`, so punctuation stays in the comparison.
`var-heading-title-case` prints the heading as `Government Warning:` with the body unchanged and is
marked `warning_exact: true` with `warning_heading_caps: false` — decisive, because the verbatim rule
ignores the heading's case and the separate capitals rule is what catches it.

Case in the body is regulated nowhere. §16.22(a)(2) rules the heading's case only. A comparison that
sent every all-capitals approved label to a reviewer would be reporting a difference no regulation
names.

**Why, on an unmeasured boldness.** Both readers already say whether their stroke-width measurement was
confident (`app/vision/local.py`, `app/vision/cloud.py`). Against a reject-severity rule, treating "not measured" as "not bold" turns the product's own
blindness into a rejection of a label that may well be printed in bold. The element that *was* read —
the capitals — is still decided, so a title-case heading is rejected whether or not anyone measured its
weight.

**Rejected.** *Keep the four implementations, switched off* — unreachable code against a reader that
does not exist, each carrying a wrong verdict for whoever switches it on. The four rules stay and
point at one shared `unmeasurable` validator, the three implementation bodies go and the fifth rule
goes outright, because the rule entry with its citation and its notes is the durable record and the
body was not. *One shared "not measured"
reason code* — four rules ask four different questions, and a reviewer reads the code's description as a
sentence, where "a measurement was not taken" does not say which. *Delete the §16.22(a)(4) decision table with `cpi_lookup`* — the table is the regulation's
three normative rows as data; it costs nothing, the loader resolves the reference, and it is what a characters-per-inch check reads the day a
reader reports a physical scale. *Report a case-only difference as needs-review* — proposed in
`docs/research/2026-09-15-matching-rules.md` under that document's own *Open points* heading, where it
was never settled; the manifest settles it the other way, and `var-heading-title-case` is not compatible
with any other reading. *Normalize punctuation out along with spacing* — `ttb-26240001000454` must still
fail on `PROBLEMS"`, and §16.21 fixes the statement's punctuation as much as its words. *Rename
`equality_match.py`* — it keeps `enumerated_match`, which is still equality against an enumerated list,
and renaming would touch seven test files for no change in behaviour.

**Because** a check that cannot be made must not be reported as made, and must not be reported as failed
either. Between passing a label nobody checked and rejecting one the product could not see, the honest
answer is to say which measurement is missing and hand the label to a reviewer.

<a id="0014"></a>
## 0014. Cross-unit net contents is compared within the rounding the standards of fill carry

**Evidence:** `docs/research/2026-09-15-ttb-regulatory-framework.md`.

**Chosen.** When the net contents on the label and on the application are in **different** units, the
two agree if they are within **1% of the figure the application declared**. When they are in the **same**
unit they must be equal, as before. The 1% is data in the rule pack, not a constant in the validator: it
sits in the `tolerance:` block of each `*.net_contents.matches_application` rule as
`cross_unit_relative: 0.01`, in all three beverage packs. A rule that carries no tolerance compares
exactly in both cases.

**Why a tolerance at all.** The container sizes the regulations authorize are metric, and the customary
figure a label prints for one of them is that size converted and rounded to a tenth of a fluid ounce.
375 mL is 12.6803 fluid ounces and the label prints `12.7 FL. OZ.`; converting 12.7 back gives 375.58
mL, not 375. A comparison that demands equality therefore rejects a compliant label **by construction**:
the rounding is already in the figure the label prints, and no reader or parser can undo it. Four of the
nine failures the answer key uncovered are this shape.

**Why 1%, and not some other number.** The tolerance has to be wide enough to absorb that rounding and
narrow enough that one authorized size cannot pass as another. Both bounds come from the authorized
standards of fill — 27 CFR §4.72 for wine and §5.203 for distilled spirits, as amended by T.D. TTB-200,
effective 2025-01-10.

- **The floor: 0.633%.** Converting every authorized size to fluid ounces and rounding to a tenth — the
  precision the labels in `tests/fixtures/labels/manifest.json` actually print, which gives 50 mL as
  1.7 FL OZ and 375 mL as 12.7 FL OZ — the worst case is 0.550%, at 50, 100, 200 and 250 mL. A label may also print the tenth *below*
  the true figure so the customary statement does not overstate the contents: a 250 mL can prints
  `8.4 FL OZ`, which is 0.633% low. That is the widest gap a printed customary figure opens on an
  authorized size, so the tolerance must be at least 0.633%.
- **The ceiling: 1.216%.** Take each authorized size and the customary figure printed for the nearest
  size that prints a different one. The closest such pair is in the spirits list: 710 mL against the
  `24.3 FL OZ` printed for 720 mL, which converts to 718.64 mL — 1.216% away from 710. A tolerance at or
  above that would let a 720 mL label pass against a 710 mL application, so the tolerance must stay
  below 1.216%.

1% sits between the two and is the round number in that gap.
`tests/rules/_validators/test_quantity_match.py` recomputes both bounds from the two size lists and
asserts the shipped tolerance sits between them, so an edit that loosens it fails with the reason
attached rather than passing quietly.

**Where the tenth comes from.** It is observed, not cited. Every customary figure in the fixture corpus
is printed to a tenth of a fluid ounce — `12.7 FL. OZ.` on a 375 mL label, `11.2 FL. OUNCES` on a 331 mL
one, `1 PT. 0.9 FL. OZ. (500 mL)` on a 500 mL one — and each matches its metric size converted and
rounded to a tenth. The research records that equivalent customary units are *permitted* alongside metric
(§5.70(a), §7.70(a), §4.37) but prescribes no precision for them and publishes no equivalents table;
its only rounding note, "Liters use decimals to nearest hundredth," is about metric liters. If
the regulation does fix a precision and it is coarser than a tenth, the floor rises and 1% may no longer
clear it — that is the one thing worth re-checking against the regulation itself.

**Why the number lives in the rule pack.** Determinism is a first-class criterion: the same input gives
the same answer, and a reviewer can read the reason a verdict went the way it did. A tolerance held in
the pack is a number a reviewer can look up beside the rule that used it, and a number a rule pack
version pins. A constant in `quantity_match.py` would be neither. `app/schemas/rules.py` already declares the
`tolerance` field and `tests/test_rules_yaml_round_trip.py` already covers it; nothing else in the pack
used it until now.

**Rejected.** *Comparing at the label's printed precision* — convert the application's figure into the
label's unit, round to the number of decimal places the label printed, demand equality. Deterministic,
and it closes the three cross-unit failures, but it has two holes: it still rejects the compliant 250 mL
can, computing 8.4535, rounding to 8.5 and failing against the printed 8.4; and it stops being a check at
coarse precision, since a label printing `1 PINT` has a last printed digit of one whole pint, so the rule
admits anything within half a pint and an application declaring 700 mL passes against a pint label, and
`ttb-26240001000563` is exactly that shape. *A table of admissible equivalents*, every authorized size
listed with the customary figures a label may print for it and a pair admissible only if it appears —
the most explainable design, and it cannot be completed, because
malt beverages have no standards of fill, so any lawful malt size outside the list would be reported as a
disagreement; all four of the failures this decision closes are malt labels. *27 CFR §7.71's net-contents
tolerances as the source of the number* — those cover the difference between the liquid in the container
and the declaration on it, a filling-line tolerance; this app compares two *declarations* about the same
container and never sees the liquid, the same reason [0008](#0008) removed the carried-over alcohol
tolerance. *A middle band* — pass inside 1%, needs-review between 1% and the next authorized size, fail
beyond; the band would be 1% to 1.216% wide, too thin to carry a third outcome, and its second boundary
would need a derivation of its own.

**Cost, stated.** Authorized sizes closer together than the rounding itself — 330 against 331 mL, 473
against 475, 568 against 570 — print the **same** customary figure. No tolerance of any width can tell
them apart, because the label genuinely does not say which one it is. That is a limit of a customary
declaration, not of this rule. Malt beverages have **no** federal standards of fill at all (§7.70); the
bounds above are derived from the wine and spirits lists and applied to malt as well, because a malt label
prints its customary figure with the same rounding even though the size it rounds is unconstrained.

<a id="0015"></a>
## 0015. The brand check compares an admissible set, not one string

**Evidence:** `docs/research/2026-09-15-matching-rules.md`.

**Chosen.** The brand comparison no longer asks whether the label's mark equals the application's
`brand_name`. It asks whether the mark is **one of the names the application says the label may carry**:
the brand the application declares; the fanciful name, where it declares one; and every trade name it
marks `(Used on label)` inside its free-text applicant block. Four routes run against every one of those
values, in order, and the finding names which value matched and how:

| Route | What it establishes | Verdict it can reach |
|---|---|---|
| Exact | The two are the same once normalised | match |
| Whole words | One value's words sit inside the other's as a consecutive run | match |
| Score | Jaro-Winkler similarity of the two normalised strings | match, review, or mismatch by threshold |
| First letter | The score the two reach with a disagreeing first character dropped from both | **review only, never a match** |

Normalisation is what the research specifies — NFKC, curly quotes straightened, ™ ® © dropped, whitespace
collapsed, trimmed, case-folded — plus one addition and minus two subtractions:

- **Added: accents fold away.** The research says "nothing else", and this is the deliberate exception. A
  label printing `ŠVYTURYS` against an application's `SVYTURYS` scored 0.9167 and went to a reviewer,
  while the same two spellings were equal for the class-and-type check, which folds accents through
  shared normalisation. One engine gave two answers about one pair of strings.
- **Removed: the punctuation strip.** Punctuation is kept, because dropping it can change a name and,
  worse, hides the change: the check reported an *exact* match on a pair that differed, and the envelope
  told the reviewer the brand matched the application exactly.
- **Removed: the legal-suffix strip.** It cut `TACONIC DISTILLERY` to `taconic` and
  `SALTIRE RARE MALT WHISKY COMPANY` to `saltire rare malt whisky`. Those words are part of the name. The
  whole-words route covers the case the strip existed for — `Stone's Throw` against
  `Stone's Throw Distilling Co.` — without deciding in advance which words are disposable.

A name-and-address side effect of the same principle: a State written out and its two-letter postal code
are folded together in `name_address_match`, so "California" corroborates "CA" (PRD FR-7).

**Why.** Three approved labels in the 38-label corpus carry a brand the application records somewhere
other than its `brand_name` field, and the old comparison rejected all three:

| Label | Label mark | Application `brand_name` | Where the application does say it |
|---|---|---|---|
| `ttb-26239001000079`, `ttb-26239001000081` | `BONEFISH` | `TACONIC DISTILLERY` | the applicant block ends `… 12581 BONEFISH (Used on label)` |
| `ttb-26233001000566` | `THE UGLY` | `UGLY SWEATER` | the declared brand itself, of which the mark is a run of whole words |

These are not near misses to be rescued with a looser threshold. In each, the application states in
writing that the label carries that name. The honest comparison is against the set of names the
application states, and the finding says which one matched — which is what a reviewer needs when the
mark on the bottle is not the brand field's wording.

The whole-words route is the same test [0007](#0007) settled
for class-and-type designations, on the same helper, for the same reason — whole words rather than
substrings, so "gin" cannot match inside "Virginia". A leading definite article is dropped before the run
is compared, because an article is not part of a mark.

The first-letter route answers a different failure. `ttb-26238001000795` prints its brand as a script logo
reading `Gallo`; the registry record spells it `QALIO`. Jaro-Winkler scores that 0.7333 against a 0.85
review floor, so the check hard-rejected a label TTB approved. The prefix bonus that makes Jaro-Winkler
good at near-matches is zero whenever the first characters differ — exactly backwards for this product,
where a stylised first letter is the single most likely reading error.

**Rejected.** *Fold the first-letter variant into one score and take the maximum* — measured, it makes
`Gin` against `Din` a 1.0, a clean match on a three-letter brand whose only distinguishing letter is
wrong. Keeping the variant as a separate route that can only reach a reviewer says the true thing: these
two spellings agree except at the character a stylised mark most often loses, so a person compares them.

| Pair | Score | First-letter variant | Reported as |
|---|---|---|---|
| `Gallo` / `QALIO` | 0.7333 | 0.8667 | needs review |
| `Gin` / `Din` | 0.7778 | 1.0000 | needs review, **not** a match |
| `Zebra` / `Cobra` | 0.7333 | 0.8333 | mismatch |
| `Acme` / `Bizmark` | 0.4643 | 0.5000 | mismatch |

*Lower the review threshold instead* — a floor low enough to admit 0.7333 also admits `Zebra` against
`Cobra`; the fix for a label whose name the application states elsewhere is to read where the application
states it, not to make every comparison in the product blurrier. *Reverse both strings and take the better
score, or add a common-affix bonus* — both measured at 0.76 for `Gallo` / `QALIO`, still below the floor,
since Jaro is invariant when both strings are reversed, so all either buys is the Winkler bonus on a
one-character common suffix. *Resolve `ttb-26233001000566` through the
trade-name list alone* — its trade name is `UGLY WINES` and the label mark is `THE UGLY`; the best score
against the whole admissible set is 0.88, short of the 0.92 a match needs, and whole-word containment is
what settles it. *Put the State-name table in
`rules/tables/` as a decision table* — the equivalence is lexical and belongs to one element, not a
regulatory list, and it would need a `decision_table_ref` on three rules across three pack files.

**Because** determinism comes first: the product should give the same answer for the same input and be
able to show a reviewer why. Every route above is an exact statement about two strings — they are equal,
one contains the other's words, they score this much, they agree after the first character — and every one
is named in the finding. A single blurrier threshold would have cleared the same three labels while making
the answer harder to defend and admitting pairs that are genuinely different names.

**Costs, stated.**

- **A one-word mark that happens to be a word of a different brand passes.** `BOURBON` on a label against
  a declared `ACME BOURBON` is a match under the whole-words route. Nothing in the 38-label corpus does
  this.
- **A punctuation-only difference reports a match.** `Lucky Lucy's` against an application's `Lucky Lucys`
  scores 0.9833 and passes. Two of this project's own documents say it should report needs review —
  `specs/0001-label-verification/requirements.md` R7 and `docs/PRD.md` FR-7 — and the corpus answer key,
  `tests/fixtures/labels/manifest.json`, says it passes with no other outcome acceptable. The deciding source is TTB's own: Form 5100.31's
  allowable revisions, item 3.b, permits a label to change "the spelling (including punctuation marks,
  changing letters from upper case to lower case and vice versa, and abbreviations) of words" without a
  new approval, provided the change does not alter the meaning. A dropped apostrophe is that change. **The
  two documents need their wording corrected to match**; until they are, this entry is the account of what
  the product does. What makes the disagreement smaller than it reads: the research's worry was that
  dropping punctuation can change a name, and the answer to that worry is to stop dropping it. Once
  punctuation is kept, a punctuation difference no longer produces a silent exact match — it produces a
  measured score graded by how much of the name the difference is, and a message the reviewer sees. A
  short name losing a character falls into the review band on its own.
- **A city name can corroborate a State.** The State fold is applied to both sides, so an over-fold is
  symmetric — a city called Washington becomes "wa" in the label reading and in the application block
  alike. What remains is that a label naming a city could corroborate an application naming the same
  word as a State. The check it feeds never rejects, so the cost is a match a reviewer would have been
  asked about, not a wrong rejection.

<a id="0016"></a>
## 0016. The country-of-origin abbreviation table is not built

**Chosen.** The country-of-origin check reads one form of the country's name: the English name the
application declares, appearing as whole words inside whatever wording the label wraps around it —
"PRODUCT OF LITHUANIA", "DISTILLED IN IRELAND". It does not read the other forms customs marking rules
accept. Where the label states an origin and it does not carry
the declared country in that one form, the check reports that it could not settle the question, at warn
severity, and a reviewer reads the label. It does not reject. The reason code
`ORIGIN.MATCH.APPLICATION_LABEL_DISAGREE` carries that meaning and its registry entry says so. An import
whose label carries **no** origin statement at all still fails, at reject severity, under
`ORIGIN.PRESENCE.MISSING` — nothing was stated there, so there is nothing to interpret. The README lists
the unread forms as a limitation.

**Why.** 19 CFR §134.45(b) and (c) accept more than the English name: the name of the country in the
language of the country ("HECHO EN MEXICO", "PRODUCTO DE ESPAÑA"); an abbreviation that "unmistakably
indicates" the country ("U.K.", "Gt. Britain"); the adjectival form ("Irish", "Italian"); and a variant
English spelling that clearly indicates the country. The regulation gives these by example and by test —
"unmistakably indicates" — not as a list. There is no table in the CFR to load. Building one means writing
it: choosing, per country, which abbreviations and which adjectival forms are unmistakable, and being
wrong about a label is worse than not checking it.

That decides the branch as much as the table. Before this change the check rejected any origin statement
it could not read, which means it rejected a compliant import that wrote its country in Spanish, or as an
adjective, or as an abbreviation — three forms the law expressly allows. A verdict of "reject" asserts the
label is wrong. This check cannot tell "the label names a different country" from "the label names the
right country in a form I do not read", and a check that cannot tell those apart must not claim the first.

**Rejected.** *Build the table now* — a per-country data set with a judgement call in every row, and this
lane's remit is the comparison, not the reference data; an unbuilt check named in the README costs less
than a built check that reports a wrong verdict, which is the project's standing rule when correctness
and breadth pull against each other. *Keep rejecting on an unrecognised origin statement* — it
rejects compliant imports; three labels in the corpus state their origin in a form the check reads, and
the failure mode is for the ones that do not, and for TTB-approved labels that do not. *Pass an unrecognised origin statement* — it reports a check as made and passed when the two sides
were never lined up, the failure this project set out to avoid. *Translate with the model reader* — [0009](#0009) removed the model reasoning layer,
and putting a language judgement back into a compliance verdict would make the answer depend on a model's
output rather than on a rule a reviewer can check.

**Because** a check that cannot be made must not be reported as made, and a verdict must not claim more
than the evidence supports. Between rejecting compliant imports and asking a person, the check asks a
person, and the README says which forms it does not read.

**Cost, stated.** The check can no longer distinguish "the label names a different country" from "the
label names the right country in a form this product does not recognise", so **both reach a reviewer**. A
label that genuinely names the wrong country is not rejected outright; it is flagged for a person. That is
the trade this product chooses: a wrong verdict on a real label is the one failure it cannot have, and an
extra review is not a wrong verdict.

<a id="0017"></a>
## 0017. A punctuation-only brand difference is a match, and the requirement text is corrected to say so

**Evidence:** Form TTB F 5100.31, allowable revisions item 3.b; measured against
the shipped comparison; [0015](#0015), which recorded the conflict and left it open.

**Chosen.** Where a label's brand mark differs from the application's only in punctuation, the product
reports a **match**, graded by how much of the name the punctuation is. The four places that said it
should report needs review are corrected to describe what the product does and why:

| Document | What it said | What it says now |
|---|---|---|
| `docs/PRD.md` FR-7 | Listed what brand comparison ignores, and punctuation was not on the list | Brand keeps punctuation and scores the difference; the score and the threshold are named |
| `specs/0001-label-verification/requirements.md` R7 | *"Given a brand of 'Stones Throw' against an application's 'Stone's Throw' … then the brand is needs review"* | …then the brand is a match, and the finding carries the score |
| `docs/research/2026-09-15-matching-rules.md`, "Proposed rule per field" | Brand row: *"Differs only by punctuation or a likely misread: needs review"* | Kept as written, with a dated correction under the table |
| the same document, "Cases worked through" | *"'Stones Throw' vs 'Stone's Throw': punctuation differs. Needs review."* | Scored 0.9846, pass, with the score shown |

Measured here against `app/rules/brand_match.py` as shipped:

| Route | `Stones Throw` / `Stone's Throw` |
|---|---|
| Exact, punctuation kept | no — `stones throw` against `stone's throw` |
| Whole words | no — `("stones","throw")` against `("stone","s","throw")` |
| Score (Jaro-Winkler) | **0.9846**, against a match threshold of 0.92 and a review floor of 0.85 |

**Why.** The regulator's own form settles it. Form TTB F 5100.31's allowable revisions, item 3.b, permits
an approved label to change "the spelling (including punctuation marks, changing letters from upper case
to lower case and vice versa, and abbreviations) of words" with no new approval, provided the change does
not alter the meaning. A dropped apostrophe is exactly that change, so a product that stopped such a label
for review would be stopping a revision TTB has already said needs no approval.

The research document was the source all four texts descended from, and it **contradicted itself**: its
opening paragraph cites that same item 3.b, and its worked case says needs review. The requirement text
inherited the worked case rather than the citation. The corpus answer key,
`tests/fixtures/labels/manifest.json`, has always said pass with no other outcome acceptable, and it is
transcribed from the labels — the one source here that is not an opinion.

This is also what the brief asks for in the place it is loudest. Dave Morrison's complaint is that
trivial differences consume the judgement he is paid for: *"Technically a mismatch? Sure. But it's
obviously the same thing."* Sending every dropped apostrophe to a person is that complaint, implemented.

**Rejected.** *Change the engine to report needs review instead* — it would keep the documents as
written at the price of routing a permitted revision to a reviewer on every label that drops a mark,
which is the cost the brief's senior agent names first, and it would have the product disagree with the
answer key transcribed off the labels. *Restore the punctuation strip, so the difference is ignored
outright* — measured and rejected in [0015](#0015): stripping produced a silent **exact** match on a pair
that differed, and the envelope then told the reviewer the brand matched the application exactly, which is
a false statement about two strings. Scoring says the true thing and shows it. *Leave the documents and
let this entry carry the difference* — this document's own preamble puts a governing document above an
entry, so an uncorrected FR-7 would make the engine the defect and oblige a later lane to "fix" working
code back to a wrong answer. *Widen the manifest to whichever answer the documents preferred* — the
manifest is ground truth transcribed from the labels and never moves to make a suite agree with prose.

**Because** a requirement that contradicts the regulator's own allowable-revision list — and the source
document it was drawn from, in that document's own opening paragraph — is the text that is wrong, not the
product built against the list.

**Cost, stated.**

- **The product reports a match on a brand pair that is not character-for-character identical, without
  asking a person.** The guard is that the score is in the finding and the reviewer sees it; there is no
  route by which a punctuation difference is silently erased, which is the failure [0015](#0015) removed.
- **The grading is by proportion of the name, not by meaning.** A long brand absorbs a punctuation
  difference that a short one does not, so two names that differ in the same way can be answered
  differently depending on their length. That is deliberate — a character is a larger share of a short
  name, and the short case is the one where a dropped mark is more likely to be a different name — but it
  is a rule about string length, and it cannot detect the rare punctuation change that does alter meaning.
- **Two approved documents changed after approval.** `docs/PRD.md` FR-7 and
  `specs/0001-label-verification/requirements.md` R7 were amended rather than the code; the amendment is
  logged in `docs/PRD-decisions.md`, which had no entries before this one.

<a id="0022"></a>
## 0022. The reason-code registry states which of its codes nothing emits, and a test holds both halves

**Evidence:** measured here against the shipped tree — 60 registered codes,
46 rules across five packs, and the scan that found `ENGINE.OVERRIDE.NOT_FOUND` unregistered.

**Chosen.** `rules/reason_codes.yaml` gains a `reviewer_vocabulary:` block listing every registered
code that no rule and no line of application code produces, each with the reason it stays, and
`tests/rules/test_reason_code_registry.py` checks the registry from both directions:

| Direction | What is checked | Where it was before |
|---|---|---|
| Rule → registry | Every rule's `reason_code`, and every rule parameter ending `reason_code`, is registered and has a description | Enforced silently at load time by the loader's cross-check 7, `app/rules/loader.py:213-223`. The only test that said so covered four codes |
| Application source → registry | Every reason code written as a quoted string in tracked `app/` or `eval/` Python is registered | Nothing checked this |
| Registry → emitter | Every registered code is emitted by a rule or by Python, **or** is declared in `reviewer_vocabulary` | Nothing checked this |
| Registry → allow-list | No `reviewer_vocabulary` entry names an unregistered code, and none names a code something does emit | Did not exist |

A code counts as written into Python when it appears as a quoted string whose first segment is a key
of the registry's own `bins:`. Two further checks in `tests/rules/test_reason_codes_yaml.py` keep
that anchor sound: every registered code sits in a declared bin, and every declared bin carries at
least one code.

**One defect was fixed by the work.** `app/api/overrides.py:115` logs
`reason_code="ENGINE.OVERRIDE.NOT_FOUND"` when a reviewer's override names an evaluation that carries
no result. The code was not in the registry, so it reached the log as an identifier with no declared
meaning, and a reviewer could not have applied it through the override endpoint, which refuses any
code the registry does not carry. It is registered, at `warn`, rather than folded into
`ENGINE.BATCH.NOT_FOUND`, which names a different condition — an unknown batch id, not an evaluation
with no result yet.

**Why.** Fourteen of the sixty registered codes are produced by nothing. That is not a fault:
`app/api/overrides.py` accepts any registered code, so each of the fourteen is a sentence a reviewer
can put on a label by hand, and four of them — `WARNING.LEGIBILITY.NO_CONTRAST`,
`WARNING.PLACEMENT.NOT_SEPARATE`, `WARNING.TYPE_SIZE.CPI_EXCEEDED`, `WARNING.TYPE_SIZE.UNDER_MIN` —
are exactly the judgements a person can make that [0013](#0013) records the product as unable to
measure. But before this entry the only way to know that a code was deliberately unemitted was a
comment beside two of the fourteen, and the other twelve looked identical to an orphan left behind by
a rename. The allow-list turns that from something a reader has to notice into something the file
says, and because the check fails on a stale entry and on a redundant one alike, the statement cannot
quietly stop being true.

It earned that within the hour. The block first listed `ENGINE.INPUT.LABEL_IMAGE_MISSING` as emitted
by nothing, which was true when it was written; the batch lane's work on `app/batch/worker.py` then
started emitting it, and the check went red on the next run rather than leaving the registry saying
something that had stopped being true. The entry was removed.

**Rejected.** *A plain orphan check, modelled on the validator one in
`tests/test_rules_yaml_round_trip.py:34-49`, with no allow-list* — it fails on purpose against the
file as shipped, so it could only have been landed by deleting fourteen codes the reviewer can still
reach for. *An allow-list covering every code no **rule** names* — thirty entries, sixteen of which
the application does emit, so the block would assert something false about more than half of what it
listed; that is why reachability counts application Python and not rules alone. *A per-code
`reviewer_vocabulary: true` field beside each entry* — it reads better next to the description, but
`ReasonCodeEntry` is `extra="forbid"` (`app/schemas/rules.py:35-40`) and the loader refuses any field
beyond `description`, `cfr_anchors` and `severity`; a top-level block needs no schema change, because
`_load_registry` reads only `version` and `codes`. *Changing `app/api/overrides.py` to log a code that
was already registered* — it would have removed the symptom and kept the gap, and the log line names
the condition correctly.

**Because** a registry edited by hand across concurrent lanes drifts mechanically, and the cure that
worked for the same failure in the decision document was a check rather than a convention.

**Cost, stated.**

- **The source scan reads quoted strings, not the program.** A reason code built by concatenation, or
  read from configuration, is invisible to it, and would show up as a registered code nothing emits —
  a false failure whose fix is to declare it or to write it as a literal.
- **The scan is blind outside the declared bins.** A code in a bin the file does not declare is not
  recognised as a reason code at all. The two bin checks in `tests/rules/test_reason_codes_yaml.py`
  close that from the registry side; nothing closes it from the Python side.
- **The rule → registry checks cannot fail in a tree where the loader runs.** The loader refuses the
  pack first, with its own message. They earn their place by stating the intent and by being proved
  against planted input in the same file, not by being the thing that catches the defect.
- **Fourteen reasons are now prose that can go stale.** If a rule starts emitting one of the fourteen,
  the redundancy check fails and the entry must go — but if the *reason* stops being true while the
  code stays unemitted, nothing notices.

<a id="0023"></a>
## 0023. The deploy runs on Hugging Face Spaces, Docker SDK, CPU Basic hardware

**Superseded by** [0025](#0025), which moves the host to Google Cloud Run;
the reasoning below is left standing because what changed is not any fact it states.
**Evidence:** `app/config.py:37`, `docs/research/2026-09-15-hosting.md`,
`huggingface.co/docs/hub/spaces-overview` and `/spaces-config-reference`.

**What was unsettled.** Two of this project's own documents disagreed. One research record picked
Hugging Face Spaces and three tracked files already assumed it; the plan of work said the host was
still unpicked. A third record, written the same day, contradicted the first on the fact the whole
choice turned on. The picking record's reasoning was a GPU argument — a GPU OCR engine, two vision
models, a dedicated accelerator tier — and every one of those premises has gone: none of those
components is in this tree, the model reasoning layer was removed ([0009](#0009)), and the reader
that ships runs on CPU. So the choice is made again here, from the architecture as it stands.

**What the deploy has to carry.** `VISION_MODE` defaults to `local` (`app/config.py:37`), so the
deployed container reads labels with an OCR engine inside the process, exactly as a clone does. Its
three ONNX models are installed by `uv sync` from the `rapidocr` wheel — 31 MB, already in the image
— so the container downloads nothing at runtime and makes no outbound call, which is what
[0004](#0004) promises. The working set for that reader is recorded in
`docs/research/2026-09-15-hosting.md` as 1.5–2 GB; it has not been re-measured here, because
measuring it means running OCR and this machine's CPU is rationed.

**Chosen.** **Hugging Face Spaces, Docker SDK, CPU Basic hardware.** CPU Basic is 2 vCPU and 16 GB
of RAM at an hourly price of zero. The platform issues TLS and a stable `*.hf.space` URL. The deploy
is a `git push` against the `Dockerfile` already in this repository — the platform builds it — so it
is one command with no build pipeline to maintain. The Space is configured from a YAML block at the
top of `README.md`; the key that matters is `app_port: 8000`, because the platform's default is 7860
and a missing line serves a reviewer a blank page.

**Because the demo URL is unauthenticated, and so the cost has to be bounded by the plan rather than
by traffic.** This is the constraint that decided it. Deliverable 2 is a URL handed to a reviewer,
with no sign-in and no rate limit in front of it. On CPU Basic the hardware costs nothing per hour,
so no amount of traffic — a reviewer, a crawler, a batch of 300 labels run twice — can produce a
charge. The fee is the plan's, it is $9 a month, and it is known before anything is pushed. The two
cheaper-looking options are metered: both require a payment method on file and bill by use, so their
$0 is a $0 that traffic can move. A bounded cost beats an unbounded one when nobody else is paying.

**Rejected.**

- *Render, Railway, Koyeb, Azure App Service F1* — all four fail on memory before anything else is
  weighed. Their free tiers are 512 MB, 0.5 GB, 512 MB and 1 GB against a 1.5–2 GB reader. Render
  also documents a ~1-minute cold start after 15 minutes idle, and Koyeb's own documentation bars
  free instances from production workloads.
- *Google Cloud Run* — clears the memory bar, deploys in one command, and is free inside a monthly
  quota. Rejected on the metering above: a billing account with a payment method is required even to
  use the free tier, and Google's own guidance is that budget controls alert rather than hard-stop.
  Its cold-start time for an image this size is not documented anywhere primary.
- *Scaleway Serverless Containers* — clears the memory bar with room to spare: a container takes up
  to 12,228 MB, and the grant is 400,000 GB-seconds and 200,000 vCPU-seconds per account per month.
  Rejected on the metering. A card is required before anything can be ordered — "Ordering Scaleway
  resources requires a valid credit card" — and past the grant every further GB-second is charged,
  because the service is "billed on a pay-as-you-go basis, strictly on resource consumption (Memory
  and CPU)". Scaleway documents no hard spending limit anywhere in its billing documentation; its
  billing alerts notify only, and say so: "Billing alerts only provide a rough estimate of what may
  be charged to your monthly invoice." It scales to zero after 15 minutes idle and publishes no
  cold-start figure.
- *Azure Container Apps* — clears the memory bar, and is rejected on the metering more sharply than
  anything else here, because the vendor documents that the stop cannot be switched on. The grant is
  180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests per subscription per month, a
  card is required at sign-up, and past the grant it bills per second on both compute and requests.
  Azure does have a spending limit that disables deployed services — but "The spending limit isn't
  available for subscriptions with commitment plans or with pay-as-you-go pricing. For those types
  of subscriptions, a spending limit isn't shown in the Azure portal and you can't enable one."
  Pay-as-you-go is exactly the state the subscription must reach to keep a URL up past the free
  account's 30 days. That leaves budgets, which are notify-only: "Resources aren't affected, and
  your consumption isn't stopped." Memory is also sold only in fixed pairs with vCPU, so 2 GiB costs
  a full vCPU whether or not the work needs one.
- *Both of the above were checked after this decision was first written*, because the record listed
  only hosts eliminated on memory and these two clear it. Neither moves the conclusion: the argument
  that rejects Cloud Run rejects them identically, and Azure's own documentation states the bound
  this decision requires is unavailable.
- *Fly.io* — the fastest documented cold start of any host checked, and sizable to 4 GB. Rejected on
  the same metering, and more sharply: it has no ongoing free tier at all, only a time-boxed trial,
  after which a card is required.
- *Oracle Cloud Always Free* — genuinely $0 with no meter, 12 GB of RAM, and always-on, so no cold
  start at all. Rejected because it is a bare VM: Docker, a reverse proxy and TLS certificates are
  all hand-built and maintained, which is not one command and not hours this project has. Oracle's
  own documentation also warns that Always Free shapes can be refused for capacity, so the deploy
  can fail at the moment it is needed.
- *Cloudflare and Vercel* — neither runs a persistent container on a free tier. Cloudflare's Python
  Workers run under WebAssembly rather than in a container and cap CPU at 10 ms per request;
  Cloudflare Containers has no free tier. Vercel is a serverless-function platform, and its Hobby
  plan is restricted to non-commercial personal use, which a job-application prototype does not
  clearly satisfy.
- *Keeping the GPU tier from the original record* — there is no GPU work left in this product to put
  on it.

**Cost, stated.**

- **$9 a month**, for as long as the URL is up. Docker Spaces require a paid plan to create — "Static
  Spaces are free for everyone. Gradio and Docker Spaces run on compute and require a paid plan to
  create: PRO for personal accounts, Team or Enterprise for organizations" — and CPU Basic's zero
  hourly rate describes the hardware, not the right to create the Space.

  **Confirmed against the live platform.** The gate was tested rather than
  read: a request to create a private Docker Space on a free personal account was refused with HTTP
  402 and this body: `{"error":"Static Spaces are free for everyone, but hosting Gradio and Docker
  Spaces on free cpu-basic requires a PRO subscription. Subscribe at https://huggingface.co/pro"}`.
  Nothing was created.

  **The gate is recent, and that matters for reading any older evidence.** It landed in
  `huggingface/hub-docs` commit `34ee0f00` on 2026-07-21, *"Update Spaces docs: paid plan required
  for compute Spaces, ZeroGPU free tier"*. The previous revision of that page said the opposite:
  *"Each Spaces environment is limited to 16GB RAM, 2 CPU cores and 50GB of (not persistent) disk
  space by default, which you can use free of charge"*, with no plan gate anywhere in it. So any
  account, note or memory of a free compute Space from before 2026-07-21 is accurate and does not
  contradict this decision.

  **What the documentation does not say, and this record will not claim.** Every clause of the new
  text is about creating — *"require a paid plan to create"*, and *"Duplicating follows the same
  rules as creating a new Space"*. **Nothing states what happens to a compute Space that already
  existed on a free account when the policy landed.** That is undocumented, not settled, and this
  decision does not rest on it either way: the deploy needs a Space created now, and creating one
  now is refused. The one documented exception does not reach this app — *"Free personal accounts
  in good standing can still host up to 2 Gradio Spaces running on ZeroGPU"* is a Gradio-SDK
  allowance, and this app ships a Docker image.
- **The Space sleeps when idle** on free hardware and the restart time is not documented. A reviewer
  arriving after a quiet period waits for a container start before the first page. This is named in
  the README rather than papered over, and it is the one thing a keep-warm ping would fix if it turns
  out to matter.
- **Nothing is deployed by this decision.** Making the app publicly reachable is the owner's call.
  [0004](#0004) settles that a deployed URL is required, not when it goes up.

<a id="0024"></a>
## 0024. The README's specification is four tests; the demo-runbook tests are removed

**Evidence:** the eight failures run and read here before any edit.

**What was wrong.** Eight tests asserting over `README.md` and a `DEMO-RUNBOOK.md` failed, and none
of the eight was a code defect. They described a different project: a development process with
stages this project never ran, links to `docs/ARCHITECTURE.md`, `docs/03-decisions.md` and
`DEMO-RUNBOOK.md` — none of which is a path in this tree — and a rehearsed demo-day script counted
down in T-30, T-5, T-1 and T-0. Because these tests are the README's specification, writing README
prose against them would have written that other project into the deliverable.

**Chosen, for the runbook tests: removed, with the file they assert over never written.**
`tests/test_demo_runbook_present.py` asserted that a `DEMO-RUNBOOK.md` documents demo-day timings, a
failure-recovery procedure and a six-stage path. No such document exists, the pipeline it describes
is not this one, and nothing in the plan of work asks for a runbook. Deliverable 2 is a URL a
reviewer opens unattended, not a demo somebody presents, so the artifact those tests demanded has no
reader.

**Chosen, for the README tests: rewritten as a specification of this README**, in
`tests/test_readme_content.py`. Two of them stopped being content checks and became guards, because
the failure each catches is the failure that actually happened:

- every document path the README names is resolved on disk, so a dead link fails in the suite rather
  than in front of a reviewer — this is the general form of the three missing paths above;
- the reading-accuracy section may contain no percentage, because this project publishes only
  figures a run on this machine produced and no such run has happened. An estimate presented as a
  measurement is the one thing that section may not hold.

**Chosen, for the deploy lint:** the duplicated Space-card assertion in `tests/test_dockerfile_lint.py`
is replaced by the check nothing else makes — that the card's `app_port` equals the port the
container's `CMD` binds. Two files asserting the same string caught nothing twice; the disagreement
between them is what serves a blank page.

**A defect in the assertions themselves, found while rewriting.** Both copies required
`hardware: cpu-basic` in the README. `hardware` is not a key the platform defines. The documented key
is `suggested_hardware`, and the reference states plainly that setting it "will not automatically
assign an hardware to this Space" — it is a suggestion for whoever duplicates the Space, and the real
hardware is chosen in the Space's own settings. The tests now require the key that exists.

**Rejected.** *Writing a `DEMO-RUNBOOK.md` to make the three tests pass* — it would add a document
nobody asked for and nobody reads, to satisfy assertions inherited rather than chosen. *Deleting the
README tests outright* — the README is the larger half of deliverable 1 and the only tracked file
with no other check on it; the assertions were pointed at the wrong project, not worthless.
*Loosening them until they passed* — that is the move this project refuses everywhere else.

**Because** a test is a statement about what the product must be, and eight statements about a
different product are worse than none: they pass responsibility for the README to a specification
nobody here wrote.

<a id="0018"></a>
## 0018. An uploaded label image is kept as a file, not in the process that received it

**Chosen.** The image a reviewer uploads is written to a file — one per evaluation, named for the
evaluation id and suffixed with its media type — in a directory under the machine's temporary
directory, and `GET /labels/{evaluation_id}/image` reads it back from there. Three properties come
with it. An id that is not letters, digits, hyphen or underscore is refused, so nothing a caller puts
in the URL can name a file outside that directory. A write lands on a staging name and is then moved
onto its final name, so a process reading the directory never sees a half-written image. And an image
is dropped once it is seven days old, swept when the next one is written.

**Rejected.** *The 64-entry dictionary of raw bytes held in one process, which this replaces.* It
failed three ways a reviewer meets in normal use: the 65th upload evicted the first page's image, a
restart lost every image, and where the service runs more than one worker the page and its image came
from different processes so the image was missing about half the time. All three are one property —
the bytes lived in one process's memory — and no bound on the dictionary fixes any of them.

*A `data:` URI embedded in the result page.* It needs no store at all, which is genuinely simpler,
but it inflates the page by a third of the image's size and re-sends it whole on every render, and
the image then exists only inside one rendered page, so a reviewer cannot reopen a result or send
someone a link to it.

*SQLite.* Durable, single-file, and no harder to deploy — but it adds a schema and a blob column to
store what the filesystem already stores as files, and it answers no question the files do not.

*Object storage, S3 or equivalent.* The only option that also survives the container being replaced
and a deployment of more than one container. It needs an account, a key and an outbound call, and
[0004](#0004) requires the same application to run from a clone with none of those.

**Because** [0004](#0004) makes the local clone and the deployed container the same application, so
the store has to need nothing from either environment: no account, no service, no configuration. A
directory of files is the only one of the four that needs nothing from both.

**Cost, stated.**

- **The images do not survive the container being replaced.** A rebuild or a redeploy starts with an
  empty directory, so a result page opened before it shows a broken image. Surviving that means paid
  persistent storage, which is a cost this prototype has no reason to carry.
- **A deployment of more than one container does not share the directory.** Every worker on one host
  does, which is the shape this deploys in; two hosts do not. Object storage is the answer if that
  ever changes, and nothing here has to be undone to get there.
- **The bound on growth is age, not size.** A burst of large uploads inside the retention window is
  bounded only by the disk under it. Age was chosen over a count because a count is exactly what put
  a live page's own image at risk.
- **The sweep reads the whole directory on every write.** At this scale it is nothing beside the
  label read it follows. At a scale where it is not, the sweep is the part that changes.

**Amended — the prototype does not meet C-2, and that is deliberate.**

`docs/PRD.md` C-2 says the product "retains no label image or application data on its server once it
has returned the results for them". A store that keeps an image for seven days does not meet it, and
the entry above did not weigh it. The owner settled it: **this is a demo, and C-2 is a
production requirement rather than a demo one.** The labels this ships are public TTB COLA Registry
images under CC0 (`app/api/ui/samples.py`), so nothing it holds is anyone's private material. C-2
stays in the PRD unchanged, because it is the right requirement for the real thing.

Only half of C-2 is engaged in any case. The one disk write anywhere in this application is the label
image — checked across `app/` — so application data, including the applicant name and address the
form collects, exists for the life of the request and is never stored or written to a log.

**What a real deployment would do instead**, none of which the prototype carries:

- **Hold the image only until the result has been delivered**, dropping it when the reviewer leaves
  the result rather than on a seven-day sweep. That is C-2 as written.
- **Keep it inside the agency's own boundary**, in an authorized environment rather than on
  third-party hosting, because a label filed with a pending application is not public until the
  certificate issues.
- **Encrypt at rest, restrict reads by role, and log every access**, so that holding anything at all
  is accountable.

The README currently states the opposite — that nothing is stored — which was true before this
entry and is not true now. Correcting it is outstanding.

<a id="0019"></a>
## 0019. The browser-facing surface is one module per job, behind one router

**Chosen.** `app/api/ui.py` — 482 lines doing six unrelated jobs — becomes the package `app/api/ui/`,
one module per job: the three page shells, the single-label upload, the image route and its store,
the sample download, the bulk upload, and two support modules for what more than one of them needs.
`app/api/ui/__init__.py` mounts all of them on one `router`, so `app/main.py` still includes one
router, and the two dependencies a test overrides are still imported from `app.api.ui`.

**Rejected.** *Leaving it as one module.* Its own docstring claimed the module "does NOT import from
`app.services`, `app.vision`, or `app.rules`", and that was false: two of the six jobs run the
engine and four do not. One module cannot carry a true statement about what it depends on while its
jobs disagree about the answer, and that statement is the one a reader needs in order to know which
routes can fail for engine reasons.

*Six modules registered one by one in `app/main.py`.* It puts the shape of the browser surface in the
file that is about boot order, and it makes adding a page an edit to the application factory.

*Splitting on the URL instead of on the job.* `/batches` renders a form, `/batches/sample.zip`
streams a download and `/batches/upload` starts a batch worker. They share a prefix and nothing else,
so a split on the path would have put three unrelated jobs back in one module.

**Because** the jobs differ in what they depend on, not in what they are called: page rendering needs
Jinja and the settings, and the two upload routes additionally need the evaluator, the rule pack and
the reader. Splitting on that line is what lets each module say truthfully what it reaches for.

**Cost, stated.**

- **Six files where there was one, and two of them exist only to be shared.** Finding where the Jinja
  environment is built is now one import hop rather than a scroll.
- **Two names are importable from two places.** `app.api.ui` re-exports the two dependency-override
  seams so existing imports keep working, and they also live in the modules that define them.

<a id="0020"></a>
## 0020. A batch item with no image is refused by name, and one bad label does not end the batch

**Chosen.** Two halves of one mechanism in `app/batch/worker.py`. An item the worker holds no image
for is refused: `_resolve_label` returns nothing, and the item gets a `needs_review` envelope with no
fields whose single audit-trail row names `ENGINE.INPUT.LABEL_IMAGE_MISSING`. An item whose
evaluation raises is refused the same way, naming `ENGINE.WORKER.UNHANDLED`. Either way the consumer
records the result, broadcasts it, and goes on to the next item. `InFlightBatch.failures` holds the
sentence a person reads, and the snapshot renders that item as `failed` with the sentence on
`failed_reason`. The `stream-end` event carries a `failed_count`.

**Rejected.** *Standing in eight bytes of PNG header, which is what the code did.* `_resolve_label`
returned a `Label` whose `image_bytes` was the literal `b"\x89PNG\r\n\x1a\n"` for any item the lookup
did not hold. Only the bulk-upload route fills that lookup, so every caller of the JSON
`POST /batches` got it: the reader, the rule engine and the disposition all ran over eight bytes that
are not an image, and the envelope reported a verdict about it. A verdict about a label nobody
supplied is a fabricated measurement, and it is worse than no answer because it looks like one.

*Re-raising, which is what the code did for a failing evaluation.* `_consume` logged and re-raised, so
`run()` cancelled the producer and the batch ended at the first bad label. A 300-label batch that
tripped on label 4 left 296 labels unchecked and told the reviewer only an error class.
`docs/PRD.md` FR-13 requires the product to name the file at fault and check the rest of the batch.

*Rejecting the whole submission at `POST /batches` with a 422.* Honest about the JSON route, and
still wrong: the upload route can carry four good files and one unreadable one, and that batch has to
run. The refusal has to live per item, and once it does, the route-level rejection is a second
mechanism saying a worse version of the same thing.

*A new SSE event type for a refusal.* A new event type is invisible to the reader that exists:
`frontend/src/sse/useBatchStream.ts` listens for `label-result` and `stream-end` and nothing else. A
`needs_review` envelope puts the refused item in the reviewer's table today with no frontend change,
and it is the same shape `app/services/evaluator.py` already emits for an image too poor to read, so
one problem gets one answer on both paths.

**Because** the product's claim is that a reviewer can trust what it says about a label. Inventing an
image breaks that claim directly, and ending the batch breaks the reviewer's ability to act on the
rest of it. Both are answered by naming the item, recording a refusal as that item's result, and
carrying on.

**Cost, stated.**

- **Every item of a JSON `POST /batches` batch is now refused.** That endpoint takes references to
  labels the caller says the server holds, and there is no store to resolve a reference to an image,
  so the honest answer to all of them is the refusal. The batch path that works is
  `POST /batches/upload`, which carries the files. This is a limitation to state in the README, not
  a regression to hide: the endpoint never checked a real label, it only appeared to.
- **The reason code's own description is now slightly wrong.**
  `rules/reason_codes.yaml` says of `ENGINE.WORKER.UNHANDLED` that "SSE stream-end carries the error
  class". It still does, but only for a failure that is not per-label; a per-label failure now
  carries the code on the item's own envelope. One line of that registry needs editing.
- **A refusal envelope carries a reason code and no sentence.** A no-fields envelope has nowhere to
  put plain words — `plain_language_explanation` exists only inside a field finding — so the sentence
  lives on the snapshot's `failed_reason` and an SSE-only client does not see it. The single-label
  path has the same gap for an unreadable image. Closing it means a schema change and a frontend
  change together.
- **A test that subscribes to the bus now sees refusals unless it supplies images.** Several worker
  tests constructed items with no lookup and were, before this, exercising the fabricated-image path
  without saying so. They now pass a `label_lookup`, which is what the bulk-upload route does.

<a id="0021"></a>
## 0021. The batch consumer paces on the reviewer's pull, not on the queue

**Chosen.** After an item's events are broadcast, `_consume` holds the next evaluation while the
slowest attached SSE subscriber is more than `lookahead_k` events behind. With no subscriber
attached the gate is inert. It polls the subscriber queues every 10 ms and has no timeout.

**Rejected.** *Leaving the bounded queue as the demand signal, which is what the code claimed.* The
module docstring called the worker "pull-based, reactive-streams-style" and called
`BoundedQueue(maxsize=k+1)` "the single structural enforcement of pull-based demand". The producer
that queue throttles iterates a tuple already in memory, so it throttles nothing that costs anything.
All the cost is in `evaluator.evaluate`, on the other side of the queue, and it ran flat out whether
or not anyone was reading. The claim was not true of the code.

*Driving the gate off the `ItemState.PRESENTED` and `REVIEWED` transitions.* Those are the
reviewer-driven states the schema already names, and they are the right long-run answer. Nothing sets
them: no endpoint accepts them and no client sends them. Building that protocol is a feature with no
client at either end.

*Waiting on a drain signal instead of polling.* Cleaner, and it means changing `app/api/_sse_bus.py`,
which is shared by every SSE consumer in the app. A 10 ms poll on a path that is idle whenever anyone
is actually reading is not worth that blast radius.

*A timeout on the gate.* A subscriber that stops reading is meant to hold the batch — that is what
pull-based demand means, and a timeout would quietly restore the flat-out behaviour for the exact
reader the gate exists for.

**Because** the reviewer's pull is the only demand signal that exists today, and the SSE subscriber
queue draining is what that pull looks like from here. Putting the window at the seam where the work
costs something is what makes `LOOKAHEAD_K` govern anything at all.

**Cost, stated.**

- **A test that subscribes and never reads now hangs instead of failing.** That is the gate working,
  and it is a bad failure mode to debug. Two of this lane's own tests had to be reworked to read
  concurrently, and a third passed only because its item count sat exactly on the boundary.
- **The gate cannot wedge, but the argument is indirect.** A reader that goes away is unsubscribed by
  the `finally` in `app/api/batches.py` when the response generator closes, and `sse_starlette`'s
  periodic ping forces that within its ping interval. If either of those changes, a departed reader
  could hold a batch open.
- **A 10 ms poll runs while the gate holds.** It is a sleep, not work, and it only runs when the
  batch is already stopped — but it is a poll, and a drain signal would be better if the bus is ever
  opened up for other reasons.
- **The slowest subscriber governs everyone.** Two reviewers watching one batch means the batch runs
  at the pace of whichever one is behind. For this product's one-reviewer-per-batch shape that is the
  intended behaviour rather than a compromise.

<a id="0025"></a>
## 0025. The deploy runs on Google Cloud Run, reached through this project's own DNS zone

**Supersedes** [0023](#0023). **Evidence:**
`cloud.google.com/free/docs/free-cloud-features`, `developers.cloudflare.com/workers/platform/limits`
and `developers.cloudflare.com/containers/pricing`; `app/config.py:37`;
`docs/research/2026-09-15-hosting.md`.

**What changed.** [0023](#0023) is not wrong about any fact it states, and none of its vendor
quotations has moved. It rejected Cloud Run on one ground only — that a metered host bills an
unauthenticated URL without a hard stop, while a $9 plan fee is known in advance — and it weighed
that against no mechanism for bounding the meter, because none was on the table. A front door was:
this project's DNS zone already exists, and a proxy in front of the service takes a rate limit. With
the meter bounded at the edge, the $9 fee buys nothing the free tier does not already give, and the
owner settled the fork.

**Chosen.** **Google Cloud Run, one service, 4 vCPU and 4 GiB, scaling to zero,** built from source
by Cloud Build so no image is built on a developer's machine. The free tier is 2 million requests,
**180,000 vCPU-seconds and 360,000 GB-seconds of memory per month**. Builds are free to 2,500
build-minutes a month on `e2-standard-2`, the default pool; naming any other machine type forfeits
that allowance entirely.

**The size is set by which allowance runs out first, and it is not the obvious one.** At 4 vCPU the
CPU allowance covers 45,000 instance-seconds a month — twelve and a half hours of request-handling,
or roughly 38,000 label checks at the reader's measured 1.18-second median ([0005](#0005)), against
an expected demand of one reviewer. In those same 45,000 seconds a 4 GiB instance consumes 180,000
GB-seconds, which is **half** the memory allowance. Memory therefore cannot be the binding
constraint at this core count, and the second and third gigabyte are free. That matters because the
reader's working set is the carried-over 1.5-2 GB figure that [0023](#0023) records as never
measured: sizing at 4 GiB buys roughly double the top of an unverified range for nothing. Memory
only begins to bind at 8 GiB, where the two allowances are exhausted together.

**Because the bound moved from the plan to the edge.** The demand [0023](#0023) makes of a host is
that an unauthenticated URL cannot run up a bill. Four settings meet it without paying a plan fee:
the service caps at two instances, takes one request at a time, times out, and sits behind a proxy
on this project's own zone carrying a rate-limiting rule. One request at a time is not only a cost
control — it is what the five-second requirement needs, and it is what makes four cores worth
having: `OCR_NUM_THREADS` defaults to the service's core count, so one read is sized to use every
core the instance has, and a second request arriving beside it would contend for those cores rather
than add to them. The same default means a developer's machine reads the way the deployed product
does.

**And because the cold start stops being unfixable.** [0023](#0023) records one unresolved cost:
free Spaces hardware sleeps after 48 hours idle, so a reviewer arriving cold waits through a
container start and a model load, and names a keep-warm ping as the thing that would fix it. On
Cloud Run a ping costs almost nothing, because CPU is billed only while a request is in flight — so
a scheduled request every ten minutes holds an instance warm for a few hundred vCPU-seconds a month
out of 180,000. Ten minutes is the interval the vendor's own figure sets: Cloud Run "might keep
instances idle for a period of time after they finish handling requests (up to 15 minutes)". The
reviewer opens a warm URL. The service also runs with startup CPU boost, which doubles the
allocation to eight cores for the first ten seconds, so the start a ping pays for is the shortest
the platform offers.

**What no vendor documents, and this record will not invent.** Google publishes no cold-start figure
for Cloud Run, for any image size. The components of one that this project has measured are the OCR
engine's 0.4-0.9 second load, once per process; container pull and interpreter start are unmeasured
here. **The deployed cold start is therefore unknown until it is timed on the service**, and the
warm path is what the keep-warm ping exists to make the one a reviewer meets.

**Rejected.**

- *Hugging Face Spaces at $9 a month* — [0023](#0023)'s reasoning in full, and still sound on its own
  terms. Rejected because the constraint it was built to satisfy is now satisfied for nothing, and
  because it leaves the cold start unaddressed while Cloud Run does not.
- *Cloudflare alone* — it cannot run this app at any price short of the Workers Paid plan. Python
  Workers run under WebAssembly rather than in a Linux container, and the free plan allows **10 ms of
  CPU per request** against a reader whose median read is 1.18 seconds. Cloudflare Containers does
  run the image, and is **"$5 USD per month"** on Workers Paid with no free tier at all. Cloudflare
  keeps the job it is good at: DNS, TLS, the rate limit, and the scheduled ping.
- *Oracle Cloud Always Free* — still genuinely unmetered, and [0023](#0023)'s objection still holds:
  a bare VM means Docker, a reverse proxy and TLS built and maintained by hand. A tunnel removes the
  proxy and the certificates, which is most of that objection, but not the machine, its patching, or
  Oracle's documented capacity refusals. Held as the fallback if the meter ever proves unbounded in
  practice.
- *Every host rejected on memory in [0023](#0023)* — unchanged. The 1.5-2 GB reader still does not
  fit a 512 MB instance.

**Cost, stated.**

- **A billing account with a payment method is required, and Google's budgets alert rather than
  stop.** This is the exact objection [0023](#0023) raised, it is still true, and the instance cap,
  the request timeout and the edge rate limit are what answer it. A budget alert at one dollar is the
  tripwire, not the brake. The brake that does exist — a budget notification wired to switch billing
  off — is a documented pattern this project has not built.
- **Storage is not free.** Artifact Registry gives **0.5 GB a month**; this image will exceed it, and
  the overage rate is ten cents per GB per month. The true figure is therefore small change, not
  zero, and it is not known until an image is built and measured.
- **The reader's 1.5-2 GB working set is still an unverified carried-over figure**, for the reason
  [0023](#0023) gives. The service is sized at 4 GiB against it, roughly double the top of that
  range, which the arithmetic above shows costs nothing at this core count. If a real run exceeds
  even that, the instance is killed and the size has to go up, which begins to cost GB-seconds
  against the same allowance.
- **Nothing is deployed by this decision.** Making the app publicly reachable is the owner's call.
  [0004](#0004) settles that a deployed URL is required, not when it goes up.

**Amended — the edge rate limit answers nothing.** It denies nothing on this plan ([0029](#0029)).
What answers the objection above is the instance cap, the request timeout, and the invoker check
([0028](#0028)), under which a request from anyone but the Worker is refused before it is billed.

<a id="0026"></a>
## 0026. Glare is not measured before the read; legibility is judged by what the reader returned

**Evidence:** the gate run over all 56 face images of the 30 real labels
and all 6 damaged variants, and the reading-accuracy run before and after.

**What was wrong.** `app/vision/quality.py` refused an image as
`WARNING.LEGIBILITY.GLARE` when over 15% of its pixels were brighter than 240 and the image's own
median was not that bright. Run over the corpus, that gate was wrong in both directions at once:

- it refused **seven faces of five real labels** that are sharp and readable — Laplacian variance
  from 643 to 2797 against a low-resolution floor of 50. Two of the five lost both faces, so those
  labels were scored against no reading at all;
- it passed `var-glare`, the variant built with a hotspot over its warning, and refused `var-skew`,
  which has no glare on it. The manifest expects `var-glare` to pass every check, so the gate had
  no case anywhere in the corpus that it was right about;
- its unit test passed because it fed synthetic noise with a 25% pure-white square, which is the
  shape of a white label background rather than the shape of glare.

**Rejected: move the threshold.** The statistic measures how light the label stock is. An unprinted
white area and a blown-out one are the same pixel values, so no count of bright pixels separates
them, and what a hotspot covered is not knowable before the label is read. Any threshold that fits
these 30 labels is fitted to them, and the labels this is judged on are not these.

**Chosen: no glare gate, and a legibility test after the read.** An image the detector finds no
text on, at any of the three rotations it tries, is an image nobody can check, and it answers
`WARNING.LEGIBILITY.LOW_RESOLUTION`. That holds whatever made the image unreadable and does not
depend on guessing the cause from the pixels. The gates that remain — low resolution by Laplacian
variance, motion blur by high-frequency energy — measure sharpness, which a global statistic can
honestly measure.

`WARNING.LEGIBILITY.GLARE` stays registered and moves to `reviewer_vocabulary` in
`rules/reason_codes.yaml`: nothing emits it, and a reviewer looking at the label can see the glare
the product cannot measure. The same file's [0013](#0013) settles that pattern for
`WARNING.LEGIBILITY.NO_CONTRAST`.

**What it cost.** A label is read before it can be refused, so an unreadable image now costs one
OCR pass — about 1.5 seconds — instead of being turned away for nothing. That is the price of not
refusing readable labels, and it is paid only on images that produce no text.

<a id="0027"></a>
## 0027. The reading-accuracy figures are published as counts, and the section no longer holds a hole

**Evidence:** the run recorded in the section itself.

**What changed.** [0024](#0024) settled that the reading-accuracy section may hold no percentage,
because no run on this machine had produced one and an estimate presented as a measurement is the
one thing that section may not contain. The constraint it recorded has not changed; the fact it
rested on has. The run has happened, over all 30 real labels and their 56 face images, so the
marked hole is filled with what it measured.

**Chosen: counts, not percentages.** Each check is published as correct of scoreable — `16 of 30` —
and not as a percentage. Thirty labels is a small denominator, and a percentage of it reads as a
precision the corpus does not carry: `53.3%` from 16 of 30 invites a comparison with a figure drawn
from thousands. The denominator differs between checks, too, because a check the label cannot
settle is left out of it rather than counted against the reader, and a bare percentage hides that.

**The guard changes rather than goes.** `test_readme_publishes_no_unmeasured_accuracy` in
`tests/test_readme_content.py` enforced the hole. It now enforces the published form: no percentage
in the section, every one of the nine checks named, and the corpus the figures came from stated.
The failure it catches is the same one — a number in front of a reviewer that no run produced.

<a id="0028"></a>
## 0028. The Cloud Run URL is closed with IAM, not hidden, because the edge cannot be the only door

**Evidence:** `docs.cloud.google.com/run/docs/securing/ingress`,
`/run/docs/authenticating/public`, `/run/docs/authenticating/service-to-service`,
`/run/docs/configuring/custom-audiences`, `/docs/authentication/token-types` and
`cloud.google.com/run/pricing`; `scripts/deploy.sh`; the live service's IAM policy.

**What was found.** [0025](#0025) bounds the meter with four settings, one of which is a rate limit
on a proxy in front of the service. That reasoning holds only if the proxy is the sole way in. It is
not: Cloud Run issues its own `run.app` URL, that URL is on the public internet, and nothing about
putting a hostname in front of the service takes it away. A rate limit at the edge that anyone can
walk around bounds nothing at all, and the service it protects is the one part of this system that
spends money per request.

**Chosen: the invoker check stays on, and the edge is the only identity that passes it.** The
service is deployed with `--no-allow-unauthenticated`; `roles/run.invoker` is granted to
`ttb-edge-invoker@ttb-label-check.iam.gserviceaccount.com` and to nothing else; and the Worker
holds a key for that account as a Worker secret and signs each forwarded request with a Google ID
token. The `run.app` URL stays reachable and answers `HTTP 403: The request was not authenticated`
to everyone else, which is the state `scripts/deploy.sh` already deploys by default.

**Because a denied request is free.** This is what makes IAM the bound rather than merely a lock.
Google's pricing page states it in one sentence: "Requests are only billed when they reach the
container after successfully being authenticated, requests denied by IAM policy are not billed." A
flood aimed straight at the `run.app` URL therefore costs nothing at all, while the edge's rate
limit ([0029](#0029)) governs the requests that do reach the container. The two are not alternatives; the invoker check is what makes
the edge limit meaningful.

**The audience is the `run.app` URL, not the hostname a reviewer sees.** "Custom domains are
currently not supported for the `aud` value", so the token the Worker mints for a request to
`ttb.aaroncarney.me` must name the Google-issued URL. A custom audience — an arbitrary string
configured on the service — is the documented way out of that, and is not taken: it adds a second
name to keep in step across the service and the Worker, to buy nothing, since the Worker is the only
caller and already knows the origin URL it forwards to.

**Rejected.**

- *Disabling the `run.app` URL* (`--no-default-url`, or the
  `run.googleapis.com/default-url-disabled` annotation). This is real and documented, and it removes
  the bypass by removing the address — including the Worker's. A Cloudflare Worker reaches this
  service over the public internet at exactly that URL, so disabling it leaves the service with no
  address the edge can use, and restoring one means a Google load balancer this project has no other
  reason to run.
- *Ingress `internal-and-cloud-load-balancing`*, for the same reason and more sharply: "Direct
  requests to the `run.app` URL from the internet are not allowed" under that setting, and the
  Worker is a public-internet caller, not a VPC client and not a Google external Application Load
  Balancer. It would lock out the edge and nobody else. Ingress stays `all`.
- *Leaving the URL open and trusting that nobody finds it.* The URL is printed by the deploy, sits
  in the Worker's configuration, and is guessable from the project number. Obscurity is not a bound,
  and the cost of being wrong is metered.
- *A shared secret header instead of an ID token.* It would keep unwanted traffic out of the app but
  not off the meter: the request still reaches the container and is still billed, because the check
  happens in this project's code rather than in IAM.

**What it costs.** An ID token is "valid for one hour, and can't be revoked", and minting one is a
signed-JWT exchange against Google's token endpoint. The Worker therefore has to hold a private key,
cache the token it gets back, and refresh it before the hour is out — the whole of that cost falls
on the edge, and none of it on the app. The key is a Worker secret. It is never committed here, and
a key that leaks is an invoker for as long as it exists, so it is revoked at the service account
rather than waited out.

**The deployment came to meet this record, and the state it describes is verified
rather than asserted.** It did not before: the service had been deployed with `TTB_PUBLIC=1`, the
IAM policy listed `allUsers` beside the edge account, and the Worker forwarded anonymously, so both
doors stood open. What closed it was removing the `allUsers` binding and redeploying without that
variable, plus the token minting in `edge/src/index.js`. Measured after the redeploy, and the pair
is what makes the claim:

- `GET https://ttb-label-check-196798689841.us-central1.run.app/` with no credentials answers **403**.
- `GET https://ttb.aaroncarney.me/api/health` answers **200** with the app's own body.

The second is what proves the first is a closed door rather than a broken service: the only
difference between the two requests is the ID token the Worker attaches. All 38 test submissions
also completed through it, so the signing survives a multipart upload.


**Amended — the edge limit governs nothing.** The rate limit this entry pairs with denies nothing
([0029](#0029)). The invoker check stands alone as the bound on who can run up the meter, and the
two-instance cap bounds how fast.

<a id="0029"></a>
## 0029. The rate limit lives in the Worker, because a Free zone's own rate limiting rule cannot see the hostname

**Evidence:** `developers.cloudflare.com/waf/rate-limiting-rules/`,
`developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/` and
`developers.cloudflare.com/workers/platform/limits/`.

**What was found.** [0025](#0025) names "a rate-limiting rule" on this project's zone as one of the
four settings that bound the meter, and does not say which mechanism carries it. Cloudflare offers
two, and on the Free plan this zone runs on, the obvious one cannot do the job. The availability
table for WAF rate limiting rules gives a Free zone **one** rule, whose expression may use only
**"Path, Verified Bot"** — the `Host` field first appears on Pro — and whose counting period is
**"10 s"** and nothing else.

`aaroncarney.me` is not this project's zone alone. Every hostname on it shares that single rule, and
a rule that cannot name a hostname either counts this project's traffic against every other site on
the zone or exempts nothing. A ten-second window is also the wrong shape for the bound being
defended: what runs up a Cloud Run bill is sustained traffic over an hour, and a limit that forgets
everything every ten seconds bounds a burst, not a bill.

**Chosen: the Workers Rate Limiting binding, inside the Worker that already fronts the service.**
The Worker is the one place that knows the request is for `ttb.aaroncarney.me`, because it is only
invoked for that hostname, so the scoping the WAF rule cannot express is free here. Its `period`
"must be either `10` or `60`", so the window is 60 seconds and the per-minute figure is what has to
be set to bound the meter.

**Rejected.**

- *A WAF rate limiting rule on the zone* — for the reasons above. It is not a threshold that needs
  tuning; it is a rule that cannot be written for one hostname on this plan.
- *Upgrading the zone to Pro for the `Host` field* — Pro is a monthly fee for a capability the
  Worker already has for nothing, and [0025](#0025)'s whole reason for choosing this shape was that
  the bound costs no plan fee.
- *No limit, relying on the two-instance cap* — the cap bounds how fast money is spent, not how
  much. Two instances held busy for a month is the whole free allowance and then some.

**Settled by measurement, and not in either direction this record expected.**
Cloudflare's documentation does not state whether the rate limiting binding is available on the
Workers Free plan — its own page, the Workers pricing page and the GA changelog were all read that
day and none says either way. This record supposed a deploy would either take the binding or refuse
it. It does neither: **it takes the binding and then never denies anything.**

The evidence, all against the deployed Worker on `ttb.aaroncarney.me`:

- `wrangler deploy` accepted the binding and reported it: `env.PROXY_RATE_LIMIT (120 requests/60s)`.
- 310 requests inside one 60-second window, 150 concurrent and 160 sequential, were **all forwarded**.
- Reconfigured to **5** requests per 60 seconds and redeployed, twelve sequential requests were all
  forwarded.
- A build that returned `limit()`'s own answer in a response header reported `success: true` on the
  tenth request of ten under that limit of five — so the call is reached, the binding is bound, and
  the verdict itself is the thing that is wrong.

**So the limit fails open, and silently**, which is worse than a refusal would have been: a
refusal at deploy time is visible, while this looks exactly like a working rate limit from every
angle except a test that exceeds it. The call stays in the Worker, because it is this record's
chosen mechanism and it begins holding the moment the platform honours it, and because removing it
would leave nothing to re-enable. But **nothing in this deployment rate-limits anything today**, and
what bounds the meter is [0028](#0028) alone: a request the invoker check denies is never billed.
The fork this record left open therefore reopens on its own terms — the zone upgrade, or a counter
of this project's own — with the added knowledge that the free binding cannot be trusted to hold.

**Two limits that come with it, neither fatal.** Counts are per Cloudflare location — "for each
unique key you pass to your rate limiting binding, there is a unique limit per Cloudflare location"
— so a distributed flood gets one allowance per location it arrives at, not one in total. Against
one reviewer's traffic that is immaterial, and against a flood the Cloud Run invoker check
([0028](#0028)) is what actually holds. A Free Worker also allows 50 subrequests per invocation,
which a one-request proxy does not approach.

**Amended — the fork is closed, not reopened: the limit stays inert and nothing replaces it.** The
owner ruled against a limiter of any kind for this deployment, the zone upgrade and a counter of our
own included. It is a free demo that few people will ever reach, and spending on a plan or building a
counter to guard it buys nothing the other two bounds do not already give. The call stays in the
Worker, inert. What bounds the cost is the invoker check ([0028](#0028)), which refuses every caller
but the Worker before a request is billed, and the two-instance cap in `scripts/deploy.sh`.

<a id="0030"></a>
## 0030. A file that is not an image is refused by name inside the batch, not by rejecting the batch

**Evidence:** `app/api/ui/submit.py`, which carries this behaviour now — it was written in
*app/api/ui/bulk_upload.py*, the module [0045](#0045) merged away; requirement R13;
[0020](#0020), which removed the premise the old behaviour rested on.

**What was wrong.** `POST /batches/upload` read every uploaded file, and the first one whose bytes
were not a PNG or JPEG ended the whole submission with a 400 and an error page. Four good label
images submitted alongside one `.txt` were all discarded, unchecked, and the reviewer's only route
back was to find the bad file themselves and upload everything again. Requirement R13 is a P0 and
asks for both halves: *"that file is named with an instruction and every other submission has
results."* The route delivered the first half and destroyed the second.

`tests/test_ui_routes.py::test_bulk_upload_rejects_non_image` held that behaviour in place and
defended it in its own docstring — a 400 was better than "silently scheduling a batch that will
explode mid-stream." That was true when it was written. [0020](#0020) made it false: the worker now
refuses an item it cannot check by name, records the refusal as that item's own result, and goes on
to the next one. There is no mid-stream explosion left to avoid, so the test was defending a cost
that no longer exists against a requirement that does. Changing it was the fix, not working around
it.

**Chosen.** The bad file is queued like every other file and refused as its own item.

| Where | What happens |
|---|---|
| The route | Reads every file, detects the type of each, and rejects nothing on that basis |
| A file that is not PNG or JPEG | Gets a `BatchItem` and an application like any other, is left out of `label_lookup`, and gets an entry in a new `refusals` map: the reason code `ENGINE.INPUT.LABEL_IMAGE_UNSUPPORTED` and the sentence naming the file |
| The worker | Checks `self._refusals` before it looks for an image, and where the caller has named a reason, uses it — the same refusal envelope, `record_failure` and `failed_count` path [0020](#0020) built |
| The reviewer | Sees the file in the batch table as `failed`, with `failed_reason` naming it and saying what to do, while every other file has results |
| No file in the set is an image | Still a 400 at the form, because there is no batch to show a refusal in — this is the empty-submission case wearing different clothes |

`ENGINE.INPUT.LABEL_IMAGE_UNSUPPORTED` is a new registry entry rather than a reuse of
`ENGINE.INPUT.LABEL_IMAGE_MISSING`. The two name different facts: the file arrived and was read and
is simply not an image, against nothing having arrived at all. The existing code's sentence tells the
reviewer to *send the label files themselves*, which is the wrong instruction for someone who did.

**Rejected.** *Letting the worker discover it, by leaving the file out of `label_lookup` and saying
nothing* — the worker would answer "no image was supplied for this item", which is false: the file
was supplied. The route is the only place that knows why, so the route is where the reason is
written. *Pre-recording the sentence with `InFlightBatch.record_failure` before the worker starts* —
the worker overwrites `failures[label_id]` when it refuses the item, so the specific sentence would
be silently replaced by the generic one; making the worker prefer an existing entry would hide the
contract in an ordering rule. *Dropping the bad file from the batch entirely and running the rest* —
it satisfies "every other submission has results" and fails "that file is named": the reviewer gets a
batch of four from a submission of five and nothing says which one went missing, which is the failure
mode this product refuses everywhere else. *A 422 listing every bad file, with the good ones
discarded* — a better error page for the same lost work.

**Because** a reviewer's batch is the unit of their attention and one unreadable file in it is not a
reason to throw away the work the product can do on the rest. That is what [0020](#0020) settled for
the worker; the upload route was the last place still deciding it the other way.

**Cost, stated.**

- **A refused item consumes a queue position and a result slot**, so a set of fifty `.txt` files
  builds a fifty-item batch that checks nothing. That is the honest rendering — each file is named —
  but it is slower and noisier than one error page would be.
- **The type check is still the first eight bytes, not a decode.** A file with a PNG header and a
  corrupt body is not caught here; it reaches the reader and is refused further down, by a different
  code. The route's guarantee is about the type a file declares itself to be, not about whether the
  image opens.
- **The refusal carries no `plain_language_explanation`.** Same gap [0020](#0020) named: the sentence
  lives on the snapshot's `failed_reason` and a client reading only the SSE stream does not see it.

<a id="0031"></a>
## 0031. The accessibility target is WCAG 2.0 A and AA, which Section 508 requires and the gate scans; WCAG 2.2 is not adopted

**Evidence:** 36 CFR part 1194 appendix A, E205.4 and E207.2, quoted in
`docs/reference/accessibility.md`; axe-core 4.11.4's own rule table, read here; `tests/test_a11y_axe.py`
as it stands; [0017](#0017), the precedent for correcting approved requirement text rather than the
product.

**What was wrong.** Three documents promised a conformance level the project was not built to reach
and had no test that could ever hold it. `docs/PRD.md` NFR-3 said *"Every screen meets WCAG 2.2 level
AA"*; `specs/0001-label-verification/requirements.md` R17 repeated it; `docs/reference/accessibility.md`
was titled for 2.2 and argued for it. The gate, `tests/test_a11y_axe.py:59` and `:75`, requests
`['wcag2a', 'wcag2aa']` — WCAG 2.0 Level A and AA, and nothing above it. The test file's own docstring
says so. A requirement above a gate that cannot fail against it is the requirement's defect, which is
what [0017](#0017) settled for FR-7.

The argument for 2.2 also did not survive being checked. `docs/reference/accessibility.md` gave two
criteria as the whole reason for the level — 2.5.8 Target Size and 2.4.11 Focus Not Obscured. Read
against the installed axe-core 4.11.4 (104 rules, `axe.getRules()`):

| Requested tag | Rules that would actually run |
|---|---|
| `wcag22aa` | `target-size` (2.5.8) |
| `wcag22a` | none |
| `wcag21aa` | `autocomplete-valid`, `avoid-inline-spacing`; `css-orientation-lock` is tagged `experimental` and does not run unless enabled by name |
| `wcag21a` | none; `label-content-name-mismatch` is tagged `experimental` |
| anything for 2.4.11 | **none, at any tag** |

So moving the gate to 2.2 would have bought exactly one meaningful rule, `target-size`, and bought
nothing at all for 2.4.11 — one of the two criteria the level was chosen for has no automated rule in
axe-core at all. A green run at 2.2 would have asserted a criterion it never examined.

**Chosen.** The target is the level Section 508 makes binding, and the documents are corrected to it.

| Where | What it says now |
|---|---|
| `docs/PRD.md` NFR-3 | Every screen meets WCAG 2.0 Level A and AA — the level Section 508 requires — read by an automated scan on each screen and a conformance review before each release |
| `specs/0001-label-verification/requirements.md` R17 | The same level, with the automated scan named alongside the reviewer |
| `tests/test_a11y_axe.py` | Unchanged. It already requests `wcag2a` and `wcag2aa`, and that is now the level the requirement names |
| `docs/reference/accessibility.md` | Titled and argued for 2.0 A and AA. Its criteria table keeps every row and marks which WCAG version each criterion arrived in, so the ten that are the promise are distinguishable from the five built above it |
| 1.4.10 Reflow, 1.4.11 Non-text Contrast, 4.1.3 Status Messages (WCAG 2.1 AA) | Built and kept, and 1.4.10 has its own test, `tests/test_reflow_320px.py`. Not promised as a conformance level |
| 2.4.11 Focus Not Obscured, 2.5.8 Target Size (WCAG 2.2 AA) | Kept in the reference as design guidance. Neither is claimed, and 2.4.11 is stated as not machine-checkable |

**Rejected.** *Adopt WCAG 2.2 AA and move the gate to match it* — the literal reading of the promise,
and the cost is the reason it was not taken: it buys one runnable rule, `target-size`, whose result on
this UI has never been measured, so the work is an unbounded frontend change discovered after the fact;
it buys nothing for 2.4.11, which no automated rule covers, so half the stated reason for the level
stays a review item either way; and it raises the product above the legal floor at a point where
nothing requires it. *Adopt WCAG 2.1 AA* — closer to what was built, since three of the criteria in the
reference are 2.1 and one of them has a dedicated test, but its axe tags add only `autocomplete-valid`
and `avoid-inline-spacing`, both structural, and neither has been run here. Naming a level the gate has
not been shown to pass would re-create the same defect one number lower. The three 2.1 criteria are
kept and tested without being promised, which is the honest form of the same thing. *Leave NFR-3 at 2.2
and record the gap as a known limitation* — costs nothing and buys nothing: the product keeps claiming
a level it does not scan, and R17 stays a P1 that no run can fail.

**Because** Section 508 is the regulation that binds this product, it names WCAG 2.0 Level A and AA,
and that is the level the gate already scans on every screen. A requirement set above what is legally
required and above what any test can hold is a promise to a reviewer that nothing in the repository
keeps.

**Cost, stated.**

- **The product no longer claims the current accessibility recommendation.** A reviewer comparing this
  against a product that states WCAG 2.2 AA sees the older standard, and `docs/approach.md` previously
  made a virtue of the opposite. The defence is that the claim is now true and the older standard is
  the one with legal force; it is still a smaller claim than the one withdrawn.
- **2.5.8 Target Size is not measured anywhere.** Every control may already be 24×24 CSS pixels or
  larger — nobody has run `target-size` against this UI, so nothing here knows. Adopting 2.2 later
  starts with that measurement.
- **2.4.11 Focus Not Obscured stays a review item under any level.** axe-core 4.11.4 carries no rule
  for it, so the sticky-header case `docs/reference/accessibility.md` names can only be caught by a
  person looking.
- **The gate does not yet cover all three screens.** `app/api/ui/shells.py` serves `/`,
  `/batch/{batch_id}` and `/batches`; `tests/test_a11y_axe.py` visits the first two. Lowering the level
  does not close that hole — NFR-3 says *every* screen at whatever level, and `/batches` rests on
  review alone until a third case is added. Named here so the correction is not mistaken for coverage.
  **Closed since:** the third case exists —
  `tests/test_a11y_axe.py::test_axe_zero_aa_violations_batch_list` scans `/batches`, so the gate now
  covers all three screens and NFR-3 is met on coverage. The cost above is left standing because it
  was true when this decision was taken; this line records that it no longer is.
- **Two approved documents changed after approval**, the same cost [0017](#0017) carried: `docs/PRD.md`
  NFR-3 and `specs/0001-label-verification/requirements.md` R17 were amended rather than the code. The
  amendment is logged in `docs/PRD-decisions.md`.

<a id="0032"></a>
## 0032. A label's identifier is not its filename: `label_id` is display text and leaves the logs, `evaluation_id` is minted

**Evidence:** `app/logging/redaction.py`'s own contract, *"nothing a
submission contains reaches the logs"*; `app/logging/otel_genai.py` as it stood; the reference
envelopes in `tests/fixtures/envelopes/batch/`, where `evaluation_id` and `label_ref` are already
different kinds of string; [0020](#0020), which put the filename in the refusal sentence on purpose.

**What was wrong.** An uploaded file's name became the label's identifier — `app/api/ui/bulk_upload.py`
built `label_id` as the batch id, the position and the filename, then handed that same string to the
evaluation as its `evaluation_id`. Both mechanisms that are supposed to keep a submission out of the
logs were bypassed, in three different ways at once:

- The formatter writes the free-text `msg` before the allow-list runs, so a message that interpolated
  the label id or the refusal sentence carried the filename out whatever the allow-list said.
- `evaluation_id` is *on* the allow-list, correctly — it is the correlation key. Deriving it from the
  filename meant the allow-list emitted the filename by design.
- Where a batch arrived as refs with no application, `app/batch/worker.py` synthesised one and used
  `label_id` as its `evaluation_id`, reaching the same place by a fourth route.

An uploader who names a file after a person therefore put that person in the logs, and the redaction
filter was never involved.

**Chosen.** The two strings are separated by what they are for.

| String | What it is | Where it goes |
|---|---|---|
| `label_id` / `label_ref` | Display text. Carries the uploader's filename so a reviewer can tell which file a row is | The page, the SSE stream, the refusal sentence. Never a log line |
| `evaluation_id` | Correlation key, minted by the app | Every log line, the audit record, the override lookup |

`label_id` came off the allow-list in `app/logging/otel_genai.py`, both upload routes and the worker's
synthesised application mint their own `evaluation_id`, and the worker's log lines carry the batch id
and the queue position instead of the label id and the reviewer's sentence.
`tests/test_logging_filename_never_leaks.py` runs the real worker with a person-named file through
both the refusal path and the ordinary path and reads what the real handler emits.

**Because** a filename is whatever the uploader typed, which makes it submission content under the
rule the redaction filter already states, and an identifier that doubles as content cannot be kept out
of telemetry by a list of field names.

**Cost, stated.**

- **A log line no longer names the file.** An operator reading logs sees `batch_id` and a queue
  position, and has to go to the batch page to learn which file that was. That is the trade the rule
  requires: the correlation is complete, the identification is not.
- **The reviewer's sentence still names the file, and it is still stored.** [0020](#0020) put it there
  so a refusal says which file was refused, and `failed_reason` on the batch snapshot keeps it. This
  decision covers the logs only; anything written to the snapshot or the audit record is a separate
  question that has not been asked.
- **`evaluation_id` for a synthesised application is now random.** Two runs of the same ref batch no
  longer produce the same id, so a test that pinned one would have to be rewritten. None did.

<a id="0033"></a>
## 0033. A single label's result is kept, so a reviewer can overrule it

**Evidence:** `app/api/overrides.py` as it stood, which searched
`app.state.batches` and nothing else; `app/api/ui/results.py`, the store this entry added — the
route that used to evaluate a single label and keep only its image was
*app/api/ui/_result_page.py*, which [0045](#0045) deleted; [0018](#0018), which settled where an
uploaded image is kept and why.

**What was wrong.** The override endpoint answered 404 for every single-label check, always. It looks
an evaluation up by walking the in-flight batches, and a single label is in no batch: the result page
rendered the envelope into the template and let it go. The interface offered the override drawer on
that page regardless, so a reviewer could fill it in, submit it, and be told the label did not exist.
The front-end source said so in a comment rather than the product doing anything about it.

The capability was not missing by decision. FR-9 asks for a reviewer override with a reason code on a
checked label, and nothing in it distinguishes a label checked on its own from one checked in a batch.

**Chosen.** Single-label results are kept where the single-label images are kept — one JSON file per
evaluation under the machine's temporary directory, swept on the same seven-day window, in
`app/api/ui/results.py`. The override endpoint tries the in-flight batches first and this store
second, writes the amended envelope back to whichever held it, and announces on the batch's stream
only when there is a batch.

**Because** the reasoning in [0018](#0018) for the image applies unchanged to the result beside it: a
page opened now must still be whole when it is looked at again, every worker on the host must read
what the others wrote, and a restart must not lose it. Two stores with one rule between them is
cheaper to hold in the head than one store with an exception in it.

**Rejected.** *Keep single-label results in memory alongside the batches* — smaller, and it is what
the batch path already does, but it fails in the three ways [0018](#0018) already rejected for the
image: a restart loses it, a second worker does not see it, and nothing bounds what one process
accumulates. It would also put the result and the image it belongs to in two different kinds of place.
*Leave it, and take the override drawer off the single-label page* — honest, and it would have cost
nothing, but it withdraws a capability the requirements ask for to avoid keeping one file.

**Cost, stated.**

- **An override is possible for seven days and then is not.** After the sweep the record is gone and
  the endpoint answers 404 again, with a message that now says so. The window is the image's window,
  chosen there for how long a page stays worth reopening, not for how long a reviewer has to change
  their mind.
- **The same result now exists in two places while a batch is in flight.** A label checked in a batch
  is in `app.state.batches`; one checked on its own is on disk. The endpoint tries them in that order,
  and an evaluation id that somehow appeared in both would be amended in memory only.
- **Nothing serves a kept single-label result back.** The store exists for the override path. Opening
  the result page again re-renders from the template, not from the store, so an override applied a
  moment ago is in the record but not on the page until the page is reloaded from a fresh check.
- **It puts applicant material on disk, which the image alone did not.** The envelope carries each
  field's `expected_value` — what the application declared, the applicant's name and address among
  them — beside the `extracted_value` read off the label. [0018](#0018) weighed a photograph of a
  public label; this weighs the form's own contents, and C-2 asks the product to keep neither. The
  narrower store this argues for is one holding only what an override needs to amend: the evaluation
  id, the per-field dispositions, and the audit trail. That was not built, and the whole envelope is
  what is written.

<a id="0034"></a>
## 0034. The bbox overlay and the evidence panel are removed, because neither can be fed truthfully

**Evidence:** `app/vision/local.py`, which reads boxes off a copy downscaled
to 1600 pixels on its longest edge and reads the warning off a frame it may have rotated;
`app/api/ui/images.py`, which serves the original uploaded bytes; the 43 distinct `cfr_citation`
strings in `rules/`, against the one piece of regulation wording the product keeps
(`assets/warnings/govt_warning_16_21.txt`, §16.21 only).

**What was wrong.** Three interface parts were built and wired to nothing. `BboxOverlay` was imported
by no page and shipped in neither bundle. `EvidencePanel` was mounted on the single-label page only as
a placeholder — closed, with every content prop an empty string — so that the bundler would still
carry it. `CitationChip` rendered as a button whose `onOpen` neither call site supplied, so on both
the single-label page and a batch's detail panel a reviewer could press it and nothing happened.

**Chosen.** `BboxOverlay` and `EvidencePanel` are deleted, with their tests. `CitationChip` keeps the
citation on the card and stops being a control: it is a span.

**Because** neither component has data behind it that this product can supply honestly.

The boxes in the envelope are in the reader's pixel space, not the uploaded image's. The reader scales
any label longer than 1600 pixels down before it detects anything, and registry photographs "run to
several thousand pixels", so for a typical upload the two spaces differ; for the government warning
the boxes may also come from a frame rotated 90 or 270 degrees. The only image the interface can show
is the original upload, at `/labels/{evaluation_id}/image`. Drawing one on the other puts the boxes in
the wrong places, and the code already says so about the one measurement that does use them: handing
the full-size image to the stroke-width measurement "would crop the wrong part of a label that was
downscaled on the way in". Making the overlay correct means carrying the reading frame's size and its
rotation, per field, through the wire schema — a schema change, not the wiring the component was left
waiting for.

The panel's left column is the regulation's own wording, and nothing here holds it. The rules name 43
distinct citation strings, many of them compound (`27 CFR §4.32(a)(1), §4.33`, `27 CFR §5 Subpart I`).
`docs/reference/` summarises the three parts in prose for a reader and is loaded by no code. The one
verbatim text the product keeps is §16.21, and it is kept because a validator matches a label's
warning against it character for character. Filling the other 42 means writing regulation text by hand
into a compliance tool with no test that can check it against the regulation — the kind of claim this
build refuses everywhere else. The panel's right column is already on the card: `RuleVerdict` carries
the plain-language explanation and the reason code, and the card itself carries extracted against
expected.

Neither part is required. `docs/PRD.md` and `specs/0001-label-verification/` ask for no region overlay
and no regulation-text panel. Both came from the component inventory in
`docs/research/2026-09-15-federal-ux-for-senior-users.md`, which is dated research and governs nothing.

**Rejected.** *Read the image's size in the browser* — `naturalWidth` and `naturalHeight` off the
served image would cost no schema change, and they are the wrong numbers: they describe the upload,
which is the space the boxes are not in. *Carry the reading frame through the envelope* — correct, and
it is the overlay's real price rather than the wiring it looked like it needed; it is what a later
version would do. *Link each chip to eCFR instead of opening a panel* — the citation strings are
heterogeneous enough that parsing them into section URLs would mislink some, and a compliance tool
showing the wrong regulation is worse than one showing none. *Leave all three in place* — every one of
their own tests passed, so nothing was failing; what was wrong is that the interface offered a
reviewer a control that does nothing, which is the one thing a reviewer cannot check for themselves.

**Cost, stated.**

- **A reviewer cannot see where on the label a value was read from.** The envelope still carries
  `field.evidence.bbox` and the raw-JSON drawer still shows it, but nothing draws it on the image.
- **A reviewer who wants the regulation's wording leaves the product to get it.** The card names the
  section; looking it up is theirs to do.
- **The work is deleted rather than shelved.** Both components and their tests are gone from the tree.
  They are in the history, at the commit before this one.

<a id="0035"></a>
## 0035. A check that runs long returns what it finished, and the guard that stops it is not the requirement's own number

**Evidence:** `docs/evidence/2026-09-17-live-timing.json` — twelve
submissions against the deployed service (commit `8cb5e70`);
`app/services/evaluator.py`; `docs/research/2026-09-15-rule-engine-architecture.md:772`.

**What was wrong.** `Evaluator._DEFAULT_SLA_SECONDS = 5.0` wrapped the whole evaluation in
`asyncio.wait_for` at exactly the five seconds R15/NFR-1 measures. When it fired, the caller got
HTTP 200, `needs_review`, **no fields**, and `total_duration_ms: 0` — and `asyncio.wait_for` cancels
the coroutine, so a read that had already finished was thrown away with it.

Measured live, the same label posted four times returned all seven fields once and none three times,
on a difference of about fifty milliseconds. On two of the blank runs `vision_duration_ms` read 4911
and 4900 while `total_duration_ms` read 0: the reader had finished and its work was discarded.
Eleven of the other twelve test submissions came back in 1.1 to 3.1 seconds, so this was one label
sitting on the line, not a slow service.

Nothing ever argued for the 5.0. `git log -L 33,33:app/services/evaluator.py` shows the line
arriving in the initial commit `5222337` with no reasoning, and there is no decision record for it.
The project's own design said the opposite: row 10 of the failure taxonomy in
`docs/research/2026-09-15-rule-engine-architecture.md` gives the whole-evaluation timeout as
"`needs_review` whole-evaluation; **partial results returned**", carrying "partial results, last
completed rule".

**Chosen.** Two changes.

A stopped evaluation returns what it had finished — the readings the reader produced and the rules
that completed — with `ENGINE.SLA.TIMEOUT` in the audit trail saying why the rest is missing, and
the time it actually spent instead of 0. The work is carried out of the cancelled frame in a
per-call holder (`_PartialEvaluation`) rather than on the Evaluator, because a batch reuses one
Evaluator across every item in it, and instance state there would let one item report another
label's readings.

The guard is now `Settings.evaluation_guard_seconds`, default 30 seconds, and it is a runaway guard
rather than a latency target. Thirty is six times the slowest whole check measured on the live
service (5.04 s), so no legitimate check can reach it, and far short of Cloud Run's 900-second
request timeout, which is the outer bound but is far too long for a page a person is waiting at.
`tests/test_deploy_healthz.py` had independently picked the same 30 seconds as the point past which
a check has not finished at all.

**Because** a cutoff that discards a valid result is a defect, not a trade-off — and this one could
not help the requirement it appeared to serve. NFR-1 asks that checks "show their results within 5
seconds". A cut-off check shows none, so it fails NFR-1 on the requirement's own words while also
failing FR-1 ("reports a result for each check that applies") and FR-8 ("For every check, the
product shows the value it read from the label beside the application value"). It converted a
latency miss into a correctness failure and bought nothing. A check that runs 5.2 seconds and
answers completely is strictly better than one truncated at 5.0, and both miss R15 equally.

**What this costs.**

- **A slow check now holds a request open longer.** Up to 30 seconds in the worst case, where before
  it returned a blank at 5. The measured worst case is 5.04 s, so nothing real approaches it, and a
  reviewer waiting is better served by an answer than by an empty page.
- **A partial result can be mistaken for a whole one.** It has field cards on it, and a rule that
  never ran reports nothing — which is not the same as finding nothing wrong. Both surfaces say so
  above the cards: `frontend/src/components/IncompleteCheckCard.tsx`, used by the single-label page
  and the batch panel so neither can describe one envelope differently.
- **R15's share has to be measured again.** Every figure published for it was taken while a marginal
  check failed as a blank rather than as a slow pass, so the share measured something other than
  what R15 asks about. The figure is owed after the next deploy.

<a id="0036"></a>
## 0036. The sideways re-read is screened by reading the strips, not by their shape alone

**Evidence:** `docs/evidence/2026-09-17-screen-corpus.json` — all 62
corpus images, measured on the development box under the six-thread OCR budget,
recording for each image what a recognition-only strip screen decides against what the full
two-angle re-read finds; `app/vision/local.py`.

**What was wrong.** `_has_sideways_text` (decision behind commit `7a9acab`) decides from box shapes
whether to read a label again at 90° and 270°. Shapes say that a label carries sideways text; they
cannot say what it says. Measured over all 62 corpus images, the re-read ran on four of them and
recovered a government warning from one — ttb-26212001000085, whose warning is printed up the edge
of its brand label. The other three paid two full detector passes to find nothing: a barcode
(ttb-26232001000404), a net-contents line (ttb-26236001000210) and an Italian brand line
(ttb-26239001000132's back). ttb-26232001000404 is the label that took 5.04 seconds on the deployed
service and was cut off.

Two things about the cost were not known before this work, and both are measured above. A detector
pass divides roughly in half between detection and recognising every box it found — 225 ms and
200 ms on a 1029×1300 label, on the development box. And a pass costs nearly the same whatever the
image's size: cropping the label to the strip that fired the gate cut a pass from 393 ms to 321 ms,
and lost the heading entirely, so the first option the plan listed — crop rather than re-read whole
— is rejected on measurement, not on judgement.

**Chosen.** Before the two rotated passes, the strips the upright pass already found are read where
they lie: each tall box is cropped, turned upright and passed to recognition alone, with detection
switched off. That costs about 10 ms a strip against about 440 ms for one rotated pass, because
nothing is detected a second time. The re-read runs only where a strip carries one of the §16.21
warning's own content words.

The screen answers yes wherever it cannot answer no — a label with no strips to read, or a strip
that came back empty, re-reads as before. A wrong yes costs what this code cost every time until
now; a wrong no is a government warning nobody checked, so the two are not weighed evenly.

Only 90° is tried for a strip, not both ways: rapidocr runs a 0/180 orientation classifier over each
crop before recognising it, so a strip printed the other way up comes back the right way round from
the same call. Measured on ttb-26212001000085, the strips read the same words at 90° and at 270°.

Alongside it, every call into the engine now names all three stages. `RapidOCR.__call__` begins with
`update_params` and what it sets stays set, so one recognition-only call would otherwise leave the
shared reader — one per process, serving every request — detecting nothing on the next label, and
failing silently by returning an output object of a different shape rather than raising.
`tests/test_vision_engine_stage_flags.py` holds both call sites to it.

**What it buys, on the development box** (six threads, the deployed service is several times slower,
and nothing here is measured on it yet):

| image | read before | read after |
|---|---|---|
| ttb-26232001000404 front — the live outlier | 1345 ms | 463 ms |
| ttb-26236001000210 front | 1406 ms | 610 ms |
| ttb-26239001000132 back | 447 ms | 194 ms |
| ttb-26212001000085 front — the warning the re-read recovers | 810 ms | 741 ms |

**Because** the re-read is the most expensive thing a read does, it exists for one field, and three
of the four labels paying for it had nothing for it to find. Reading the strips is the cheapest
question that separates them, and it asks about the words on the label rather than about the shape
of a box.

**What this costs.**

- **Every label that reaches the gate pays the screen.** 9 to 53 ms across the four images, against
  the 875 ms two rotated passes cost. The label that does re-read pays both.
- **A warning whose strips recognise as nothing recognisable is now the escape's problem.** If a
  strip returns text that carries none of the warning's words, the screen stops there. On
  ttb-26212001000085 the strips read "THE SURGEON" and "DRIVE ACAR OROPERATEMACHINERY,ANDM" — clipped
  by the box the upright detector drew, which is why the screen asks for the warning's words rather
  than for its heading. One corpus example is not proof that every sideways warning reads that
  legibly, and the corpus holds exactly one.
- **The screen's vocabulary is a second copy of the statutory wording.** It is held to
  `assets/warnings/govt_warning_16_21.txt` by `tests/test_vision_warning_screen.py` rather than by a
  comment promising they match. The reader still decides only where to look; a word that drifted
  could cost a re-read and cannot change a verdict.

<a id="0037"></a>
## 0037. A measured heading boldness may send a label to a reviewer and may never reject it

**Evidence:** `eval/heading_bold_ratios.py` and the run it produced over
all 38 labels in `tests/fixtures/labels/manifest.json`, measured on the development box
under the six-thread OCR budget; `app/vision/heading_measure.py`;
`app/rules/_validators/heading_style_check.py`; `rules/common/health_warning.yaml`.

**What was wrong.** `common.warning.heading_caps_bold` is a `severity: reject` rule, and until now a
stroke-width measurement that came back below `WIDTH_HEIGHT_RATIO_BOLD_MIN` rejected the label
outright. The threshold had never been measured against real labels — its own comment said so, and
said the re-tune "is still to come". That re-tune has now been run, and it does not produce a better
threshold. It shows the measurement cannot support a rejection at any threshold.

**What was measured.** The warning-carrying face of each of the 38 corpus labels, through the
reader's own `look()` so the crop is the frame production measures. Every label carries
`registry.status: APPROVED`, and §16.22(a)(2) requires the heading in bold, so the whole population
should sit above the cut.

- Of the 30 real labels, 28 measured confidently. Their ratios ran **0.111 to 0.508**, median
  0.1995 — a 4.6x spread across a population that is uniformly bold, where the difference between
  bold and regular type is nearer 1.5x.
- **At 0.25, 18 of those 28 came out below the cut** and would have been rejected.
- No cut fixes it. 0.10 calls all 28 bold and therefore calls everything bold; 0.15 calls 17 bold;
  0.30 calls 6. The distribution is continuous, with no gap to put a threshold in.

**The measurement tracks the photograph, not the typeface**, and the corpus shows this without
anyone having to take TTB's approvals on trust. `ttb-26232001000404` measures **0.111**. `var-blur`
is that same image Gaussian-blurred at 2.5 px — the same printing, the same type — and measures
**0.261**, 2.3x higher and on the other side of the cut. `var-glare` measures 0.555, the highest
ratio in the corpus, on a label with a white hotspot over its warning. Blur and glare thicken
strokes against a background that Otsu then thresholds differently; the ratio follows.

**What was decided.** A weight the reader *measured* may never reject a label. Where it does not
satisfy the rule — the measurement failed, was never taken, or came back low — the validator returns
insufficient evidence at warn severity under `unmeasured_weight_reason_code`, and the label goes to
a reviewer on that point alone. The words and the capitals are unaffected: both are read from the
heading's own characters, and both still reject at the rule's own severity.

A weight a payload *states* rather than measures still rejects. The legacy `heading_styles`
sub-object used by hand-built fixtures asserts a weight as a fact about the label, not as a reading
taken off a photograph, and a fixture saying its heading is regular is describing a non-compliant
label. That is the line: a measurement may not reject, an assertion may.

**What was rejected.**

- **Lowering the threshold below the corpus minimum** (0.10 or under). It removes the false
  rejections, but it makes the check vacuous — every heading passes, including one that is genuinely
  not bold — while still reading as a working check to anyone looking at the rule pack. A check that
  cannot fail is worse than a disclosed gap, because nothing tells the reader it stopped working.
- **Normalising the ratio against resolution and print scale** so it means something. This is the
  fix that would let the measurement decide again, and it is a genuine piece of work: it needs a
  scale reference the product does not have, which is the same thing decision 0006 puts the type-size
  rules out of scope for. Not started.
- **Switching the boldness check off entirely**, as decision 0013 does for the typography rules it
  cannot measure. Rejected because the measurement is not worthless — it is not good enough to
  reject on, but it is a real signal a reviewer can use, and routing it to a reviewer keeps it
  without letting it decide.

**What this costs.** A large share of compliant labels now raise a review item on boldness — on this
corpus, 18 of 28. That is the honest reading of a measurement this noisy, and it is the direction
that fails safe: the product asks a person rather than rejecting a label TTB approved.
`WIDTH_HEIGHT_RATIO_BOLD_MIN` is kept at 0.25 rather than lowered for the same reason. Now that it
chooses only between passing a label and reviewing one, a low cut buys a quieter queue by passing
headings nobody checked.

<a id="0038"></a>
## 0038. The cognac's class and type is the line the label sets largest, not its appellation line

**Evidence:** commit `8ca3ecc` and the reading it changed, replayed on the
frozen recording `tests/recordings/reader/26212001000085/front.json` at that commit and at its
parent; `app/vision/local.py` (`_warning_block`, `_largest_matching`);
`tests/fixtures/labels/manifest.json`, the `ttb-26212001000085` entry;
`tests/test_vision_replay.py::test_the_cognac_label_now_reads_its_own_designation`.

**Why there is an entry at all.** `tests/test_vision_replay.py` says what a lost reading costs:
*"It was correct when this suite was written. Either the change that did this is wrong, or this is a
trade a decision record has to argue for."* Commit `8ca3ecc` — the warning block confined to its own
column — changed one reading in the whole corpus for the worse. This is that argument.

**What changed.** `ttb-26212001000085` is an imported cognac whose front prints its designation
three times: a stylised `Cognac XO` set larger than anything else on the label, an appellation line,
and a stylised pair the engine runs together as `Cognae PefiteChampagne`. Replayed on the frozen
recording, the class-and-type payload is:

| | class and type read | confidence |
|---|---|---|
| before, at `8ca3ecc^` | `APPELLAT'ON COGNAC PETITE CHAMPAGNE CONTRÓLÉE` | 0.841 |
| after, at `8ca3ecc` | `Cognac XO` | 0.784 |

Nobody chose this directly. The old warning block took a horizontal band across the label, and the
band swallowed `Cognac XO`, so `_largest_matching` never saw the largest candidate and the
appellation line won by being the only one left. Confining the block to the warning's own column
returns `Cognac XO` to the body, and the largest line wins as the code has always said it should.

**What was decided.** Take the new reading. `_largest_matching` expresses a rule about labels — the
label says which words matter most by how large it sets them — and the old result was that rule
being denied by a bug elsewhere, not a better answer. Both strings are correct against the corpus
answer key, whose `label_observed.class_type` for this label is `Cognac XO / Cognac Petite
Champagne`. On the real route the label's class-and-type field raises nothing before or after: it
passes `spirits.class_type.matches_application` and `spirits.class_type.matches_soi` in both sweeps.
The label's overall verdict is unchanged, and it fails for other reasons. Since decision [0039](#0039) this
field goes to a reviewer, for a reading of the back face, not the front.

**What was rejected.**

- **Keeping the band so the appellation line keeps winning.** The band is the fault that failed 24
  of 37 corpus labels on `common.warning.verbatim` by reading a neighbouring column into the
  government warning. Preserving one label's richer designation is not worth reinstating it.
- **Preferring the longer candidate over the largest.** It would produce the appellation line here
  and the garbled `Cognae PefiteChampagne` elsewhere, and it replaces a rule about how labels are
  printed with a rule about string length.
- **Recording it as a known miss.** `KNOWN_MISSES` states that the reader gets something wrong. The
  reader does not get this wrong, so the line would be a false statement about the reader — which is
  what `test_the_known_misses_table_names_only_real_pairs` exists to stop.

**What this costs.**

- **The appellation is no longer reported.** A reviewer reading the result sees `Cognac XO` and not
  `Cognac Petite Champagne`; the appellation is on the photograph and nowhere in the fields. This
  product checks the designation against the application, which says `COGNAC (BRANDY) FB`, so
  nothing in scope turns on it — but a reviewer who wanted the appellation has lost it.
- **The replay suite protects this label by one assertion fewer.** The deleted assertion was
  `assert "CHAMPAGNE" in read`. What remains is that the reading contains `COGNAC` and is not the
  garbled pair.
- **Reading confidence fell from 0.841 to 0.784.** The stylised line scores lower than the
  appellation line, on a label where the fuller string was partly garbled anyway
  (`APPELLAT'ON`, `CONTRÓLÉE`).

<a id="0039"></a>
## 0039. The reader turns a line upside down only when it is all but certain, and the warning comparison removes spacing

**Evidence:** `docs/evidence/2026-09-17-line-flip.json`, which holds every
reading below; `app/vision/local.py` (`LINE_FLIP_CONFIDENCE`);
`app/rules/_validators/verbatim_hash.py`; `rules/common/health_warning.yaml`;
`tests/test_reader_line_flip.py`; `tests/rules/_validators/test_verbatim_hash.py`.

**What was wrong.** After the warning block was confined to its own column (`8ca3ecc`), 18 of the 38
corpus labels were still rejected under `common.warning.verbatim`, and the corpus answer key
records only four of them as printing a statement that differs from §16.21. Reading each rejected warning against the §16.21 text showed two
causes that were not the label's fault.

- **The reader turned upright lines upside down.** rapidocr runs a 0/180 orientation classifier over
  every line it detects, and flips a line when the classifier's confidence clears `Cls.cls_thresh`,
  0.9 by default. On this corpus that default flips upright lines of the warning, and a flipped line
  reads as noise: `ttb-26218001000369` came back 131 characters away from the §16.21 text.
- **The comparison collapsed spacing but did not remove it.** Decision 0013 says spacing is not
  compared. Collapsing turns a run of spaces into one, but it cannot restore a space the reader lost,
  so `IMPAIRSYOUR` for `IMPAIRS YOUR` on `ttb-26239001000217` rejected an approved label for
  spacing.

**What was measured.** All on the development box, under the six-thread OCR budget, against the code
at `29f7841` unless it says otherwise.

The classifier threshold, on the nine faces whose readings moved when the classifier was switched off
(distance is characters away from the §16.21 text; 0 is an exact read):

| face | 0.9 (default) | 0.95 | 0.99 | 0.999 | off |
|---|---|---|---|---|---|
| `ttb-26218001000369` back | 131 | 57 | 0 | 0 | 0 |
| `var-skew` back | 131 | 57 | 0 | 0 | 0 |
| `ttb-26239001000079` back | 53 | 53 | 2 | 2 | 2 |
| `ttb-26239001000081` back | 57 | 57 | 57 | 3 | 3 |
| `ttb-26212001000085` front (the sideways cognac)¹ | 227 | 1 | 1 | 1 | 1 |
| `ttb-26240001000573` front | 119 | 119 | 109 | 109 | 109 |
| `…132` front, `…662` back, `…716` back | 0 | 0 | 0 | 0 | 0 |

¹ The one character left on the cognac is the label's, not the reader's: it prints `ALCOHOLIC
BEVERAGE IMPAIRS`, singular, and the reader now returns exactly that.

Every label through the real route, both faces sent, before and after the change:

| | before (`29f7841`) | threshold 0.999 alone | classifier off | after (`2ac3af5`) |
|---|---|---|---|---|
| rejected on `common.warning.verbatim` | 18 | 16 | 16 | **15** |
| rule failures across the corpus | 32 | 30 | 33 | **29** |
| labels newly rejected on any rule | — | 0 | 3 | **0** |

The four labels whose printed warning really differs from §16.21 are rejected on the warning in
every one of the four sweeps: `ttb-26229001000034` (*"the RISKS of birth defects"*),
`ttb-26212001000085` (*"ALCOHOLIC BEVERAGE IMPAIRS"*), `ttb-26240001000454` (a closing quotation
mark where the full stop belongs) and `var-warning-wording` (*"MAY IMPAIR"*).

**What was decided.**

1. **The classifier stays on and flips a line only at a confidence of 0.999**
   (`LINE_FLIP_CONFIDENCE`). 0.999 is the lowest threshold measured that reads every warning above as
   well as switching the classifier off does, and it keeps the classifier for the labels that need it.
2. **The warning comparison removes every space rather than collapsing runs of them.** The canonical
   form is now `nfkc → ascii_quotes → join_line_break_hyphens → drop_whitespace → casefold`, and the
   asset hash is re-pinned to it. Removing spaces cannot make a different statement equal the
   mandated one: the letters, digits and punctuation still have to match in order, and all four
   corpus labels that print a different statement are still rejected. `eval/read_accuracy.py` already scored the warning this
   way, so the score and the rule now agree.

**What was rejected.**

- **Switching the classifier off.** It clears the same warnings, and it newly rejects the brand on
  three labels: `ttb-26239001000132`, a sample offered on the landing page, `var-heading-title-case`
  and `var-warning-wording`. A change that rejects a label on a field it used to read correctly
  costs more than it buys. 0.999 shows no such break.
- **A lower threshold.** 0.95 leaves `ttb-26218001000369` and `var-skew` 57 characters wrong, and 0.99
  leaves `ttb-26239001000081` 57 wrong.
- **Cutting the warning out and reading it enlarged.** At 2x, 15 of the 38 warnings match against 19
  read the ordinary way, and six that matched stop matching; at 3x, 12 match and eight stop.
- **Re-reading each warning line on its own.** With the recognition model in use, 24 match, the most
  of any option, but two warnings that match today stop matching (`ttb-26231001000333`,
  `ttb-26238001000795`), and a rotated label reads nothing. With the English-only PP-OCRv5 model, 16
  match and six stop; with the larger PP-OCRv6 medium model, 21 match and three stop. An option that
  rejects approved labels the reader handles correctly today is not taken, whatever it clears
  elsewhere. Combining a per-line re-read with the 0.999 threshold was not measured.

**What this costs.**

- **Three labels gain a review item.** The reader now reads lines it used to garble, and a field
  picker sometimes chooses a wrong one of them.
  - `ttb-26212001000085`, the cognac: its class and type goes to a reviewer on both
    `spirits.class_type.matches_application` and `spirits.class_type.matches_soi`. The merged reading
    takes each field from the face that read it most confidently, and for this label that is the back
    both before and after. Before, the back read `COGNAC dePradière 16120 BIR4C` (0.840), a
    misassembled line that happened to spell `COGNAC` correctly; now it reads `Cognae Petite
    Champagne` (0.804). The front still reads `Cognac XO` (0.784), as decision 0038 intended, and
    loses to the back in both cases. So the last paragraph of 0038, that this field raises nothing on
    the real route, no longer holds.
  - `ttb-26218001000369` and `var-skew`, the same bottle: name and address goes to a reviewer. The
    back face used to yield the US importer, `EASTERN LIQUORS USA. INC`; it now yields the
    producer, `ALLIED BLENDERS AND DISTILLERS LIMITED`.
- **Three labels lose a review item.** `ttb-26231001000662`, `ttb-26236001000716` and
  `var-brand-case-punctuation` now read their name and address where they did not.
- **No reading time, measured on the development box.** Timed alternately in one process over 32
  faces, so machine load falls on both arms alike, the reader took a median 447 ms per face at 0.999
  and 478 ms at 0.9, and the paired difference has a median of −10 ms. The route sweeps disagree with
  each other — 0.97 s median with the threshold alone, 1.46 s at the change, with identical reader
  code — because they ran minutes apart on a shared machine. The deployed service has not been
  re-measured.
- **Fifteen labels are still rejected on the warning, and 11 of them print the mandated words.**
  On four the reader invented an accented letter; on six it got one to three characters or
  punctuation marks wrong, which no reader option above fixed; and on `ttb-26240001000573` the
  warning block still takes in an importer's address. §16.21 fixes the punctuation, so none of these
  can be absorbed by loosening the comparison, and this decision does not try. [0040](#0040)
  sends the misread ones to a reviewer.

**Amended — the canonical form drops `ascii_quotes`.**

The form is now `nfkc → join_line_break_hyphens → drop_whitespace → casefold`. `ascii_quotes` turned
curly quotation marks straight, and §16.21's text contains no quotation mark of either kind, so a
label that prints one differs from the mandated text with or without the op. Removing it changes no
comparison and leaves the asset pin as it was. Mutation testing found it: no test could tell the op
from its absence. `collapse_whitespace`, `tighten_punctuation_spacing` and `strip_outer_ws`, which no
rule named once `drop_whitespace` replaced them, are removed with it, and a rule that names an op
that does not exist is refused at load, naming the rule and the op.

<a id="0040"></a>
## 0040. A warning that differs only where the reader misreads is reported as needs review, and a lower-case Surgeon General is never a match

**Evidence:** `app/rules/_validators/verbatim_hash.py`; `tests/rules/_validators/test_verbatim_hash.py`;
the TTB distilled spirits, wine and malt beverage labeling checklists.

**What was wrong.** `common.warning.verbatim` was wrong in both directions. Of the 15 corpus labels it
called mismatched, 11 print the mandated words and the reader misread them ([0039](#0039)): an
accent added to a letter (`BEVERÁGES`, `ÍMPAIRS`, `WOMÈN`, `DRIVÉ`), `(I)` for `(1)`, `ORINK` for
`DRINK`, or one punctuation mark added, dropped or swapped. And because the comparison folds the
case of the whole body, a label printing "surgeon general" in lower case matched. All three TTB
checklists ask *"Are the "S" in Surgeon and "G" in General capitalized?"*

**Chosen.** Where no hash matches, the check lines the reading up against the statement and sorts each
difference. An accent on a letter the statement prints plain, a swap inside `1 I l |` or `0 O D`,
and one punctuation mark added, dropped or swapped are kinds the reader is measured to invent. If
every difference is one of those, the check reports needs review under
`WARNING.VERBATIM.NOT_CONFIRMED` and names each difference, so the reviewer checks those spots on the
label. Any other difference — a letter or a word added, dropped or changed — stays a mismatch. A
reading that matches but shows the S or G of Surgeon General in lower case reports needs review.

On the corpus readings this turns 10 of the 11 false mismatches into needs review. The three labels
that print different words (`RISKS`, `BEVERAGE`, `MAY IMPAIR`) stay mismatches. `ttb-26240001000454`,
which ends `PROBLEMS"`, goes to needs review, which its answer key accepts. `ttb-26240001000573` stays
a mismatch, because its reading takes in an importer's address; that is a reader defect, not this
check's.

**Rejected.** *A confidence threshold* — measured, the reader's confidence does not separate its
misreads from true differences at any granularity: at the best per-character threshold, 3 of the 11
misreads still sit above it, and the per-warning confidence the rule's `confidence_floor` reads
separates none. *Folding accents and punctuation out of the comparison* — 27 U.S.C. 215(a) prescribes
the statement word for word, and the checklists ask *"Does it match the exact wording and
punctuation?"* A label that really prints an accent or a changed mark is not compliant, so it must
never match; needs review is the most this check can say without knowing which is at fault.
*Report a lower-case S or G as a mismatch* — the reader can read a capital as lower case, and FR-9
sends a reading the product cannot trust to a reviewer. No reading in the corpus shows either letter
in lower case, so no corpus result changes. *Report the misreads as mismatches and leave the reviewer
to sort them out* — a mismatch the product cannot stand behind teaches the agent to discount every
mismatch it reports.

**Because** the product reports what it can stand behind. A difference it cannot tell apart from its
own misreading is a question for the reviewer, not a finding against the label, and a statement TTB
would return for its capitals must never be reported as a match.

<a id="0041"></a>
## 0041. The service checks one batch at a time, and keeps a finished batch only until the next one starts

**Evidence:** `app/batch/admission.py`; `app/batch/worker.py`; `app/api/body_limit.py`;
`tests/test_one_batch_at_a_time.py`; `tests/test_body_limit_replay.py`.

**What was wrong.** Memory had no bound. Every batch stayed in memory, finished or not, until the
service restarted, and nothing stopped a second batch from starting while the first was still being
checked: the upload page is one click away on every page, including the page showing the running
batch's results, and `POST /batches` took any number. Each batch also held every uploaded image
until its last label was done, and the request-size guard held a second copy of every upload while
the application read it.

**Chosen.** One batch at a time. While a batch is being checked, a second one is refused from either
route with a 409 that says how far the running batch has got. Starting a batch drops the one before
it, so a finished batch's results stay readable until the next upload and no longer. The worker lets
go of each label's image as soon as that label is checked, and the request-size guard hands the body
on in the pieces it arrived in instead of joining them into a copy. What the service holds at once
is now one upload, shrinking as it is checked.

There is no login, so the service cannot tell the reviewer who started a batch from anyone else.
The limit is one batch per running copy of the service, and whoever uploads while a batch runs is
told to wait. "Running" is read off the worker task, not off the results, so a worker that stopped
on an error does not hold the service shut.

**Rejected.** *One batch per person* — with no login there is no person to count against. *The new
upload cancels the running batch* — with no login, a second visitor would end the first reviewer's
batch halfway through. *Stream the upload instead of reading it whole* — it lowers what one request
holds, but not how many batches pile up, which is what made memory unbounded; with one batch at a
time, one request is the whole of it. *Paginate the results table* — a batch is at most 100 labels.

**Because** a batch is a demonstration a reviewer watches from start to finish: the upload takes them
straight to its results and the first result arrives almost at once. A second batch run beside it
would compete for the same reader, and a batch nobody will open again is memory the service has no
reason to hold.

<a id="0042"></a>
## 0042. A scheduled ping holds an instance warm, because the first thing a visitor met was a 36-second wait

**Evidence:** `edge/src/index.js` (`scheduled`); `edge/wrangler.jsonc` (`triggers.crons`);
`scripts/deploy.sh:315`; [0025](#0025).

**What was wrong.** The service runs with `--min-instances 0`, and the startup probe holds traffic
off a new instance until the OCR models are loaded. So a visitor arriving at a quiet service waited
for a container start and a model load before seeing a page. Measured on the deployed service on
2026-09-19, against `https://ttb.aaroncarney.me/`:

```
cold: ttfb=36.48s  code=200
warm: ttfb=0.14s   code=200
```

Nothing about the application is slow. The warm path is 140 milliseconds. The 36 seconds is the
price of having scaled to zero, and it was being paid by whoever arrived first — which, for a
prototype whose whole purpose is to be opened by someone who has never seen it, is everyone who
matters.

[0025](#0025) already argued this and named the fix: "a scheduled request every ten minutes holds an
instance warm for a few hundred vCPU-seconds a month." It was never built. That record also said the
deployed cold start was unknown until timed on the service. It has now been timed.

**Chosen.** A cron trigger on the edge Worker, every five minutes, calling
`${ORIGIN}/api/health` with the same invoker token the Worker mints for a forwarded request. Any
request resets the instance's idle clock, so the ping sends the cheapest one the service has. The
models are loaded by the startup probe before Cloud Run routes anything to an instance, so the ping
never reloads them; it only keeps the instance that already holds them from being reclaimed.

Five minutes, not the ten 0025 costed. Google documents no idle-retention window for a Cloud Run
instance, so ten minutes was a guess at an undocumented number. Five sits below the fifteen minutes
commonly observed with margin to spare, and the extra cost is nil: 8,640 pings a month, each a few
milliseconds of CPU, against a free allowance measured in millions of requests.

The ping does not call the rate limit. That binding exists to bound a flood arriving from outside,
and this request is the Worker's own; counting it against the same key would spend a reviewer's
budget on housekeeping. A failed ping is logged and swallowed, because the next one is five minutes
away and a throw reaches nobody.

**Accepted cost.** `--concurrency 1` means a ping that arrives while a reviewer's check is running
starts a second instance, which cold-starts. It is a few seconds of an instance nobody is waiting
on, and `--max-instances 2` caps how far it can go.

**Rejected.** *`--min-instances 1`* — it is the direct fix and it bills a 4-vCPU, 4 GiB instance
around the clock whether or not anyone visits, which is the one thing [0025](#0025) chose this host
to avoid. *Pinging `/healthz`* — it rebuilds the evaluator, so it does more work than keeping an
instance alive requires. *A ping from outside the Worker* — the invoker check ([0028](#0028)) means
an unsigned request is refused with a 403 and never reaches the service, so a plain uptime pinger
would hold nothing warm; the Worker is the only thing already holding the key.

**Confirmed to hold, not merely to land.** Two signals were required and both are in. That the ping
*lands* was shown on 2026-09-19 from the container's own access lines. That it *holds* an instance
was left open, because a warm figure on its own proves nothing — Cloud Run may have kept the
instance for reasons of its own. Measured on 2026-09-20: `https://ttb.aaroncarney.me/` was left
alone for a full 25 minutes, from 00:23:18Z to 00:48:18Z, and the landing page then answered

```
after 25 minutes idle: ttfb=0.284s  code=200
```

against the 36.48s cold and 0.14s warm above. The figure is attributable because the log for the
same span carries the pings and nothing else: `/api/health` at 00:20:45Z, 00:25:41Z, 00:30:53Z,
00:35:41Z, 00:40:45Z and 00:45:48Z, six requests on the five-minute period spanning the whole
window, with **no container start and no shutdown line anywhere in it** — so one instance served
throughout and the request that produced the 0.284s figure appears in that same log at 00:48:19Z.
Read it back with

```
gcloud logging read 'resource.type="cloud_run_revision"' --project=ttb-label-check \
  --limit=60 --freshness=30m --format="value(timestamp,textPayload)"
```

and read the container's text payload rather than filtering on `httpRequest.requestUrl`: these
pings do not appear under `httpRequest` at all, so that filter returns nothing while the access
line is plainly there.

**Because** a prototype is judged by someone who opens it once. A 36-second blank page is the first
and possibly only thing that person learns about it, and it says nothing true about the product
behind it.

<a id="0043"></a>
## 0043. The batch carries the applications too, as one CSV, and the sample pack ships both halves

**Evidence:** `app/api/ui/_application_csv.py`; `app/api/ui/submit.py`, which took over the
upload route this entry describes as *app/api/ui/bulk_upload.py* ([0045](#0045));
`app/api/ui/samples.py` (`applications_csv_for`); `tests/test_batch_checks_against_applications.py`;
[0010](#0010), [0019](#0019), [0020](#0020).

**What was wrong.** The brief's central ask is a label checked against the application filed for it,
across batches of 200-300. The engine has always done it — `POST /batches` takes
`BatchItemRef{label_ref, application_ref}` — but the only path a reviewer could reach dropped the
application half. `app/api/ui/bulk_upload.py` said so in its own words: *"A bulk upload carries
images and no applications, so there is nothing to compare each label against."* Every comparison
rule in the pack then reported that it had nothing to compare, and the page showed a column of
**Not checked** beside **Expected (empty)**. A reviewer who downloaded the sample pack and uploaded
it watched the product decline to do the assignment.

**Chosen.** The applications travel as a **CSV**, one row per label: the image filename, then the
ten fields the single-label form posts. `/batches/sample.zip` ships that file, `applications.csv`,
beside the images, filled in from `tests/fixtures/labels/manifest.json` — the application really
filed for each label in the registry. The batch form takes it in a field of its own **or** among the
images, because a reviewer who unzips the pack and selects everything sends it through the image
picker, and refusing it there would name the one file carrying the applications as the one file that
was not read.

Rows join to labels on the filename stem — the same stem `app/api/ui/_faces.py` already reads to
decide that `lucy-front.jpg` and `lucy-back.jpg` are one label. A row may name either face or the
bare stem; all three reduce to one key.

A row's own `beverage_type` beats the form's select, because a pack of wines, beers and spirits is
one batch and a single select cannot be right for all three. A label the CSV has no row for is not
an error: it is read and checked for what every label must carry, and its reply says nothing was
compared ([0010](#0010)). That path existed before this entry and is unchanged.

**Two rows for one label is refused, not resolved.** Picking one of them silently compares a label
against an application that was never filed for it. At 300 labels the failure that matters is not
"no application" but "the wrong one", and it is the one failure a reviewer cannot see from the page.

**Rejected.** *The JSON envelope `POST /batches` already takes* — right for a machine and wrong for
a person, who has 300 filings in a spreadsheet and a spreadsheet writes CSV. *A sidecar file per
label* — it multiplies the file count against the 100-file cap the form already enforces, so a
300-label batch that fitted before would not. *Filenames carrying the application values* — ten
fields do not fit in a filename, and the brief bars integration with COLAs Online (C-1), so a file
the reviewer supplies is the honest stand-in for the feed a real deployment would read from the
system of record.

**The curated sample buttons are retired with it.** The landing page offered four labels as buttons,
each with a blurb describing what checking it would show. That is a tour of the product rather than
the product, and one blurb asserted an outcome the engine explicitly refuses to assert: it said of a
beer that *"Neither photograph of this beer shows a bottler's name and address, and the check says
so"*, where the check says *"The reader did not find a name and address on this label, so this check
was not made. That is not a finding that the label lacks it."* The demonstration is the pack now,
dropped into the same form a reviewer's own labels go through. What the blurbs explained is in
`README.md` and `docs/approach.md`, which the brief asks for by name. `POST /samples/{sample_id}`
stays: it is a real path to one shipped label against its filed application, and nothing about it
was a tour.

**An untouched file input still posts a part, and it shadowed the CSV.** Found by driving the form
in a browser rather than by posting to the route. A file input the reviewer never touches sends an
empty part with no filename; read as an applications file it took precedence over the real CSV in
the image picker, and every label in the batch came back with nothing compared. An HTTP client's own
multipart writer drops that part, so the in-process test passed while the page was broken — the same
lesson as the result card in [0020](#0020): a check that reads the envelope is not a check on what
the reviewer sees. `tests/test_batch_checks_against_applications.py` builds the browser's bytes by
hand.

**Because** the product is the comparison. A batch that reads labels and compares nothing is the
half of the job the brief is not about.

<a id="0044"></a>
## 0044. The page takes the back of the label, and the five-second share is published as what that costs

**Evidence:** `app/ui/templates/check.html` and `app/api/ui/submit.py` — the page and the route
this entry describes as *single.html* and *single_upload.py*, renamed and merged by
[0045](#0045); `tests/test_single_page_offers_the_back.py`; `tests/test_deploy_healthz.py`;
`docs/evidence/2026-09-20-five-second-both-faces-run1.json` and
`docs/evidence/2026-09-20-five-second-both-faces-run2.json` (the two runs, row by row);
[0005](#0005), [0035](#0035), [0036](#0036).

**What was wrong.** `POST /` had accepted a second face called `label_back` since the multi-face
work, and its docstring, its route and its tests were all written for two faces. The page offered
one file input. No reviewer using the product could send a back, and the government warning is
printed on the back of 20 of the 30 corpus labels: the one entry point a reviewer reaches answered
fast and wrongly, reporting a warning missing that the label carries. The plan's own gate had
ticked the item, because it tested the sample route, which cannot fail on the page's markup.

**Chosen.** The page asks for a front and an optional back, and the five-second measurement sends
what the page sends. The owner took the trade explicitly — add the input, re-measure on the deployed
service, and publish whatever number comes back including a miss.

**What it cost, measured 2026-09-20 on the deployed service.** 18 of 37 checks inside five seconds
in one run and 21 of 37 in a second run minutes later, against R15/NFR-1's 95 percent. Medians of
5.01 and 4.38 seconds, slowest 9.01. The 33 submissions carrying a back ran at medians of 5.55 and
4.95; the four with only a front ran 4 of 4 inside the budget at 2.39 and 2.74. The previous
deployed commit, which could only be sent fronts, measured 35 of 37 inside five seconds. Nothing
was stopped early and nothing came out of the cache in either run, so the harness is measuring slow
checks rather than blank ones ([0035](#0035)).

**Not chosen, and not yet measured: reading the faces concurrently.** `app/vision/local.py` reads
`label.faces` one after another, and within a process it reads one image at a time: a single OCR
engine serves every request and a second read waits on the first. Reading two faces at once is
therefore not a matter of issuing both reads together — it means lifting that serialisation. Nobody
has measured what that does, either to the time a reviewer waits for one check or to the time each
label takes inside a batch, and both are the measurement to take.

**Because** a check that answers in three seconds about the wrong half of the label is not a faster
product, it is a wrong one. The requirement is missed and the number saying so is published beside
the requirement, rather than the number being kept by not sending the back.

<a id="0045"></a>
## 0045. One system: every check is a batch, including a batch of one

**Evidence:** `app/api/ui/submit.py`; `app/api/ui/shells.py`; `app/ui/templates/check.html`;
`app/ui/templates/results.html`; `frontend/src/app.tsx`;
`frontend/src/components/LabelResult.tsx`; `tests/test_ui_routes.py`;
`tests/test_one_batch_at_a_time.py`; `tests/test_single_page_offers_the_back.py`;
[0019](#0019), [0020](#0020), [0041](#0041), [0043](#0043), [0044](#0044).

**What was wrong.** There were two products in one repository. `GET /` took one label and answered
with a server-rendered result page; `GET /batches` took a folder and answered with a table a
reviewer clicked into. A reviewer had to decide which of two systems they were in before they had
checked anything, and the two answered differently about the same label: the single page rendered
its result into the HTML, the batch page streamed it into a React island, and every capability had
to be built twice or be missing from one of them. The multi-face work landed on the single page and
not the batch page ([0044](#0044)); the applications CSV landed on the batch page and not the single
page ([0043](#0043)). Each fix widened the gap it was fixing.

Nothing underneath was ever split. The engine has always been handed one `(application, label)`
pair at a time, and the batch worker has always broadcast each label's result the moment it landed
rather than holding the first one back. The split was in the interface alone.

**Chosen.** One form and one results page. `GET /` is the only way in, for one label or three
hundred. `POST /` always starts a batch — a batch of one is a batch — and always answers `303` to
`/batch/{batch_id}`. That page mounts the island, which subscribes to the result stream, **opens
the first result the moment it arrives**, and lists the rest only when there is a rest. So the
reviewer reads one graded label while the others are still being checked, which is what the owner
asked for: one graded item per moment, and the whole batch processed.

`POST /samples/{sample_id}` takes the same path — `launch_batch`, then the same redirect — so a
shipped sample and a reviewer's own upload cannot demonstrate different behaviour. `GET /batches`
is kept as a 308 redirect to `/`, because it is the URL the deployed service has been handing out
and a bookmark that 404s tells a reviewer the product is broken when what happened is that it got
simpler.

**What it costs, both accepted.**

*A single label can now be refused.* Admission allows one batch at a time ([0041](#0041)), and a
single-label check is a batch, so a reviewer submitting one label while a 300-label batch runs is
told to wait. Before this entry that reviewer was never refused — the single path ran outside
admission entirely, which is to say it ran outside the one-batch-at-a-time guarantee and could put a
second OCR load on a machine already committed to one. The refusal is the honest form of a limit
that was always there; hiding it on one of two paths was the defect.
`tests/test_one_batch_at_a_time.py::test_one_label_waits_for_a_running_batch_too` pins it.

*Two photographs of one label need a tick.* Files pair into faces by name — `<stem>-front` and
`<stem>-back` (`app/api/ui/_faces.py`) — and a reviewer who photographed both faces on a phone has
`IMG_4417.jpg` and `IMG_4418.jpg`, which nothing can pair. So the form offers *These images are all
faces of one label*, the `one_label` field, and `app/api/ui/submit.py::_as_one_label` places every
uploaded image on one label in the order it was picked. Renaming files is not a thing to ask of
someone checking one label.

**Rejected.** *Keep both pages and share components between them* — that is what was already being
attempted, and it is what produced a multi-face single page and a multi-face-blind batch page. Two
surfaces drift whatever they share, because each fix is applied where it was noticed. *Make the
batch page a list and keep the single page for one label* — a reviewer with one label and a reviewer
with three hundred want the same thing first, which is the first graded label; a list is a worse
answer to both. *Render the one-label result server-side and stream only batches* — one result, two
renderers, and the server-rendered one cannot show a result that is still arriving.

**The results island keeps the batch table for when there is a batch.** A submission of one renders
no table at all — there is nothing to list — which is why `tests/test_a11y_axe.py` no longer carries
the empty-table case it used to.

**Because** a reviewer should not have to know which of a product's two halves they are in. There is
one system, it presents one graded item per moment, and the whole batch is processed.

<a id="0046"></a>
## 0046. The regulation is in the product, because the eCFR will hand it over and a test can check it

**Evidence:** `app/cfr/citations.py`; `app/cfr/corpus.py`; `app/api/cfr.py`; `tools/fetch_cfr.py`;
`assets/cfr/manifest.json`; `frontend/src/components/CitationPanel.tsx`;
`frontend/src/components/CitationChip.tsx`; `frontend/src/app.tsx`;
`tests/test_cfr_citations.py`; `tests/test_cfr_corpus.py`;
`tests/test_cfr_corpus_matches_ecfr.py`; `tests/test_cfr_route.py`;
`assets/warnings/govt_warning_16_21.txt`; [0034](#0034), [0018](#0018).

**What changed since 0034.** [0034](#0034) deleted the citation panel and made the citation chip a
span. Its reason was not that a panel is the wrong shape — it was that nothing could fill one
honestly: "Filling the other 42 means writing regulation text by hand into a compliance tool with no
test that can check it against the regulation — the kind of claim this build refuses everywhere
else."

The eCFR publishes an API, and this machine can reach it. Probed 2026-09-20:
`GET https://www.ecfr.gov/api/versioner/v1/full/{date}/title-27.xml?part=4&section=4.33` answers 200
with the section as structured XML — heading, paragraphs, amendment note. So the wording can be
fetched rather than typed, and a test can re-fetch it and compare. 0034's reason is spent, and this
entry is argued on its own rather than against 0034's conclusion.

**0034's second objection is not spent, and it is what shaped this.** 0034 also rejected linking
each chip to the eCFR, because "the citation strings are heterogeneous enough that parsing them into
section URLs would mislink some, and a compliance tool showing the wrong regulation is worse than
one showing none." An API does not answer that: it serves a section to a caller who already knows
how to name one, and the rule pack names its sections in prose — `27 CFR §4.32(a)(1), §4.33`,
`27 CFR §5 Subpart I`, `27 CFR §4.35(e), 19 CFR §134.45`.

So the parse is the load-bearing part, and it refuses rather than guesses. `parse_citation` reads a
citation whole or yields nothing: a reference it cannot cover fails the whole string, not just its
own part, because showing a reviewer the one reference of three that parsed tells them the rule
rests on that reference alone. `tests/test_cfr_citations.py` asserts every shape the pack uses
against the sections a reader of that string would turn to, written out rather than computed, and
asserts that ten strings which invite a guess — a title with no section, a subpart with no part,
trailing prose — yield nothing. It also reads the pack itself and fails if any citation in it does
not parse, so a citation added tomorrow is covered on the day it is added.

**Chosen.** `tools/fetch_cfr.py` reads every citation in `rules/`, parses it, and fetches the
sections it names from the eCFR, writing each into `assets/cfr/` with a manifest recording the
source URL, the issue date, the retrieval date and a SHA-256. Twenty-four sections across two
titles cover all 43 citations, in 164 KB. `GET /cfr?citation=…` serves them. The results page
reserves a column for `CitationPanel`, which fills in place; `CitationChip` is a button again.

**Whole sections, not the cited paragraph.** A rule cites `§4.32(a)(1)`; the panel shows §4.32 and
says the finding rests on (a)(1). A reviewer deciding whether a label complies needs the clause in
its context, and a tool that quotes one clause of a section is making an editorial choice about the
regulation it has no standing to make.

**Fetched once and committed, not fetched per request.** The product makes no outbound network call
(`README.md`), and a compliance tool whose regulation text depends on a third party being up is
worse than one that ships the text. Committing it also means an amendment arrives as a diff somebody
reviews. This is the bargain `assets/warnings/govt_warning_16_21.txt` already makes for §16.21.

**Each title is pinned at its own issue date.** The titles do not move together: on the day this was
written the eCFR had title 27 issued 2026-09-16 and title 19 issued 2026-08-26, and a request naming
a date a title has no issue for is a 404. The fetcher asks the API which dates it has, and the
manifest records what was actually retrieved rather than what somebody typed.

**The test 0034 asked for exists and passes.** `tests/test_cfr_corpus_matches_ecfr.py` re-fetches
every section and compares it character for character with the committed file. It reaches the
network, so it runs on `TTB_CHECK_ECFR=1` rather than by default — the bargain
`tests/test_deploy_healthz.py` already makes. Run 2026-09-20: 24 passed. There is also one check
that needs no network at all: this repository pinned §16.21 independently, for the verbatim
validator, and `tests/test_cfr_corpus.py` asserts the fetched §16.21 carries the same sentences. If
the fetch or its XML extraction were mangling the regulation, that is where it would show.

**A chip is a control only where something opens.** 0034's finding was that the chip "rendered as a
button whose `onOpen` neither call site supplied, so on both the single-label page and a batch's
detail panel a reviewer could press it and nothing happened" — offering a reviewer a control that
does nothing is "the one thing a reviewer cannot check for themselves". That rule is kept
literally rather than reversed: `CitationChip` takes `onOpen` as optional and renders a span
without it. The results page supplies one; anywhere that does not gets text.

**Rejected.** *Link the chip to ecfr.gov* — an outbound link takes the reviewer out of the product
mid-comparison, and it still needs the same parse to build a URL, so it carries 0034's mislinking
risk without the benefit. *A pop-up or an overlay* — the reviewer's task is comparing the finding
with the regulation, and an overlay covers the thing being compared. *Fetch at runtime* — see above.
*Hold the paragraph only* — see above. *Parse in the island* — two grammars that agree until they do
not; the one that mislinks is the one nobody tested.

**Cost, stated.**

- **The corpus goes stale silently unless someone runs the check.** The committed text is the issue
  of the date in the manifest. `TTB_CHECK_ECFR=1` catches drift, and nothing runs it on a schedule.
  A deployment that mattered would run it in the pipeline.
- **164 KB of regulation text is now in the repository and in the image.**
- **The panel is only as good as the rule pack's citations.** It shows the section a rule names. A
  rule citing the wrong section gets a panel confidently showing the wrong regulation — the parse is
  tested, the citations in the pack are not.
- **A reviewer still cannot see where on the label a value was read from.** 0034's other cost stands
  untouched; the bbox is still in the reader's pixel space.

**Because** a reviewer deciding whether a label complies should be able to read the rule it is being
held to, in the place they are deciding, and this product can now show them that wording without
anybody having typed it.
