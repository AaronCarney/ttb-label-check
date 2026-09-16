# 0016. The country-of-origin abbreviation table is not built

Date: 2026-09-16

## Choice

The country-of-origin check reads one form of the country's name: the English name the application
declares, appearing as whole words inside whatever wording the label wraps around it — "PRODUCT OF
LITHUANIA", "DISTILLED IN IRELAND". It does not read the other forms customs marking rules accept.

Where the label states an origin and it does not carry the declared country in that one form, the
check reports that it could not settle the question, at warn severity, and a reviewer reads the
label. It does not reject. The reason code `ORIGIN.MATCH.APPLICATION_LABEL_DISAGREE` carries that
meaning and its registry entry says so.

An import whose label carries **no** origin statement at all still fails, at reject severity, under
`ORIGIN.PRESENCE.MISSING`. Nothing was stated there, so there is nothing to interpret.

The README lists the unread forms as a limitation.

## Why

19 CFR §134.45(b) and (c) accept more than the English name:

- the name of the country in the language of the country — "HECHO EN MEXICO", "PRODUCTO DE ESPAÑA";
- an abbreviation that "unmistakably indicates" the country — "U.K.", "Gt. Britain";
- the adjectival form of the country's name — "Irish", "Italian";
- a variant English spelling that clearly indicates the country.

The regulation gives these by example and by test — "unmistakably indicates" — not as a list. There
is no table in the CFR to load. Building one means writing it: choosing, per country, which
abbreviations and which adjectival forms are unmistakable, and being wrong about a label is worse
than not checking it.

That decides the branch as much as the table. Before this change the check rejected any origin
statement it could not read, which means it rejected a compliant import that wrote its country in
Spanish, or as an adjective, or as an abbreviation — three forms the law expressly allows. A
verdict of "reject" asserts the label is wrong. This check cannot tell "the label names a different
country" from "the label names the right country in a form I do not read", and a check that cannot
tell those apart must not claim the first.

## Alternatives rejected

- **Build the table now.** It is a per-country data set with a judgement call in every row, and this
  lane's remit is the comparison, not the reference data. An unbuilt check named in the README costs
  less than a built check that reports a wrong verdict, which is the project's standing rule when
  correctness and breadth pull against each other.
- **Keep rejecting on an unrecognised origin statement.** It rejects compliant imports. Three labels
  in the corpus state their origin in a form the check reads; the failure mode is for the ones that
  do not, and TTB approved labels that do not.
- **Pass an unrecognised origin statement.** It reports a check as made and passed when the two
  sides were never lined up — the failure this project set out to avoid.
- **Translate with the model reader.** `docs/decisions/0009` removed the model reasoning layer.
  Putting a language judgement back into a compliance verdict would make the answer depend on a
  model's output rather than on a rule a reviewer can check.

## The cost, stated

The check can no longer distinguish "the label names a different country" from "the label names the
right country in a form this product does not recognise", so **both reach a reviewer**. A label that
genuinely names the wrong country is not rejected outright; it is flagged for a person. That is the
trade this product chooses: a wrong verdict on a real label is the one failure it cannot have, and
an extra review is not a wrong verdict.

## Constraint that decided it

A check that cannot be made must not be reported as made, and a verdict must not claim more than the
evidence supports. Between rejecting compliant imports and asking a person, the check asks a person,
and the README says which forms it does not read.
