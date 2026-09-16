# 0006. The health warning's typography rules are out of scope

Date: 2026-09-15

## Choice

Four rules in the health-warning pack are switched off, each carrying the reason in its own `notes`
field:

| Rule | What it checks | Citation |
|---|---|---|
| `common.warning.contrasting_bg` | The warning sits on a contrasting background | §16.22(a)(1) |
| `common.warning.cpi_max` | Characters per inch, against the §16.22(a)(4) table | §16.22(a)(4) |
| `common.warning.type_size_min` | Minimum type size | §16.22(b) |
| `common.warning.separate_apart` | The warning is separate and apart from other information | §16.21 |

The app checks the warning's words and their order, that "GOVERNMENT WARNING" is present, and that
those first two words are in capitals and bold. It does not check contrast, characters per inch,
type height or isolation. The README states this as a limitation.

A fifth rule, `common.warning.heading_phrase`, is switched off as redundant, not as out of scope:
it asked for evidence named `warning_heading` that no reader produces, so it never ran, and
`common.warning.heading_caps_bold` already checks the same two words along with the capitals and
bold weight §16.22(a)(2) requires.

## Why

Three of the four cannot be measured from the only input the app has:

- Type height and characters per inch are physical measurements. §16.22(b) sets the minimum in
  millimetres and keys it to container size — 1 mm at 237 mL or less, 2 mm up to 3 L, 3 mm above
  that. Turning pixels into millimetres needs the image's physical scale, which a photograph does
  not carry (`docs/reference/health-warning.md`, "What an image check can and cannot see").
- `type_size_min` as written compares a point value against a fixed 2.0 and ignores container size
  altogether, so a pass from it does not mean what its citation says it means.
- Contrast needs the colour of the text and of the surface behind it, sampled at the warning's
  exact position. No reader in this app reports either.

`separate_apart` is different: isolation is a relationship between blocks on the page, and a
photograph does carry it. No reader measures it today, so the rule is unbuilt rather than
unbuildable.

The deciding fact is that TTB does not check these itself. The instructions to Form TTB F 5100.31
say TTB "does not routinely review submitted labels for compliance with applicable requirements for
mandatory label information regarding type size, characters per inch, or contrasting background"
(`docs/reference/health-warning.md`, TTB guidance). A prototype that rejects labels on three
measurements the agency does not routinely review would be wrong about the job.

## Alternatives rejected

- **Leave them enabled.** Each reads a key no reader emits, so each returns a failure on every
  label, compliant ones included. The product's whole purpose is to tell a compliant label from a
  non-compliant one; enabled, these four make every submission a rejection.
- **Pass when the measurement is absent.** This reports a check as made and passed when nothing was
  measured. It is the exact failure the project set out to avoid: a document or a screen claiming a
  check the code only stubbed.
- **Build the measurements.** Contrast needs colour sampling at the warning's position; the other
  two need a known physical scale, which means the container size plus a fiducial or a calibration
  step in the upload. That is a larger piece of work than the brief asks for, and the brief's own
  account of the warning is Jenny's: the words exactly, with "GOVERNMENT WARNING:" in capitals and
  bold. That is what `verbatim` and `heading_caps_bold` check.

## Constraint that decided it

A check that cannot be made must not be reported as made. Between failing every label and claiming
a measurement that never happened, the honest third option is to not run the rule and to say so in
the README.
