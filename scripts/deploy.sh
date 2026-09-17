#!/usr/bin/env bash
#
# Deploy this repository to Google Cloud Run (decision 0025).
#
# Cloud Build builds the Dockerfile at the repository root and Cloud Run serves
# the image, so the deploy is one command and nothing is built here. What gets
# uploaded is an export of the current commit, not the working directory, so an
# untracked file cannot reach the build.
#
#   scripts/deploy.sh --check   Run every preflight that needs no network, then
#                               stop. Proves the repository is deployable
#                               without making anything public.
#   scripts/deploy.sh           Run the preflights, then build and deploy.
#
# The service keeps Cloud Run's invoker check enabled, so the URL Cloud Run
# issues answers nothing without a Google-signed ID token. One service account
# holds that permission, and its key lives in the Cloudflare Worker that fronts
# the service. This is what bounds the meter: Google's pricing page states that
# "requests are only billed when they reach the container after successfully
# being authenticated, requests denied by IAM policy are not billed", so a flood
# aimed at the Cloud Run URL costs nothing, and every request that does arrive
# has passed the edge's rate limit first (decision 0025).
#
# Deploying makes the app reachable through that edge, which is the owner's call
# to make.
#
# Environment:
#   TTB_GCP_PROJECT   The Google Cloud project to deploy into. Required for the
#                     deploy, not for --check.
#   TTB_REGION        Cloud Run region. Defaults to us-central1.
#   TTB_SERVICE       Cloud Run service name. Defaults to ttb-label-check.
#   TTB_INVOKER_SA    The service account permitted to invoke the service.
#                     Defaults to ttb-edge-invoker in TTB_GCP_PROJECT.
#   TTB_PUBLIC        Set to 1 to deploy the service with its Cloud Run URL open
#                     to anyone, instead of behind the invoker check. The edge
#                     proxy decision 0025 describes does not exist yet, so this
#                     is what makes the URL answer a reviewer who clicks it. The
#                     instance cap below is then the only thing bounding the
#                     meter. Deploying open is the owner's call every time.

set -euo pipefail

CHECK_ONLY=0
case "${1:-}" in
    --check) CHECK_ONLY=1 ;;
    "") ;;
    *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."

REGION="${TTB_REGION:-us-central1}"
SERVICE="${TTB_SERVICE:-ttb-label-check}"

# The port Cloud Run sends traffic to. It must be the port the container binds,
# and the preflight below is what holds the two together.
SERVICE_PORT=8000

# One request at a time, because the reader's own measurements show concurrent
# reads contending for the same cores: eight at once moved the 95th percentile
# from 2.26 seconds to 10.02 seconds (decision 0005). Serving one at a time is
# what the five-second requirement needs, and it caps the meter as a side
# effect. Two instances is the ceiling on what traffic can spend; 900 seconds is
# the batch requirement of 300 submissions inside 10 minutes, plus headroom.
#
# Four vCPU and 4 GiB, because CPU is what the free allowance runs out of first
# and memory is therefore free headroom (decision 0025). The reader's working
# set is a carried-over 1.5-2 GB that has never been measured, so the size is
# set at roughly double the top of that range.
CPU=4
MEMORY=4Gi
CONCURRENCY=1
MAX_INSTANCES=2
TIMEOUT=900

# Hold traffic off an instance until its models are loaded.
#
# Without this Cloud Run routes a request the moment uvicorn binds the port,
# and the OCR models load lazily on first use - inside that request. The load
# pushed the evaluation past the evaluator's five-second SLA, so the first
# person to click got ENGINE.SLA.TIMEOUT and an empty result: no findings, no
# explanation of why. Observed on the live service 2026-09-16, and it is not a
# first-boot-only fault - CONCURRENCY is 1, so every scale-up makes another
# instance that would do the same.
#
# /healthz is the probe because loading the models is already what it does: it
# builds the same evaluator a submission builds and answers 503 until that
# succeeds, which is what lets an orchestrator hold traffic back. The reader is
# one object per process (app/deps.py), so what the probe loads is what the
# next request reads with.
#
# 30s per attempt and four attempts allows two minutes, well over the seconds a
# load takes, so a cold disk does not fail an otherwise healthy revision. An
# attempt cut off at timeoutSeconds is safe: ensure_loaded holds a lock, so the
# retry waits on the load already running rather than building a second engine.
#
# timeoutSeconds must be SMALLER than periodSeconds - Cloud Run rejects the
# revision otherwise, and the rejection is the whole deploy, not just the probe
# (Container#Probe: "Must be smaller than periodSeconds"). Keep the gap when
# changing either number.
STARTUP_PROBE=httpGet.path=/healthz,initialDelaySeconds=0,timeoutSeconds=20,periodSeconds=30,failureThreshold=4

FAILED=0
fail() { echo "  FAIL  $*" >&2; FAILED=1; }
pass() { echo "  ok    $*"; }

echo "Preflight:"

# 1. The image Cloud Build builds.
if [ -f Dockerfile ]; then
    pass "Dockerfile is present"
