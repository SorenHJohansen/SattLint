"""Compatibility wrapper for structural report builders.

Internal SattLint code should prefer imports from
``sattlint.devtools.structural.structural_reports``.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from typing import Any

from .structural import structural_reports as _structural_reports

_MISSING = object()
_OWNER_SEAM_NAMES = tuple(name for name in dir(_structural_reports) if not name.startswith("__"))


def _seam_override(name: str, original: Any) -> Any:
    candidate = globals().get(name, _MISSING)
    if candidate is _MISSING:
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


def __getattr__(name: str) -> Any:
    value = getattr(_structural_reports, name)
    if callable(value) and (name.startswith("_") or name[:1].islower()):

        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            return _call_owner_with_test_seams(name, *args, **kwargs)

        return _wrapped
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_structural_reports)))
