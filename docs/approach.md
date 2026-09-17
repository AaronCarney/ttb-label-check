# Approach, tools and assumptions

## The problem we set out to solve

TTB's compliance agents review roughly 150,000 label applications a year, and most of each review is
matching. Does the brand name printed on the bottle say what the application says. Is the alcohol
figure the declared one. Is the government health warning present, and word for word. A simple
application takes five to ten minutes by eye, and in peak season importers file hundreds at once.

This app does the matching and leaves the deciding to the agent. It reads a photograph of a label,
compares it to the application filed for it, and returns one result per element — pass, fail, or
needs review — with the regulation behind it. It never approves and never rejects.

## What we were asked, and what we decided it meant

The brief's technical requirements are a single sentence: use whatever languages and libraries you
prefer, we want to see what decisions you make. There was no requirements list to implement. So the
first real decision was how to build one.

**We took the requirements from the interviews, not from the field list.** The list of seven label
elements is the only part of the brief that looks like a specification, and it says nothing about
speed, batches, error handling, or who uses this. The four people in the transcripts say all of it.
Every requirement we built against traces back to a person or a passage, and three asks are recorded
as deliberately unanswered — so an ask nobody met cannot later be mistaken for one nobody noticed.

**When the four of them wanted different things, we ranked them, and the ranking changes with the
phase.** For a prototype the deputy director decides, then the senior agent whose adoption it lives
or dies by. In production that inverts: IT and the authorizing officials decide, and the reviewing
agents do not. Weighting all four equally would have hidden whose answer actually settles a
disagreement.

**Two numbers come from the brief. Every other number is ours, and is marked as ours.** Five seconds
for a single check and 200 to 300 labels in a peak batch are stated. The rest — the percentile the
five seconds applies to, the ten-minute batch target, the accessibility level, the matching
thresholds — we inferred. Naming them costs the appearance of certainty and buys something better: if
Treasury's real standard is different, that is a line of a requirements document to change, not a
redesign.

**We cut three checks before writing any code.** Conditional fields like sulfite and organic
declarations, the several-hundred-entry list of approved wine appellations, and an audit of
permissible changes to an already-approved label. The last is the one that needed the argument,
because it is the most impressive-looking of the three — and it is a different problem from the one
we were asked to solve. The brief prefers a working core to ambitious incompleteness, and these are
the cuts that preference bought.

## The constraints nobody chose

Federal work has rules that outrank engineering preference. These shaped more of the product than any
technical taste did.

**The regulation the product enforces.** The checks come from the parts of the alcohol regulations
covering wine, spirits, malt beverages and the health warning, plus the Customs rule on
country-of-origin marking, which is where an importer's label most often turns. We pulled each text
from the official source on a dated day and committed it, rather than working from memory. The health
warning goes further: its exact wording is stored as a fixed asset and compared by fingerprint, so a
change to the regulation's text is a deliberate act and not a silent drift.

**Some rules cannot be checked from a photograph, and we switched them off rather than guess.** Three
of the warning's typographic requirements — contrasting background, characters per inch, type height
— need the physical scale of the label or the colour of the ink. An uploaded image carries neither.
Each rule stays visible with its citation and the reason it does not run. TTB's own form instructions
confirmed the judgement: the agency does not routinely review labels for those either. A check that
reports a verdict it has not earned is the one failure this product cannot have, so a switched-off
rule produces no finding at all rather than a quiet pass.

**The regulation that governs the product itself.** Nothing in the brief asks for accessibility, but a
federal application is bound by Section 508 regardless, and that standard is binding regulation
rather than agency policy. We built to the current accessibility recommendation rather than to
508's older floor, because building to the floor ships something already behind.

The heavier federal gates are real and none of them is met here. Each is named with what it would
actually require:

- **An authority to operate.** Nothing runs on an agency network without one, and the assessment
  behind it is where a prototype's shortcuts surface. Its effect on this build was to rule out
  anything designed to be hard to assess. The rules are readable data carrying their own citations,
  every choice has a recorded reason, and the system can enumerate every verdict it is capable of
  producing. An assessor's questions have answers that do not depend on asking us.
- **FedRAMP.** It governs which hosted services a federal system may call at all, and it is why the
  reader that runs by default runs on the machine rather than in someone's cloud.
- **Federal AI use governance.** An AI system that decides against a member of the public draws the
  heaviest version of that review. Our answer is structural rather than procedural: **the model never
  decides.** It reads, and rules with regulatory citations decide what the reading means. What an
  AI use-case account would have to describe here is a reader whose output is evidence, not a
  judgement that has to be defended on its own authority.
