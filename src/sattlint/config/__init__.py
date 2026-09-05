"""Configuration management for SattLint.

Owns config types, defaults, validation, TOML I/O, path resolution, display,
and self-check.  ``ConfigDict``/``TOP_LEVEL_CONFIG_FIELDS`` is the single source
of truth for the top-level config contract (asserted at import in
:mod:`sattlint.config.defaults`).
"""

from __future__ import annotations

import os as _os

from . import io as _config_io_module
from . import validation as _config_validation_module
from .defaults import DEFAULT_CONFIG
from .types import ConfigDict

os = _os
ConfigValidationError = _config_validation_module.ConfigValidationError
ConfigValidationResult = _config_validation_module.ConfigValidationResult
target_exists = _config_validation_module.target_exists
validate_config = _config_validation_module.validate_config
validate_effective_config = _config_validation_module.validate_effective_config
validate_loaded_config = _config_validation_module.validate_loaded_config
get_config_path = _config_io_module.get_config_path
load_config = _config_io_module.load_config
save_config = _config_io_module.save_config
configured_targets = _config_validation_module.configured_targets
validation_errors_by_key = _config_validation_module.validation_errors_by_key

_configured_targets = configured_targets
_validation_errors_by_key = validation_errors_by_key


def self_check(cfg: ConfigDict) -> bool:
    from ._self_check import self_check as _self_check  # noqa: PLC0415

    return _self_check(cfg)


__all__ = [
    "DEFAULT_CONFIG",
    "ConfigDict",
    "ConfigValidationError",
    "ConfigValidationResult",
    "configured_targets",
    "get_config_path",
    "load_config",
    "save_config",
    "self_check",
    "target_exists",
    "validate_config",
    "validate_effective_config",
    "validate_loaded_config",
    "validation_errors_by_key",
]
