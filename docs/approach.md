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

**What the brief actually asks for is short, and most of what it says is not an ask.** It asks for
two things: a source repository carrying all the code, a README with setup and run instructions, and
brief documentation of approach, tools and assumptions; and a deployed URL where a working prototype
can be accessed and tested. It also asks that the app handle labels carrying information like the
one worked example it gives. Everything else is context, and reading it as a specification would
have been the first mistake available. The seven-element list arrives under the words "For
reference" and "common elements include", with the brief itself noting the exact requirements vary
by beverage type — which is why the regulations, and not that list, set the checks. The pointer to
ttb.gov is an encouragement to read. So is the suggestion to generate test labels, which we
declined for a reason given later. And the one wish about photographs shot at bad angles and in bad
light is marked out of scope by the person asking for it, in the same sentence. We treated each of
those as what it was, and the requirements came from elsewhere.

**We took the requirements from the interviews, not from the field list.** The list of seven label
elements is the only part of the brief that looks like a specification, and it says nothing about
speed, batches, error handling, or who uses this. The four people in the transcripts say all of it.
Every requirement we built against traces back to a person or a passage, and the one ask we met with
no requirement at all is recorded as such — so an ask nobody answered cannot later be mistaken for
one nobody noticed.

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

**We built the answer key before the thing it grades.** The labels were collected and transcribed the
day before there was an application to read them — 30 approved labels from the public register, each
with what it prints and the verdict each check should return — and the rule pack came before the code
that runs it. Writing the tests after the code is the usual order and it was the live alternative; it
produces tests that agree with the code, and a transcription of what a bottle actually prints does
not. The cost is that the key was written blind, and several entries in it had to be corrected once
real readings arrived — two of them settled by measuring the image rather than by eye.

## What we looked up before we chose

**We took each fact from the document that owns it.** The regulations came from the official
electronic code, the hosting limits and prices from each vendor's own documentation rather than a
summary of it, each recorded with the page and the day it was read, so a change in a vendor's terms
shows up as a difference rather than a surprise. What we could not confirm that way we wrote down as
unconfirmed rather than filling it in from general knowledge, and a marketing claim is marked as the
vendor's claim, not as a fact. Where a study rests on general knowledge instead of a live source, it
says so at the top. The rule cost us answers: the hosting study ends with a list of the questions it
could not settle.

**The reading corrected us before the code could.** The spirits alcohol tolerance we started from
was half the real one, and we had taken the 2022 rewrite of the labelling rules to cover all three
beverage types when it had left wine behind — wine still runs on text written in 1960. Either would
have shipped as a check that was confidently wrong about genuine labels, and neither would have
failed a test we wrote ourselves.

**The gaps we could not close, we designed around.** Most hosts, the one we deployed to among them,
do not publish how long it takes to wake a sleeping service, so the speed figures here come from
measuring the running deployment and not from a page. TTB puts every approved label on the public
record but serves them one at a time, with nothing to download in bulk, so each test label was found
and transcribed by hand. Widening the corpus, the work that would firm up every accuracy figure
here, is bounded by that hand work and not by permission.

**What we inferred about the four people is marked as inferred.** Their words and their roles are on
the record; what they want, and what would make them refuse to adopt this, is our reading, labelled
as ours wherever the design leans on it.

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

**Part of the regulation is a standard, not a measurement.** Several requirements are written as a
test a person applies rather than a figure a machine can compare: an import's origin marking counts
if an abbreviation unmistakably indicates the country, the warning has to stand separate and apart
from the rest of the label, mandatory wording has to be readily legible, and the words of a spirits
designation have to be similarly conspicuous. Nothing lists which abbreviations qualify, or how far
apart is apart. We could have picked a number for each and shipped it as the rule — the version that
demonstrates as complete — and did not, because a threshold we invented would be applied to a real
producer as though the regulation said it. So each goes to a person: the origin check reads the
country's plain English name, passes on a match, and sends every other form to review rather than
rejecting it. That costs coverage, not correctness — a compliant Spanish-marked import lands in the
reviewer's pile, which is work rather than a wrong answer. The check still rejects a label carrying
no origin statement at all, because an absence is a fact rather than a judgement.

**Two sets of requirements are not covered at all, and were not on the record as choices.** The rule
that the warning's letters must not be so compressed that it stops being legible has no entry
anywhere. Neither do the legibility, separateness, conspicuousness and minimum-type-height
requirements the wine, spirits and malt parts place on a label's mandatory wording — the regulation
texts we pulled carry all of them, and no check and no limitation names one. Most would have ended
where the rules above did, with a person or switched off, so no verdict is wrong because of this.
What is wrong is the record: a requirement we decided not to check and one we never noticed look
identical from outside, and only the first was written down. We found these while writing this
account, and name them rather than leave the list looking complete.

