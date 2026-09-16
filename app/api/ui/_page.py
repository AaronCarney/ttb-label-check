"""What every page shell needs to render: the templates, and the settings.

Kept apart from the routes so that a module serving one page does not have to
carry the Jinja wiring for the others.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import Settings

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "ui" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


def _get_settings() -> Settings:
    """The process settings, as a dependency so a test can override them.

    Every UI route resolves settings through this one function, so overriding
    it in one place changes every page at once.
    """
    return Settings()
