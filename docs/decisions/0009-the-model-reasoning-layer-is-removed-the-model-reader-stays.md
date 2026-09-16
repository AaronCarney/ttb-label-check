# 0009. The model reasoning layer is removed; the model reader stays

Date: 2026-09-16

## Choice

The optional layer that sent a finished rule result to a language model for a second opinion is
deleted: `app/orchestrator/` and its three tasks, the component that merged the model's note back
into a rule result, the predicate that decided when to call it, and the schema the model answered
in. The `openai` and `anthropic` SDK dependencies go with it, and so does the development-only
route that was meant to show the model's raw calls.

**The reader that uses a hosted vision model stays** (`app/vision/cloud.py`, decision 0005). It is a
different thing and it is what the brief's AI requirement is about: it turns a photograph of a
label into fields, which is the step no deterministic code can do. Removing a reasoning layer does
not remove the model from the product.

## Why

The layer could not change a verdict, by construction, and it was switched off by default. Four
independent facts, each verified in the code before deletion:

1. **Its output was discarded.** The merge step matched the model's notes to rule results by rule
   identifier, and neither backend ever set one. Every note arrived unattributable and was dropped.
2. **Even a matched note was cosmetic.** The merge step wrote only to a free-text `message` field.
   It was forbidden by contract from touching the outcome, the severity or the reason code — the
   three values a verdict is made of.
3. **The channel that would have shown it to a reviewer was sealed.** The envelope builder hard-codes
   the field-card's AI suggestion block to "not present", so nothing the model said could reach the
   screen.
4. **It was off.** The master switch defaulted to false, so the default run never called it.

Nothing in `docs/PRD.md` requires it, and no decision record asks for it. It was 644 lines of
subsystem plus roughly twenty test files, and it reached into eighteen files elsewhere in the app —
configuration, dependency wiring, the evaluator, the health check, the metrics timeline. That reach
is the cost: every one of those files had to be read and understood by anyone changing the app, to
establish a layer that provably did nothing.

Determinism decided it. A checker that must show a reviewer why it reached a verdict is worth more
than one that consults a model and then ignores the answer.

## Alternatives rejected

- **Turn the switch on and make the layer count.** That means letting a model influence a
  compliance verdict. The product's value is that the same label gives the same answer with a
  citation attached, and a reviewer can see the reasoning. Giving that up buys a second opinion
  nobody asked for.
- **Leave it switched off and untouched.** Dead code is not free. It misleads a reader about what
  the product does, it has to be kept importable, and its tests have to keep passing. Two SDK
  dependencies stay in the install for a code path that never executes.
- **Keep the interface and delete the implementations.** An interface with no implementation and no
  caller is the same dead weight in fewer lines, and it still suggests a capability that is not
  there.

## Consequence

The product's deterministic path is unchanged: every check, every verdict and every reason code is
exactly what it was. What is gone is a layer that could not have altered any of them.

One trace remains on purpose. The per-evaluation telemetry block carries a duration field for this
layer, and it now always reports zero. It is a required field on the response envelope that the
frontend and the recorded response fixtures both read, so removing it costs a schema change, a
frontend change and a rewrite of every fixture, in exchange for one integer. It stays until
something else changes that schema.
