"""Compatibility wrapper for structural report builders.

Internal SattLint code should prefer imports from
``sattlint.devtools.structural.structural_reports``.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from functools import wraps
from typing import Any

from .structural import structural_reports as _structural_reports

_MISSING = object()
_OWNER_SEAM_NAMES = tuple(name for name in dir(_structural_reports) if not name.startswith("__"))
_DEFAULT_EXPORTS: dict[str, Any] = {}


def _seam_override(name: str, original: Any) -> Any:
    candidate = globals().get(name, _MISSING)
    if candidate is _MISSING:
        return original
    if candidate is _DEFAULT_EXPORTS.get(name, _MISSING):
        return original
    return candidate


@contextmanager
def _patched_owner_test_seams():
    originals = {name: getattr(_structural_reports, name, _MISSING) for name in _OWNER_SEAM_NAMES}
    for name, original in originals.items():
        override = _seam_override(name, original)
        if override is _MISSING:
            continue
        setattr(_structural_reports, name, override)
    try:
        yield
    finally:
        for name, original in originals.items():
            if original is _MISSING:
                with suppress(AttributeError):
                    delattr(_structural_reports, name)
                continue
            setattr(_structural_reports, name, original)


def _call_owner_with_test_seams(name: str, *args: Any, **kwargs: Any) -> Any:
    with _patched_owner_test_seams():
        return getattr(_structural_reports, name)(*args, **kwargs)


def _export_owner_seam(name: str, value: Any) -> None:
    if callable(value) and (name.startswith("_") or name[:1].islower()):

        @wraps(value)
        def _wrapped(*args: Any, _name: str = name, **kwargs: Any) -> Any:
            return _call_owner_with_test_seams(_name, *args, **kwargs)

        globals()[name] = _wrapped
        _DEFAULT_EXPORTS[name] = _wrapped
        return

    globals()[name] = value
    _DEFAULT_EXPORTS[name] = value


for _name in _OWNER_SEAM_NAMES:
    _export_owner_seam(_name, getattr(_structural_reports, _name))

__all__ = [name for name in _OWNER_SEAM_NAMES if not name.startswith("__")]


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
