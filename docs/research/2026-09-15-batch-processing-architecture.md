# Batch Processing Architecture for the TTB ALFD Verification Prototype

**Scope.** This document answers Q6.1–Q6.10 with primary-source citations. It analyzes queueing, lookahead, concurrency, backpressure, mid-batch override semantics, in-flight state, multi-agent extensibility, lookahead sizing math, peak-season batch shape, and resource sizing for a prototype where a single ALFD agent reviews labels one-at-a-time, with batches of 200–300 (occasionally up to ~500) labels arriving from large importers in peak season. Per-label processing budget (input handling + OCR/Vision + AI orchestration + rule engine + audit assembly + serialization) is **p50 ≈ 2.7 s, p99 ≈ 5.0 s** under the 5-second SLA from [T3](./2026-09-15-rule-engine-architecture.md)/[T4](./2026-09-15-ocr-vision-architecture.md). Anecdotal agent review time is **5–10 minutes per simple application** (treated as p50 = 300 s, upper-bound = 600 s, with complex cases ~900 s as a tentative p90). All review-time numbers are flagged as anecdotal and unverified; [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) should drive a measurement campaign before production sizing.

---

## TL;DR

- **Throughput is human-bound, not compute-bound.** With agent review time R ≈ 300–600 s and per-label processing P ≈ 3–5 s, the ratio P/R ≪ 1 means a single worker with concurrency 1–3 keeps the agent saturated with massive headroom; the dominant constraint is human review (Little's Law; Kleinrock 1975). For 300 labels the wall-clock floor is 25–50 hours of agent work — well below TTB's 15-day operational ceiling but far longer than compute.
- **Use a bounded, pull-based, backpressured FIFO with a small warm-pool of 2–3 lookahead labels.** This is the canonical "Reactive Streams" pattern (Reactive Streams 1.0.4 §1–3) implemented with Python `asyncio` for the prototype: simple, on-prem-portable, federal-firewall-friendly, and consistent with Twelve-Factor backing services. Avoid serverless and distributed task queues for the prototype (YAGNI; Beck/Fowler).
- **Independence-by-default for mid-batch override, with a soft anomaly detector.** When the agent rejects label N, continue processing N+1…N+k under an independence assumption (ack already cheap; cancellation of in-flight is bounded). Surface a soft prompt only if a sequential anomaly detector (CUSUM/SPRT/ADWIN) flags M-of-N consecutive lookahead labels failing for the same reason. Mid-batch UX is flagged for cross-topic synthesis with **[T8](./2026-09-15-federal-ux-for-senior-users.md)**.

---

## Key Findings

1. The project's shape — *one consumer, one source, bursty producer, highly variable consumer service time, P/R ≪ 1* — is in the well-studied small-buffer/single-server regime where pull-based reactive-streams patterns (Reactive Streams 1.0.4; Akka Streams; Project Reactor; Kafka consumer pull) are precisely the right primitive.
2. Lookahead sizing is a *control problem*. Closed-loop (EWMA / Netflix-style adaptive concurrency, modeled on TCP Vegas) is overkill for the prototype; open-loop with a small fixed cap (k=2–3) is correct for a single agent. Adaptive control becomes valuable only in production multi-agent.
3. Backpressure semantics are not optional: even with k small, an agent stall (lunch, escalation) can saturate any unbounded buffer. The Reactive Streams `Subscription.request(n)` credit model and the Akka Streams overflow strategies (`Backpressure`, `DropHead`, `DropTail`, `DropBuffer`, `DropNew`, `Fail`) are the standard playbook.
4. **YAGNI applies to the multi-agent (47-ALFD) future state**: the prototype interface should be agent-id-aware (so the call sites and event schema carry an agent identifier), but the queue topology, fairness policy, and coordinator should not be built. Evolutionary-architecture practices (Ford et al.) favor making the right interface seams now, not the full implementation.
5. Compute is not the binding resource. For 300 labels at P50 ≈ 2.7 s, raw processing is ~13.5 minutes wall-clock with concurrency 1; the agent's 25–50 h review time dominates by 100×–200×.

---

## Details

### Q6.1 — Queue architecture patterns for variable-time work

**The shape of this problem.** One consumer (one ALFD agent) pulls one label at a time. The producer is a label-batch upload (200–300, occasionally larger). The consumer's "service time" is wildly variable (5–600+ seconds). The internal pre-processing pipeline (OCR/Vision + LLM + rules) has its own internal latency budget of ~2.7–5 s per label. The architectural question is: what queue + transport sits between the batch-upload producer and the human consumer, with the OCR/LLM pipeline as a *staging stage* in between?

| Pattern | Fit for project | Notes |
|---|---|---|
| **Simple FIFO with worker pool** | ✅ Strong fit | Canonical "task queue" pattern; one worker pool processes labels into a "ready" buffer. Kleppmann, *Designing Data-Intensive Applications*, Ch. 11, treats this as the baseline asynchronous messaging pattern. |
| **Priority queue with explicit head** | ⚠️ Marginal | The agent sees labels in submission order; priority is implicit (= batch index). A priority queue is overkill unless cross-batch reordering matters, which it doesn't for the prototype. |
| **Pull vs push delivery** | ✅ **Pull** | Pull is correct because the *consumer* (the agent) controls cadence. This matches Kafka's design rationale: "data is pushed to the broker from the producer and pulled from the broker by the consumer … a pull-based system [lets a slow consumer] catch up … and enables aggressive batching" (Apache Kafka design docs, "The Consumer," kafka.apache.org/documentation §4.5). |
| **Reactive Streams / backpressured streams** | ✅ Strong fit | Reactive Streams 1.0.4 (reactive-streams.org) defines the minimal four-interface contract (`Publisher`, `Subscriber`, `Subscription`, `Processor`) for asynchronous stream processing with non-blocking backpressure. The contract is built around `Subscription.request(n)` — the subscriber explicitly asks for `n` items, which is exactly the lookahead-size semantics we need. Akka Streams and Project Reactor are conformant implementations. |
| **Kafka consumer-style pull** | ⚠️ Future-state | Kafka's consumer-group + offsets model (Kafka design docs, "Consumer Position" and "Consumer Groups") is a great match for the *production* multi-agent case but is heavyweight for a single-agent prototype. |
| **Work-stealing (Cilk/ForkJoinPool/Tokio)** | ❌ Not applicable to single agent | Blumofe & Leiserson, "Scheduling Multithreaded Computations by Work Stealing," *J. ACM* 46(5):720–748, 1999, prove that work-stealing achieves expected execution time `T₁/P + O(T_∞)` on P processors for fully strict computations. With P = 1 (one agent), there is nothing to steal. Work-stealing becomes the right primitive when we have multiple agents/workers and want decentralized load balancing — i.e., production. |

**Recommendation (prototype):** A bounded FIFO with pull-semantics and Reactive-Streams-style request credits. Concretely, an `asyncio.Queue(maxsize=k)` (or equivalent in any chosen runtime) where the agent's "next" action is a `request(1)` and the OCR/LLM pipeline produces into the queue under backpressure. Treat the agent as the `Subscriber` and the OCR/LLM pipeline as a `Processor` per Reactive Streams 1.0.4 §3.

### Q6.2 — Lookahead sizing as a control problem

The question is: how many labels do we proactively process ahead of the agent? This is a control-theory problem with three regimes:

- **Open-loop.** Pick a fixed `k` (e.g., k=2 or k=3). Always keep up to `k` "ready" labels staged. Simple, no measurement loop. This is the prototype recommendation.
- **Closed-loop (EWMA / proportional).** Measure rolling agent review time R̂ and rolling per-label processing P̂ over a sliding window; adjust `k` to satisfy `k ≥ ⌈P̂/R̂⌉ × safety_factor`. EWMA ("exponentially weighted moving average") is the simplest stable estimator. Åström & Murray, *Feedback Systems* (Princeton, 2010), Ch. 1–2, give the canonical primer on stability/transient response of feedback controllers.
- **Adaptive (TCP-Vegas style).** Probe up while latency is flat, back off when a signal of saturation appears. This is exactly what the **Netflix Concurrency Limits** library (github.com/Netflix/concurrency-limits) does for service concurrency: `VegasLimit` estimates queueing delay from RTT, `Gradient2Limit` uses RTT gradient, and `AIMDLimit` implements additive-increase/multiplicative-decrease per Jacobson's TCP congestion-avoidance design (Jacobson & Karels, "Congestion Avoidance and Control," *SIGCOMM '88*; Netflix Tech Blog, "Performance Under Load: Adaptive Concurrency Limits @ Netflix"). The Vegas insight — `gradient = RTT_noload / RTT_actual`, and the limit should track this gradient — is a beautifully economical proxy for queue formation.
- **Predictive.** Build a model of agent review-time distribution and prefetch accordingly. Patterson's prefetching survey work in storage systems and the **Linux adaptive readahead** patches by Wu Fengguang (LWN, "Adaptive file readahead," lwn.net/Articles/155510; Wu et al., "Linux readahead: less tricks for more," *Linux Symposium* 2007) are the canonical references for adaptive prefetch — readahead window grows when the application is memory-rich and accesses are sequential, shrinks under memory pressure or when access patterns turn random. The same intuition applies: ramp `k` up when the agent is "hot" (sustained fast reviews) and shrink it when the agent slows.