**The regulation that governs the product itself.** Nothing in the brief asks for accessibility, but a
federal application is bound by Section 508 regardless, and that standard is binding regulation
rather than agency policy. We built to the level it makes binding, WCAG 2.0 A and AA, and the check
page, the result page and the batch-list page are all scanned against it automatically on each run,
which is every screen the product serves. **The scan is built not to flatter us:** a check the
scanner cannot decide fails it rather than passing, so an undecidable result cannot read as a clean
one. One check stands as reviewed rather than decided — the empty batch table renders column headers
with no rows beneath them — and the reasoning sits beside the test.

Sharpening that scan kept turning up real defects. Six result-page cases once reported text whose
colour contrast sat below the AA threshold; the test that holds the layout to a 320-pixel viewport
once failed on a 27-pixel overflow; and widening the scan to measure every visible button, hovered
as well as at rest, caught three painting white text on a white or near-white background. Tracing
their cause found two more the scan cannot reach, both behind a development-only flag. All were
ours and all are fixed. The last five shared one cause: a base stylesheet set a button's background
and its text colour in the same rule, so a component that overrode only the background kept a white
label it never asked for. So the claim we can make is that we built the mechanism and, on every
page the product serves, met the part of the standard a machine can judge. Section 508 asks for a
conformance review as well as an automated scan, and that review has not been run. A disposition is
never carried by colour alone, which has its own passing test. We stopped short of claiming a newer conformance level for a different reason: of the two criteria
that would have justified one, axe-core runs no rule for either at the tags this gate requests, and
for one of them it has no rule at any tag at all. A claim the product cannot test is the kind of promise this build refuses to
make anywhere else.

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
  prototype keeps two things for seven days: an uploaded image, so a result page survives a restart,
  and every check's result, so a reviewer can overrule a finding on it. That second one used to
  restate what the application declared, the applicant's name and address included; it no longer
  does. Every value it read and every value the application declared is blanked before the file is
  written, and what stays is what an override amends — the dispositions, the citations, the reason
  codes and the trail. Seven days is still a convenience rather than a retention policy, and a real
  deployment needs a period set by the agency's records schedule rather than by a constant in the
  code. Our own requirements say the product should keep nothing; two files on disk is not nothing,
  so we left the requirement standing rather than quietly lowering the bar to what we built.

**The agency's own plumbing.** The IT interview sets three constraints and none is negotiable: no
integration with TTB's existing systems, outbound traffic blocked at the firewall, and nothing new to
operate. They decided the architecture more than any preference did. No integration means the
application's values arrive with the submission and there is no database anywhere in the product.
Blocked outbound traffic is why the default reader ships its own models, needs no key, and makes no
network call. Nothing new to operate is why a clone and the deployed service are the same
application, and why the app holds no state a restart cannot rebuild.

**What it costs to run.** Cost was our last criterion on purpose — it cannot buy back a failure on
any of the others. Two choices here were free, and each gave up something different.

The default reader is free because it costs processor time rather than money: no per-call charge, no
account, and it runs where outbound traffic is blocked. What it gave up is accuracy on hard images —
the display-type and split-box limits named under what we can prove are the price of that choice,
not incidental defects. The hosted alternative would run a few hundred dollars a year of inference
at TTB's volume, computed from published rates rather than measured by us, and the money is not why
it is off: it is off because a reviewer must be able to clone this and run it without an account,
and because the firewall the brief describes would refuse the call anyway.

The deployment is free because it moved from a nine-dollar monthly plan into a free tier, and what
that gave up is a brake on the bill. The allowance is 180,000 processor-seconds a month, which at
the service's four cores is twelve and a half hours of request handling, or roughly 38,000 label
checks at the reader's measured 1.18-second median. TTB's 150,000 applications a year is about
12,500 a month, so on volume alone the allowance covers the agency about three times over; what it
does not cover is a peak-season burst, because each running copy reads one label at a time and
hundreds filed at once queue rather than fan out. The real exposure is not the meter but the
absence of a stop: the provider's budgets alert rather than cut off, so what bounds the bill is the
invoker check, which refuses every caller but our own front door before a request is billed, the
two-instance cap and the request timeout. The rate limit at the edge denies nothing, measured, and
is left in place inert. Storage is the one
line that is not zero — the image exceeds the half-gigabyte grant, at ten cents per gigabyte per
month — and it is small change rather than nothing.

