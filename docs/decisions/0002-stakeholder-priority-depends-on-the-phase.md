# 0002. Stakeholder priority depends on the phase

Date: 2026-09-15

## Choice

Four people in the brief shape what the prototype does. While it is a prototype, their asks weigh
in this order, with the weights used when two asks pull against each other:

1. **Sarah Chen, Deputy Director of Label Compliance: 100%.** She sponsors the work, decides whether
   it goes further, and set its firmest limits: results in about 5 seconds, a tool her 73-year-old
   mother could figure out with "no hunting for buttons", and batch uploads of 200 to 300 labels.
   The batch ask is also Janet's, of the Seattle office, who is named but was not interviewed.
2. **Dave Morrison, senior compliance agent of 28 years: 90%.** Whether agents take the tool up turns
   on reactions like his. He asks for judgement on trivial differences ("STONE'S THROW" on the label
   against "Stone's Throw" in the application) and for a tool that does not make his work harder.
3. **Jenny Park, junior compliance agent of 8 months: 80%.** She names the strictest check, the
   warning word for word with "GOVERNMENT WARNING:" in capitals and bold, and the hardest input:
   photos taken at angles, in bad light or with glare, which she herself places as possibly out of
   scope.
4. **Marcus Williams, IT Systems Administrator: 70%.** His limits bind any production path more than
   the prototype: no COLA integration, nothing sensitive stored, and outbound traffic blocked to many
   domains. For the prototype he asks: "Just don't do anything crazy."

In production the order changes. Marcus and the IT leadership above him become the ones who decide,
through FedRAMP, authority to operate and PII review, and Dave's informal influence counts for less.
The prototype is built for the first order and records how it would meet the second.

## Alternatives rejected

- **Weighing all four equally.** It hides whose asks decide whether the prototype goes further.
- **A power and interest grid alone.** It files Dave as low power, although adoption turns on senior
  agents like him, and it gives Marcus most weight in the phase where he asked for least.

## Constraint that decided it

The brief (`specs/0001-label-verification/PRD.md`): Sarah's three asks, which it sets in bold;
Dave's "You need judgment"; Jenny's "It has to be **exact**"; and Marcus's "for a prototype? Just
don't do anything crazy."
