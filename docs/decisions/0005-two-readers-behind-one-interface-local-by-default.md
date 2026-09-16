# 0005. Two readers behind one interface, local by default

Date: 2026-09-15

## Choice

Reading a label image into fields is one replaceable component behind one interface. Two readers
implement it:

- **A local CPU OCR engine, shipped in the app and used by default.** It needs no key and makes no
  outbound call, so a clone runs and checks labels out of the box, and the product works inside a
  network that blocks outbound traffic.
- **A hosted vision model, used when a key is present.** It is enabled by an environment variable.
  Where it is available it reads more accurately; where it is not, the product still works.

Neither reader decides anything. Rules decide; the reader only reports what it saw, with a
confidence, and the product says "needs review" where the reader is unsure.

**Open point.** Measured on 13 real labels on 2026-09-15, the hosted model returned the government
health warning word for word on 12 of 13, and the local engine with simple parsing on 6 of 13
(`docs/research/2026-09-15-extraction.md`). The warning must be checked exactly, so the local
reader's parsing has to close that gap, and the shipped accuracy figure is whatever the evaluation
run measures once it has.

## Alternatives rejected

- **Hosted model only.** Fastest to good accuracy, and it is what the measurement favours. It fails
  the brief's IT constraint outright: a product that cannot run without an outbound call cannot run
  in the environment it is for. It also makes a clone unusable without an account and a key.
- **Local engine only.** Fully self-contained, and it satisfies the firewall constraint completely.
  At 6 of 13 on the exact warning it does not yet meet the check the brief is most explicit about,
  and committing to it alone removes the evidence that a better reader exists.
- **Choosing the reader per request at run time, by content.** More moving parts to explain and to
  test, for an accuracy gain that has not been measured. The interface leaves it available later.

## Constraint that decided it

The brief's IT interview — outbound traffic is blocked to many domains, and an earlier pilot lost
features to blocked endpoints — together with the owner's instruction of 2026-09-15 that everything
be "contained within the app itself if possible to make installing simple". Decision 0003's
criterion 5 requires that the part calling an outside service be replaceable by one running inside
the agency's network without a rewrite.

## Evidence

`docs/research/2026-09-15-extraction.md`, measured 2026-09-15: hosted model 2.03 s median and 2.75 s
worst, one at a time, on 13 real applications; local CPU OCR 1.18 s median and 2.60 s worst. Per-field
accuracy for both is tabulated there.
