# Measurement evidence

A decision in `docs/decisions.md` that rests on a measurement has to let a
reviewer check the measurement, not just read the conclusion drawn from it.
Where the measurement is a one-off run over the corpus or against the deployed
service, it cannot be re-derived from the repository alone — re-running it costs
OCR passes over 62 images, or a deploy. This folder holds those runs.

Nothing else belongs here. A number a test asserts is evidence the test carries,
and it needs no file. A number that is going to change belongs in the code that
produces it.

## What is here

### `2026-09-17-live-timing.json`

Twelve submissions against the deployed service at `https://ttb.aaroncarney.me`,
commit `8cb5e70`. `rows` carries one entry per submission with
the end-to-end duration the caller saw. Cited by decision 0035, which is about
what a check that runs long returns.

### `2026-09-17-screen-corpus.json`

One row for each of the 62 corpus images, measured on the development box
under the six-thread OCR budget. Each row records what a
recognition-only strip screen decides about the image (`gate`, `n_tall`,
`screen_ms`, `strips`) against what the full two-angle re-read actually finds
(`reread`), so the screen can be judged against the pass it would replace.
Cited by decision 0036, which is about screening the sideways re-read by reading
the strips rather than by their shape alone.

### `2026-09-17-line-flip.json`

The measurements behind decision 0039, which is about how sure the reader's
0/180 line classifier must be before it turns a line upside down, and about
removing spacing from the government warning comparison. Development box,
six-thread OCR budget. It holds:

- `threshold_by_face`: nine faces read at classifier thresholds 0.9, 0.95,
  0.99 and 0.999 and with the classifier off, each with how far its warning
  reading is from the §16.21 text.
- `fields_changed_by_strict_threshold`: the class and type and the name and
  address the reader returns at 0.9 and at 0.999, for the two labels where
  that field moved to review.
- `reader_options`: the warning face of all 38 labels read six other ways
  (cropped and enlarged, each line re-read with three recognition models),
  with the text each returned and whether it matches.
- `timing_interleaved`: the reader's time per face at 0.9 and at 0.999,
  alternated in one process over 32 faces so machine load falls on both alike.
- `sweeps`: all 38 labels through the real route, both faces sent, at the
  commit before the change, with the threshold alone, with the classifier off,
  and at the change itself. Each row is the verdict and every finding that did
  not pass.

## Re-measuring

All three runs read the corpus in `tests/fixtures/labels/` and the transcription in
`tests/fixtures/labels/manifest.json`. The corpus is ground truth and does not
move, so a re-measurement is comparable to the run recorded here. Local OCR runs
under the six-thread budget the project works to; a run at a different thread
count gives different durations and the same readings.
