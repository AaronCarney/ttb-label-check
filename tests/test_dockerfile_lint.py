"""Lint the container build and the Space card without invoking docker.

`docker build` is not run here — it is minutes of CPU and this machine has a
thermal fault — so everything provable by reading the build inputs is proved by
reading them. Three of these checks exist because the failure they catch is only
visible at deploy time, when the reviewer is already looking at the URL:

* a `COPY` whose source is not in the tree, which fails the build;
* a `COPY` whose source `.dockerignore` excludes, which succeeds and ships an
  image missing a file the app opens on its first request;
* a Space `app_port` that disagrees with the port the container listens on,
  which serves a blank page.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "docker-compose.yml"
DOCKERIGNORE = ROOT / ".dockerignore"
README = ROOT / "README.md"
DEPLOY = ROOT / "scripts" / "deploy.sh"


def _copy_sources() -> list[str]:
    """Every build-context path the Dockerfile copies in.

    The last token of a `COPY` is the destination; `--from=` stages copy from an
    earlier image rather than from the build context, so they are skipped.
    """
    sources: list[str] = []
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("COPY "):
            continue
        tokens = stripped.split()[1:]
        if any(t.startswith("--from=") for t in tokens):
            continue
        sources.extend(t for t in tokens[:-1] if not t.startswith("--"))
    return sources


def _is_excluded(path: str) -> bool:
    """Whether `.dockerignore` excludes `path`, by Docker's last-match-wins rule.

    An approximation, and deliberately a narrow one: it handles the exact and
    directory-prefix patterns this file uses, not the full `filepath.Match`
    grammar. It is enough to catch the case that matters here — a directory
    excluded wholesale and a subtree of it negated back in.
    """
    excluded = False
    for raw in DOCKERIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        pattern = line.lstrip("!").rstrip("/")
        if path == pattern or path.startswith(pattern + "/") or fnmatch.fnmatch(path, pattern):
            excluded = not negated
    return excluded


def test_cpu_dockerfile_uses_python_312_slim() -> None:
    content = DOCKERFILE.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in content
    assert "uv sync" in content
    assert "CMD" in content and "uvicorn" in content
    assert "0.0.0.0" in content and "8000" in content
    # The built island bundle ships inside the image with `COPY app ./app`.
    assert "COPY app ./app" in content


def test_dockerfile_copies_only_paths_that_exist() -> None:
    missing = sorted(s for s in _copy_sources() if not (ROOT / s).exists())
    assert not missing, f"Dockerfile copies paths that are not in the tree: {missing}"


def test_dockerignore_keeps_every_copied_path() -> None:
    """A copied path that `.dockerignore` drops builds a quietly broken image."""
    dropped = sorted(s for s in _copy_sources() if _is_excluded(s))
    assert not dropped, f".dockerignore excludes paths the Dockerfile copies: {dropped}"


def test_compose_file_pins_model_snapshot() -> None:
    """Switching to the hosted reader must not float the model version.

    The container runs the local reader by default and needs no pin to do its
    job. The pin is here for the reviewer who sets `VISION_MODE=cloud`: an
    unpinned snapshot makes two runs of the same label unreproducible.
    """
    cpu = COMPOSE.read_text(encoding="utf-8")
    assert "LLM_MODEL_SNAPSHOT" in cpu
    cpu_pin = re.search(r"LLM_MODEL_SNAPSHOT.*\$\{LLM_MODEL_SNAPSHOT:-([^}]+)\}", cpu)
    assert cpu_pin and cpu_pin.group(1)


def test_compose_environment_names_are_all_read_by_the_app() -> None:
    """Every name the compose file sets is one `app/config.py` declares.

    A variable nothing reads is a promise the container does not keep, and
    nothing else in the tree would notice it.
    """
    from app.config import Settings

    known = {
        (field.alias or name).upper()
        for name, field in Settings.model_fields.items()
    }
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    for service, spec in compose["services"].items():
        set_names = set(spec.get("environment", {}) or {})
        unread = sorted(n for n in set_names if n.upper() not in known)
        assert not unread, f"service {service!r} sets variables nothing reads: {unread}"


def test_compose_default_vision_mode_matches_the_app_default() -> None:
    """`docker compose up` must work with no secrets, like a clone does.

    Defaulting the container to the hosted reader would make the one-command
    path fail on a missing `OPENAI_API_KEY`, which is the opposite of what
    decision 0004 promises.
    """
    from app.config import Settings

    app_default = Settings.model_fields["vision_mode"].default
    compose = COMPOSE.read_text(encoding="utf-8")
    found = re.search(r"VISION_MODE:\s*\$\{VISION_MODE:-([^}]+)\}", compose)
    assert found, "compose does not give VISION_MODE a default"
    assert found.group(1) == app_default


def test_dockerignore_excludes_frontend_source() -> None:
    lines = [ln.strip() for ln in DOCKERIGNORE.read_text(encoding="utf-8").split("\n")]
    assert "frontend/" in lines or "frontend" in lines
    assert any("node_modules" in ln for ln in lines)


def test_space_app_port_matches_the_port_the_container_listens_on() -> None:
    """The one number the Space card and the Dockerfile must agree on.

    The platform routes to `app_port` and defaults it to 7860; uvicorn binds the
    port in `CMD`. If they differ the deploy comes up healthy and serves nothing.
    """
    card_port = re.search(r"^app_port:\s*(\d+)", README.read_text(encoding="utf-8"), re.MULTILINE)
    assert card_port, "README Space card does not declare app_port"
    cmd_port = re.search(r'"--port",\s*"(\d+)"', DOCKERFILE.read_text(encoding="utf-8"))
    assert cmd_port, "Dockerfile CMD does not pin a port"
    assert card_port.group(1) == cmd_port.group(1)


def test_deploy_preflight_passes() -> None:
    """The deploy script's own checks run here, and pass, without pushing.

    This is as far as the deploy can be proved without making the app publicly
    reachable, which is the owner's call. `--check` runs every check that needs
    no network: the Dockerfile is present, the Space card declares a Docker
    Space, its `app_port` matches the container's port, the built island bundle
    is tracked, and every path the build copies exists.
    """
    assert DEPLOY.exists(), "scripts/deploy.sh is the one-command deploy"

    parses = subprocess.run(["bash", "-n", str(DEPLOY)], capture_output=True, text=True)
    assert parses.returncode == 0, f"deploy.sh does not parse: {parses.stderr}"

    check = subprocess.run(
        ["bash", str(DEPLOY), "--check"], capture_output=True, text=True, cwd=ROOT
    )
    assert check.returncode == 0, (
        f"deploy preflight failed:\n{check.stdout}\n{check.stderr}"
    )


def test_deploy_script_does_not_push_without_a_target() -> None:
    """Running it with no `TTB_SPACE` must stop, not guess at a destination."""
    run = subprocess.run(
        ["bash", str(DEPLOY)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(ROOT)},
    )
    assert run.returncode == 2, f"expected a usage exit, got {run.returncode}"
    assert "TTB_SPACE" in run.stderr
