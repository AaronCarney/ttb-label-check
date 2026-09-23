#!/usr/bin/env bash
#
# The checks every commit passes before it is pushed or deployed (decision 0067).
#
# They run on this machine, not on a hosted runner: the lint, the formatter, the
# type check and the whole suite with its coverage report. A pass is recorded
# against the exact commit that was tested, and `.githooks/pre-push` and
# `scripts/deploy.sh` both read that record, so a commit nothing has tested
# cannot leave the machine or reach the service by accident.
#
# The tree must be clean. A pass over uncommitted changes proves nothing about
# the commit, so the checks refuse to start rather than record a verdict for a
# tree nobody can name.
#
# The browser tests skip themselves when pnpm is missing and the suite still
# reports green, so this refuses to run without it rather than record a pass
# that proved nothing about the interface.
#
# Environment:
#   TTB_CI_RECORD_DIR   Where passes are recorded, one empty file per commit.
#                       Defaults to ci-passed inside the repository's git
#                       directory, so the record never enters a commit.

set -euo pipefail

cd "$(dirname "$0")/.."

RECORD_DIR="${TTB_CI_RECORD_DIR:-$(git rev-parse --git-path ci-passed)}"

if [ -n "$(git status --porcelain)" ]; then
    echo "The working tree has uncommitted changes, so a pass would not belong to any commit." >&2
    echo "Commit or stash them, then run this again. Nothing was checked." >&2
    exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
    echo "pnpm is not on PATH, so the browser tests would skip and the run would prove" >&2
    echo "nothing about the interface. Install it, then run this again." >&2
    exit 1
fi

# The pnpm that builds the island is the one `frontend/package.json` declares.
# One taken from whatever was newest on the day is how a major version that moved
# where pnpm reads its settings arrived without anyone choosing it.
DECLARED="$(sed -n 's/.*"packageManager": *"pnpm@\([^"]*\)".*/\1/p' frontend/package.json)"
if [ "$(pnpm --version)" != "$DECLARED" ]; then
    echo "pnpm $(pnpm --version) is installed, but frontend/package.json declares ${DECLARED}." >&2
    echo "Install that version (corepack enable, or npm install --global pnpm@${DECLARED})." >&2
    exit 1
fi

COMMIT="$(git rev-parse HEAD)"
echo "Checking ${COMMIT}."

uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest --cov --cov-report=term

# The suite writes nothing tracked, and HEAD cannot move under a running check
# without someone committing mid-run. Either would make the pass belong to a tree
# other than the one tested, so both are checked before it is recorded.
if [ "$(git rev-parse HEAD)" != "$COMMIT" ] || [ -n "$(git status --porcelain)" ]; then
    echo "The tree changed while the checks ran, so no pass was recorded for ${COMMIT}." >&2
    git status --short >&2
    exit 1
fi

mkdir -p "$RECORD_DIR"
: > "$RECORD_DIR/$COMMIT"
echo "Passed. Recorded ${COMMIT} as checked."
