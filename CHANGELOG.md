# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A label is read on this machine, with no outbound call, and that reader is the default. A second
  reader using a vision model sits behind the same interface. See `docs/decisions/0005`.
- The reader's accuracy is scored against the real labels and their recorded ground truth.
- Every declared element of an application — brand name, class and type, alcohol content, net
  contents, name and address, country of origin, and the health warning — is compared against what
  the label says, and each comparison states what counts as the same value.
- A grader can enter an application's details on the page and check a label against them.

### Changed

- The app loads the OCR models once for the process instead of once for every label, so a label no
  longer waits about a second for them, and the readiness check at `/healthz` warms the reader that
  serves submissions rather than one it discards.
- The bird's-eye view and the codemap in `ARCHITECTURE.md`, and the build, test and run commands in
  `CLAUDE.md`, describe the application as it now stands.

### Removed

- The optional layer that asked a language model for a second opinion on a finished rule result is
  gone, along with the two language-model SDK dependencies it needed and the development-only route
  that showed its raw calls. It was switched off by default and could not change a verdict: its
  output was discarded before it reached a rule result, and the channel that would have shown it to
  a reviewer was sealed. The reader that uses a vision model to turn a label photograph into fields
  is unaffected. See `docs/decisions/0009`.
- Installed dependencies and compiled Python are no longer tracked: `frontend/node_modules` and
  `__pycache__` are build output and are rebuilt from `uv.lock` and `pnpm-lock.yaml`.
- The telemetry block sent with each result no longer carries `orchestrator_duration_ms`. It timed a
  coordination step the app no longer performs, so it was always reported as zero, and nothing in
  the interface read it. The other three timings — total, per-rule and reading — are unchanged.

## [0.1.1] - 2026-09-15

### Fixed

- The rule engine reports a compliant label as compliant. Five defects together made that
  impossible, and each made a correct label fail: the engine looked up the application's declared
  value under the reader's field name only, so alcohol content, the government warning, the name and
  address and the country of origin were compared against nothing; the word-for-word warning check
  and the class-and-type check hashed and compared the reader's payload rather than the reading
  inside it; the warning heading was compared literally against a phrase written without the colon a
  compliant label carries; and the class-and-type check required the label's designation to equal a
  standard of identity rather than include one.
- The government-warning presence check now judges the warning, not the payload carrying it. A label
  with an empty warning used to pass it.

### Changed

- The health warning's four typography rules — contrasting background, characters per inch, type
  size and separate-and-apart — no longer run, each with its reason recorded in the rule pack. See
  `docs/decisions/0006`. `common.warning.heading_phrase` no longer runs as a duplicate of
  `common.warning.heading_caps_bold`.
- A class-and-type designation passes when it includes a recognised standard of identity as whole
  words, and both permitted spellings of "whisky" are accepted. See `docs/decisions/0007`.