**Why open-loop is right for the prototype.** The fundamental sizing identity is Little's Law (Little, "A Proof for the Queuing Formula L = λW," *Operations Research* 9(3):383–387, 1961): the average number of in-flight items L equals arrival rate λ times mean time-in-system W. For our pipeline, the agent's "arrival rate" of new requests is 1/R ≈ 1/300 per second, and the per-label processing time is W = P ≈ 3 s. So the *expected* in-flight count to keep the agent never-waiting is:

`L = λ·W = (1/R) × P = P/R ≈ 0.01`

That's <1 in expectation. Even with p99 protection (W = 5 s), `L ≈ 0.017`. The marginal value of going from k=1 to k=3 is to absorb (a) cold-start jitter, (b) the long tail of the OCR/LLM step, and (c) any p99 spikes. There is no marginal value in adaptive control at k ≤ 3 with R ≫ P. Adaptive control becomes interesting only when (i) we run multiple agents off a shared producer (production), (ii) the upstream OCR/LLM service exhibits time-varying capacity, or (iii) costs at the LLM/OCR provider become a tight optimization target ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md)).

**Recommendation:** Open-loop k=2–3 with a hard cap. Add an EWMA monitor of P and R for *observability* but do not feed it back into k for the prototype.

### Q6.3 — Concurrency and worker model for the prototype