else
    fail "no Dockerfile at the repository root — there is nothing to build"
fi

# 2. The one number the service and the container must agree on. Cloud Run
#    routes to the port named at deploy time; uvicorn binds the port named in
#    CMD. If they differ, the container starts and no request ever reaches it.
CMD_PORT="$(sed -n 's/.*"--port",[[:space:]]*"\([0-9]\{1,\}\)".*/\1/p' Dockerfile | head -n 1)"
if [ "$SERVICE_PORT" = "$CMD_PORT" ]; then
    pass "the service port $SERVICE_PORT matches the port the container binds"
else
    fail "the service port '$SERVICE_PORT' does not match the container's port '${CMD_PORT:-unset}'"
fi

# 3. The built frontend. The image has no Node stage on purpose — the bundle is
#    committed and ships through 'COPY app ./app'. Untracked, the build
#    succeeds and serves pages with no interface on them.
MISSING_BUNDLE=0
for asset in app/ui/static/island/single.js app/ui/static/island/batch.js app/ui/static/island/style.css; do
    if ! git ls-files --error-unmatch "$asset" >/dev/null 2>&1; then
        MISSING_BUNDLE=1
        echo "        untracked: $asset" >&2
    fi
done
if [ "$MISSING_BUNDLE" -eq 0 ]; then
    pass "the built island bundle is tracked and will ship in the image"
else
    fail "the built island bundle is not tracked — the deploy would serve pages with no interface"
fi

# 4. Every path the build copies in.
COPY_MISSING=0
while read -r src; do
    if [ ! -e "$src" ]; then
        COPY_MISSING=1
        echo "        missing: $src" >&2
    fi
done < <(awk '/^COPY /{for (i = 2; i < NF; i++) if ($i !~ /^--/) print $i}' Dockerfile)
if [ "$COPY_MISSING" -eq 0 ]; then
    pass "every path the Dockerfile copies is in the tree"
else
    fail "the Dockerfile copies paths that are not in the tree"
fi

# 5. Only committed work is deployed. Uncommitted changes are not an error, but
#    deploying without them silently is the surprise worth naming.
if [ -n "$(git status --porcelain)" ]; then
    echo "  note  the working tree has uncommitted changes; only the current commit is deployed"
else
    pass "the working tree is clean"
fi

if [ "$FAILED" -ne 0 ]; then
    echo "Preflight failed. Nothing was deployed." >&2
    exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
    echo "Preflight passed. Not deploying, because --check was given."
    exit 0
fi

if [ -z "${TTB_GCP_PROJECT:-}" ]; then
    echo "Set TTB_GCP_PROJECT to the Google Cloud project to deploy into." >&2
    exit 2
fi

if ! command -v gcloud >/dev/null 2>&1; then
    echo "gcloud is not on PATH. Install the Google Cloud CLI and run 'gcloud auth login'." >&2
    exit 2
fi

# Export the commit rather than the directory. This is what keeps an untracked
# file out of the upload, and it makes the deployed image a function of the
# commit alone.
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
git archive --format=tar HEAD | tar -x -C "$STAGING"

if [ "${TTB_PUBLIC:-0}" = "1" ]; then
    ACCESS_FLAG=--allow-unauthenticated
else
    ACCESS_FLAG=--no-allow-unauthenticated
fi

echo "Deploying ${SERVICE} to ${REGION} in ${TTB_GCP_PROJECT}. Cloud Build builds the image."
gcloud run deploy "$SERVICE" \
    --project "$TTB_GCP_PROJECT" \
    --region "$REGION" \
    --source "$STAGING" \
    --port "$SERVICE_PORT" \
    --cpu "$CPU" \
    --memory "$MEMORY" \
    --concurrency "$CONCURRENCY" \
    --max-instances "$MAX_INSTANCES" \
    --min-instances 0 \
    --timeout "$TIMEOUT" \
    --cpu-boost \
    --startup-probe "$STARTUP_PROBE" \
    --set-env-vars VISION_MODE=local \
    "$ACCESS_FLAG"

if [ "${TTB_PUBLIC:-0}" = "1" ]; then
    echo "Deployed open: the service URL answers anyone. The two-instance cap is"
    echo "the only bound on the meter. Delete the service when the review is done."
    exit 0
fi

# The one identity allowed to call the service. Without this the deploy is
# reachable by nobody at all, including the edge, which is the safe direction to
# fail but not a working product.
INVOKER_SA="${TTB_INVOKER_SA:-ttb-edge-invoker@${TTB_GCP_PROJECT}.iam.gserviceaccount.com}"
echo "Granting ${INVOKER_SA} permission to invoke ${SERVICE}."
gcloud run services add-iam-policy-binding "$SERVICE" \
    --project "$TTB_GCP_PROJECT" \
    --region "$REGION" \
    --member "serviceAccount:${INVOKER_SA}" \
    --role roles/run.invoker >/dev/null

echo "Deployed. The service URL is printed above; it answers only a caller"
echo "bearing an ID token for ${INVOKER_SA}."
