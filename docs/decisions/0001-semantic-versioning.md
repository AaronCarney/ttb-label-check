# 0001. Semantic Versioning

Date: 2026-09-10

## Choice

The project's version follows Semantic Versioning 2.0.0 and reads `MAJOR.MINOR.PATCH`. It starts at
`0.0.0`. Once a stack is chosen, the version lives in that stack's package manifest.

## Alternatives rejected

- **Calendar versioning** (`YYYY.MM.N`). It dates a release but cannot say whether anything that
  worked before has stopped working, which is the question a reviewer asks of a new version.
- **No version.** Dates and commit hashes cannot mark a release point that someone discussing the
  work can name.

## Constraint that decided it

Every change needs a number that says whether it breaks something that worked before. Semantic
Versioning is the scheme whose positions carry that meaning.
