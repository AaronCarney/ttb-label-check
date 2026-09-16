<!-- updated: 2026-09-16 -->
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

Standard: `olorin/standards/workflow/decision-document.md`. Consolidated 2026-09-16 out of
sixteen separate files under `docs/decisions/`, which was a departure from the workspace's practice
of one decision document per project. The entry numbers are the numbers those files carried, so an
existing citation to `docs/decisions/0011` is entry 0011 here and links resolve as
`docs/decisions.md#0011`.

When a decision changes, add a dated entry below the original. Do not edit the original away; the
superseded reasoning is what makes the change legible later.

---

<a id="0001"></a>
## 0001. Semantic versioning

**Decided:** 2026-09-10.

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

**Decided:** 2026-09-15. **Evidence:** the brief, `specs/0001-label-verification/PRD.md`.

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

**Decided:** 2026-09-15.

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

**Decided:** 2026-09-15.

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
item; and the owner instructed on 2026-09-15 that this version runs locally with a cloud option if
time allows, and that "everything we include [is] contained within the app itself if possible to make
installing simple".

<a id="0005"></a>
## 0005. Two readers behind one interface, local by default

**Decided:** 2026-09-15. **Evidence:** `docs/research/2026-09-15-extraction.md`.

**Chosen.** Reading a label image into fields is one replaceable component behind one interface, with
two implementations:

- **A local CPU OCR engine, shipped in the app and used by default.** It needs no key and makes no
  outbound call, so a clone runs and checks labels out of the box, and the product works inside a
  network that blocks outbound traffic.
- **A hosted vision model, used when a key is present**, enabled by an environment variable. Where
  it is available it reads more accurately; where it is not, the product still works.

Neither reader decides anything. Rules decide; the reader reports what it saw with a confidence, and
the product says "needs review" where the reader is unsure.

**Open point.** Measured on 13 real labels on 2026-09-15, the hosted model returned the government
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

**Decided:** 2026-09-15. **Extended by** [0013](#0013), which settles what these rules answer instead.

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

**Decided:** 2026-09-15.

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

**Decided:** 2026-09-16.

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

**Decided:** 2026-09-16.

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

**Decided:** 2026-09-16.

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
beverages and every other rule lists exactly one — checked across all five rule files on 2026-09-16 —
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
thing a grader may submit; turning it away is a larger product change than the defect warrants and it
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
a grader drops in an image to see the app work, and it is the brief's most prominent single
requirement that is lost. It is recovered in full by giving the rule model a way to say "applies
whatever the beverage is", which is recorded for the consolidation pass with the five files it touches.

**One test states the behaviour this replaces** and now fails:
`tests/test_ui_end_to_end_comparison.py::test_without_an_application_nothing_is_compared_and_the_label_is_still_checked`
asserts that an image-only upload still runs the comparison rules and has them opt out. With no
beverage named, no comparison rule can be selected to opt out. The test is in another lane's files and
is handed to the consolidation pass with the replacement stated.

<a id="0011"></a>
## 0011. The alcohol-content format check is switched off until the reader returns the label's wording

**Decided:** 2026-09-16.

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

<a id="0012"></a>
## 0012. A class-and-type designation the app cannot place goes to a reviewer, not to a rejection

**Decided:** 2026-09-16.

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

**Decided:** 2026-09-16. **Extends** [0006](#0006), which put four of these checks out of scope. That
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

    nfkc → ascii_quotes → join_line_break_hyphens → collapse_whitespace →
    tighten_punctuation_spacing → casefold → strip_outer_ws

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
does not exist, each carrying a wrong verdict for whoever switches it on; `meta-plan-decisions/0009`
decided this shape directly, with the four rules staying and pointing at one shared `unmeasurable`
validator, the three implementation bodies going and the fifth rule going outright, because the rule
entry with its citation and its notes is the durable record and the body was not. *One shared "not measured"
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

**Decided:** 2026-09-16. **Evidence:** `docs/research/2026-09-15-ttb-regulatory-framework.md`.

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

**Decided:** 2026-09-16. **Evidence:** `docs/research/2026-09-15-matching-rules.md`.

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

**Decided:** 2026-09-16.

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

**Decided:** 2026-09-16. **Evidence:** Form TTB F 5100.31, allowable revisions item 3.b; measured against
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

Measured here on 2026-09-16 against `app/rules/brand_match.py` as shipped:

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

<a id="0018"></a>
## 0018. An uploaded label image is kept as a file, not in the process that received it

**Decided:** 2026-09-16.

**Chosen.** The image a grader uploads is written to a file — one per evaluation, named for the
evaluation id and suffixed with its media type — in a directory under the machine's temporary
directory, and `GET /labels/{evaluation_id}/image` reads it back from there. Three properties come
with it. An id that is not letters, digits, hyphen or underscore is refused, so nothing a caller puts
in the URL can name a file outside that directory. A write lands on a staging name and is then moved
onto its final name, so a process reading the directory never sees a half-written image. And an image
is dropped once it is seven days old, swept when the next one is written.

**Rejected.** *The 64-entry dictionary of raw bytes held in one process, which this replaces.* It
failed three ways a grader meets in normal use: the 65th upload evicted the first page's image, a
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

<a id="0019"></a>
## 0019. The browser-facing surface is one module per job, behind one router

**Decided:** 2026-09-16.

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
