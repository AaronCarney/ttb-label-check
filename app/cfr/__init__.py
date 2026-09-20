"""The regulation text behind a finding's citation.

A finding names the section it rests on. This package turns that name into the
sections it refers to (`citations`) and answers with the wording of those
sections from text pinned in `assets/cfr/` (`corpus`).

Nothing here reaches the network. The text is fetched once by
`tools/fetch_cfr.py`, committed with the hash and the date it was retrieved, and
checked against the eCFR by `tests/test_cfr_corpus_matches_ecfr.py`, which runs
only when asked. The product's promise of no outbound call is why
(`README.md`); the promise that the wording is the regulation's own, and not
something typed in by hand, is why the fetcher exists at all
(`docs/decisions.md#0046`).
"""
