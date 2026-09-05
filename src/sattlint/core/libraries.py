"""Classification of expected-but-unavailable external SattLine libraries."""

from __future__ import annotations

_EXPECTED_UNAVAILABLE_LIBRARY_REASONS: dict[str, str] = {
    "controllib": "expected proprietary dependency",
}


def is_expected_unavailable_library(name: str) -> bool:
    return name.casefold() in _EXPECTED_UNAVAILABLE_LIBRARY_REASONS


def expected_unavailable_library_reason(name: str) -> str | None:
    return _EXPECTED_UNAVAILABLE_LIBRARY_REASONS.get(name.casefold())