Every one of those is a figure a reviewer can check rather than a claim that the choice was costless.

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
turn that into verdicts. We built a layer that sent finished results to a language model for a second opinion, and then
deleted it — 644 lines of subsystem and about twenty test files, reaching into eighteen more — because a compliance verdict a
model can influence cannot be defended to the person who has to sign it. What the deletion buys is
the property the product is sold on: the same label and the same application give the same answer
every time, with a citation attached. What it costs is every capability that needs judgement beyond a
scored comparison. Those go to a person, which is the same answer the senior agent gave.

**Nothing we depend on can move under us quietly.** The reader that runs by default sits inside the
application, so there is no vendor who can change it. The optional hosted reader names a dated
snapshot of the model rather than the name that follows whatever the vendor shipped last, and the
prompt it sends carries its own version; the recorded answers the tests replay are filed under that
snapshot, so moving to a new model leaves the tests with nothing to replay and says so. A vendor's
upgrade is then a change someone makes deliberately and re-proves, rather than a day when the same
label starts giving a different verdict.

**Every seam is there because something outside the code forced it.** The reader sits behind an
interface with two implementations because the agency's outbound traffic is blocked: the one that
ships has to run with no key and no network call, and the one that reads harder images has to be
replaceable by something inside the agency's own boundary without a rewrite. The uploaded image is a
file on disk rather than something held in the process because the clone a reviewer runs and the
deployed container are the same application, and a directory of files is the only store that needs no
account, no service and no configuration. Every check's result sits beside it for the same reason
and on the same sweep, because an override arriving after the batch that held it has been dropped
needs something to amend. We added no seam for elegance, and the seam we have not
built is named as missing: no rule can yet say "this applies whatever the beverage is", which is why a
label filed with no application is read and not checked.

**Rules are data, not code.** Every check is an entry naming the regulation section it enforces, and
the build fails if a check tries to carry that citation in code instead. A compliance officer can
read what the app checks without reading a programming language, and a regulation change is an edit
to data rather than a release.

**Three outcomes, and the third is a real answer.** Pass, fail, and needs review. Needs review is
used wherever the app can see an element but cannot honestly settle it, and it is the destination for
every uncertainty rather than a fallback. Each result carries what was read, the application's value
beside it, the rules that ran with their citations, and a confidence level, laid out next to the
label image itself, so a reviewer checks the answer against the label rather than trusting it. The
reading also records which part of the image it came from, and the interface deliberately does not
draw that region on the label: the box is measured in the frame the reader worked in, which is the
photograph after it has been shrunk to fit and sometimes turned upright, not the photograph the page
shows. A box drawn from it would point confidently at the wrong place. Finding the spot on the label
is still the reviewer's own work.

**The regulation itself is in the product, and it was not typed in.** A finding's citation opens a
column beside it holding the wording of the section — reserved, so it fills in place rather than
covering the finding it explains, and reached from a chip that is a button so keyboard and pointer
reach it alike. We had refused this once (`docs/decisions.md#0034`): the rules name 43 citations and
the product held the wording of one, and filling the rest meant typing regulation text into a
compliance tool with no test that could check it. What changed is that the eCFR publishes an API
this machine can reach, so the wording is fetched from the government's own copy, committed with its
issue date and a hash, and re-checked against that copy by a test.

The part the API did not solve is the part that shaped the work. Our rules cite in prose —
`27 CFR §4.32(a)(1), §4.33`, `27 CFR §5 Subpart I`, `27 CFR §4.35(e), 19 CFR §134.45` — and the eCFR
is addressed by title, part and section, so something has to read one into the other. 0034 had
rejected linking the chips for exactly this: heterogeneous strings "would mislink some, and a
compliance tool showing the wrong regulation is worse than one showing none". So the parser refuses
rather than guesses. A citation it cannot read whole yields nothing and the panel says the text is
not held; a reference it cannot cover fails the whole string rather than showing the reviewer the
parts that parsed, which would tell them the rule rests on less than it does. Every shape the rule
pack uses is asserted against the sections a reader of that string would turn to, and ten strings
that invite a guess are asserted to yield nothing (`docs/decisions.md#0046`).

**Whether the record would answer a producer who contests a rejection.** It would not, and that is
worth saying because everything above makes it sound as though it would. What survives is short —
a check's result keeps for seven days so an override has something to amend, and then it is
gone. What survives is also emptied on purpose: to keep no applicant material on disk, the kept copy
blanks the value read off the artwork and the value the application declared, so it records that a
field was rejected without recording what it said. That is the right privacy answer and it makes the
kept copy useless as evidence — the two goals are in real conflict here, and we chose privacy. What survives is half-labelled: the trail attached to each verdict now names the rule set that
produced it, by version and content hash, but it names the reader not at all — so a kept copy can
say which rules judged that label and not what read it. The full record is in the result page's
own source, but the interface offers no save, no print and no download, and the drawer that would
display it is a developer's switch that is off by default — so getting the record means calling the
service directly, which a developer does and a reviewing agent does not. Every rule that fired on an
element is counted into that element's verdict and every citation is shown, but only the first
finding's explanation is written out, so a label failing the fifth of the warning's seven rules says
so without saying which one. And an override carries a made-up session number rather than a name,
because nothing signs anyone in.

