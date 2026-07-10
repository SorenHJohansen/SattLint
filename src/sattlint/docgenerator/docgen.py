"""Compatibility shim for the active docgen package."""

from __future__ import annotations

from sattlint.docgenerator import docgen as _docgen_package

globals().update(
    {
        name: getattr(_docgen_package, name)
        for name in dir(_docgen_package)
        if not (name.startswith("__") and name not in {"__all__"})
    }
)
