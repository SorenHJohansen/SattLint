"""Compatibility wrapper for parser-core grammar constants."""

from sattline_parser.grammar import constants as _constants


def __getattr__(name: str):
    return getattr(_constants, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_constants)))
