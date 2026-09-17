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
commit `8cb5e70`, on 2026-09-17. `rows` carries one entry per submission with
the end-to-end duration the caller saw. Cited by decision 0035, which is about
what a check that runs long returns.

### `2026-09-17-screen-corpus.json`

One row for each of the 62 corpus images, measured on the development box on
2026-09-17 under the six-thread OCR budget. Each row records what a
recognition-only strip screen decides about the image (`gate`, `n_tall`,
`screen_ms`, `strips`) against what the full two-angle re-read actually finds
(`reread`), so the screen can be judged against the pass it would replace.
Cited by decision 0036, which is about screening the sideways re-read by reading
the strips rather than by their shape alone.

## Re-measuring

Both runs read the corpus in `tests/fixtures/labels/` and the transcription in
`tests/fixtures/labels/manifest.json`. The corpus is ground truth and does not
move, so a re-measurement is comparable to the run recorded here. Local OCR runs
under the six-thread budget the project works to; a run at a different thread
count gives different durations and the same readings.
