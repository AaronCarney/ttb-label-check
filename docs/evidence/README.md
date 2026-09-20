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

### `2026-09-20-five-second-both-faces-run1.json` and `-run2.json`

Two runs against the deployed service at `https://ttb.aaroncarney.me`,
minutes apart on 2026-09-20, each sending both faces of every corpus label the
way the page sends them. `summary` holds the figures the README quotes — checks
made, how many carried a back, how many finished inside five seconds, the median
and the slowest, and the counts of checks stopped early or answered out of the
cache. `rows` holds one entry per check with what came back, not only how long
it took, because a harness keeping the clock alone cannot tell a slow check from
a blank one. Produced by the deploy latency harness,
`TTB_DEPLOY_URL=<url> TTB_LATENCY_RECORD_DIR=<dir> uv run pytest
tests/test_deploy_healthz.py -k five_second`, whose record was copied here.
Cited by decision 0044, which is about the page taking the back of the label and
publishing what that cost.

### `2026-09-20-batch-latency-run1.json` and `-run2.json`

The two numbers a reviewer feels, measured twice over the same twelve corpus
labels, both faces each. `alone` is one submission at a time with nothing else
in the service — what a reviewer waits for after pressing check. `batch` is the
same twelve sent together, where the wait is the first result and then the gap
between results rather than the total. Both are timed from the `label-result`
event on `/batches/{id}/stream`, which is the event the page itself waits on.
`engine_total_duration_ms` is the service's own figure for the work, so the
queueing can be told apart from the reading.

Taken on the development box against a service started
`OCR_NUM_THREADS=4 nice -n 19 taskset -c 0-3 uv run uvicorn app.main:app --port
8123` — the shape the deployed service runs, on hardware about four times
faster. Only the comparison between the two numbers transfers; the seconds do
not. Produced by `nice -n 19 taskset -c 4-7 uv run python -m
tools.measure_batch_latency --labels 12 --out <path>`. Cited by decision 0047,
which is about leaving the read serialisation alone.

### `2026-09-20-read-scaling.json`

What reading two images at once would buy, measured before anything was built to
do it. A running copy reads one image at a time behind `_read_lock`
(`app/vision/local.py`), so the tool lifts that lock by calling `_read` directly
and measures the shapes the change could take against the reader as it is.
Three sections, each shape in its own process and repeated three times:

- `thread_ladder`: one read at one, two and four engine threads, with
  `cores_busy` — CPU seconds over wall seconds — saying how much of the machine
  a single read already uses, which decides whether there is anything left for a
  second read to take.
- `one_label_two_faces`: the reviewer's wait for one check, read serially
  against read at once.
- `twelve_faces`: throughput over a batch, for the serial reader, for one shared
  engine with the lock lifted, and for one engine per worker with the thread
  budget split. Each carries `slowest_image_seconds` and `rss_mb` beside the
  seconds per image, because the shapes that win on throughput lose on both.

Produced one shape per invocation, each in a fresh process:
`OCR_NUM_THREADS=4 nice -n 19 taskset -c 0-3 uv run python -m
tools.measure_read_scaling --images N --threads 4 --only '<shape>'`, which is
what the file's own `notes.how_it_was_produced` records. Cited by decision 0047.

## Re-measuring

Every run here reads the corpus in `tests/fixtures/labels/` and the
transcription in `tests/fixtures/labels/manifest.json`. The corpus is ground
truth and does not move, so a re-measurement is comparable to the run recorded
here. The two deployed runs need a deploy as well, and they measure the commit
that was live on the day: a later run on later code answers a different question
rather than checking this one. Local OCR runs under the six-thread budget the
project works to; a run at a different thread count gives different durations
and the same readings.

The three 2026-09-20 concurrency runs are the exception to the thread budget:
they are measurements *of* the thread count, so they run at the four threads the
service has and say so in the file. `2026-09-20-batch-latency-*.json` also takes
its twelve labels through the product's own sample pack rather than off disk,
and takes the first twelve by TTB ID because `GET /batches/sample.zip` draws its
labels at random and two runs asking for twelve would otherwise read two
different twelves.
