# 0007. A class-and-type designation includes its standard of identity

Date: 2026-09-15

## Choice

The class-and-type rules pass when the label's designation **includes** a recognised class or type
as a run of whole words, not when it equals one. The validator `enumerated_match` takes a new
`match_mode` parameter: `exact` stays the default, and the four class-and-type rules set
`contains_designation`.

The rules changed: `spirits.class_type.present`, `spirits.class_type.matches_soi`,
`wine.class_type.present`, `malt.class_type.present`.

Each list also gains the spellings that appear on real labels. §5.143(b) permits "whisky" or
"whiskey", so both are listed for every whisky entry.

## Why

A label does not carry a bare standard of identity. It carries the standard with the qualifiers the
regulation permits around it:

| On the label | The standard it declares |
|---|---|
| KENTUCKY STRAIGHT BOURBON WHISKEY | bourbon whisky |
| CALIFORNIA TABLE WINE | table wine |
| INDIA PALE ALE | ale |

Checked by equality against a list of bare standards, every one of those fails. The three qualifier
kinds are all required or permitted by the regulations the rules cite: the state of distillation
must appear adjacent to the designation for the named whisky types (§5.66(f)), and "straight" is
part of the standard itself (§5.143).

Whole words, not substrings. A substring test would find "gin" inside "Virginia" and pass a wine as
a spirit.

## Alternatives rejected

- **List the full designations.** Every state of distillation, crossed with straight and bottled-in-bond
  and single-barrel, crossed with both spellings of whisky. The list would run to thousands of
  entries and would still miss the next one.
- **Match the last word only.** "KENTUCKY STRAIGHT BOURBON WHISKEY" ends in "whiskey", which is a
  class, so the shallow rule would pass — but the deep rule asks for the *type*, bourbon whisky, and
  the last word alone cannot tell bourbon from rye.
- **Normalise spellings in Python.** A whisky/whiskey equivalence in the validator puts a fact about
  the regulation in code, where the rule pack is the place for it. The allow-list is already data;
  the spellings belong beside it.

## Constraint that decided it

Rules decide and a reader only reports, so a rule has to be right about what the regulation asks.
The regulation asks for a designation that declares a recognised standard of identity, not for a
label that repeats the standard's name and nothing else.
