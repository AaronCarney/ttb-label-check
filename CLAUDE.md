# ttb-label-check

Read `docs/PRD.md` first. It is the scope authority once approved; while it reads `Status: draft`,
it is not one yet.

## Commands

No stack is chosen yet, so there are no build, test or run commands. Add them here when there are.

| Task | Command |
|---|---|

## Layout

| Path | Holds |
|---|---|
| `ARCHITECTURE.md` | How the system is laid out, and where the code that does each thing lives. |
| `CHANGELOG.md` | What changed in each version. |
| `docs/README.md` | Index of every document under `docs/`, one line each. |
| `docs/PRD.md` | What is being built, for whom, and why. |
| `docs/PRD-decisions.md` | Every change to the PRD's text, once it has been approved. |
| `docs/decisions/NNNN-*.md` | One settled build decision per file, numbered. |
| `docs/research/YYYY-MM-DD-*.md` | One dated finding per file. |
| `docs/plans/YYYY-MM-DD-*.md` | One plan per file. |
| `specs/NNNN-slug/` | One directory per specified change. |
| `src/` | Application code. |
| `tests/` | Tests; `tests/fixtures/` holds their input files. |

## Conventions

- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `build:`, `ci:`),
  imperative mood, one coherent change per commit.
- Commit with an explicit pathspec, `git commit -o <paths>`, never a bare `git commit`.
- No credential, key or token is ever committed. `.env` files stay local; `.env.example` is the
  committed template.
