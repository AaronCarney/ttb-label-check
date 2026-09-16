# Architecture

## Bird's-eye view

The product takes one label application and the artwork submitted with it, and returns a per-check
verdict: which declared elements match the label, which do not, and which a person needs to look at.

Three ideas carry the design.

**A reader reports; rules decide.** Reading the label and judging it are separate steps that never
mix. A reader returns only what it saw, as a field observation with the image region it came from
and a confidence. It never returns a verdict. Every verdict comes from the rule pack, so a check can
be traced to the regulation behind it and changed without touching extraction code.

**The rules are data, not code.** The checks live in YAML under `rules/`, one rule per label
element, each with its CFR citation, its severity, and the validator that implements its comparison.
Validators are small, general functions — compare two quantities, compare two designations, hash a
verbatim block. Adding a check is a rule-pack edit. Validator code carries no regulation citation at
all; `tests/test_validator_registry.py` enforces that, and the citation lives with the rule.

**Reading works with no outbound connection.** A local OCR reader ships inside the app and is the
default, because the agents who would use this work behind a firewall that blocks outbound calls.
A cloud vision reader sits behind the same interface for comparison. Neither is wired into the rule
engine's decisions (`docs/decisions/0005`).

A verdict of `fail` means a rule the pack lets reject found a disagreement. `needs_review` means
either a rule whose disagreement is a reviewer's call rather than evidence the label is wrong, or a
reading the product was not sure enough of. `pass` means every applicable check passed and none was
skipped.

## Request flow

One evaluation, from `POST /labels` or the page form, runs in this order
(`app/services/evaluator.py`):

1. **Cache.** A hash over the canonicalised application and label, minus the per-call evaluation ID,
   so repeating the same submission in a session does not repeat the work.
2. **Read.** The configured reader returns one observation per label element.
3. **Tag the beverage type.** The application says whether this is wine, spirits or a malt beverage;
   a reader cannot, because nothing on a bottle reliably distinguishes them. Tagging here keeps the
   reader reporting only what it saw while still selecting the rule pack the application implies.
4. **Image-quality gate.** An image too small, too glared or too blurred to judge returns a
   needs-better-photo result rather than a verdict computed from an unreadable image.
5. **Run the rule pack.** Each rule selects the observations its `evidence_required` names, and runs
   its validator against the application's declared value for that element.
6. **Optional model refinement,** off by default. Every check on the requirements list is
   deterministic, and outbound model traffic is what the firewall constraint rules out. When it is
   enabled, the model may add explanation; it cannot change an outcome, a severity or a reason code.
7. **Decide.** Any failure the rule pack lets reject makes the submission `fail`; all passes make it
   `pass`; anything else is `needs_review` (`app/services/disposition.py`).
8. **Build the envelope,** with the audit trail, the per-rule timeline and the metrics.

A batch runs the same evaluation per label on a bounded queue, streaming each result to the browser
as it finishes, so a 300-label batch shows its first verdicts immediately instead of after the last.

## Codemap

| Path | Holds |
|---|---|
| `app/main.py` | Builds the FastAPI application: logging, routers, static files, and the per-process state a batch needs. |
| `app/config.py` | Every setting and every secret name, read here and only here. |
| `app/deps.py` | Chooses the reader and assembles the evaluator for a request. |
| `app/api/` | HTTP surface. `labels.py` evaluates one submission; `batches.py` accepts a batch and streams its results; `ui.py` serves the pages and the upload form; `healthz.py` reports readiness; `overrides.py` records an agent's decision to overrule a check; `eval.py` is development-only. |
| `app/vision/` | The readers. `base.py` is the interface both implement; `local.py` reads on this machine with no outbound call and is the default; `cloud.py` reads with a vision model; `quality.py` gates unusable images; `heading_measure.py` measures whether the warning heading is set in bold. |
| `app/rules/` | The engine. `loader.py` reads and cross-checks the YAML pack at startup; `yaml_engine.py` selects the rules that apply to each observation and runs them; `_validators/` holds one function per comparison kind, registered by name. |
| `app/services/` | One step of the flow each: `evaluator.py` composes them, and `disposition.py`, `aggregation.py`, `confidence.py`, `envelope_builder.py`, `audit.py`, `metrics_builder.py`, `cache.py` do the rest. `application_mapper.py` and `application_form.py` turn an application into the declared values the rules compare against. |
| `app/batch/` | The batch path: a bounded queue, a worker, and the anomaly check that flags a batch failing far more often than its neighbours. |
| `app/schemas/` | The pydantic types. `wire/` holds what crosses the HTTP boundary; the rest are internal. |
| `app/logging/` | JSON-line logging, secret redaction, and a ring buffer of recent calls for the development view. |
| `app/ui/` | Jinja page shells and the built frontend bundle they mount. |
| `rules/` | The rule pack: `common/` for the health warning, then one file per beverage type, plus `tables/` for unit conversions and `reason_codes.yaml` for the code each finding reports. |
| `assets/` | Text the rules compare against verbatim, pinned by hash. |
| `frontend/` | React island source, built by Vite into `app/ui/static/`. |
| `eval/` | Scores the reader against the real labels and their recorded ground truth. |
| `tests/` | Tests; `tests/fixtures/labels/` holds the real labels and their ground truth. |
