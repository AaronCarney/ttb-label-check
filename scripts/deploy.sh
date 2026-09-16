#!/usr/bin/env bash
#
# Deploy this repository to its Hugging Face Space (decision 0023).
#
# The Space builds the Dockerfile at the repository root and reads its own
# configuration from the YAML block at the top of README.md, so the deploy is a
# git push and nothing else. There is no build pipeline to keep in step.
#
#   scripts/deploy.sh --check   Run every preflight that needs no network, then
#                               stop. Proves the repository is deployable
#                               without making anything public.
#   scripts/deploy.sh           Run the preflights, then push.
#
# Pushing makes the app publicly reachable, which is the owner's call to make.
#
# Environment:
#   TTB_SPACE   The Space to push to, as "owner/name". Required for the push,
#               not for --check.
#   HF_TOKEN    A write token, if git is not already configured for
#               huggingface.co. Optional.

set -euo pipefail

CHECK_ONLY=0
case "${1:-}" in
    --check) CHECK_ONLY=1 ;;
    "") ;;
    *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."

FAILED=0
fail() { echo "  FAIL  $*" >&2; FAILED=1; }
pass() { echo "  ok    $*"; }

echo "Preflight:"

# 1. The image the Space builds.
if [ -f Dockerfile ]; then
    pass "Dockerfile is present"
else
    fail "no Dockerfile at the repository root — the Space has nothing to build"
fi

# 2. The Space card. Without 'sdk: docker' the platform picks a different
#    runtime and never looks at the Dockerfile.
if head -n 1 README.md | grep -qx -- '---' && grep -qx 'sdk: docker' README.md; then
    pass "README declares a Docker Space"
else
    fail "README does not open with a Space card declaring 'sdk: docker'"
fi

# 3. The one number the card and the container must agree on. The platform
#    routes to app_port and defaults it to 7860; uvicorn binds the port named in
#    CMD. If they differ, the Space comes up healthy and serves a blank page.
CARD_PORT="$(sed -n 's/^app_port:[[:space:]]*\([0-9]\{1,\}\).*/\1/p' README.md | head -n 1)"
CMD_PORT="$(sed -n 's/.*"--port",[[:space:]]*"\([0-9]\{1,\}\)".*/\1/p' Dockerfile | head -n 1)"
if [ -n "$CARD_PORT" ] && [ "$CARD_PORT" = "$CMD_PORT" ]; then
    pass "app_port $CARD_PORT matches the port the container binds"
else
    fail "app_port '${CARD_PORT:-unset}' does not match the container's port '${CMD_PORT:-unset}'"
fi

# 4. The built frontend. The image has no Node stage on purpose — the bundle is
#    committed and ships through 'COPY app ./app'. Untracked, the Space builds
#    cleanly and serves pages with no interface on them.
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

# 5. Every path the build copies in.
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

# 6. Only committed work is pushed. Uncommitted changes are not an error, but
#    deploying without them silently is the surprise worth naming.
if [ -n "$(git status --porcelain)" ]; then
    echo "  note  the working tree has uncommitted changes; only commits are pushed"
else
    pass "the working tree is clean"
fi

if [ "$FAILED" -ne 0 ]; then
    echo "Preflight failed. Nothing was pushed." >&2
    exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
    echo "Preflight passed. Not pushing, because --check was given."
    exit 0
fi

if [ -z "${TTB_SPACE:-}" ]; then
    echo 'Set TTB_SPACE to the Space to push to, as "owner/name".' >&2
    exit 2
fi

REMOTE="https://huggingface.co/spaces/${TTB_SPACE}"
if [ -n "${HF_TOKEN:-}" ]; then
    REMOTE="https://user:${HF_TOKEN}@huggingface.co/spaces/${TTB_SPACE}"
fi

echo "Pushing to ${TTB_SPACE}. The Space rebuilds on the push."
git push "$REMOTE" HEAD:main
echo "Pushed. Watch the build at https://huggingface.co/spaces/${TTB_SPACE}"
