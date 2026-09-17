# Accessibility exceptions

`tests/manual/a11y-smoke.md` makes any failed step of the manual screen-reader
pass a release blocker. This folder is the one way past that: an exception filed
here and reviewed by the project owner lets a release go out with a known,
written-down accessibility failure in it.

Nothing else belongs here. An accessibility defect that is going to be fixed is a
defect, not an exception, and it needs no file.

## Filing one

One file per exception, named `YYYY-MM-DD-<short-slug>.md`, holding:

- **What fails** — the checklist step, and what a screen-reader user actually
  gets instead of what the step asks for.
- **Which criterion** — the WCAG 2.0 A or AA criterion it misses, from
  `docs/reference/accessibility.md`.
- **Who it affects, and how badly** — whether the affected user can still finish
  the task by another route, or cannot finish it at all.
- **Why it is shipping anyway** — the constraint that made fixing it first the
  wrong call.
- **When it is revisited** — a date or the condition that closes it.
- **Who approved it** — the project owner, and the date they did.

An exception with no approval is not an exception, and the release is still
blocked.

## What is on file

Nothing. No accessibility exception has been filed, so every checklist step in
`tests/manual/a11y-smoke.md` is still a release blocker with no way around it.
