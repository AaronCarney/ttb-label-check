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

**What the brief actually asks for is short, and most of what it says is not an ask.** Two
deliverables: a source repository with a README carrying setup and run instructions and brief
documentation of approach, tools and assumptions; and a deployed URL where a working prototype can
be accessed and tested. It also asks that the app handle labels carrying information like the one
worked example it gives. Everything else is context, and reading it as a specification would have
been the first mistake available. The seven-element list arrives under "For reference" and "common
elements include", with the brief itself noting that exact requirements vary by beverage type —
which is why the regulations, and not that list, set the checks. The pointer to ttb.gov is an
encouragement to read, as is the suggestion to generate test labels, which we declined for a reason
given later. The one wish about photographs shot at bad angles and in bad light is marked out of
scope by the person asking for it, in the same sentence.

**We took the requirements from the interviews, not from the field list.** The list of seven
elements says nothing about speed, batches, error handling, or who uses this; the four people in the
transcripts say all of it. Every requirement traces back to a person or a passage, and the one ask
we met with no requirement at all is recorded as such, so an ask nobody answered cannot later be
mistaken for one nobody noticed.

**When the four of them wanted different things, we ranked them, and the ranking changes with the
phase.** For a prototype the deputy director decides, then the senior agent whose adoption it lives
or dies by. In production that inverts: IT and the authorizing officials decide, and the reviewing
agents do not. Weighting all four equally would have hidden whose answer actually settles a
disagreement.

**Two numbers come from the brief. Every other number is ours, and is marked as ours.** Five seconds
for a single check and 200 to 300 labels in a peak batch are stated. The percentile the five seconds
applies to, the ten-minute batch target, the accessibility level and the matching thresholds we
inferred. Naming them costs the appearance of certainty and buys something better: if Treasury's
real standard is different, that is a line of a requirements document to change, not a redesign.

**We cut three checks before writing any code.** Conditional fields like sulfite and organic
declarations, the several-hundred-entry list of approved wine appellations, and an audit of
permissible changes to an already-approved label. The last needed the argument, because it is the
most impressive-looking of the three and it is a different problem from the one we were asked to
solve. The brief prefers a working core to ambitious incompleteness, and these are the cuts that
preference bought.

**We built the answer key before the thing it grades.** The labels were collected and transcribed
the day before there was an application to read them — 30 approved labels from the public register,
each with what it prints and the verdict each check should return — and the rule pack came before
the code that runs it. Writing the tests after the code is the usual order and it was the live
alternative; it produces tests that agree with the code, and a transcription of what a bottle
actually prints does not. The cost is that the key was written blind, and several entries had to be
corrected once real readings arrived.

## What we looked up before we chose

**We took each fact from the document that owns it.** The regulations came from the official
electronic code, the hosting limits and prices from each vendor's own documentation rather than a
summary of it, each recorded with the page and the day it was read, so a change in a vendor's terms
shows up as a difference rather than a surprise. What we could not confirm that way we wrote down as
unconfirmed rather than filling it in from general knowledge, and a marketing claim is marked as the
vendor's claim. The rule cost us answers: the hosting study ends with a list of the questions it
could not settle.

**The reading corrected us before the code could.** The spirits alcohol tolerance we started from
was half the real one, and we had taken the 2022 rewrite of the labelling rules to cover all three
beverage types when it had left wine behind — wine still runs on text written in 1960. Either would
have shipped as a check that was confidently wrong about genuine labels, and neither would have
failed a test we wrote ourselves.

**The gaps we could not close, we designed around.** Most hosts, the one we deployed to among them,
do not publish how long it takes to wake a sleeping service, so the speed figures here come from
measuring the running deployment. TTB puts every approved label on the public record but serves them
one at a time, so each test label was found and transcribed by hand. Widening the corpus, the work
that would firm up every accuracy figure here, is bounded by that hand work and not by permission.

**What we inferred about the four people is marked as inferred.** Their words and their roles are on
the record; what they want, and what would make them refuse to adopt this, is our reading, labelled
as ours wherever the design leans on it.

