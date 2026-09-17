# Approach, tools and assumptions

The full record behind the short version in [README.md](../README.md). Each entry is a fork where a
competent team could have gone the other way, the reason this one was taken, and what it cost.
Where a decision has its own numbered entry, this document links to it rather than repeating it.

## 1. How the requirements were derived

The brief's entire Technical Requirements section is one sentence:

> You are free to use any programming languages, frameworks, or libraries you prefer. We want to see
> what kind of engineering, design, and integration decisions you make.

So there was no requirements list to implement. What the brief supplies is four interview
transcripts, a list of label elements, one sample label, and the evaluation criteria. Every
requirement this project built against is therefore its own construction, and the first decisions
were about how to construct them.

**Requirements were derived by mapping every ask in the brief, then checking the map for holes.**
The alternative was to read requirements off the brief's "Additional Context" field list, which is
the only part of it that looks like a specification. That list is seven label elements and nothing
else — it says nothing about speed, batches, error handling, or who the user is, all of which the
transcripts state plainly. So the transcripts were read as the requirement source and the field list
as one input among them. The coverage table in
[the requirement list](../specs/0001-label-verification/requirements.md) has one row per ask, with
the person or brief section it came from and the requirement that answers it; three rows deliberately
end in "no requirement", which is the point of building the table — an ask that is recorded as
consciously unanswered cannot be mistaken later for one that was missed.