**That gap is the cost of keeping almost nothing, and closing it is not a coding problem.** The same
constraint that makes this safe to run — no database, two directories of files that empty themselves
after a week, almost nothing for a privacy reviewer to ask about — is what leaves a contested
rejection with no record to answer it. A
deployment that must stand behind its verdicts needs three things we did not build: a retention
period set by the agency's records schedule, a sign-in so an override names a person, and real
versions on the trail. We would rather name the gap than fit a cheap version of it: a record that filled the reader's name
with a placeholder would be worse than no record, because it would look like evidence.

**We designed around the error that costs more.** A false rejection sends a compliant applicant back
round a process that takes weeks, and it is the error that would end a pilot. A false pass is caught
downstream by the agent, who rules on every finding anyway. That asymmetry is why anything
unmeasurable goes to review rather than to rejection.

**The numbers, and which of them we can defend.** Three numbers shape this product and they are not
equally well founded. The
tolerance that lets a net contents figure in millilitres match one in fluid ounces is one percent,
derived rather than picked: above the 0.633 percent that rounding needs across every container size
the regulations authorise, below the 1.216 percent at which an authorised size stops being
distinguishable from the customary figure printed for the size next to it — and a test recomputes
both bounds on every run, so the number cannot drift from its reason. One label at a time per
running copy is a choice about the machine rather than a measured threshold: a read is sized to use
all four of the service's processor cores, so a second read beside it would compete with the first
rather than add to it.
The brand-matching thresholds — 0.92 to pass, 0.85 to send to a person — rest on published
record-matching work and on an argument about which error costs more, not on this project's own
labels. That is the weaker evidence, and we would rather say so than present all three as equally
settled.

Each of the three breaks differently in each direction, and each would be re-tuned differently.
Tighten the tolerance and a compliant metric label mismatches on rounding alone; loosen it and an
authorised container size passes as the size next to it — so re-tuning it is not a judgement call
but a recomputation from the authorised-sizes table, which the test already does. Raise the one
label at a time and the slowest five percent degrades the way the measurement showed; it cannot go
below one, so the only direction is worse, and re-tuning means re-measuring on the core count the
deployment actually has, because the figure is a property of the processor rather than of the code.
Raise the brand thresholds and punctuation differences start going to a person, which is work
without a finding; lower them and a genuinely different brand passes, which is the error this
product cannot have — and re-tuning them needs the corpus sweep the next paragraph describes.

Three more numbers are set and are not thresholds anybody tuned. The four upload caps are derived,
and the derivation for each sits beside it in the code, as described above. The seven-day retention
window is a convenience, named as one, and a real deployment takes its period from the agency's
records schedule instead. The 1600-pixel long edge the reader downscales to before reading is the
one of the three that could cost accuracy, and nothing here measures what it costs.

**A larger set of numbers has no recorded reason at all.** The bands that turn a confidence score
into low, medium or high. The confidence floor each rule demands before returning a verdict. The
per-field multipliers for how sure the reader is it picked the right text — a note explains why a
field found by a text pattern keeps more confidence than one found by type size, but nothing
explains why the figure is 0.75 rather than 0.8. Both surviving image-quality gates. And the
stroke-width ratio deciding whether the warning's heading is bold, which matters most, because the
code says it is uncalibrated and it still drives a rule that can reject a label. Being wrong here is
not symmetrical — too strict sends compliant labels to a person, too loose lets a doubtful one reach
the agent who is reading it anyway — which is why they were safe to ship unargued, and is no reason
to leave them so. Re-tuning every one needs the same thing: a wider corpus of real labels with a
human verdict on each, swept against the thresholds. That has not been done.

**One label is checked first, then the rest run behind it.** The reviewer gets a real result in
seconds instead of a progress bar, and starts working while the remainder runs. The batch then paces
itself against how fast they are actually reading, rather than racing ahead to compute results nobody
has asked for. Measured over twelve labels on the development box, that is
what a batch buys and it is all it buys: the first result lands at 1.49 seconds, about what one
label costs on its own, and the rest arrive roughly 1.12 seconds apart. Per label a batch is no
dearer than a check alone — 1.16 seconds against 1.23 — and the engine's own time per label is the
same either way, 1164 ms alone against 1179 ms inside the batch. A batch is a queue of the same
work rather than a cheaper way to do it, and what it buys a reviewer is starting after one label
instead of after twelve (`docs/evidence/2026-09-20-batch-latency-run1.json`; the seconds belong to
that box, not to the deployed service).