## The constraints nobody chose

Federal work has rules that outrank engineering preference. These shaped more of the product than
any technical taste did.

**The regulation the product enforces.** The checks come from the parts of the alcohol regulations
covering wine, spirits, malt beverages and the health warning, plus the Customs rule on
country-of-origin marking, which is where an importer's label most often turns. Each text was pulled
from the official source on a dated day and committed rather than worked from memory, and the
warning's wording is a fixed asset compared by fingerprint, so a change to the regulation is a
deliberate act rather than a silent drift.

**Where a rule cannot be checked from a photograph, we switched it off rather than guess.** Three of
the warning's typographic requirements need the label's physical scale or the colour of its ink, and
an uploaded image carries neither. The alternative was a threshold we invented, applied to a real
producer as though the regulation said it. So a switched-off rule produces no finding at all rather
than a quiet pass, and stays visible with its citation and its reason.

**Part of the regulation is a standard, not a measurement, and those go to a person.** An
abbreviation that unmistakably indicates a country, a warning standing separate and apart, wording
readily legible, a designation similarly conspicuous — each is a test a person applies, and nothing
says which abbreviations qualify or how far apart is apart. So the origin check passes the plain
English name and sends every other form to review, which costs coverage rather than correctness: a
compliant Spanish-marked import becomes work for a reviewer, not a wrong answer. A label carrying no
origin statement at all is still rejected, because an absence is a fact rather than a judgement.

**Two sets of requirements are not covered at all, and were not on the record as choices.** Most
would have ended where the rules above did, so no verdict is wrong because of this. What is wrong is
the record: a requirement we decided not to check and one we never noticed look identical from
outside, and only the first was written down. We found them while writing this account, and
`README.md`'s *Limitations* now names them.

**The regulation that governs the product itself.** Nothing in the brief asks for accessibility, but
a federal application is bound by Section 508 regardless, and that standard is binding regulation
rather than agency policy. We built to the level it makes binding, WCAG 2.0 A and AA, and every
screen the product serves is scanned on each run. The scan is built not to flatter us: a check the
scanner cannot decide fails it rather than passing, so an undecidable result cannot read as a clean
one.

Sharpening it kept turning up real defects — six result-page cases below the AA contrast threshold,
a 27-pixel overflow at a 320-pixel viewport, three buttons painting white text on a near-white
background when hovered, and two more behind a development-only flag. All were ours and all are
fixed. So what we can claim is the mechanism, and the part of the standard a machine can judge, on
every page; the conformance review by a person has not been run, and we did not claim a newer
conformance level because axe-core runs no rule for either criterion that would justify one.

**The heavier federal gates are real, and none of them is met here.** An authority to operate, the
FedRAMP rules on which hosted services a federal system may call, federal AI use governance, and a
privacy review with a records schedule would each have to be satisfied before this ran on an agency
network. Two shaped the build anyway: the default reader runs on the machine rather than in
someone's cloud, and **the model never decides** — it reads, and rules carrying citations decide
what the reading means.

**The agency's own plumbing.** The IT interview sets three constraints and none is negotiable: no
integration with TTB's existing systems, outbound traffic blocked at the firewall, and nothing new
to operate. They decided the architecture more than any preference did: the application's values
arrive with the submission and there is no database anywhere in the product; the default reader
ships its own models, needs no key and makes no network call; and a clone and the deployed service
are the same application, holding no state a restart cannot rebuild.