**Competing asks were settled by ranking the four people, and the ranking changes with the phase.**
While this is a prototype the weights are Sarah Chen 100, Dave Morrison 90, Jenny Park 80, Marcus
Williams 70, and that order decides when two asks pull against each other
([decision 0002](decisions.md#0002)). Weighing all four equally was rejected because it hides whose
asks decide whether the work goes further; a power-and-interest grid alone was rejected because it
files Dave as low power when adoption turns on senior agents like him, and it gives Marcus the most
weight in the phase where he asked for the least — his words for the prototype are "Just don't do
anything crazy." The ranking inverts in production: Marcus and the IT leadership above him become
the deciders, through FedRAMP, authority to operate and PII review. The prototype is built for the
first order and records how it would meet the second, which is why the constraints Marcus set are
written as constraints rather than as requirements — see §2.

**Each requirement carries the reason it exists, in its own text.** Every scope and constraint entry
in [the product requirements](PRD.md) is followed by a `Because` line naming the fact in the brief
that forced it. This costs length — the document is longer than a bare requirement list — and it buys
the thing a bare list cannot do: when a requirement is later cut or switched off, the reason it
existed is still on the page to argue against, which is what made the cuts in §5 arguable rather
than arbitrary.

**Inferred numbers are marked as inferred.** The brief states two numbers that became requirements:
about five seconds for a single check, which Sarah Chen sets in bold and ties to the failed vendor
pilot, and 200 to 300 applications in a peak-season batch. Everything else numeric in the
requirements is this project's inference, and the inference is visible rather than presented as an
instruction:

| Number | Where it is used | Basis |
|---|---|---|
| 5 seconds | NFR-1, single-check latency | Stated in the brief, in bold |
| 300 submissions | NFR-2, batch size | Stated in the brief as a 200–300 range; the upper bound was taken |
| 95% of checks | NFR-1, the percentile the 5 seconds applies to | Inferred. The brief says "results back in about 5 seconds", which is not a percentile |
| 10 minutes | NFR-2, batch completion | Inferred. The brief gives the batch size but no time for it |
| WCAG 2.2 level AA | NFR-3, accessibility | Inferred from Section 508, not from the brief — see §2 |
| 90% of checks agree | S-1, the release gate on the test corpus | Inferred |
| 0.92 similarity | FR-7, the brand-match threshold | Inferred, then re-derived against real labels — see §3 |

Naming the inferred ones costs the appearance of certainty. It buys a reviewer the ability to
disagree with a number without disagreeing with the product: if Treasury's real requirement is 99%
inside five seconds rather than 95%, that is one line of a requirement document, not a redesign.

**The scope line was drawn at the elements the brief lists, and three candidate checks were cut
before any code was written.** Conditional label fields (sulfite, organic, allergen, cochineal), the
279-entry American Viticultural Area list for wine appellations, and the 41-item allowable-revisions
check were all ruled out. The grounds differ and are worth separating: the conditional fields are not
mandatory and no person in the brief asked for them; the AVA list is a wine-only rule and checking
one beverage type in depth before all three are checked at all inverts the brief's own preference for
a working core; and the allowable-revisions check is a different problem — auditing changes to an
already-approved label, not comparing a label to its application. Cutting the third is the one that
needed the argument, because it is the most impressive-looking of the three.

**Build choices are judged by seven criteria in a fixed order, and failing an earlier one is
disqualifying** ([decision 0003](decisions.md#0003)). Speed, the exact warning check and judgement
on trivial differences come first, measured on real labels — vendor figures and generated labels do
not count as evidence. A working core comes second. The rejected alternative was scoring each option
against all the criteria and summing: that lets a strong cost score buy back a missed five-second
limit, and the brief's own account of the abandoned vendor pilot is the evidence that a slow tool is
dropped whatever else it does well.

The assumptions made in the gaps the brief left are listed in
[the README](../README.md#assumptions), which is where the graded deliverable puts them.

## 2. The constraints nobody chose

### The regulation the product enforces

The rules are 27 CFR Part 4 (wine), Part 5 (distilled spirits), Part 7 (malt beverages) and Part 16
(the health warning), plus 19 CFR §134.45 for country-of-origin marking, which is Customs' rule
rather than TTB's and is the one an importer's label most often turns on.

**The regulation is pinned, not remembered.** Each part was pulled from the eCFR API on 2026-09-15,
current as of 2026-09-11, and the extracts live in [docs/reference/](reference/) with their source
and date at the top of each file. The Government Health Warning goes further: its 283 characters are
a committed asset compared against by hash, so an edit to the regulation's text is a deliberate
commit and not a silent drift. The alternative — reading the warning text out of a Python constant —
costs nothing to write and gives no way to tell a typo from an amendment.

**A rule the app applies lives in the rule pack with its citation, never in code.** Every check is a
YAML entry naming the CFR section it enforces, and `tests/test_validator_registry.py` fails the build
if a validator carries a citation instead. What it buys: a compliance officer can read what the app
checks without reading Python, and a regulation change is a data edit. What it costs: an indirection
between the rule and the code that runs it, which is why the loader cross-checks the pack at startup
and refuses to boot on a rule naming a validator that does not exist.

**Three checks the regulation defines cannot be made from a photograph, and they are switched off
rather than guessed.** Contrasting background (§16.22(a)(1)), characters per inch (§16.22(a)(4)) and
type height (§16.22(b)) need the physical scale of the label or the colour of the ink, and an
uploaded image carries neither. Each stays in the pack with its citation and the reason it is off, so
a reader can see the check exists and why it does not run ([0006](decisions.md#0006),
[0013](decisions.md#0013)). The confirming fact came from TTB's own form: the instructions to
Form 5100.31 say TTB does not routinely review labels for type size, characters per inch or
contrasting background either. A check that reports a verdict it has not earned is the one failure
this product cannot have, and switching a rule off produces no finding at all rather than a pass.

### The regulation that governs the product

Nothing in the brief asks for accessibility. A federal application is bound by Section 508 anyway,
which is why NFR-3 sets WCAG 2.2 level AA — 508 incorporates WCAG 2.0 AA as its floor, and 2.2 is
the current recommendation, so building to the floor would ship a product already behind. That number
is marked as inferred in §1 for the same reason as the others: a reviewer who knows Treasury's real
standard can change one line.

The heavier federal constraints are real and deliberately out of the prototype: FedRAMP authorization,
an authority to operate, and a privacy review of anything holding applicant material. Those are
production gates, and the record says so rather than pretending the prototype cleared them — it is
also why the stakeholder ranking in §1 inverts for production, where IT and the authorizing officials
decide and the reviewing agents do not.

One place this bites today: PRD constraint C-2 says the product retains no label image once it has
returned a result. It does not meet that. The uploaded image is written to disk so a result page
survives a restart, and swept after seven days. The labels this prototype ships are public COLA
Registry images under CC0, so nothing it holds is anyone's private material, and the requirement
stays in the PRD unchanged because it is the right requirement for the real thing
([0018](decisions.md#0018)). A demo that quietly failed that requirement while claiming to meet it
would be worse than one that misses it on the record.

### The agency's own plumbing

The IT interview sets three constraints, and none of them is negotiable by this project: no
integration with COLA or any other TTB system, outbound traffic blocked at the firewall, and nothing
new to operate. They decide more of the architecture than any preference did.

- **No COLA integration** means the application's declared values arrive with the submission rather
  than being fetched, and there is no database anywhere in the app.
- **Blocked outbound traffic** is why the default reader runs on the machine, ships its own models in
  the wheel, needs no key and makes no outbound call ([0005](decisions.md#0005)). The hosted reader
  exists behind the same interface for the environment that can reach it, and the two are
  substitutable because the rules — not the reader — decide every verdict.
- **Nothing new to operate** is why a clone and the deployed container are the same application with
  a thin layer between them ([0004](decisions.md#0004)), and why the app holds no state a restart
  cannot rebuild, except the one image file above.

### What it costs to run

The seventh build criterion is that an option is free or cheap, and it is last on purpose: it cannot
buy back a failure on any of the six above it. Government readers are not weighing a return on
investment here, so what follows is the cost of running the thing and what each free choice gave up.

**Reading a label costs CPU, not money.** The default reader has no per-call cost. The hosted reader
was measured at about $0.0011 per application at paid rates, and the prototype's own measurements ran
on a free tier. At TTB's stated volume of roughly 150,000 applications a year, the hosted reader
would be a few hundred dollars a year of inference — which is not the reason it is off by default.
It is off because a reviewer must be able to clone this and run it with no account.

**The deployment is the only line item, and it moved from $9 a month to nothing.** That reversal is
in §5, because what drove it is not what it looks like.

**What free costs.** A scale-to-zero service has a cold start, and Sarah Chen's five seconds is the
requirement most at risk from it — the mitigation is a keep-warm ping and startup CPU boost, and the
figure is unmeasured until the service is up. The free allowance is CPU-bound: about 45,000
instance-seconds a month at the size this runs, roughly twelve hours of request handling, which is
ample for a demo and would not survive a real agency's traffic for a week. Image storage is not free
beyond half a gigabyte. Every one of those is a number a reviewer can check rather than a claim that
the choice was costless.

### The people who would use it

Four people in the brief, and the design answers them individually rather than in aggregate.

- **Dave Morrison**, 28 years in the job: "You need judgment." So no check auto-rejects, every finding
  carries the rule and the citation behind it, and a difference the app cannot settle goes to him
  labelled as unsettled rather than resolved by a guess.
- **Jenny Park**, eight months in: "It has to be **exact**." So the warning is compared word for word
  against the pinned regulation text, and the parts of §16.22 that cannot be measured from a photo are
  visibly switched off rather than silently skipped.
- **Sarah Chen**, deputy director: five seconds, no hunting for buttons, 200 to 300 in a batch. So the
  single check is the front door, the batch streams each result as it finishes rather than making her
  wait for the last one, and one label is run on its own before the rest so the first answer arrives
  quickly.
- **Marcus Williams**, IT: "Just don't do anything crazy." Answered in the section above, by building
  nothing that needs him.

## 3. How the system was built

### The seams

Three seams, and each one exists because something on the other side of it may have to change.

1. **Reader behind an interface.** Two implementations, one contract: an image goes in, field
   observations with evidence come out. Swapping the reader cannot change a verdict, because the
   reader does not produce verdicts.
2. **Rules as data.** The pack is YAML with citations; the engine selects the rules that apply to an
   observation and runs named validators. A regulation change is an edit to data.
3. **One envelope out.** Every path — single, batch, short-circuit — returns the same structure, with
   per-field findings, the audit trail, and metrics. The browser page and the batch stream read the
   same object, so a change to what a verdict carries cannot reach one surface and miss the other.

### What the model may do, and what bounds it

A model may read a label. It may not decide anything. An earlier layer that sent finished results to
a language model for a second opinion was removed outright — about 644 lines reaching into 18 files,
plus two SDK dependencies ([0009](decisions.md#0009)) — because a compliance verdict that a model can
influence cannot be defended to the person who has to sign it. What the removal buys is the property
the product is sold on: the same label and the same application give the same answer every time, with
a citation attached. What it costs is every capability that needs judgement beyond a scored
comparison; those go to a human, which is the same answer Dave gave.

### The stack

The choices and the reason for each are in the README's [tools table](../README.md#tools-and-why-each-one).
What that table does not say is what was turned down. A client-side framework for the whole interface
was rejected because only the evidence area needs real interactivity and a build step on the reviewer's
machine is a barrier to running this at all; the built bundle is committed so no Node is needed. A GPU
reading stack was designed early and dropped with the hardware premise it rested on. A database was
never added, because nothing outlives a request that the filesystem cannot hold.

### The numbers, and what set them

Three thresholds decide outcomes, and none of them is a guess left where it landed.

- **0.92 brand similarity.** Set from research, then re-derived against real labels. `Stones Throw`
  against `Stone's Throw` measures 0.9846; `Gallo` against a misread `QALIO` measures 0.7333, which
  is why a first-letter-dropped variant is a review route and never a match
  ([0015](decisions.md#0015)).
- **1% cross-unit tolerance on net contents.** Derived, not chosen: the standards of fill in
  §4.72/§5.203 as amended by T.D. TTB-200 put the floor at 0.633% and the ceiling at 1.216%, and a
  test recomputes both bounds and asserts the shipped value sits between them
  ([0014](decisions.md#0014)). Same-unit comparisons stay exact.
- **Lookahead of three labels in a batch.** The reviewer's pull is the demand signal; reading further
  ahead than that spends CPU on results nobody has asked for yet ([0021](decisions.md#0021)).

### What a verdict carries

Every field result carries what was read from the label, the application's value beside it, the rules
that ran with their CFR citations and reason codes, a confidence band, and the region of the image the
reading came from. Three outcomes only — match, mismatch, needs review — and the third is a real
answer rather than a failure to produce one. The reason codes are a registry with a test in four
directions, so a code cannot be emitted without being declared, or declared and silently never used
([0022](decisions.md#0022)).

### What each kind of error costs

A false rejection is the expensive error: it sends a compliant applicant back round a process that
takes weeks, and it is the error that would end the pilot. A false pass is caught downstream by the
reviewing agent, who approves or rejects every finding anyway. That asymmetry is why unmeasurable
checks go to review rather than to reject, why an unplaceable country-of-origin statement is a review
and not a rejection ([0016](decisions.md#0016)), and why an unmeasured boldness on the warning heading
is a review while the capitals — which were read — are still decided.

### What it refuses to take

- **A label with no application is read but not checked**, and the audit trail says so before the
  label is read. The beverage the application declares is what selects the rule pack, and the readers
  cannot tell a wine from a spirit. The cost is stated rather than hidden: an image-only upload loses
  the warning check, which is the brief's most prominent single requirement
  ([0010](decisions.md#0010)).
- **A batch item with no usable image is refused by name and the batch continues.** One bad file in
  300 used to be able to end the run; now it produces a needs-review result naming the file, and the
  other 299 are checked ([0020](decisions.md#0020)).

### The order the work runs in

One label is checked on its own first, and the rest run as a batch behind it. The reviewer sees a real
result in seconds instead of watching a progress bar, and the batch then paces itself against how fast
they are actually working through the results.

## 4. What is proven, and what is not

**The answer key is real labels.** `tests/fixtures/labels/` holds 30 approved labels from TTB's public
COLA Registry — 14 spirits, 8 wine, 8 malt, 14 of them imports — with 56 face images, plus 8
deliberately flawed variants. Each carries a transcription of what it prints and the expected result
per check. The key is ground truth independent of the reader, and it is never widened to make a
claim come out right: three separate decisions record a claim being changed to match the corpus rather
than the other way round.

**What that has caught.** Thirteen reject-severity failures against real approved labels from one
class-and-type rule, closed to zero with no other verdict moved ([0012](decisions.md#0012)). A format
check that matched a string it had built itself and would have rejected lawful silence
([0011](decisions.md#0011)). A glare gate that refused seven faces of five perfectly readable labels
and had no case anywhere in the corpus it was right about ([0026](decisions.md#0026)). A tolerance
rule set that could never report a match for any label of any type, because the second number it
compared against comes from a laboratory and this app never sees one ([0008](decisions.md#0008)). In
every one of those, the unit tests were green: each was found by running the thing against real
labels, which is the argument for having the corpus at all.

**Reading accuracy is published as counts, not percentages.** The
[README's table](../README.md#reading-accuracy) gives each check as correct-of-scoreable over the
whole corpus — 30 of 30 on the warning being present, 14 of 30 on it being word for word, 16 of 30 on
brand. A percentage drawn from thirty labels reads as a precision this corpus does not carry
([0027](decisions.md#0027)). The figures are not flattering and they are the honest state of a CPU
reader on display type.

**What is not proven.** The five-second requirement has no figure: it belongs to the deployed
hardware, the service is not up, and a number measured on a developer's machine would describe the
wrong computer — the test is written and runs the moment there is a URL. The ten-minute figure for a
300-label batch has no instrument at all. Neither of those is presented anywhere in this repository as
met.

## 5. What changed while it was being built

**The deploy host moved, and not for the reason it looks like.** The first decision put the service on
Hugging Face Spaces at $9 a month, on one argument: a public demo URL is unauthenticated, so the cost
had to be bounded by a plan rather than by traffic, and no mechanism for bounding a metered host was
on the table ([0023](decisions.md#0023)). The second decision moved it to Google Cloud Run
([0025](decisions.md#0025)). No fact had changed — the $9 gate was confirmed live and still stands.
What changed is that a mechanism appeared: this project already had its own DNS zone, a proxy in front
of the service takes a rate-limit rule, and with the meter bounded at the edge, plus a two-instance
ceiling, concurrency of one and a request timeout, the $9 bought nothing the free tier did not already
give. The constraint never moved; the instrument that satisfies it did, and the cost fell out.

**A requirement was corrected rather than the code.** The specification said a brand differing only in
punctuation should go to a reviewer. Form 5100.31's own allowable-revisions item permits punctuation
changes with no new approval, and the research that set the requirement contradicted itself between its
opening and its worked example. `Stones Throw` against `Stone's Throw` is the case Dave complains about
by name. So the PRD and the requirement list were amended and the change logged, rather than making the
product do the wrong thing consistently ([0017](decisions.md#0017)).

**A second opinion from a language model was built and then removed** — see §3. **A pre-read glare gate
was built, measured against the corpus, and deleted** when it turned out to be measuring how light the
label stock is. **A rule that could never pass was deleted rather than left switched off**, and a
different rule in a similar state was switched off rather than deleted, because one was unbuildable and
the other was merely unbuilt; the two entries argue with each other on the record.

## 6. How the work was run

**Every fork is recorded where it was decided, with what was rejected and what decided it.**
[docs/decisions.md](decisions.md) is 27 entries and it governs nothing on purpose: it records why, and
a rule that binds future work goes to the requirements or the rule pack instead. A superseded entry is
marked and left standing rather than edited away, which is why the host reversal above can be read as
it happened rather than as it was later rationalised.

**Checks replace conventions wherever one is available.** The README's own claims are a test — every
document path it names must resolve, and its accuracy section may not contain a percentage. The rule
pack fails the build on a rule with no validator. The reason-code registry is checked in four
directions. Each of those started as a convention somebody broke.

**The work ran as several sessions at once, split by file ownership**, because two writers in one file
is the failure that costs a day. Where a fix belonged to a file another session owned, it was written
down and handed over rather than reached into — three of the entries above are handovers of exactly
that kind.

**What was cut for time, named as cut.** The evaluation corpus was right-sized from 250 labels to
about 50, and the record says plainly that this was a calendar-driven cut rather than a principled
one. Wine depth beyond the seven elements, malt formula matching, and the 41-item allowable-revisions
audit were all ruled out before any code was written. The brief prefers a working core to ambitious
incompleteness; the cuts are on the record so that preference can be checked rather than claimed.