The substitutability constraint (cloud OK for prototype, but architecture must allow on-prem swap) and the federal-context reality (FedRAMP boundaries, agency firewalls, GSA cloud-smart constraints — see fedramp.gov "Is FedRAMP Mandatory?", which makes serverless choices materially constrained when an agency requires on-prem or GovCloud-only deployment) heavily favor a **portable, runtime-agnostic** worker model.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Single-process asyncio (Python) / Node event loop** | Trivially portable; runs on a laptop, a VM, a container, or behind a federal firewall; no broker required; minimal dependencies. Native non-blocking I/O for OCR/LLM HTTP calls. (Python docs, `asyncio` library; "Coroutines and Tasks") | GIL-bound for CPU work, but our CPU is negligible (cloud OCR/LLM). | ✅ **Recommended for prototype.** |
| **Multi-process worker pool (Python `multiprocessing` / gunicorn workers)** | Scales past GIL for CPU-bound tasks. | Overkill for I/O-bound OCR/LLM workload. | ⚠️ Defer. |
| **Distributed task queue (Celery, RQ, Dramatiq, Arq)** | Battle-tested patterns: prefetch counts, autoscale, late acks (Celery docs, "Optimizing" and "Workers Guide"). | Adds a broker (Redis/RabbitMQ) — extra moving piece, extra firewall surface, extra ATO scope. | ⚠️ Defer to [T11](./2026-09-15-economic-cost-effectiveness-analysis.md)/production. |
| **Cloud-native serverless (AWS Lambda, Cloud Run, Azure Functions)** | Auto-scale, pay-per-request. | Violates the portability target; FedRAMP boundary complications; cold-start latency interferes with our 5-s SLA on first label of a batch. | ❌ Not recommended. |

This is the **Twelve-Factor "backing services" pattern** (12factor.net §IV, §VIII): backing resources (LLM, OCR provider, optional Redis) are attached over the network via configuration. Worker processes are stateless and disposable. No code change is needed to swap LLM providers or move on-prem.

**Worker isolation.** Even the prototype should adopt **bulkhead** and **circuit-breaker** patterns from Nygard, *Release It!* 2nd ed. (Pragmatic Bookshelf, 2018): a separate concurrency limiter on each external dependency (OCR provider; LLM provider) so a slow LLM does not block OCR throughput. The Netflix Concurrency Limits library's `AbstractPartitionedLimiter` is the prototype model (github.com/Netflix/concurrency-limits, README §"Limiter Implementations"). For the prototype, simple `asyncio.Semaphore(n)` per upstream dependency is sufficient; in production, switch to `Gradient2Limit` or Vegas.

**Recommendation:** Single Python process, `asyncio` event loop, with two bounded semaphores (one for OCR, one for LLM) sized 2–3 each. Heroku-style "worker process" model (twelve-factor §VIII), so production can simply scale horizontally if needed.

### Q6.4 — Backpressure when lookahead saturates

What happens if the agent goes to lunch mid-batch?

**Bounded buffer is mandatory.** Reactive Streams 1.0.4 §2.7 mandates that buffer sizes be known and controlled by subscribers via `Subscription.request(n)`: "One of the underlying design principles is that all buffer sizes are to be bounded and these bounds must be known and controlled by the subscribers." (reactive-streams.org). Without this, a fast OCR/LLM pipeline plus a stalled agent equals unbounded queue growth — the **bufferbloat** failure mode (Gettys & Nichols, "Bufferbloat: Dark Buffers in the Internet," *ACM Queue* 9(11), 2011; Gettys et al., "BufferBloat: What's Wrong with the Internet?" *CACM* 55(2):40–47, 2012). In our context bufferbloat manifests as wasted compute spend on labels the agent may never reach, not as latency, but the same bounded-buffer discipline applies.

**Overflow strategies.** Akka Streams gives the canonical taxonomy (Akka docs, "Buffers and working with rate"; `OverflowStrategy` Java API):
- `Backpressure` — block upstream (the right default for finite work like this).
- `DropHead` — drop the oldest queued item to admit a new one.
- `DropTail` — drop the youngest queued item.
- `DropBuffer` — drop the entire buffer.
- `DropNew` — refuse to admit the new item.
- `Fail` — fail the stream with `BufferOverflowException`.

