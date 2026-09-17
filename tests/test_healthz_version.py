"""`/api/health` must report the version that is actually running.

It reported a hardcoded "0.1.0" until this test existed, so the release that
cut 0.2.0 left the one field identifying a deploy still saying 0.1.0. Nobody
looking at a live service could tell which build answered them. The number now
comes from the installed package's own metadata, and this holds it to the
release the repository declares.
"""
import tomllib
from pathlib import Path

from app.config import Settings


def _declared_version() -> str:
    return tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]


def test_app_version_is_the_released_version():
    """Not a constant: the number the repository cut is the number reported."""
    assert Settings().app_version == _declared_version()


def test_app_version_comes_from_package_metadata():
    """The number is read, not written here: break the read and it is unknown.

    A version this module cannot establish must be reported as unknown rather
    than guessed, which is the same rule the rules layer follows for a field
    the reader did not find.
    """
    import app.config as config

    class _Missing:
        PackageNotFoundError = config.metadata.PackageNotFoundError

        @staticmethod
        def version(_name: str) -> str:
            raise config.metadata.PackageNotFoundError

    original = config.metadata
    config.metadata = _Missing
    try:
        assert Settings().app_version == "unknown"
    finally:
        config.metadata = original