- **A privacy review and a records schedule.** Anything holding applicant material needs both. This
  prototype keeps an uploaded image for seven days so a result page survives a restart. That is a
  convenience, not a retention policy, and a real deployment needs a period set by the agency's
  records schedule rather than by a constant in the code. Our own requirements say the product should
  keep nothing; it does not meet that, and we left the requirement standing and the failure on the
  record rather than quietly lowering the bar.

**The agency's own plumbing.** The IT interview sets three constraints and none is negotiable: no
integration with TTB's existing systems, outbound traffic blocked at the firewall, and nothing new to
operate. They decided the architecture more than any preference did. No integration means the
application's values arrive with the submission and there is no database anywhere in the product.
Blocked outbound traffic is why the default reader ships its own models, needs no key, and makes no
network call. Nothing new to operate is why a clone and the deployed service are the same
application, and why the app holds no state a restart cannot rebuild.

**What it costs to run.** Cost was our last criterion on purpose — it cannot buy back a failure on
any of the others. Reading a label costs processor time, not money: the default reader has no
per-call charge. The hosted alternative would run a few hundred dollars a year of inference at TTB's
volume, computed from published rates rather than measured by us, and that is not why it is off by
default. It is off because a reviewer must be able to clone this and run it without an account. The
deployment itself moved from a nine-dollar monthly plan to nothing, inside a free tier whose
allowance is about twelve and a half hours of request handling a month — ample for a demonstration,
and not enough to survive a real agency's traffic for a week. Every one of those is a figure a
reviewer can check rather than a claim that the choice was costless.

**The people who would use it.** Four people in the brief, answered individually rather than in
aggregate. The agent with 28 years in the job said "you need judgment", so nothing auto-rejects,
every finding carries the rule behind it, and anything the app cannot settle goes to him labelled
unsettled rather than resolved by a guess. The reviewer eight months in said it has to be exact, so
the warning is compared word for word and the parts that cannot be measured are visibly switched off
rather than silently skipped. The deputy director wanted speed, no hunting for buttons, and batches,
so results stream back as each finishes rather than making her wait for the last one. IT said don't
do anything crazy, and we answered by building nothing that needs them.

## How we built it

**The model reads. The rules decide.** That line is the centre of the design. A reader turns a
photograph into text and locations; rules written as data, each naming the regulation it enforces,
turn that into verdicts. We built a layer that sent finished results to a language model for a second
opinion, and then deleted it — around 600 lines across 18 files — because a compliance verdict a
model can influence cannot be defended to the person who has to sign it. What the deletion buys is
the property the product is sold on: the same label and the same application give the same answer
every time, with a citation attached. What it costs is every capability that needs judgement beyond a
scored comparison. Those go to a person, which is the same answer the senior agent gave.

**Rules are data, not code.** Every check is an entry naming the regulation section it enforces, and
the build fails if a check tries to carry that citation in code instead. A compliance officer can
read what the app checks without reading a programming language, and a regulation change is an edit
to data rather than a release.

**Three outcomes, and the third is a real answer.** Pass, fail, and needs review. Needs review is
used wherever the app can see an element but cannot honestly settle it, and it is the destination for
every uncertainty rather than a fallback. Each result carries what was read, the application's value
beside it, the rules that ran with their citations, a confidence level, and the part of the image the
reading came from — so a reviewer can check the answer instead of trusting it.

**We designed around the error that costs more.** A false rejection sends a compliant applicant back
round a process that takes weeks, and it is the error that would end a pilot. A false pass is caught
downstream by the agent, who rules on every finding anyway. That asymmetry is why anything
unmeasurable goes to review rather than to rejection.

**One label is checked first, then the rest run behind it.** The reviewer gets a real result in
seconds instead of a progress bar, and starts working while the remainder runs. The batch then paces
itself against how fast they are actually reading, rather than racing ahead to compute results nobody
has asked for.

## Tools, and why each

Plain Python for the service, because the reading and rules libraries live there and the brief's
priority is a working core rather than a novel stack. A conventional server-rendered interface with
one interactive area, rather than a full client-side application, because only the evidence panel
needs real interactivity and requiring a build step on the reviewer's machine is a barrier to running
this at all. No database, because nothing outlives a request that a file cannot hold. A processor-only
reader that ships with the code, because the firewall constraint makes any cloud-first design
unrunnable inside the agency. A container as the unit of deployment, so the clone and the deployed
service are the same thing.

## What we can prove, and what we cannot

**Our answer key is real labels.** We assembled 30 approved labels from TTB's public registry across
all three beverage types, 14 of them imports, plus 8 deliberately flawed variants. The brief suggested
generating test labels; we used real ones because a generated label proves the reader can read what
we drew, and a real one proves it can read what a producer actually printed. Each carries a
transcription of what it prints and the expected result for each check, so the key is independent of
the reader being tested.