**What it refuses to take.** An upload is identified by its own first bytes, and anything that is
not a PNG or a JPEG is turned away before the reader sees it; what the browser declares the file to
be is never consulted, because that is whatever the client chose to send. An image the app hands
back later can only be asked for by a restricted set of characters, so no request can name a path
outside the store. One bad file in a batch is refused by name and every other file still runs —
ending a 300-label submission because one was a spreadsheet would punish the reviewer for the
uploader's mistake. Size and count are bounded as well, and every bound is checked before the bytes
behind it are read: 31.5 MB in one request, 1.5 MB for any single image, 100 images in a batch, and a
refusal for any image whose header declares more than fifty million pixels — the decompression bomb
that no byte cap catches, since a few kilobytes of PNG can declare a canvas of fifty thousand pixels
square. Each number is derived rather than picked, and the file that defines them states the
derivation beside each one: the request cap sits under the host's own body limit, so a refusal comes
from this service naming the file that was too big rather than from the platform naming nothing, and
the per-image cap is TTB's own, since COLAs Online refuses a label image over 1.5 MB and nothing
larger can ever have been filed. A batch refused for size names every file that caused it, not the
first alone.
The hundred-image count is worth reading next to the request cap rather than on its own, because the
two only agree while the images are small: a hundred files fit one request only if they average under
322.3 KB. At the 1.5 MB per-image cap 20 fit, at the largest label in our own corpus — 547 KB — 59,
and at the corpus median of about 184 KB all hundred. So the count is a fairness limit and the bytes
are the real one, and a reviewer sending a hundred large files is refused by the request cap with
every offending file named. `files_that_fit()` in `app/api/limits.py` derives those numbers from the
caps; this paragraph does not carry its own arithmetic.
Memory is bounded by one batch. The service checks one batch at a time and refuses a second while
the first runs, keeps a finished batch only until the next one starts, and lets go of each image
once its label is checked, so what it holds at once is one upload, shrinking as it is checked. There
is no login, so the limit is per running copy of the service rather than per person: whoever uploads
while a batch runs is told how far it has got and asked to wait (`docs/decisions.md#0041`).

**What a log is allowed to contain.** Logging is an allow-list rather than a filter: a line carries
only the fields named in advance, anything else attached is dropped without comment, and the fields
that could hold applicant material — the application's contents, the image bytes, the text read off
the label — are blanked by a second pass. Both halves have tests. What the allow-list does not
govern is a line's message text, which the formatter writes before the allow-list runs, so the
discipline it enforces is that nothing carrying applicant material may reach a message at all. One
thing did. The name of the file the uploader sent was also the identifier every line correlated on,
so an uploader who named a file after a person put that person in the log — the allow-list had been
built to make exactly that impossible, and a string that was on it by design walked around it. The
two are now separated by what they are for: the filename is display text that reaches the page and
the refusal sentence, and the identifier a line correlates on is minted by the app. The test that
holds it runs a person-named file through both the refusal path and the ordinary path and reads
what the real handler emits.

## Tools, and why each

Plain Python for the service. No other language was weighed, and that is the honest account: the
reading and rules libraries live in Python, so any other choice would have put a foreign-function
call under the one component whose accuracy the whole product rests on, and the brief's priority is
a working core rather than a novel stack. A conventional server-rendered interface with
a small interactive layer, rather than a full client-side application, because the parts that need
real interactivity are few — the keyboard path an agent uses to overrule a finding, and the batch
page that fills in as each result streams back — and requiring a build step on the reviewer's
machine is a barrier to running this at all. No database: a directory of files beat both an embedded database, which
answers no question the files do not, and object storage, which needs an account, a key and an
outbound call the clone cannot make. A processor-only reader that ships with the code, over a
design that only calls a hosted model — which cannot run where this product is for — and over
picking a reader per image at run time, which adds moving parts for an accuracy gain nobody has
measured. A container as the unit of deployment, over the cheaper runtimes that are not containers:
the edge-worker tier we costed runs under WebAssembly and caps processor time at ten milliseconds a
request, which a reader that takes two seconds cannot use at any price. The container also means the
clone and the deployed service are the same thing.

## What we can prove, and what we cannot

