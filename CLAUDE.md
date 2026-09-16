# ttb-label-check

Checks an alcohol beverage label against the data in its TTB label application, and reports which
fields match, which do not, and which need a human look.

Read `docs/PRD.md` first. It is the scope authority once approved; while it reads `Status: draft`,
it is not one yet.

## Commands

Python dependencies are managed with `uv` against a committed `uv.lock`. A bare `python` resolves
outside the project environment and fails to import `app`, so every Python command runs through
`uv run`.

| Task | Command |
|---|---|
| Install dependencies | `uv sync --frozen` |
| Run the app | `uv run uvicorn app.main:app --port 8000` |
| Run the app with reload | `uv run task demo` |
| Run the tests | `uv run pytest -q` |
| Score the reader on real labels | `uv run python -m eval.read_accuracy` |
| Install frontend dependencies | `cd frontend && pnpm install` |
| Build the frontend island | `cd frontend && pnpm build` |
| Run the frontend tests | `cd frontend && pnpm test` |

Editing `frontend/src/tokens/globals.css` requires a frontend build, and the built
`app/ui/static/island/style.css` is committed alongside the source change;
`tests/test_island_build_clean.py` fails on a difference between them.

## Stack

Python 3.12 with FastAPI and pydantic; the rules the app applies are a YAML pack under `rules/`,
loaded and validated at startup rather than written in Python. The interface is a Jinja page shell
with a React island mounted into it, built by Vite. A label is read by one of two extractors behind
a single interface — a local OCR reader that ships in the app and needs no outbound call, which is
the default, and a cloud vision reader (`docs/decisions/0005`).

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
| `docs/reference/` | Rule text the app checks, each copy pinned to the date it was read. |
| `specs/NNNN-slug/` | One directory per specified change. |
| `app/` | Application code. `ARCHITECTURE.md` maps it. |
| `rules/` | The YAML rule pack: one rule per label element, with its CFR citation. |
| `assets/` | Text the rules compare against, such as the health warning, pinned by hash. |
| `eval/` | Scores the reader against the real labels and their ground truth. |
| `frontend/` | React island source; its build output lands in `app/ui/static/`. |
| `tests/` | Tests; `tests/fixtures/` holds their input files. |

## Conventions

- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `build:`, `ci:`),
  imperative mood, one coherent change per commit.
- Commit with an explicit pathspec, `git commit -o <paths>`, never a bare `git commit`.
- No credential, key or token is ever committed. `.env` files stay local; `.env.example` is the
  committed template.
- A rule the app applies lives in the YAML pack with its CFR citation, not in Python. Validator code
  carries no regulation citation; `tests/test_validator_registry.py` enforces that.
- A comment or docstring explains what the code does and why, and cites this project's own records
  (`docs/decisions/`, `docs/PRD.md`) or the CFR. It does not reference a planning stage, a work
  cycle, or a document that does not exist in this repository.
