# 0003. How build choices are judged

Date: 2026-09-15

## Choice

Every build choice (scope, extraction, stack, host) is judged by these criteria, in this order. A
choice that fails an earlier criterion is out, however well it does on a later one.

1. **It meets the firmest asks, measured on the deployed prototype with real labels.** Results
   within about 5 seconds per label (Sarah); the warning checked word for word, with its heading in
   capitals and bold (Jenny); trivial differences judged as the same value (Dave). Vendor figures and
   fake labels do not count as evidence.
2. **A working core comes first.** The common label elements across all three beverage types are
   checked before any one type is checked in depth, and batch upload is part of the core.
3. **Every result can be checked by the agent.** It shows which element, what was read, what was
   expected and which rule applied. Where the prototype cannot tell, it says "needs review" rather
   than guess.
4. **Anyone can use it unaided.** A public URL with no sign-in, sample labels one click away, and a
   README that is enough to run it (Sarah's 73-year-old benchmark, and the brief's deliverables).
5. **It fits Marcus's limits and has a path through the firewall.** Every outbound service is named.
   The part that calls an outside service can be replaced by one that runs inside the agency's
   network without a rewrite. Each option states what it would cost at the agency's volume and what
   federal authorization it would need.
6. **It is the smallest thing that meets 1 to 5 in the time left.** Nothing is built only for show.
7. **It is free or cheap.** No money goes on anything that is only cosmetic.

What the README and the results claim is limited to what was measured, and says under what
conditions.

## Alternatives rejected

- **Engineering merit alone.** For a federal agency, cost and authorization can overturn an
  engineering pick. Leaving them to a later review lets the design assume away limits it did not
  know about.
- **Weighted scores summed across criteria.** A strong score on cost could then buy back a missed
  5-second limit, and the brief's failed pilot shows that a slow tool is abandoned whatever else it
  does well.

## Constraint that decided it

Stakeholder priority (decision 0002), and the brief's line that "a working core application with
clean code is preferred over ambitious but incomplete features".
