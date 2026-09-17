"""The deploy must hold traffic off an instance until its models are loaded.

Without a startup probe Cloud Run routes a request the moment uvicorn binds the
port, and the OCR models load lazily on first use - inside that request. On the
live service that load pushed the evaluation past the evaluator's five-second
SLA, so the first person to click got ENGINE.SLA.TIMEOUT and an empty result.
It is not a first-boot-only fault: the deploy serves one request per instance,
so every scale-up makes another instance that would do the same.

These assert the deploy script still configures the probe. Dropping the flag is
silent - the deploy succeeds and the fault comes back - so it is worth a test
rather than a comment.
"""

import re
from pathlib import Path

import pytest

SCRIPT = Path("scripts/deploy.sh")


@pytest.fixture(scope="module")
def script() -> str:
    return SCRIPT.read_text()


def _probe_settings(script: str) -> dict[str, str]:
    """The probe's key=value pairs, as the script hands them to gcloud."""
    match = re.search(r"^STARTUP_PROBE=(\S+)", script, re.M)
    assert match, "scripts/deploy.sh no longer defines STARTUP_PROBE"
    return dict(pair.split("=", 1) for pair in match.group(1).split(",") if "=" in pair)


def test_deploy_passes_a_startup_probe(script: str):
    """The flag reaches gcloud. Defining the value and not passing it is the
    failure this catches."""
    assert "--startup-probe" in script, (
        "scripts/deploy.sh does not pass --startup-probe, so Cloud Run will "
        "route a request before the models are loaded"
    )


def test_the_probe_is_the_endpoint_that_loads_the_models(script: str):
    """/healthz, not /. It builds the same evaluator a submission builds and
    answers 503 until that succeeds; any other path returns 200 while the
    models are still cold, which would make the probe a no-op."""
    assert _probe_settings(script).get("httpGet.path") == "/healthz"


def test_timeout_is_smaller_than_the_period(script: str):
    """Cloud Run rejects the revision otherwise, and it rejects the whole
    deploy, not just the probe. The first version of this probe had
    timeoutSeconds=10 against periodSeconds=5 and would have failed on contact.

    Container#Probe: "Must be smaller than periodSeconds".
    """
    settings = _probe_settings(script)
    timeout = int(settings["timeoutSeconds"])
    period = int(settings["periodSeconds"])
    assert timeout < period, (
        f"timeoutSeconds={timeout} is not smaller than periodSeconds={period}; "
        "Cloud Run will reject the revision"
    )


def test_the_probe_allows_longer_than_a_model_load(script: str):
    """A cold container reads three ONNX files off disk. Allow well over that,
    so a slow disk does not fail an otherwise healthy revision."""
    settings = _probe_settings(script)
    allowed = int(settings["periodSeconds"]) * int(settings["failureThreshold"])
    assert allowed >= 60, (
        f"the probe gives up after {allowed}s; a cold model load needs more headroom"
    )