**What it costs to run.** Cost was our last criterion on purpose — it cannot buy back a failure on
any of the others. The reader is free because it costs processor time rather than money, and it gave
up accuracy on hard images, named under what we can prove rather than left to be found. The
deployment is free on an allowance that covers TTB's volume about three times over, though not a
peak-season burst. The exposure is the absence of a stop rather than the meter: budgets alert rather
than cut off, so what bounds the bill is the invoker check, which refuses every caller but our own
front door before a request is billed, the two-instance cap and the request timeout
([decision 0025](decisions.md#0025); the figures are in `operations.md`).

**The people who would use it.** Four people, answered individually rather than in aggregate —
`README.md`'s *What it is* gives each answer. What belongs here is that answering them one at a time
is itself a constraint: the senior agent's "you need judgment" and the junior reviewer's demand for
exactness pull against the deputy director's demand for speed, and every place this product declines
to decide is a place the first two won.

## How we built it

**The model reads. The rules decide.** A reader turns a photograph into text and locations; rules
written as data, each naming the regulation it enforces, turn that into verdicts. A layer that sent
finished results to a language model for a second opinion was built and then deleted — 644 lines
reaching into eighteen more files — because a verdict a model can influence cannot be defended to
the person who signs it. Every capability needing judgement beyond a scored comparison goes to a
person instead.

**Rules are data, not code.** Every check is an entry naming the section it enforces, and the build
fails if a check carries that citation in code instead, so a compliance officer can read what the
app checks without reading a programming language. Nothing we depend on moves under us quietly
either: the default reader sits inside the application, and the optional hosted one names a dated
snapshot of the model, so a vendor's upgrade is a change someone makes deliberately.

**Every seam is there because something outside the code forced it.** The reader sits behind an
interface with two implementations because the agency's outbound traffic is blocked — what ships
must run with no key, and what reads harder images must be replaceable inside the agency's boundary.
The image and each result are files on disk because a clone and the deployed container are the same
application. The seam we did not build is named as missing: no rule can say "this applies whatever
the beverage is", which is why a label filed with no application is read and not checked.

**Three outcomes, and the third is a real answer.** Pass, fail, and needs review, the third used
wherever the app can see an element but cannot honestly settle it. Each result carries what was
read, the application's value beside it, the rules that ran with their citations and a confidence
level, next to the label image so a reviewer checks the answer rather than trusting it. The
interface deliberately does not draw the region a reading came from: that box was measured in the
frame the reader worked in, not the photograph the page shows.

**The regulation itself is in the product, and it was not typed in.** A citation opens a column
holding that section's wording, fetched from the eCFR's API, committed with its issue date and a
hash, and re-checked by a test. We had refused this once, because filling 43 citations meant typing
regulation text into a compliance tool with no test that could check it (`docs/decisions.md#0034`).
The parser now refuses rather than guesses — a citation it cannot read whole yields nothing, and a
reference it cannot cover fails the whole string (`docs/decisions.md#0046`).

**We designed around the error that costs more.** A false rejection sends a compliant applicant back
round a process that takes weeks, and it is the error that would end a pilot; a false pass is caught
downstream by the agent, who rules on every finding anyway. That asymmetry is why anything
unmeasurable goes to review rather than to rejection.

**The record would not answer a producer who contests a rejection.** To keep no applicant material
on disk, the result kept for seven days blanks both what was read and what the application declared,
the trail names the rule set but not the reader, and an override carries a session number because
nothing signs anyone in. That is the right privacy answer and it makes the kept copy useless as
evidence. Closing the gap needs a records schedule, a sign-in and real versions on the trail rather
than code.

**The thresholds are not equally well founded, and the gap is on the record.** The one percent that
lets millilitres match fluid ounces is derived — above the 0.633 percent rounding needs across every
authorised container size, below the 1.216 percent at which one authorised size stops being
distinguishable from the next — with a test recomputing both bounds on every run. The brand
thresholds, 0.92 to pass and 0.85 to send to a person, rest on published record-matching work rather
than on this project's labels. A larger set has no recorded reason at all: the confidence bands, the
floor each rule demands, the per-field multipliers, both image-quality gates, and the stroke-width
ratio deciding whether the heading is bold, which matters most because the code says it is
uncalibrated and it still drives a rule that can reject a label. Being wrong is not symmetrical —
too strict sends compliant labels to a person, too loose lets a doubtful one reach the agent reading
it anyway — so they were safe to ship unargued. Re-tuning them needs a wider corpus with a human
verdict on each, and that has not been done.

**One label is checked first, then the rest run behind it.** The reviewer gets a real result in
seconds instead of a progress bar, and the batch paces itself against how fast they are reading.
Over twelve labels that is all a batch buys: per label it is no cheaper than a single check, 1.16
seconds against 1.23, so it is a queue of the same work
(`docs/evidence/2026-09-20-batch-latency-run1.json`, taken on the development box).

**What it refuses to take.** An upload is identified by its own first bytes, never by what the
browser declares it to be, and an image can only be asked for by a restricted set of characters, so
no request names a path outside the store. One bad file in a batch is refused by name and the rest
still run. Size and count are bounded before the bytes behind them are read, and memory by one batch
at a time (`docs/decisions.md#0041`).

The hundred-image count only agrees with the request cap while the images are small: a hundred files
fit one request only if they average under **322.3 KB**. At the 1.5 MB per-image cap **20** fit; at
the largest label in our own corpus, 547 KB, **59**. So the count is a fairness limit and the bytes
are the real one, and `files_that_fit()` derives both from the caps rather than restating them.

**What a log is allowed to contain.** Logging is an allow-list rather than a filter: a line carries
only the fields named in advance, and fields that could hold applicant material are blanked by a
second pass. What it does not govern is a line's message text, and one thing walked around it — the
uploaded file's name was also the identifier every line correlated on, so naming a file after a
person put that person in the log. Display text and the correlating identifier are now separate, the
second minted by the app.

## Tools, and why each

Plain Python for the service. No other language was weighed, and that is the honest account: the
reading and rules libraries live in Python, so any other choice would have put a foreign-function
call under the one component whose accuracy the whole product rests on, and the brief's priority is
a working core rather than a novel stack. A conventional server-rendered interface with a small
interactive layer, rather than a full client-side application, because the parts that need real
interactivity are few — the keyboard path an agent uses to overrule a finding, and the batch page
that fills in as each result streams back — and requiring a build step on the reviewer's machine is
a barrier to running this at all. No database: a directory of files beat both an embedded database,
which answers no question the files do not, and object storage, which needs an account, a key and an
outbound call the clone cannot make. A processor-only reader that ships with the code, over a design
that only calls a hosted model — which cannot run where this product is for — and over picking a
reader per image at run time, which adds moving parts for an accuracy gain nobody has measured. A
container as the unit of deployment, over the cheaper runtimes that are not containers: the
edge-worker tier we costed runs under WebAssembly and caps processor time at ten milliseconds a
request, which a reader that takes two seconds cannot use at any price. The container also means the
clone and the deployed service are the same thing.

## What we can prove, and what we cannot

**Our answer key is real labels.** We assembled 30 approved labels from TTB's public registry across
all three beverage types, 14 of them imports, plus 8 deliberately flawed variants. The brief
suggested generating test labels; we used real ones because a generated label proves the reader can
read what we drew, and a real one proves it can read what a producer actually printed. Each carries
a transcription of what it prints and the expected result for each check, so the key is independent
of the reader being tested.

**That corpus caught four failures that unit tests called green.** A class-and-type rule that failed
thirteen genuinely approved labels. A format check that matched a string it had built itself. An
image-quality gate that rejected seven faces of five perfectly readable labels and was right about
none. A tolerance rule that could never report a match for any label, because the second figure it
compared against comes from a laboratory and this app never sees one. Every one was found by running
the product against real labels, which is the argument for having the corpus at all.

**The same corpus is what a reviewer downloads, and it is meant to be run rather than read about.**
`/batches/sample.zip` ships ten of the thirty at random, both faces where both were filed, and
`applications.csv` beside them carrying the application really filed for each. Dropped whole into
the batch form it exercises the product's actual claim — every label checked against its own
application — across all three beverage types, over passes that are not literal matches, with the
country-of-origin check actually running on the imports, and including a label whose photographs
show no bottler's name and address, which comes back as a check that was not made rather than as a
finding that the label lacks it. That distinction is the product's central honesty.

**The eight flawed variants are not in the pack, and that is deliberate.** They are real labels with
one thing altered — a word of the warning repainted, a heading dropped into title case, an
application's alcohol content set to 45% where the label prints 40% — and they exist in the test
corpus to prove the checks can fail. A demonstration built out of planted failures proves the plant
rather than the product, so the pack ships approved labels only. A reviewer who wants to watch a
check fail changes one value in `applications.csv` and re-uploads, which is exactly the mismatch
between a filing and a label that this product exists to catch.

**We publish reading accuracy as counts, not percentages.** Thirty of thirty on the warning being
present, twenty of thirty on it being word for word, seventeen of thirty on brand. A percentage
drawn from thirty labels reads as a precision this corpus does not carry. The figures are not
flattering and they are the honest state of a processor-only reader on display typefaces.

**The five-second requirement is measured on the deployed service, and it is missed.** It belongs to
the deployed hardware, so we measure it there rather than on a developer's machine: 18 of 37 checks
inside five seconds in one run and 21 of 37 in a second minutes later, against a requirement of 95
percent, with medians of 5.01 and 4.38 seconds. Nothing was stopped early and nothing came out of
the cache, so these are slow checks rather than blank ones.

**The cost is the second face, and it bought a correct answer.** Until 2026-09-19 the page took one
image and the same set measured 35 of 37 inside five seconds — but the warning is on the back of 20
of the 30 corpus labels, so those fast answers reported a warning missing that the label carries.
The page now takes a front and a back, read one after the other, and the submissions carrying a back
came in at a median of 5.55 and 4.95 seconds against 2.39 and 2.74 for the four that have only a
front. We took the trade knowingly and we publish the number it cost.

**Reading the faces concurrently was the untried lever, and it has now been tried on the bench
rather than in the product.** A running copy holds one reader and takes one image at a time behind a
lock, so the change is lifting that lock and not merely asking for both faces together; we measured
each shape it could take, in-process at the four threads the service runs, before building any of
it. The cores turn out to be spoken for already. A single read keeps 3.69 of 4 cores busy, and the
thread ladder says why: 1.198, 0.693 and 0.535 seconds per image at one, two and four engine threads
is close to linear, so four cores are genuinely working and nothing is idle for a second read to
take. Read at once, one label's two faces took 1.60 seconds where reading them in turn took 1.38,
and kept only 2.4 cores busy against 3.74 — the Python half of a read does not run alongside itself,
so the concurrent shape loses more to contention than it wins. For the one check a reviewer is
waiting on, the lever lengthens the wait it was meant to shorten, by about 16 percent.

**Over a queue the sign flips, and the price is what decided it.** Twelve faces cost 0.535 seconds
per image as built, 0.475 with two engines of two threads and 0.450 with four engines of one — 11 to
16 percent better. The slowest single image goes from 1.10 seconds to 1.92 and then 3.45, and
resident memory from 658 MB to 911 and 1267 MB against the service's 4 GiB. That is throughput
bought with the wait of whichever label a reviewer happens to be watching, and with the headroom of
a 4 GiB instance. The smallest version of the change is the worst of the lot: lifting the lock and
leaving one shared engine gave 0.734 seconds per image, 37 percent worse than doing nothing. So the
serialisation stays ([decision 0047](decisions.md#0047)), and the shapes compare on this box even
though the seconds do not compare to the deployed service
(`docs/evidence/2026-09-20-read-scaling.json`).

**Three levers have been tried now, and none of them closes the requirement.** More processor cores
moved one check of thirty-eight. Reading both faces at once costs the single check more than it
saves. The reading path itself has been tuned three times, most recently by reading a label's
sideways strips before reading the whole label again, which took the slowest corpus read from
1345 ms to 463 ms ([decision 0036](decisions.md#0036)). Earlier published shares of 87, 89, 71 and
92 percent stand as history only: they predate that tuning and a harness that could not tell a check
the evaluation guard had blanked from a slow one ([decision 0035](decisions.md#0035)).

**Two things we did not prove.** A reader cannot tell an unmeasured claim from a measured one by
looking, so each is named. The ten-minute target for a 300-label batch has no instrument at all — no
test and no figure. And accessibility past what a machine can check: the automated scan covers all
three screens and the batch table both empty and populated, and the last run was green, but whether
it passes is the result of a run rather than a property of the build. The manual review the
requirement really asks for has not been run. The first is a missing measurement; the second is a
limit on the proof rather than a gap in the build, and it is the half that needs a person.

## What changed, and what would change next

**The deploy host moved, and not for the reason it looks like.** We first took a fixed-price host
at nine dollars a month: a public demo URL is open to anyone, so cost had to be bounded by a plan
rather than by traffic, and we could not bound a pay-per-use host. We moved to one anyway. No fact
had changed; what changed is that a mechanism appeared — we already had our own domain, and a
proxy in front of the service could carry a rate limit. The constraint never moved; the instrument
that satisfied it did.

**We corrected a requirement rather than the code.** Our specification said a brand differing only
in punctuation should go to a reviewer. TTB's own form permits punctuation changes with no new
approval, and the research behind the requirement contradicted itself — "Stones Throw" against
"Stone's Throw" is the case the senior agent complains about by name. So we amended the
requirement rather than making the product do the wrong thing consistently.

**We stopped explaining the product inside the product.** The landing page had carried four
curated labels as buttons, each with a sentence saying what checking it would show. One asserted
an outcome the engine refuses to assert — that a beer's photographs show no bottler's name and
address *"and the check says so"*, where the check says only that it could not make the finding.
The larger fault was the tour itself: a demo is worth something only if it is the product with
data supplied. The buttons are gone, the sample pack carries applications alongside its images,
and what those sentences explained lives in `README.md`.

**We deleted work that could not earn its place.** The second-opinion layer described above. An
image-quality gate that turned out to be measuring how light the label stock is. A rule that could
never pass, deleted — while a different rule in a similar state was switched off instead, because
one was unbuildable and the other merely unbuilt.

**Who would run it, and what they would watch.** The agency's own IT would, and their interview
was explicit that they take on nothing new to operate, so the product had to be operable by
someone who did not write it. Logs carry the identifiers needed to follow one submission through,
with applicant material kept out, and every check leaves a line with its outcome, its reason code
and what it cost. That is where operability stops: no metrics endpoint, no alerting, no dashboard,
and a compliance service nobody is watching is one nobody can vouch for.

**What we would do next, in order.** Run a real accessibility review rather than an automated one,
the half of that requirement a machine cannot do for us; bound the memory a batch holds, the one
way a caller can still make this service fall over; instrument the batch timing, the one
requirement with no measurement at all; then widen the corpus, which firms up every accuracy
figure here.

## How the work was run

Every fork is recorded where it was decided, with what was rejected and why. The record is
`docs/decisions.md`, one numbered entry per fork, and it is what a line of code traces back to: a
module that exists because of an argument cites that argument's number in a comment beside the
code. Eighteen modules carry such a citation today, naming thirteen decisions — so the trace works
where somebody wrote it; no index guarantees it everywhere. What is guaranteed is the other
direction: a test walks every `docs/decisions.md#NNNN` reference in the repository and fails if
one names an entry that does not exist, so a citation cannot rot into a dead link when the code
around it moves.

**How a change gets released.** Versions follow the usual three-part convention; the running
service reads its own from the installed package rather than a constant in the source — that
constant went stale, still saying 0.1.0 after the release that cut 0.2.0, which made the one field
identifying a running build the one field that lied. The deploy builds from an export of the
committed revision rather than the working tree, so nothing uncommitted can reach the image.

**The pipeline gates the deploy.** Until one existed, seven browser tests failed unnoticed for
days; every push now runs the lint, the formatter, the types and the whole suite, and no job may
be allowed to fail — a test reads the pipeline file and fails if one is, because a job that cannot
fail the pipeline is the same defect as a test that cannot fail. `scripts/deploy.sh` reads that
verdict for the exact commit it is about to ship and refuses anything short of a pass, so a proven
commit and a deployed image are no longer two separate acts of remembering.

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