**Our answer key is real labels.** We assembled 30 approved labels from TTB's public registry across
all three beverage types, 14 of them imports, plus 8 deliberately flawed variants. The brief suggested
generating test labels; we used real ones because a generated label proves the reader can read what
we drew, and a real one proves it can read what a producer actually printed. Each carries a
transcription of what it prints and the expected result for each check, so the key is independent of
the reader being tested.

**The same corpus is what a reviewer downloads, and it is meant to be run rather than read
about.** `/batches/sample.zip` ships ten of those thirty labels at random, both faces of each where
both were filed, and `applications.csv` beside them carrying the application really filed for each
one. Unzipped and dropped whole into the batch form, it exercises the product's actual claim —
every label checked against its own application — rather than a demonstration of it. What the pack
puts in front of a reviewer, from the thirty it draws on:

- **All three beverage types in one batch**, which is why a row's own `beverage_type` overrides the
  form's single select: fourteen distilled spirits, eight wines and eight malt beverages, each
  judged by the rule pack for its own class.
- **Labels that are more than one photograph.** Twenty-six of the thirty were filed with a back, and
  twenty of them print their GOVERNMENT WARNING there. A batch that read fronts only would fail the
  warning check on labels that carry it, so pairing the faces is not a convenience — it is the
  difference between the corpus passing and the corpus failing.
- **Passes that are not literal matches**, which is most of what a reviewer's judgement is spent on:
  a label printing `CHARDONNAY` against an application declaring `TABLE WHITE WINE`, a brand matched
  on the fanciful name the same application declares, two differently worded quantities reduced to
  one figure.
- **The country-of-origin check actually running**, because fourteen of the thirty are imports and
  the check does not apply to the rest.
- **What the product refuses to decide.** A label whose photographs do not show a bottler's name and
  address comes back as *"The reader did not find a name and address on this label, so this check
  was not made"* — not as a finding that the label lacks it. That distinction is the product's
  central honesty and the pack demonstrates it on a real label.

**Eight deliberately flawed variants are not in the pack, and that is deliberate.** They are real
labels with one thing altered — one word of a GOVERNMENT WARNING repainted from *impairs* to *may
impair*, a warning heading dropped into title case, an application's alcohol content set to 45%
where the label prints 40% — and they exist in the test corpus to prove the checks can fail. What
ships in the batch pack is thirty approved labels, because a demonstration built out of planted
failures proves the plant rather than the product. Nothing in the app offers a variant to click:
they live in the repository, under `tests/fixtures/labels/`, and the tests are what exercise them. A
reviewer holding the pack who wants to watch a check fail has the honest version of the same thing
available — change one value in `applications.csv` and re-upload, which is exactly the mismatch
between a filing and a label that this product exists to catch.

**That corpus caught four failures that unit tests called green.** A class-and-type rule that failed
thirteen genuinely approved labels. A format check that matched a string it had built itself. An
image-quality gate that rejected seven faces of five perfectly readable labels and was right about
none. A tolerance rule that could never report a match for any label, because the second figure it
compared against comes from a laboratory and this app never sees one. Every one was found by running
the product against real labels, which is the argument for having the corpus at all.

**We publish reading accuracy as counts, not percentages.** Thirty of thirty on the warning being
present, twenty of thirty on it being word for word, seventeen of thirty on brand. A percentage drawn
from thirty labels reads as a precision this corpus does not carry. The figures are not flattering
and they are the honest state of a processor-only reader on display typefaces.

**The five-second requirement is measured on the deployed service, and it is missed.** It belongs
to the deployed hardware, so we measure it there rather than on a developer's machine. Measured
2026-09-20, with both faces of each label: 18 of 37 checks inside five seconds in one run and 21 of
37 in a second run minutes later, against a requirement of 95 percent. Medians of 5.01 and 4.38
seconds; slowest 9.01. Nothing was stopped early and nothing came out of the cache in either run,
so these are slow checks rather than blank ones.

**The cost is the second face, and it bought a correct answer.** Until 2026-09-19 the page took one
image, and the same set measured 35 of 37 inside five seconds — but the government warning is on
the back of 20 of the 30 corpus labels, so those fast answers reported a warning missing that the
label carries. The page now takes a front and a back, the faces are read one after another, and the
submissions carrying a back came in at a median of 5.55 and 4.95 seconds against 2.39 and 2.74 for
the four that have only a front. We took the trade knowingly and we publish the number it cost.