For a TTB batch (where every label must eventually be reviewed), the only correct strategy is `Backpressure`: stop pulling, let the OCR/LLM pipeline idle, do not drop work. Drop strategies are appropriate for telemetry streams, not for queues of regulatory work that must be completed.

**Idle-worker behavior.** When the agent has stopped: workers should *complete in-flight items* (≤ 5 s) and then *go idle*. Do not pre-process speculative labels beyond `k`. Also: cancel in-flight work *only* if cancellation is cheap (e.g., the LLM API call has not started yet); otherwise let it finish and cache the result. This is consistent with Project Reactor's and gRPC's credit-based flow control: "the receiving side is not forced to buffer arbitrary amounts of data … backpressure is application-level flow control from the subscriber to the publisher" (gRPC docs, "Flow Control," grpc.io/docs/guides/flow-control). HTTP/2's `WINDOW_UPDATE` frame is the wire-level analog — credit is replenished only as the consumer drains.

**Resumption (warm vs cold).** When the agent returns: warm-cache resumption is preferable. Keep the existing OCR/LLM results for the staged labels in memory (they are session-scoped, per the no-persistence requirement — see Q6.6). If the lookahead labels were dropped due to a process restart, accept the cold-start cost — the agent will see a 1–5 s delay on the next label, which is within SLA.

**Cost implications.** Every label pre-processed but not yet reviewed represents a sunk OCR + LLM cost. With bounded `k` and a ~100×–200× ratio of R/P, a stalled agent leaks at most `k` labels' worth of compute (~$0.01–$0.10/label depending on provider). At k=3 this is bounded waste; at k=300 (no backpressure) it would be the full batch's cost. Bounded `k` *is* the cost-control mechanism.

**Tail-at-scale considerations.** Dean & Barroso, "The Tail at Scale," *CACM* 56(2):74–80, 2013, observe that even rare slow operations dominate user-perceived latency at scale. For our case the analog is: a single OCR/LLM p99 spike of ~5 s is exactly within budget, but a p99.9 spike of, say, 12 s is not. Their mitigations — *hedged requests* (issue a duplicate request to a second replica after a percentile threshold), *tied requests*, and *backup requests* — are applicable to the OCR/LLM stage in production. For the prototype, simply log p99/p99.9 and rely on per-call timeouts.

**Bulkhead.** Each external dependency (OCR, LLM) should have its own concurrency budget (Nygard, *Release It!* 2nd ed., Ch. 5 "Stability Patterns": Bulkheads). This prevents a hung LLM from also blocking OCR throughput.

### Q6.5 — Mid-batch override semantics

When the agent rejects label N, what should we do with already-processed lookahead labels N+1…N+k?

**Three options.**

1. **Continue processing under an independence assumption.** The default. Rejection of N is uncorrelated with the disposition of N+1.
2. **Pause and confirm direction.** Treat rejection as a possible signal of a batch-wide issue (e.g., same submitter, same defect class), and prompt the agent before continuing.
3. **Surface a soft pattern-detection prompt.** Continue processing, but if a sequential anomaly detector fires, surface a non-blocking prompt.

**Recommendation: option 1 (continue) with an explicit anomaly-detection rule that escalates to option 3 only when the data warrants.**

This is fundamentally a *sequential hypothesis testing* problem. Wald's **Sequential Probability Ratio Test (SPRT)** ("Sequential Tests of Statistical Hypotheses," *Annals of Mathematical Statistics* 16(2):117–186, 1945) gives the canonical formalism: at each label, compute the cumulative likelihood ratio between H₀ ("this batch is normal") and H₁ ("this batch is uniformly bad / has a systemic defect"). Stop and prompt when the ratio crosses an upper threshold; continue when it stays in the indifference region. SPRT is provably optimal in expected sample size for any prescribed (α, β) error rates for simple-vs-simple hypotheses (Wald & Wolfowitz, 1948); our batch-quality test is composite, so the optimality property is approximate, but the formalism still applies as a starter rule.

Page's **CUSUM** ("Continuous Inspection Schemes," *Biometrika* 41:100–115, 1954) is a closely related recursive form: `S_t = max(0, S_{t-1} + log(q(Y_t)/p(Y_t)))`, with an alarm when `S_t > h`. CUSUM is widely used in clinical-trial early-stopping rules (Grigg, Farewell & Spiegelhalter, "Use of risk-adjusted CUSUM and RSPRT charts for monitoring in medical contexts," *Stat. Methods Med. Res.* 12(2), 2003) — exactly the analog the project should think in: the agent is, in effect, running a quality-control inspection on the importer's batch.

