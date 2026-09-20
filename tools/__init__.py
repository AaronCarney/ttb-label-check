"""Tools that build committed assets, run by hand and not by the app.

Nothing under `app/` imports this package. `fetch_cfr` retrieves the regulation
text the citation panel shows and writes it into `assets/cfr/` with the hash and
the date it was retrieved, so the running service never calls out to get it.
"""
