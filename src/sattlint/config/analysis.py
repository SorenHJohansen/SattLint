"""Typed accessors for analyzer-specific configuration under ``analysis``.

Analyzers read their knobs through these helpers so the config shape stays in
one place instead of each analyzer reaching into ``cfg["analysis"][...]`` with
loose dict lookups.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any, cast

DEFAULT_UNSAFE_DEFAULT_TOKENS = ("bypass", "enable")

DEFAULT_CYCLOMATIC_MODULE_THRESHOLD = 20
DEFAULT_CYCLOMATIC_STEP_THRESHOLD = 10
DEFAULT_CYCLOMATIC_EQUATION_BLOCK_THRESHOLD = 10

DEFAULT_FAN_IN_OUT_THRESHOLD = 3

#: Largest source file the loader parses. A hostile or accidental giant file
#: is refused before the parser reads any of its bytes.
DEFAULT_SOURCE_BYTE_LIMIT = 8 * 1024 * 1024
#: Largest ICF file the ICF analyzer reads.
DEFAULT_ICF_BYTE_LIMIT = 16 * 1024 * 1024
#: Largest total of source bytes over every configured root.
DEFAULT_PROJECT_BYTE_LIMIT = 512 * 1024 * 1024

#: The drawing grid a module uses when it writes no ``Grid`` clause.
DEFAULT_MODULE_GRID = 0.02
#: Distance below which a value counts as sitting exactly on the grid.
#: Serialized sources write coordinates with up to six decimals, so the
#: tolerance absorbs that rounding without hiding a real off-grid value.
DEFAULT_MODULE_GRID_TOLERANCE = 1e-5


def _analysis_section(config: Mapping[str, Any] | None) -> dict[str, Any]:
    if not config:
        return {}
    analysis = config.get("analysis")
    if isinstance(analysis, dict) and all(isinstance(key, str) for key in cast(dict[object, object], analysis)):
        return cast(dict[str, Any], analysis)
    return {}


def _positive_int(value: object, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return default


def unsafe_default_tokens(config: dict[str, Any] | None) -> tuple[str, ...]:
    """Return the configured unsafe-default token set.

    When ``analysis.unsafe_default_tokens`` is configured it replaces the
    default ``bypass``/``enable`` set; otherwise the defaults apply.
    """
    raw_tokens = _analysis_section(config).get("unsafe_default_tokens")
    if not isinstance(raw_tokens, list):
        return DEFAULT_UNSAFE_DEFAULT_TOKENS
    tokens = tuple(token for token in (str(token).strip() for token in cast(list[object], raw_tokens)) if token)
    return tokens or DEFAULT_UNSAFE_DEFAULT_TOKENS


def cyclomatic_module_threshold(config: dict[str, Any] | None) -> int:
    return _positive_int(
        _analysis_section(config).get("cyclomatic_module_threshold"),
        DEFAULT_CYCLOMATIC_MODULE_THRESHOLD,
    )


def cyclomatic_step_threshold(config: dict[str, Any] | None) -> int:
    return _positive_int(
        _analysis_section(config).get("cyclomatic_step_threshold"),
        DEFAULT_CYCLOMATIC_STEP_THRESHOLD,
    )


def cyclomatic_equation_block_threshold(config: dict[str, Any] | None) -> int:
    return _positive_int(
        _analysis_section(config).get("cyclomatic_equation_block_threshold"),
        DEFAULT_CYCLOMATIC_EQUATION_BLOCK_THRESHOLD,
    )


def _positive_float(value: object, default: float) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool) and isfinite(value) and value > 0:
        return float(value)
    return default


def fan_in_out_threshold(config: dict[str, Any] | None) -> int:
    return _positive_int(
        _analysis_section(config).get("fan_in_out_threshold"),
        DEFAULT_FAN_IN_OUT_THRESHOLD,
    )


def module_grid(config: dict[str, Any] | None) -> float:
    """The drawing grid used when a module writes no ``Grid`` clause."""
    return _positive_float(_analysis_section(config).get("module_grid"), DEFAULT_MODULE_GRID)


def module_grid_tolerance(config: dict[str, Any] | None) -> float:
    """The distance below which a value counts as sitting exactly on the grid."""
    return _positive_float(
        _analysis_section(config).get("module_grid_tolerance"),
        DEFAULT_MODULE_GRID_TOLERANCE,
    )


def source_byte_limit(config: Mapping[str, Any] | None) -> int:
    """Largest source file the loader parses, in bytes."""
    return _positive_int(
        _analysis_section(config).get("source_byte_limit"),
        DEFAULT_SOURCE_BYTE_LIMIT,
    )


def icf_byte_limit(config: Mapping[str, Any] | None) -> int:
    """Largest ICF file the ICF analyzer reads, in bytes."""
    return _positive_int(
        _analysis_section(config).get("icf_byte_limit"),
        DEFAULT_ICF_BYTE_LIMIT,
    )


def project_byte_limit(config: Mapping[str, Any] | None) -> int:
    """Largest total of source bytes over every configured root, in bytes."""
    return _positive_int(
        _analysis_section(config).get("project_byte_limit"),
        DEFAULT_PROJECT_BYTE_LIMIT,
    )


__all__ = [
    "DEFAULT_CYCLOMATIC_EQUATION_BLOCK_THRESHOLD",
    "DEFAULT_CYCLOMATIC_MODULE_THRESHOLD",
    "DEFAULT_CYCLOMATIC_STEP_THRESHOLD",
    "DEFAULT_FAN_IN_OUT_THRESHOLD",
    "DEFAULT_ICF_BYTE_LIMIT",
    "DEFAULT_MODULE_GRID",
    "DEFAULT_MODULE_GRID_TOLERANCE",
    "DEFAULT_PROJECT_BYTE_LIMIT",
    "DEFAULT_SOURCE_BYTE_LIMIT",
    "DEFAULT_UNSAFE_DEFAULT_TOKENS",
    "cyclomatic_equation_block_threshold",
    "cyclomatic_module_threshold",
    "cyclomatic_step_threshold",
    "fan_in_out_threshold",
    "icf_byte_limit",
    "module_grid",
    "module_grid_tolerance",
    "project_byte_limit",
    "source_byte_limit",
    "unsafe_default_tokens",
]
