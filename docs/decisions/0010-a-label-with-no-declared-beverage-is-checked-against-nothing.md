# 0010. A label filed without a beverage class is checked against nothing

Date: 2026-09-16

## Choice

**The application decides which rules run, and where it names no beverage, no rule runs.**

An upload that arrives without an application — the drop-zone on the landing page accepts one — is
no longer checked against the distilled-spirits rules. It is checked against nothing. The reply
still carries what the reader read off the label, and its audit trail carries one row saying no
rule set could be chosen:

```
rule_id:      ENGINE.RULE_PACK.NOT_SELECTED
disposition:  needs_review
evidence_ref: rule_pack/none
```

**Every reply names the rules that produced it**, whether or not any ran. Where the application
does name a beverage, the same row reads:

```
rule_id:      ENGINE.RULE_PACK.SELECTED
disposition:  not_applicable
evidence_ref: rule_pack/wine
```

`rule_pack/wine` means the wine rules together with the ones that apply to every beverage. The row
is written before the label is read, so a reply cut short by an unreadable image or by the
five-second limit carries it too.

## Why

**The reader's own answer is not evidence.** Both readers tag every reading they produce
`spirits` — `app/vision/local.py:211,242` and `app/vision/cloud.py:265,314` — because nothing on a
bottle reliably distinguishes a wine from a spirit and nothing ever asked them to try. Until now
`app/services/evaluator.py` replaced that tag only when the application named a beverage, so a wine
label filed without an application inherited `spirits` and was checked against the spirits rules.

That is the one failure this product cannot have. The spirits rules include the standards of
identity: `spirits.class_type.matches_application` asks whether the designation on the label is one
of the classes Part 5 Subpart I defines. A wine label reading `TABLE WHITE WINE` is not, so the app
would have reported a compliant wine label as failing a rule that never applied to it — a rejection
manufactured out of a guess nobody made.

**No reply is better than a wrong one here.** The alternative is to keep guessing, and a guess that
is right two times in three is worse than an honest refusal, because a reviewer cannot tell the two
thirds from the third.

**Nothing in the rule model can express "whatever the beverage is".** Every rule declares
`applies_to_classes`, and `app/rules/yaml_engine.py:123` selects a rule only where a reading's class
is in that list. The eight health-warning rules in `rules/common/health_warning.yaml` list all three
beverages, and every other rule lists exactly one — checked across all five rule files on
2026-09-16. So the warning rules are already independent of the beverage in substance. What stops
them running is the mechanism: `FieldObservation.beverage_class` is a required three-valued field
(`app/schemas/extracted.py:61`) with no way to say "not stated", so a reading has to claim a
beverage before any rule will look at it, including the eight that do not care which.

Making those eight run without a beverage means changing the reading model, the rule model, the
loader, the engine and the health-warning rule file. That is the right fix and it is not this one.
Until it lands, an upload with no application gets no health-warning check.

## What this costs

**An image on its own no longer gets the checks that need no application** — that the label carries
a brand, a class, a net-contents statement, and the §16.21 government warning. It gets the reading
and a statement that nothing was checked.

This is a loss on the demonstration path, where a grader drops in an image to see the app work, and
it is the brief's most prominent single requirement that is lost. It is recovered in full by giving
the rule model a way to say "applies whatever the beverage is", which is recorded for the
consolidation pass with the five files it touches.

**One test states the behaviour this replaces** and now fails:
`tests/test_ui_end_to_end_comparison.py::test_without_an_application_nothing_is_compared_and_the_label_is_still_checked`
asserts that an image-only upload still runs the comparison rules and has them opt out. With no
beverage named, no comparison rule can be selected to opt out. The test is in another lane's files
and is handed to the consolidation pass with the replacement stated.

## Alternatives rejected

**Refuse the upload outright, with a 400 and "pick the beverage type".** The form already marks the
field required (`app/ui/templates/single.html:35`), and `app/services/application_form.py:152`
already refuses a form that fills in any other application field without it. Rejected because two
tests deliberately accept an image on its own —
`tests/test_ui_application_fields.py::test_an_image_on_its_own_still_evaluates` and the end-to-end
test above — so the product has already decided that an image alone is a thing a grader may submit.
Turning it away is a larger product change than the defect warrants, and it removes the reading as
well as the checks.

**Run the beverage-independent rules anyway, by tagging the reading with a fixed beverage and
discarding every result that came from a beverage-specific rule.** This keeps the health-warning
check on the image-only path, which is the strongest argument for it. Rejected because the tag
would be a claim the product cannot support: the reading, and every result built from it, would
carry `beverage_class: spirits` into the audit trail for a label nobody classified. Fixing a defect
whose shape is "the audit trail states a beverage nobody declared" by restating it more quietly is
not a fix.

**Run the rules once per beverage and keep the results common to all three.** Exact, and it needs no
fixed tag — a rule that applies to every beverage produces the same `rule_id` in all three runs, so
intersecting the three gives precisely the beverage-independent rules. Rejected for the same reason:
the readings still have to carry a beverage in each run, and the results kept still carry whichever
one was picked. It also runs the spirits standards-of-identity checks against a wine label three
times over to throw the answers away.

## Constraint that decided it

A reply that names no rules is honest about what it did not do. A reply built on a beverage nobody
declared is not, and the reviewer reading it has no way to tell.
