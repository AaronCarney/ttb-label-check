# 0004. The prototype runs locally from a clone, and also deploys

Date: 2026-09-15

## Choice

The product is built to run on a reviewer's own machine first: a clone, one install step and one
command to start, with everything it needs contained in the repository. It needs no account, no API
key and no outbound network call to do its job.

Deployment is a thin layer over that same app — a container image and a start command — so a public
URL is a short step at the end rather than a separate build.

Both are delivered. The brief asks for a README with setup and run instructions *and* a deployed
application URL; they are separate deliverables, not alternatives.

## Alternatives rejected

- **Deployed only, with the README pointing at the URL.** It leaves deliverable 1's "setup and run
  instructions" unmet, and "attention to requirements" is one of the six evaluation criteria.
- **Local only, with deployment left as a stated limitation.** It leaves deliverable 2 unmet. It
  also fails the reviewer who wants to test the prototype without installing anything.
- **Building for the host first and making local work follow.** Hosted-first designs acquire
  dependencies on the host's storage, secrets and networking, and the agency firewall is precisely
  the constraint this product has to survive.

## Constraint that decided it

The brief's Deliverables section, which lists "README with setup and run instructions" under the
repository and "Deployed Application URL — Working prototype we can access and test" as a second
item; and the owner's instruction of 2026-09-15 that this version runs locally, with a cloud option
if time allows, and that "everything we include [is] contained within the app itself if possible to
make installing simple".
