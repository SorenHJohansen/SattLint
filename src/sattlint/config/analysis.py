"""Typed accessors for analyzer-specific configuration under ``analysis``.

Analyzers read their knobs through these helpers so the config shape stays in
one place instead of each analyzer reaching into ``cfg["analysis"][...]`` with
loose dict lookups.
"""

from __future__ import annotations

from typing import Any, cast

DEFAULT_STEP_PREFIX = "ST_"
DEFAULT_TRANSITION_PREFIX = "TR_"
DEFAULT_SEQUENCE_PREFIX = ""
DEFAULT_EQUATION_PREFIX = ""

DEFAULT_UNSAFE_DEFAULT_TOKENS = ("bypass", "enable")

DEFAULT_CYCLOMATIC_MODULE_THRESHOLD = 10
DEFAULT_CYCLOMATIC_STEP_THRESHOLD = 6
DEFAULT_CYCLOMATIC_EQUATION_BLOCK_THRESHOLD = 10

DEFAULT_FAN_IN_OUT_THRESHOLD = 3


def _analysis_section(config: dict[str, Any] | None) -> dict[str, Any]:
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


def spec_compliance_prefixes(config: dict[str, Any] | None) -> dict[str, str]:
    """Return the resolved spec-compliance name prefixes.

    ``step_prefix``/``transition_prefix`` default to the established ``ST_`` /
    ``TR_`` conventions. ``sequence_prefix``/``equation_prefix`` default to
    empty, which disables those checks unless a prefix is configured.
    """
    spec_compliance = _analysis_section(config).get("spec_compliance")
    if not isinstance(spec_compliance, dict):
        return {
            "step_prefix": DEFAULT_STEP_PREFIX,
            "transition_prefix": DEFAULT_TRANSITION_PREFIX,
            "sequence_prefix": DEFAULT_SEQUENCE_PREFIX,
            "equation_prefix": DEFAULT_EQUATION_PREFIX,
        }
    mapping = cast(dict[str, object], spec_compliance)
    return {
        "step_prefix": _prefix_value(mapping.get("step_prefix"), DEFAULT_STEP_PREFIX),
        "transition_prefix": _prefix_value(mapping.get("transition_prefix"), DEFAULT_TRANSITION_PREFIX),
        "sequence_prefix": _prefix_value(mapping.get("sequence_prefix"), DEFAULT_SEQUENCE_PREFIX),
        "equation_prefix": _prefix_value(mapping.get("equation_prefix"), DEFAULT_EQUATION_PREFIX),
    }


def _prefix_value(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


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


def fan_in_out_threshold(config: dict[str, Any] | None) -> int:
    return _positive_int(
        _analysis_section(config).get("fan_in_out_threshold"),
        DEFAULT_FAN_IN_OUT_THRESHOLD,
    )


__all__ = [
    "DEFAULT_CYCLOMATIC_EQUATION_BLOCK_THRESHOLD",
    "DEFAULT_CYCLOMATIC_MODULE_THRESHOLD",
    "DEFAULT_CYCLOMATIC_STEP_THRESHOLD",
    "DEFAULT_EQUATION_PREFIX",
    "DEFAULT_FAN_IN_OUT_THRESHOLD",
    "DEFAULT_SEQUENCE_PREFIX",
    "DEFAULT_STEP_PREFIX",
    "DEFAULT_TRANSITION_PREFIX",
    "DEFAULT_UNSAFE_DEFAULT_TOKENS",
    "cyclomatic_equation_block_threshold",
    "cyclomatic_module_threshold",
    "cyclomatic_step_threshold",
    "fan_in_out_threshold",
    "spec_compliance_prefixes",
    "unsafe_default_tokens",
]
