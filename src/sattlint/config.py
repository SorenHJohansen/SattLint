"""Configuration management for SattLint."""

from __future__ import annotations

import os as _os

from . import _config_defaults as _config_defaults_module
from . import config_io as _config_io_module
from . import config_validation as _config_validation_module
from .config_types import ConfigDict

os = _os
DEFAULT_CONFIG = _config_defaults_module.DEFAULT_CONFIG
ConfigValidationError = _config_validation_module.ConfigValidationError
ConfigValidationResult = _config_validation_module.ConfigValidationResult
target_exists = _config_validation_module.target_exists
validate_config = _config_validation_module.validate_config
validate_effective_config = _config_validation_module.validate_effective_config
validate_loaded_config = _config_validation_module.validate_loaded_config
get_config_path = _config_io_module.get_config_path
get_graphics_rules_path = _config_io_module.get_graphics_rules_path
load_config = _config_io_module.load_config
save_config = _config_io_module.save_config
configured_targets = _config_validation_module.configured_targets
validation_errors_by_key = _config_validation_module.validation_errors_by_key

_configured_targets = configured_targets
_validation_errors_by_key = validation_errors_by_key


def self_check(cfg: ConfigDict) -> bool:
    from ._config_self_check import self_check as _self_check  # noqa: PLC0415

    return _self_check(cfg)