**Reading the faces concurrently was the untried lever, and it has now been tried on the bench
rather than in the product.** A running copy holds one reader and takes one image at a time behind a
lock, so the change is lifting that lock and not merely asking for both faces together; we measured
each shape it could take, in-process at the four threads the service runs, before building any of
it. The cores turn out to be spoken for already. A single read keeps 3.69 of 4 cores busy, and the
thread ladder says why: 1.198, 0.693 and 0.535 seconds per image at one, two and four engine
threads is close to linear, so four cores are genuinely working and nothing is idle for a second
read to take. Read at once, one label's two faces took 1.60 seconds where reading them in turn took
1.38, and kept only 2.4 cores busy against 3.74 — the Python half of a read does not run alongside
itself, so the concurrent shape loses more to contention than it wins. For the one check a reviewer
is waiting on, the lever lengthens the wait it was meant to shorten, by about 16 percent.

**Over a queue the sign flips, and the price is what decided it.** Twelve faces cost 0.535 seconds per
image as built, 0.475 with two engines of two threads and 0.450 with four engines of one — 11 to 16
percent better. The slowest single image goes from 1.10 seconds to 1.92 and then 3.45, and resident
memory from 658 MB to 911 and 1267 MB against the service's 4 GiB. That is throughput bought with
the wait of whichever label a reviewer happens to be watching, and with the headroom of a 4 GiB
instance. The smallest version of the change is the worst of the lot: lifting the lock and leaving
one shared engine gave 0.734 seconds per image, 37 percent worse than doing nothing. So the
serialisation stays ([decision 0047](decisions.md#0047)), and the shapes compare on this box even
though the seconds do not compare to the deployed service
(`docs/evidence/2026-09-20-read-scaling.json`).

**Three levers have been tried now, and none of them closes the requirement.** More processor
cores moved one check of thirty-eight. Reading both faces at once costs the single check more than
it saves. The reading path itself has been tuned three times — most recently by reading a label's
sideways strips before reading the whole label again, which took the slowest corpus read from
1345 ms to 463 ms on the development box ([decision 0036](decisions.md#0036)). Earlier published
shares of 87, 89, 71 and 92 percent stand as history only: they predate that tuning and a harness
that could not tell a check the evaluation guard had blanked from a slow one
([decision 0035](decisions.md#0035)).

**Two things we did not prove.** A reader cannot tell an unmeasured claim from a measured one by
looking, so each is named:

- The ten-minute target for a 300-label batch has no instrument at all — no test and no figure.
- Accessibility past what a machine can check. The automated scan now covers all three screens and
  the batch table both empty and populated. Whether it passes is the result of a run rather than a
  property of the build, and the last run we made was green. One check axe cannot decide by itself
  is recorded with the review that settled it rather than discarded, so an undecidable check no
  longer reads as a pass. The manual review the requirement really asks for has not been run, and
  an automated pass is the floor of an accessibility claim rather than the whole of one.

The first is a missing measurement. The second is a limit on the proof rather than a gap in the
build: the requirement was written, the mechanism was built, the half a machine can check is met,
and the half that needs a person is the half a week-long build ran out of time for.

## What changed, and what would change next

**The deploy host moved, and not for the reason it looks like.** We first put the service on a
fixed-price host at nine dollars a month, on one argument: a public demo URL is open to anyone, so the
cost had to be bounded by a plan rather than by traffic, and we had no way to bound a
pay-per-use host. We later moved to a pay-per-use service. No fact had changed and the nine-dollar
figure still stood. What changed is that a mechanism appeared — we already had our own domain, and a
proxy in front of the service could carry a rate limit. With the meter bounded at the edge, the plan
fee bought nothing the free tier did not already give. The constraint never moved; the instrument
that satisfied it did. Deployed, the rate limit turned out to deny nothing, and what bounds the meter
is the other half of that proxy: the service answers no caller but it, and a request it refuses is
never billed.

**We corrected a requirement rather than the code.** Our specification said a brand differing only in
punctuation should go to a reviewer. TTB's own form permits punctuation changes with no new approval,
and the research behind the requirement contradicted itself. "Stones Throw" against "Stone's Throw"
is exactly the case the senior agent complains about by name. So we amended the requirement and
logged the change, rather than making the product do the wrong thing consistently.

**We stopped explaining the product inside the product.** The landing page had carried four
curated labels as buttons, each with a sentence saying what checking it would show, and the batch
page had offered a starter pack of images with no applications. Two things were wrong with that. The
smaller: one of those sentences asserted an outcome the engine explicitly refuses to assert, telling
a reader that a beer's photographs show no bottler's name and address *"and the check says so"*,
where the check says only that it could not make the finding — so the tour contradicted the product
it was touring. The larger: a demo is only worth anything if it is the product with data supplied,
and a page of curated buttons is a different artifact from the one an agency would run. So the
buttons and their sentences are gone, the sample pack carries the applications too, and the
demonstration is now a reviewer unzipping that pack into the same form their own labels go through.
What the sentences explained lives here and in `README.md`, which is where a reader can be told
things the product itself has no business claiming.

**We deleted work that could not earn its place.** The second-opinion layer described above. An
image-quality gate that turned out to be measuring how light the label stock is. A rule that could
never pass, deleted — while a different rule in a similar state was switched off instead, because one
was unbuildable and the other merely unbuilt.

**Who would run it, and what they would watch.** The agency's own IT would, and their interview was
explicit that they take on nothing new to operate — so the product had to be operable by someone who
did not write it. One readiness check answers whether the service is up and doubles as the warm-up
that loads the reading models, so a copy that cannot load them announces itself as not ready rather
than failing the first real label. Logs carry the identifiers needed to follow one submission
through, with applicant material kept out, and every check leaves one line with its outcome, the
reason code behind it and what it cost. That is where the operability stops: nobody is told when
those lines go wrong — no metrics endpoint, no alerting, no dashboard — and nothing records what the
service did beyond those lines and the results it keeps for a week so an override has
something to amend. An operator can find out whether it is right only by reading the logs. Those are prerequisites before this ran inside the agency, not improvements: a compliance
service nobody is watching is one nobody can vouch for. What bounds the cost is the invoker check,
which refuses every caller but our own front door before a request is billed, and the two-instance
cap. The rate limit at the edge denies nothing — measured on the deployed service rather than
inferred from the code, and recorded in `edge/src/index.js` beside the call — and is left in place
inert.

**What we would do next, in order.** Run a real accessibility review rather than an automated one,
which is the half of that requirement a machine cannot do for us; bound the memory a batch holds,
which is the one way a caller can still make this service fall over; instrument the batch timing,
which is the one requirement with no measurement at all; then widen the corpus, which is the work
that makes every figure above more trustworthy.

## How the work was run

Every fork is recorded where it was decided, with what was rejected and what settled it. The record
is `docs/decisions.md`, one numbered entry per fork, and it is how a line of code traces back to its
reason: a module that exists because of an argument cites that argument's number in a comment beside
the code it explains, and a check names the regulation section it enforces in the rule file rather
than in code. Eighteen modules carry such a citation today, naming thirteen decisions, alongside the
requirement ids the same comments use — so the trace works where somebody wrote it and there is no
index that guarantees it everywhere. What is guaranteed is the other direction: a test walks every
`docs/decisions.md#NNNN` reference in the repository and fails if one names an entry that does not
exist, so a citation cannot rot into a dead link even when the code around it moves.

That record governs nothing on purpose — it says why, and anything meant to bind future work goes
into the requirements or the rules instead. A decision that was later reversed is marked and left
standing rather than edited away, so the host reversal above can be read as it happened rather than
as it was later rationalised.

Where a convention could be replaced by a check, we replaced it. The README's own claims are tested:
every document path it names must resolve, and its accuracy section is forbidden from containing a
percentage. The rule set fails the build if a rule has no implementation. Each of those started as a
convention somebody broke.

**How a change gets released.** Versions follow the usual three-part convention, and the running
service reads its own from the installed package rather than a constant in the source — the constant
went stale, still saying 0.1.0 after the release that cut 0.2.0, which made the one field
identifying a running build the one field that lied. A changelog records each release, and there is
one tagged release so far. The deploy builds from an export of the committed revision rather than
the working tree, so nothing uncommitted on a developer's machine can reach the image, and it runs
five checks first: the container file is present, the port the service is told to use is the one the
container opens, the built interface bundle is committed, every path the build copies exists, and
the working tree is clean. Every push runs the rest. Until a pipeline existed the suite ran only
when somebody typed the command, which is how seven browser tests failed unnoticed for days; the
pipeline now runs the three commands the README documents — lint, formatting, types — and then the
whole suite on an image that installs pnpm and Playwright, so the browser group actually runs
instead of skipping itself green. No job may be allowed to fail, and a test reads the pipeline file
and fails if one is, because a job that cannot fail the pipeline is the same defect as a test that
cannot fail. Origin is GitLab and that is where it runs; the GitHub remote is a mirror and runs
nothing. The pipeline also gates the deploy. `scripts/deploy.sh` reads GitLab for the pipeline
belonging to the exact commit it is about to ship and refuses unless that pipeline says `success`: a
commit that was never pushed has no pipeline and is refused, one still running is refused, and one
that failed is refused. `TTB_SKIP_PIPELINE_CHECK=1` is the escape hatch for a deploy that has to go
out while GitLab is unreachable, and it prints on the terminal that nothing has tested what is being
shipped. So a proven commit and a deployed image are no longer two separate acts of remembering;
what is still a person's own act is typing the deploy command at all.

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
