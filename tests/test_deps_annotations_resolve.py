"""`app/deps.py`'s annotations must name things that actually exist.

`app/deps.py` carries `from __future__ import annotations`, so every
annotation in it is stored as a string and never evaluated during an
ordinary import. That hides a real mistake: an annotation may name a class
the module never imported, and nothing says so until something tries to
resolve it — `typing.get_type_hints`, a documentation generator, or a
framework that inspects a signature at runtime. Ruff's `F821` found three
such names here.

These tests resolve the annotations on purpose, which is the only way the
mistake becomes visible.
"""

from __future__ import annotations

import inspect
import typing

import app.deps


def _module_functions() -> list:
    return [
        obj
        for _, obj in inspect.getmembers(app.deps, inspect.isfunction)
        if obj.__module__ == app.deps.__name__
    ]


def test_module_level_annotations_resolve() -> None:
    """Every module-level annotation names something importable."""
    typing.get_type_hints(app.deps)


def test_every_function_signature_resolves() -> None:
    """Every function's parameter and return annotations resolve."""
    unresolved: list[str] = []
    for func in _module_functions():
        try:
            typing.get_type_hints(func)
        except NameError as exc:  # one report per function, not the first only
            unresolved.append(f"{func.__name__}: {exc}")
    assert not unresolved, "annotations naming things that do not exist: " + "; ".join(unresolved)
