"""Compatibility wrapper for parser-core grammar constants."""

from typing import Any

from sattline_parser.grammar import constants as _constants


def __getattr__(name: str) -> Any:
    return getattr(_constants, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_constants)))