**That corpus caught four failures that unit tests called green.** A class-and-type rule that failed
thirteen genuinely approved labels. A format check that matched a string it had built itself. An
image-quality gate that rejected seven faces of five perfectly readable labels and was right about
none. A tolerance rule that could never report a match for any label, because the second figure it
compared against comes from a laboratory and this app never sees one. Every one was found by running
the product against real labels, which is the argument for having the corpus at all.

**We publish reading accuracy as counts, not percentages.** Thirty of thirty on the warning being
present, fourteen of thirty on it being word for word, sixteen of thirty on brand. A percentage drawn
from thirty labels reads as a precision this corpus does not carry. The figures are not flattering
and they are the honest state of a processor-only reader on display typefaces.

**The five-second requirement is measured, and it is missed.** It belongs to the deployed hardware,
so we measured it there rather than on a developer's machine. Checking all 38 test submissions one at
a time returned 34 of 38 inside five seconds through the address a reviewer actually uses. The
requirement is 95 percent. The misses are narrow and they cluster — every one landed between five and
5.21 seconds — and an earlier run passed outright, so the honest statement is that the rate sits on
the line rather than well below it. Nothing has been tuned for speed, and the obvious lever, more
processor cores, is untried.

**Two things we did not prove.** A reader cannot tell an unmeasured claim from a measured one by
looking, so each is named:

- The ten-minute target for a 300-label batch has no instrument at all — no test and no figure.
- Accessibility is checked automatically, but at the older standard, so the two criteria that were
  our stated reason for targeting the newer one are never scanned. Two screens are scanned, the
  single-label page and a batch's results; the bulk-upload page is not. And the manual review the
  requirement really asks for has not been run — an automated pass is the floor of an
  accessibility claim, not the whole of one.

The first is a missing measurement. The second is the pattern we would rather name than hide: the
requirement was written, the mechanism was built, and the proof stopped at the half a machine can
do. That is what a week-long build produces when the deadline arrives before the test does.

## What we changed our minds about

**The deploy host moved, and not for the reason it looks like.** We first put the service on a
fixed-price host at nine dollars a month, on one argument: a public demo URL is open to anyone, so the
cost had to be bounded by a plan rather than by traffic, and we had no way to bound a
pay-per-use host. We later moved to a pay-per-use service. No fact had changed and the nine-dollar
figure still stood. What changed is that a mechanism appeared — we already had our own domain, and a
proxy in front of the service could carry a rate limit. With the meter bounded at the edge, the plan
fee bought nothing the free tier did not already give. The constraint never moved; the instrument
that satisfied it did.

**We corrected a requirement rather than the code.** Our specification said a brand differing only in
punctuation should go to a reviewer. TTB's own form permits punctuation changes with no new approval,
and the research behind the requirement contradicted itself. "Stones Throw" against "Stone's Throw"
is exactly the case the senior agent complains about by name. So we amended the requirement and
logged the change, rather than making the product do the wrong thing consistently.

**We deleted work that could not earn its place.** The second-opinion layer described above. An
image-quality gate that turned out to be measuring how light the label stock is. A rule that could
never pass, deleted — while a different rule in a similar state was switched off instead, because one
was unbuildable and the other merely unbuilt.

**What we would do next, in order.** Scan the bulk-upload page and raise the automated accessibility
check to the standard we committed to, then run a real accessibility review rather than an automated
one; instrument the batch timing, which is the one requirement with no measurement at all; then widen
the corpus, which is the work that makes every figure above more trustworthy.

## How the work was run

Every fork is recorded where it was decided, with what was rejected and what settled it. That record
governs nothing on purpose — it says why, and anything meant to bind future work goes into the
requirements or the rules instead. A decision that was later reversed is marked and left standing
rather than edited away, so the host reversal above can be read as it happened rather than as it was
later rationalised.

Where a convention could be replaced by a check, we replaced it. The README's own claims are tested:
every document path it names must resolve, and its accuracy section is forbidden from containing a
percentage. The rule set fails the build if a rule has no implementation. Each of those started as a
convention somebody broke.

## Assumptions we made

The brief says it values how gaps are filled independently, so these are stated as our calls rather
than as findings:

- The user is a TTB compliance agent reviewing a submission, not an applicant checking their own
  label before filing.
- The application's declared values arrive with the submission. Nothing is fetched from TTB's
  existing systems, because IT ruled that out.
- One label image per submission is the normal case, front and back where supplied.
- English-language labels. The regulations provide for other languages, and we do not handle them.
- The agent makes the final call on every element. The product never approves and never rejects.
- Where the brief gave a range, we built to the harder end of it.
