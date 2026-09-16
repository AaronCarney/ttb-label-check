# Documentation

- [Product requirements](PRD.md) — what is being built, for whom, and why.
- [PRD amendments](PRD-decisions.md) — every change to the PRD's text after approval.

## Decisions

One settled build decision per record, numbered, written the day it settled.

- [0001 Semantic versioning](decisions/0001-semantic-versioning.md) — how this project's version number moves.
- [0002 Stakeholder priority depends on the phase](decisions/0002-stakeholder-priority-depends-on-the-phase.md) — whose need leads, and when.
- [0003 How build choices are judged](decisions/0003-how-build-choices-are-judged.md) — the criteria every later choice is measured against.
- [0004 The prototype runs locally from a clone, and also deploys](decisions/0004-the-prototype-runs-locally-and-deploys.md) — why both are required and not alternatives.
- [0005 Two readers behind one interface, local by default](decisions/0005-two-readers-behind-one-interface-local-by-default.md) — reading a label with no outbound call.
- [0006 The health warning's typography rules are out of scope](decisions/0006-typography-rules-are-out-of-scope.md) — what a photograph cannot measure, and what is reported instead.
- [0007 A class-and-type designation includes its standard of identity](decisions/0007-a-designation-includes-its-standard-of-identity.md) — when a designation counts as matching.

## Reference

Rule text the app checks, each pinned to the date it was read.

- [Reference library](reference/README.md) — what the folder holds and how it is kept.
- [Accessibility](reference/accessibility.md) — the WCAG 2.2 AA criteria the app must meet.
- [Health warning](reference/health-warning.md) — the Government Health Warning text and format rules.
- [Label elements](reference/label-elements.md) — mandatory label elements for wine, spirits and malt beverages.

## Research

One dated finding per file.

- [Label law](research/2026-09-15-label-law.md) — what federal law requires on a label, by beverage type.
- [Matching rules](research/2026-09-15-matching-rules.md) — which label-to-application differences count as the same value.
- [Extraction](research/2026-09-15-extraction.md) — measured speed, accuracy and cost of reading a label into fields.
- [Test labels](research/2026-09-15-test-labels.md) — the real and flawed test labels and their ground truth.
- [Hosting](research/2026-09-15-hosting.md) — which free hosts can serve the app with a public URL.
- [App stack and architecture](research/2026-09-15-app-stack-architecture.md) — stack options for the app.
- [Batch processing](research/2026-09-15-batch-processing-architecture.md) — how a 300-label batch could run.
- [COLA operational context](research/2026-09-15-cola-operational-context.md) — how the COLA system and label review work.
- [Decision communication](research/2026-09-15-decision-communication-visualization.md) — presenting cost and uncertainty to decision makers.
- [Cost-effectiveness](research/2026-09-15-economic-cost-effectiveness-analysis.md) — an economic analysis of the prototype.
- [Eval corpus sourcing](research/2026-09-15-eval-corpus-sourcing-runbook.md) — a runbook for gathering evaluation labels.
- [Eval harness](research/2026-09-15-eval-harness-design.md) — test corpus size, statistics and evaluation design.
- [Federal deployment](research/2026-09-15-federal-deployment-compliance.md) — policy and compliance paths for federal use.
- [UX for federal and senior users](research/2026-09-15-federal-ux-for-senior-users.md) — interface design for the agents.
- [Label image sourcing](research/2026-09-15-label-image-sourcing-survey.md) — where label images can be sourced.
- [LLM orchestration](research/2026-09-15-llm-orchestration-architecture.md) — how a language model fits into checking.
- [MVP scope](research/2026-09-15-mvp-scope-demo-shape.md) — scope and demo shape for a first version.
- [OCR and vision](research/2026-09-15-ocr-vision-architecture.md) — OCR and vision-model options.
- [Rule engine](research/2026-09-15-rule-engine-architecture.md) — validation and rule-engine design.
- [Rule pack interface](research/2026-09-15-rule-pack-validator-interface.md) — a rule-pack and validator interface.
- [Stakeholder frameworks](research/2026-09-15-stakeholder-frameworks.md) — the brief's stakeholders and their needs.
- [TTB regulatory framework](research/2026-09-15-ttb-regulatory-framework.md) — the regulations behind label review.
- [Verification targets](research/2026-09-15-verification-targets-research.md) — what can be verified, and registry access.
- [Vision stack](research/2026-09-15-vision-stack.md) — vision stack and latency options.