For the case where pre- and post-change distributions are unknown (the realistic case here — we don't know what defective batches look like), **ADWIN** (Bifet & Gavaldà, "Learning from Time-Changing Data with Adaptive Windowing," *SDM 2007*, doi:10.1137/1.9781611972771.42) is the right primitive: it maintains a sliding window and provides rigorous false-positive/false-negative guarantees while adapting the window size to the rate of change.

**Concrete starter rule for the prototype:**
- Keep a sliding window of the last *N* = 10 dispositions.
- If *M* ≥ 5 of the last 10 lookahead labels would have failed *for the same TTB rule code or same defect class*, surface a **soft, non-blocking prompt**: "The last 5 of 10 labels in this batch failed for [reason X]. Continue, or pause to inspect submitter trend?"
- Default action is "continue" — do not block the agent.

**Design grounding: prefer undo over confirmation.** The "soft, non-blocking prompt" choice follows the canonical HCI principle that confirmation dialogs should be replaced with undoable actions for routine decisions. The principle is formulated most directly in **Aza Raskin, "Never Use a Warning When You Mean Undo," *A List Apart* №241, July 21, 2007** (alistapart.com/article/neveruseawarning) — confirmation dialogs habituate users to click through and provide little real safety; an undoable, non-blocking action is the proper substitute. The principle is reinforced by **Nielsen's Heuristic #3 "User Control and Freedom"** (Nielsen Norman Group, "10 Usability Heuristics for User Interface Design") and is foundational in **Jef Raskin, *The Humane Interface*** (Addison-Wesley, 2000), chapters on Quantification and Modelessness/Habituation. The well-known practical precedent is **Gmail's "Undo Send"** feature (Michael Leggett, "New in Labs: Undo Send," Official Gmail Blog, March 19, 2009; generally available via Google Workspace Updates, June 22, 2015).

**Cross-topic flag → [T8](./2026-09-15-federal-ux-for-senior-users.md).** The *visual* design of the soft prompt, the *wording*, the *placement*, and how the agent's interaction with it (dismiss / pause / inspect) interacts with the rest of the review UI is a UX question. T6 specifies *that* a prompt fires and *under what statistical condition*; [T8](./2026-09-15-federal-ux-for-senior-users.md) specifies *what it looks like and how it disrupts the agent's flow*. **This is an explicit cross-topic synthesis question; not answered here.**

### Q6.6 — In-flight state model

What state must the prototype track for an in-progress batch?

**Per-label state machine (session-scoped):**
```
queued → processing → ready → presented → reviewed → disposed
                ↘ failed (with reason; retry-eligible or terminal)
```

- `queued`: label exists in the input batch but has not yet entered the OCR/LLM pipeline.
- `processing`: pipeline running; partial results may exist.
- `ready`: OCR + LLM + rule outputs available; presentable to the agent.
- `presented`: the agent is currently viewing this label.
- `reviewed`: the agent has issued a disposition (approve / reject / needs-correction).
- `disposed`: persisted to evidence, with the reasoning for the disposition.

**Order of processing vs presentation.** They diverge: processing is parallel-ish (concurrency 2–3), presentation is strictly serial in submission order. A small `ready_buffer` keyed by batch index decouples them.

**Batch metadata** (session-scoped): submitter, submission timestamp, total count, current presentation index, agent id (even though there is one agent — see Q6.7).

**No-persistence constraint — sourcing note.** The no-persistent-storage constraint comes from `docs/PRD.md` C-2: "The product retains no label image or application data on its server once it has returned the results for them." The prototype therefore keeps no audit trail either — session-only — and a production version would have to meet document-retention obligations instead. It is a data-handling and scope requirement, not a stakeholder-priority decision. The federal-norm grounding for session-only handling derives from the **Privacy Act of 1974** (5 U.S.C. § 552a, data-minimization principle), **NIST SP 800-53 Rev. 5** controls **PT-7** (Data Minimization and Retention) and **SI-12(2)** (Minimize PII in Testing, Training, and Research), **NIST SP 800-122** (Guide to Protecting the Confidentiality of PII), and the **OMB M-03-22 / E-Government Act §208** PIA process — all of which incentivize prototypes to stay below collection/retention thresholds.

**Recovery contract.** All in-flight state lives in process memory (or in an *ephemeral* Redis if we want process-restart resilience). The accepted prototype recovery behavior is: **on crash, the user re-uploads the batch.** This is the simplest correct option; it avoids the entire durable-workflow design space and is consistent with prototype scope.

**Patterns and references for production future-state.**
- The **actor model** (Akka, akka.io/docs) with one actor per batch and one actor per label gives clean per-batch state isolation and supervision-tree restart semantics.
- **Akka Cluster Sharding** + **event sourcing** for per-batch durable state.
- **Kafka offsets / consumer groups** as the resumable-batch primitive: the consumer's "current offset" is the production analog of "current presentation index" (Kafka design docs, "Consumer Position"; Confluent docs, "Kafka Consumer Design").
- **Temporal / Cadence** (temporal.io; cadenceworkflow.io) for durable workflows: workflow code is deterministic so a crash can replay the event history and reconstruct exact state. This is the right primitive for a regulated, multi-day workflow but is overkill for the prototype.
- For ephemeral state with optional snapshotting: Redis as a session-scoped store. The Twelve-Factor App's "Processes" rule (12factor.net §VI: "Execute the app as one or more stateless processes") is the discipline.

**Recommendation:** Pure in-memory per-batch state for the prototype. Document the "re-upload on crash" recovery contract explicitly in the runbook. Build the per-label state machine and the batch context object so that swapping in Redis later (or Temporal in production) is a localized change.

### Q6.7 — Multi-agent shared queue (future-state)

**Should the prototype design accommodate 47 agents?**

**Recommendation: agent-id-aware interfaces, but no multi-agent topology.**

Building a multi-agent coordinator now (work-stealing, fairness scheduler, distributed offset tracking) is a textbook **YAGNI** violation (Beck, *Extreme Programming Explained*, 2nd ed.; Fowler, "Yagni," martinfowler.com/bliki/Yagni.html: "Yagni only applies to capabilities built into the software to support a presumptive feature; it does not apply to effort to make the software easier to modify"). Per Ford, Parsons & Kua, *Building Evolutionary Architectures* (O'Reilly, 1st ed. 2017; 2nd ed. 2022), the right move is to enable evolution by getting the *seams* right while deferring the implementation:

- **Now (prototype):** every event/log/disposition record carries an `agent_id` field, even though it is always the same value. The lookahead buffer is keyed on `(batch_id, agent_id)`. The OCR/LLM result cache has `agent_id` in its key (so cross-agent caching is possible later but not present now).
- **Later (production):** swap the in-process FIFO for a Kafka topic with consumer groups (each agent = one consumer in the group, with one partition per agent for sticky assignment), or for a RabbitMQ work queue with `prefetch=1` and fair dispatch (RabbitMQ docs, "Work Queues" tutorial: "we can use the `basic.qos` method with `prefetch_count=1` … this tells RabbitMQ not to give more than one message to a worker at a time"; RabbitMQ docs, "Consumer Prefetch"). Celery's routing keys give the same primitive at the application layer.
- **Fairness primitive (production).** Weighted-round-robin or deficit-weighted-round-robin (DWRR) is the standard fairness scheduler when agents have different availability or skill profiles; this is an extension of the **work-stealing** pattern (Blumofe & Leiserson, *J. ACM* 1999), which has been formally analyzed and is the basis of Cilk, Java's `ForkJoinPool`, and Tokio's scheduler. Work-stealing's strong property — expected runtime `T₁/P + O(T_∞)` — is what makes a 47-agent pool nearly linearly scalable in throughput, *if* the work units are reasonably uniform.

**Cost of designing-in multi-agent now (rejected).** Adds a broker dependency, agent-affinity logic, fairness policy, and per-agent observability — significant code that will almost certainly be rewritten when actual production constraints (deployment topology, ATO boundary, agent-skill heterogeneity) are known.

**Cost of refactoring later (accepted).** Replacing an in-process FIFO with a broker-backed queue is a localized change if the seams (interfaces, agent_id propagation, consumer-pull semantics) are right.

### Q6.8 — Lookahead sizing math

**Inputs (with explicit assumptions).**
- Agent review time R (anecdotal, *unverified*): p50 = 300 s (5 min), upper-bound = 600 s (10 min), p90 ≈ 900 s for complex applications. **Flag: these are stakeholder-anecdote values, not measured. [T11](./2026-09-15-economic-cost-effectiveness-analysis.md) should drive a measurement campaign.**
- Per-label processing P ([T3](./2026-09-15-rule-engine-architecture.md) + [T4](./2026-09-15-ocr-vision-architecture.md)): p50 ≈ 2.7 s, p99 ≈ 5.0 s.
- Concurrency C (in-process): the number of labels we can have *in pipeline* simultaneously.
- Lookahead size k: number of labels we proactively keep "ready" for the agent.

**No-wait condition.** The agent never waits on the pipeline iff the pipeline produces faster than the agent consumes. With concurrency C and processing time P, pipeline rate = C/P. Agent rate = 1/R. The condition is:

`C/P ≥ 1/R   ⇔   C ≥ P/R`

For R = 300, P = 3: `P/R = 0.01`, so **C = 1 is sufficient with a 100× safety margin.**

**Little's Law** (Little, *Operations Research* 1961). In steady state, `L = λ·W`. Here λ is the agent's "consumption rate" of newly-ready labels (= 1/R in steady state once the pipeline is keeping up), and W is the time a label spends in the pipeline (= P). So:

`L = (1/R) × P = P/R ≈ 0.01 (p50), ≈ 0.017 (p99)`

The expected number of in-flight labels needed to keep the agent busy is well below 1. The lookahead is essentially "have one label ready ahead of the agent at all times."

**Why k > 1 still matters.**
- **Cold-start.** First label of a batch has no warm cache; OCR endpoint may be cold; an empty pipeline takes 1 × P seconds to fill.
- **p99 protection.** A single OCR/LLM call at 5 s consumes the full agent SLA; if the agent finishes their current review during that 5 s, they wait. With k = 2 and concurrency 2, the *next* label is essentially always ready.
- **Queue priming for batches.** When a fresh batch arrives, parallel-priming 2–3 labels gives the agent zero wait on the first three reviews.
- **Heavy-traffic safety margin.** Kingman's heavy-traffic approximation (Kingman, "The Single Server Queue in Heavy Traffic," *Math. Proc. Cambridge Phil. Soc.* 57(4):902–904, 1961) — `E[W_q] ≈ ρ/(1−ρ) × (c_a² + c_s²)/2 × τ` — shows that wait time blows up super-linearly in utilization ρ. For us ρ = P/R ≪ 1, so this is irrelevant in practice; included only for completeness as a sanity check.

**M/M/c sanity check.** For an M/M/c queue (Allen, *Probability, Statistics, and Queueing Theory: With Computer Science Applications*, 2nd ed., Academic Press, 1990, pp. 679–680; Kleinrock, *Queueing Systems Vol. 1: Theory*, Wiley, 1975), the probability of queueing (Erlang-C) approaches zero rapidly when offered load `a = λ/μ` is much less than `c`. With λ = 1/300 and μ = 1/3, `a = 0.01`; even c = 1 gives near-zero waiting probability.

**Recommendation:**
- **Concurrency C = 2** (two parallel OCR/LLM pipelines).
- **Lookahead cap k = 2–3** (two or three labels can be in the "ready" buffer).
- Result: a *warm pool* of 2–3 labels processed proactively to absorb p99 tails (~5 s) within the agent's review window (≥ 300 s).

### Q6.9 — Realistic peak-season batch shape and dominant constraint

**Empirical batch shape.** Sarah's anecdote: 200–300 labels per large importer in peak season. [T2](./2026-09-15-cola-operational-context.md) establishes that TTB does not publish seasonality data. CY2026 YTD through April = 55,528 applications (TTB FAQ data). For prototype risk planning, treat **300 as a mid-estimate; treat 500 as a worst-case** (industry patterns include occasional very large submissions).

**Wall-clock floor for one agent on one batch (compute-only).** With C = 2 and P = 3 s, pipeline throughput is ~0.67 labels/s. For 300 labels: ~7.5 minutes of pipeline time. For 500: ~12.5 minutes. **This is dominated by the agent.**

**Wall-clock for one agent on one batch (agent-bound).**
- 300 labels × 5 min/label = 1500 min = **25 hours of agent work** ≈ **3 working days** (8.5 hr/day after breaks).
- 300 labels × 10 min/label = 3000 min = **50 hours of agent work** ≈ **6 working days**.
- 500 labels × 5 min = 41.7 hours ≈ 5 days.
- 500 labels × 10 min = 83.3 hours ≈ 10 days.

**Dominant constraint.** Agent review throughput, by ~100×–200× over compute. Fan-out across multiple agents (production future-state) is the only way to materially reduce wall-clock; adding more compute to the prototype yields essentially no marginal benefit beyond the current k=2–3 sizing.

**Operational ceiling.** TTB's stated 15-business-day service goal provides the operational ceiling. At even the 10-min-per-label upper bound, a single agent can clear a 500-label batch in ~10 working days, leaving ~5 days of slack within the goal — assuming no other batches are competing. In practice batches queue for agent attention, which is why the production architecture (47 agents) exists.

**Heavy-traffic warning.** If utilization ρ of the *agent* (fraction of working time spent on a single batch) approaches 1 — i.e., the queue of pending batches exceeds agent throughput — Kingman's formula tells us wait times explode. The TTB-level analog to wait time is calendar processing time, and this is consistent with TTB's published median 1–5 calendar-day end-to-end times reflecting agent-pool utilization, not per-label compute. (Note these public times include multi-step round-trips and are not directly comparable to per-label review times.)

### Q6.10 — Resource sizing recommendation

**Prototype (one agent).**
- **Workers:** single Python process with `asyncio` event loop.
- **Concurrency:** 2–3 coroutines for OCR/LLM calls (per Q6.8).
- **Memory headroom:** ~1 GB for image buffers + partial OCR output + LLM context. Image-heavy labels can have 5–20 MB raw input; with k=3 in-flight that's <100 MB hard floor; the rest is Python overhead, model client buffers, and headroom.
- **GPU:** **None.** Cloud OCR (e.g., a managed OCR endpoint) and LLM inference are remote; the prototype host is purely an orchestrator.
- **CPU:** 2 vCPUs sufficient.
- **Disk:** ephemeral; logs only.
- **Network:** outbound to OCR/LLM endpoints; latency-sensitive (every 100 ms of round-trip eats into the 5-s SLA).

**Sizing methodology — Brendan Gregg's USE method** (Gregg, "The USE Method," brendangregg.com/usemethod.html; "Thinking Methodically about Performance," *ACM Queue* 10(12), 2012; *Systems Performance* 2nd ed., Pearson, 2020). For each resource — CPU, memory, network, OCR-budget, LLM-budget — track Utilization, Saturation, and Errors. Specifically:
- CPU utilization < 70% (heavy-traffic queue theory rule of thumb: target 70–80% utilization to keep p99 in check; above ~70% Kingman's `ρ/(1−ρ)` term grows steeply).
- Memory: track allocation rate and GC pressure; saturation indicator is swap activity.
- OCR/LLM concurrency saturation: track the `asyncio.Semaphore` queue depth; non-zero saturation is the early-warning signal.
- Errors: 4xx/5xx from OCR/LLM endpoints, timeouts, retries.

**Production (47 agents) — defer to [T11](./2026-09-15-economic-cost-effectiveness-analysis.md).** The analysis is more involved:
- Fan-out by agent: per-agent worker (or per-agent queue partition).
- Compute can still be centralized: a shared OCR/LLM call pool serves all agents, sized from peak QPS.
- **Peak QPS.** With 47 agents averaging one new label every ~360 s (R = 300–600 s), steady-state QPS ≈ 47/360 ≈ 0.13 labels/s. Even at 5× burstiness, that is < 1 QPS — trivial for cloud OCR/LLM at typical commercial rate plans.
- **Cost mix.** Cloud OCR pricing typically scales linearly per page; LLM tokens scale linearly with content size. Self-hosting a GPU inference server makes sense only at much higher QPS or for data-residency reasons (federal on-prem).
- **Adaptive concurrency** (Netflix Concurrency Limits) becomes valuable in production: VegasLimit on the OCR/LLM client to auto-detect provider degradation and shed load.

[T11](./2026-09-15-economic-cost-effectiveness-analysis.md) (economic analysis) should drive the production-cost model.

---

## Caveats

1. **Agent review time of 5–10 minutes is anecdotal.** It is the only data point we have, but it is not measured. Treat all R-derived numbers in Q6.8–Q6.9 as order-of-magnitude. Recommend a measurement campaign (instrument the existing manual review process with timing telemetry) before production sizing.
2. **Per-label processing budget (P = p50 ~2.7 s, p99 ~5.0 s) is from [T3](./2026-09-15-rule-engine-architecture.md)/[T4](./2026-09-15-ocr-vision-architecture.md) estimates.** It assumes specific OCR/LLM provider latencies; provider changes could shift these by 30–50%.
3. **Batch size of 200–300 (worst case ~500)** is an industry-pattern estimate, not from TTB-published data. Real distribution is unknown.
4. **The prototype recovery contract** ("re-upload on crash") is acceptable explicitly because of the no-persistence requirement (`docs/PRD.md` C-2). Production must replace this with durable workflow primitives (Temporal, Akka event sourcing, or Kafka offsets).
5. **Where the no-persistence constraint comes from.** It is `docs/PRD.md` C-2, a data-handling and scope requirement rather than a stakeholder-priority decision, and this document cites it as such.
6. **Cross-topic synthesis (X-1, etc.) is deferred.** Q6.5 explicitly defers UX details to [T8](./2026-09-15-federal-ux-for-senior-users.md). The economic and production-sizing analysis is deferred to [T11](./2026-09-15-economic-cost-effectiveness-analysis.md).
7. **FedRAMP/firewall context** is a real constraint but project-specific; the architecture's portability target is what matters operationally — the prototype must run on a developer laptop, in commercial cloud, *and* on agency on-prem hardware without code change.
8. **Anomaly-detection threshold (M of N)** in Q6.5 is a starter rule, not statistically calibrated. Real calibration requires pilot data and is a follow-on item.
9. **"P/R ≪ 1" only holds while labels are simple.** If the OCR/LLM pipeline grows (e.g., multi-page documents, multi-language disambiguation, more complex rule packs), P could rise to 10–30 s. The architecture remains sound but `k` should grow proportionally.
10. **SPRT optimality is for simple-vs-simple hypotheses.** Wald & Wolfowitz (1948) proved expected-sample-size optimality under those conditions; our batch-quality test is composite, so the property is approximate. The starter rule in Q6.5 is fit-for-purpose for prototype, not statistically optimal.

---

## Open issues / follow-on work

- **Measurement of agent review time** with the current manual workflow (precondition for confident lookahead sizing).
- **Calibration of the SPRT/CUSUM/ADWIN anomaly threshold** for mid-batch override (Q6.5) using pilot data.
- **UX synthesis ([T8](./2026-09-15-federal-ux-for-senior-users.md)) for the soft-prompt** when anomaly fires.
- **Economic model ([T11](./2026-09-15-economic-cost-effectiveness-analysis.md))** for production multi-agent: cloud OCR/LLM cost vs self-hosted GPU inference, FedRAMP-boundary cost implications.
- **Decision framework** for when (in production scale-up) to migrate from in-process FIFO to Kafka/RabbitMQ/Celery — likely tied to the agent-pool size and the deployment-topology requirements.
- **Adaptive concurrency cutover** (Netflix Concurrency Limits / Vegas) for production OCR/LLM clients.
- **Tail-mitigation strategy** (Dean & Barroso 2013) for the OCR/LLM stage in production: hedged requests, tied requests, or backup requests.
- **Durable-workflow design** (Temporal vs Akka event sourcing vs Kafka offsets) for production batch state, crash recovery, and multi-day workflows.
- **Memory and crash testing** of the prototype under simulated 500-label batches with intentional agent stalls.
- **Provider-redundancy plan** for OCR and LLM (circuit-breaker behavior on provider outage; do we degrade to a slower fallback or fail the batch?).