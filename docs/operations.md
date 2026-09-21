# Running the deployed service

How the deployed service is provisioned, how its address is closed, how it is kept warm and how a
deploy is authorised. None of this is needed to run the app — `README.md`'s *Getting started* is —
and none of it is a deliverable. It lives here so the two graded documents can be about the product
instead of about its hosting.

## What the service runs on

Cloud Run, **4 vCPU and 4 GiB, one request at a time**, scaling to zero behind a two-instance cap.
Startup CPU boost doubles the allocation to eight cores for the first ten seconds of a container
start, so the start a keep-warm ping pays for is the shortest the platform offers. Inside the
container one uvicorn worker holds one OCR reader, and that reader is allowed **four threads**:
`OCR_NUM_THREADS` defaults to the service's core count and sets onnxruntime's intra-op and inter-op
pools and OpenCV's thread count alike. OpenBLAS is held to two threads by the image, because left
unset it runs one thread per core and contends with the sessions a read has already sized.

One request at a time is not only a cost control — it is what the five-second requirement needs: a
read is sized to use all four cores, so a second check arriving at the same moment would compete
with the first rather than run beside it ([decision 0025](decisions.md#0025)). That a second read
has nothing left to use is measured rather than assumed ([decision 0047](decisions.md#0047)).

Every figure here was read back from the deployed service on 2026-09-19 rather than copied from the
deploy script.

## The address, and why the Cloud Run URL will not answer

`https://ttb.aaroncarney.me` is this project's own hostname rather than the one Cloud Run issues. A
small Cloudflare Worker in `edge/` answers it and forwards to the service, addressing the origin by
its own hostname because Cloud Run's front end routes on the Host header, and it signs each request
with a Google ID token minted from a key held as a Worker secret. Deployed with
`npx wrangler deploy` from that directory; the key is never in this repository.

[Decision 0028](decisions.md#0028) argues why the design closes the Cloud Run URL with IAM rather
than hiding it — a request IAM denies is never billed — and [0029](decisions.md#0029) records the
rate limit that was meant to sit beside it. **The first is now the state of the deployed service;
the second is not, and the code says so where each is measured.** At the last measurement, the IAM
policy grants `roles/run.invoker` to `ttb-edge-invoker@ttb-label-check.iam.gserviceaccount.com` and
to nobody else, the Cloud Run URL answers `/api/health` with **403** and no credentials at all, and
the hostname above answers it with 200. So the hostname is the only way in, which is what 0028
argues for.

This has moved during the project — the service was deployed open with `TTB_PUBLIC=1` so a reviewer
could reach it, and `scripts/deploy.sh` will reopen or reclose it depending on the access flag it is
given, so treat this as a measurement rather than a fixed property. The rate limit denies nothing
and is left in place inert. What bounds the meter is the invoker check, since a request it refuses
is never billed, and the two-instance cap in `scripts/deploy.sh`. The Worker comment in
`edge/src/index.js` carries both measurements.

## The same Worker holds the service warm

Cloud Run runs at `--min-instances 0`, so an idle instance is reclaimed and the next visitor pays a
container start plus an OCR model load. Measured on 2026-09-19 that cost **36.48 seconds** to first
byte, against **0.14 seconds** on a warm instance — nothing about the application is slow; the wait
was the price of having scaled to zero.

A cron trigger on the Worker now calls `/api/health` every five minutes with the same invoker token,
which keeps the instance that already holds the loaded models from being reclaimed. That it holds is
measured rather than assumed: left alone for 25 minutes on 2026-09-20, the landing page still
answered in **0.284 seconds**, and the log for that span carries six pings on the five-minute period
with no container start in it. [Decision 0042](decisions.md#0042) records the period, the rejected
`--min-instances 1`, and the measurements.

## Deploying

The deploy is one command. Cloud Build builds the `Dockerfile` at the root of this repository from
an export of the current commit, and Cloud Run serves the image it produces, so nothing is built on
a developer's machine and an untracked file cannot reach the build. The host itself is settled in
[decision 0025](decisions.md#0025).

```bash
scripts/deploy.sh --check                   # every check that needs no network; deploys nothing
TTB_GCP_PROJECT=your-project scripts/deploy.sh
```

`--check` is what proves the repository is deployable without making it public: it runs every
precondition the deploy has that needs no network, and names any that fails. It runs as part of the
test suite.

## A deploy refuses a commit the pipeline has not passed

The preflights answer whether the repository is shippable — a `Dockerfile`, a service port matching
the container's, a tracked interface bundle — and none of them runs a test. `.gitlab-ci.yml` runs
the lint, the formatter, the type check and the whole suite, and its verdict belongs to one commit,
so the deploy reads that verdict for the exact commit it is about to upload and stops if it is
anything but a pass. A commit nobody has pushed has no verdict at all, and the refusal says to push
it.

This needs `glab` and `jq` on the path. `TTB_SKIP_PIPELINE_CHECK=1` deploys without the verdict, for
when GitLab is unreachable, and prints on the terminal that nothing has tested what is being
shipped.
