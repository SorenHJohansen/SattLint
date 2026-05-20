"""Validation helpers and defaults for SattLint configuration."""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard, cast

from ._config_defaults import (
    DEFAULT_CONFIG,
)
from ._config_defaults import (
    DOCUMENTATION_CATEGORY_KEYS as _DOCUMENTATION_CATEGORY_KEYS,
)
from ._config_defaults import (
    DOCUMENTATION_LEGACY_CATEGORY_KEYS as _DOCUMENTATION_LEGACY_CATEGORY_KEYS,
)
from ._config_defaults import (
    DOCUMENTATION_LEGACY_RULE_KEYS as _DOCUMENTATION_LEGACY_RULE_KEYS,
)
from ._config_defaults import (
    DOCUMENTATION_RULE_LIST_KEYS as _DOCUMENTATION_RULE_LIST_KEYS,
)
from ._config_defaults import (
    NAMING_RULE_TARGETS as _NAMING_RULE_TARGETS,
)
from ._config_defaults import (
    NAMING_STYLE_KEYS as _NAMING_STYLE_KEYS,
)
from .types import TargetName

type ConfigDict = dict[str, object]


VALID_TOP_LEVEL_KEYS = frozenset(
    {
        "analyzed_programs_and_libraries",
        "mode",
        "scan_root_only",
        "fast_cache_validation",
        "debug",
        "program_dir",
        "ABB_lib_dir",
        "icf_dir",
        "other_lib_dirs",
        "analysis",
        "documentation",
        "ignore_ABB_lib",
    }
)

VALID_ANALYSIS_KEYS = frozenset({"sfc", "naming", "rule_profiles"})
VALID_NAMING_TARGETS = frozenset({"variables", "modules", "instances"})
VALID_NAMING_STYLES = frozenset({"infer", "pascal", "camel", "snake", "upper_snake", "lower", "upper"})


@dataclass(frozen=True, slots=True)
class ConfigValidationError:
    key_path: str
    message: str


@dataclass(frozen=True, slots=True)
class ConfigValidationResult:
    passed: bool
    errors: tuple[ConfigValidationError, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": [{"key_path": e.key_path, "message": e.message} for e in self.errors],
        }


def _is_config_dict(value: object) -> TypeGuard[ConfigDict]:
    if not isinstance(value, dict):
        return False
    typed_value = cast(dict[object, object], value)
    return all(isinstance(key, str) for key in typed_value)


def _config_dict(value: object) -> ConfigDict | None:
    return value if _is_config_dict(value) else None


def _object_list(value: object) -> list[object]:
    if isinstance(value, list):
        return list(cast(list[object], value))
    if isinstance(value, tuple):
        return list(cast(tuple[object, ...], value))
    return []


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = list(cast(list[object], value))
    if not all(isinstance(item, str) for item in items):
        return None
    return [item for item in items if isinstance(item, str)]


def _deep_merge_dict(base: ConfigDict, override: ConfigDict) -> ConfigDict:
    merged = deepcopy(base)
    for key, value in override.items():
        nested_override = _config_dict(value)
        nested_base = _config_dict(merged.get(key))
        if nested_override is not None and nested_base is not None:
            merged[key] = _deep_merge_dict(nested_base, nested_override)
            continue
        merged[key] = value
    return merged


def _normalize_documentation_rule_keys(config: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(cast(ConfigDict, config))
    documentation = _config_dict(normalized.get("documentation"))
    if documentation is None:
        return cast(dict[str, Any], normalized)

    classifications = _config_dict(documentation.get("classifications"))
    if classifications is None:
        return cast(dict[str, Any], normalized)

    for legacy_key, short_key in _DOCUMENTATION_LEGACY_CATEGORY_KEYS.items():
        if legacy_key not in classifications:
            continue
        legacy_rule = classifications.pop(legacy_key)
        if short_key in classifications:
            continue
        classifications[short_key] = legacy_rule

    for rule_value in list(classifications.values()):
        rule = _config_dict(rule_value)
        if rule is None:
            continue
        for legacy_key, short_key in _DOCUMENTATION_LEGACY_RULE_KEYS.items():
            if legacy_key not in rule:
                continue
            legacy_values = rule.pop(legacy_key)
            if short_key in rule:
                continue
            rule[short_key] = legacy_values

    return cast(dict[str, Any], normalized)


def get_documentation_config(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    documentation_defaults = deepcopy(cast(ConfigDict, DEFAULT_CONFIG["documentation"]))
    if not cfg:
        return cast(dict[str, Any], documentation_defaults)

    normalized_cfg = cast(ConfigDict, _normalize_documentation_rule_keys(cfg))

    documentation_override = _config_dict(normalized_cfg.get("documentation"))
    override = documentation_override if documentation_override is not None else normalized_cfg
    return cast(dict[str, Any], _deep_merge_dict(documentation_defaults, override))


def _build_validation_result(errors: list[ConfigValidationError]) -> ConfigValidationResult:
    return ConfigValidationResult(
        passed=len(errors) == 0,
        errors=tuple(errors),
    )


def _merge_validation_results(*results: ConfigValidationResult) -> ConfigValidationResult:
    merged_errors: list[ConfigValidationError] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        for error in result.errors:
            marker = (error.key_path, error.message)
            if marker in seen:
                continue
            seen.add(marker)
            merged_errors.append(error)
    return _build_validation_result(merged_errors)


def _configured_targets(cfg: dict[str, Any]) -> tuple[TargetName, ...]:
    typed_cfg = cast(ConfigDict, cfg)
    return tuple(
        TargetName(normalized)
        for raw_target in _object_list(typed_cfg.get("analyzed_programs_and_libraries", []))
        if (normalized := str(raw_target).strip())
    )


def _validation_errors_by_key(validation: ConfigValidationResult) -> dict[str, tuple[str, ...]]:
    errors_by_key: dict[str, list[str]] = {}
    for error in validation.errors:
        errors_by_key.setdefault(error.key_path, []).append(error.message)
    return {key: tuple(messages) for key, messages in errors_by_key.items()}


normalize_documentation_rule_keys = _normalize_documentation_rule_keys
configured_targets = _configured_targets
validation_errors_by_key = _validation_errors_by_key
deep_merge_dict = _deep_merge_dict


def validate_config(cfg: dict[str, Any]) -> ConfigValidationResult:
    errors: list[ConfigValidationError] = []
    typed_cfg = cast(ConfigDict, cfg)

    for key in typed_cfg:
        if key not in VALID_TOP_LEVEL_KEYS:
            errors.append(
                ConfigValidationError(
                    key_path=key,
                    message=f"Unknown config key '{key}'. Expected one of: {', '.join(sorted(VALID_TOP_LEVEL_KEYS))}",
                )
            )

    mode = typed_cfg.get("mode")
    if mode is not None and mode not in {"official", "draft"}:
        errors.append(
            ConfigValidationError(
                key_path="mode",
                message=f"Invalid mode '{mode}'. Expected 'official' or 'draft'.",
            )
        )

    analysis_value = typed_cfg.get("analysis")
    analysis = _config_dict(analysis_value)
    if analysis_value is not None and analysis is None:
        errors.append(
            ConfigValidationError(
                key_path="analysis",
                message="analysis must be a table/object.",
            )
        )
    elif analysis is not None:
        for key in analysis:
            if key not in VALID_ANALYSIS_KEYS:
                errors.append(
                    ConfigValidationError(
                        key_path=f"analysis.{key}",
                        message=f"Unknown analysis key '{key}'. Expected one of: {', '.join(sorted(VALID_ANALYSIS_KEYS))}",
                    )
                )

        naming_value = analysis.get("naming")
        naming = _config_dict(naming_value)
        if naming is not None:
            for target in naming:
                if target not in VALID_NAMING_TARGETS:
                    errors.append(
                        ConfigValidationError(
                            key_path=f"analysis.naming.{target}",
                            message=f"Unknown naming target '{target}'. Expected one of: {', '.join(sorted(VALID_NAMING_TARGETS))}",
                        )
                    )
            for target in _NAMING_RULE_TARGETS:
                target_rule = _config_dict(naming.get(target, {}))
                if target_rule is None:
                    errors.append(
                        ConfigValidationError(
                            key_path=f"analysis.naming.{target}",
                            message=f"analysis.naming.{target} must be a table/object",
                        )
                    )
                    continue

                style = str(target_rule.get("style", "infer")).strip().lower()
                if style not in _NAMING_STYLE_KEYS:
                    errors.append(
                        ConfigValidationError(
                            key_path=f"analysis.naming.{target}.style",
                            message=f"analysis.naming.{target}.style must be one of: {', '.join(_NAMING_STYLE_KEYS)}",
                        )
                    )

                allow = _string_list(target_rule.get("allow", []))
                if allow is None:
                    errors.append(
                        ConfigValidationError(
                            key_path=f"analysis.naming.{target}.allow",
                            message=f"analysis.naming.{target}.allow must be a list of strings",
                        )
                    )

        sfc_value = analysis.get("sfc")
        sfc = _config_dict(sfc_value)
        if sfc_value is not None and sfc is None:
            errors.append(
                ConfigValidationError(
                    key_path="analysis.sfc",
                    message="analysis.sfc must be a table/object",
                )
            )
        elif sfc is not None:
            step_groups = sfc.get("mutually_exclusive_steps", [])
            if not isinstance(step_groups, list):
                errors.append(
                    ConfigValidationError(
                        key_path="analysis.sfc.mutually_exclusive_steps",
                        message="analysis.sfc.mutually_exclusive_steps must be a list",
                    )
                )

            step_contracts = _config_dict(sfc.get("step_contracts", {}))
            if step_contracts is None:
                errors.append(
                    ConfigValidationError(
                        key_path="analysis.sfc.step_contracts",
                        message="analysis.sfc.step_contracts must be a table/object",
                    )
                )
            else:
                for step_name, contract in step_contracts.items():
                    if not step_name.strip():
                        errors.append(
                            ConfigValidationError(
                                key_path="analysis.sfc.step_contracts",
                                message="analysis.sfc.step_contracts keys must be non-empty strings",
                            )
                        )
                        continue
                    typed_contract = _config_dict(contract)
                    if typed_contract is None:
                        errors.append(
                            ConfigValidationError(
                                key_path=f"analysis.sfc.step_contracts.{step_name}",
                                message=f"analysis.sfc.step_contracts.{step_name} must be a table/object",
                            )
                        )
                        continue
                    for key in ("required_enter_writes", "required_exit_writes"):
                        values = _string_list(typed_contract.get(key, []))
                        if values is None:
                            errors.append(
                                ConfigValidationError(
                                    key_path=f"analysis.sfc.step_contracts.{step_name}.{key}",
                                    message=(
                                        f"analysis.sfc.step_contracts.{step_name}.{key} must be a list of strings"
                                    ),
                                )
                            )

        if naming_value is not None and naming is None:
            errors.append(
                ConfigValidationError(
                    key_path="analysis.naming",
                    message="analysis.naming must be a table/object",
                )
            )

    documentation_value = typed_cfg.get("documentation")
    documentation = _config_dict(documentation_value)
    if documentation_value is not None and documentation is None:
        errors.append(
            ConfigValidationError(
                key_path="documentation",
                message="documentation must be a table/object.",
            )
        )
    elif documentation is not None:
        classifications = _config_dict(documentation.get("classifications", {}))
        if classifications is None or not classifications:
            errors.append(
                ConfigValidationError(
                    key_path="documentation.classifications",
                    message="documentation.classifications must be a non-empty table/object",
                )
            )
        else:
            for category, rule in classifications.items():
                if category not in _DOCUMENTATION_CATEGORY_KEYS:
                    errors.append(
                        ConfigValidationError(
                            key_path=f"documentation.classifications.{category}",
                            message=(f"documentation.classifications.{category} is not a supported category"),
                        )
                    )
                    continue
                typed_rule = _config_dict(rule)
                if typed_rule is None:
                    errors.append(
                        ConfigValidationError(
                            key_path=f"documentation.classifications.{category}",
                            message=f"documentation.classifications.{category} must be a table/object",
                        )
                    )
                    continue
                for key in _DOCUMENTATION_RULE_LIST_KEYS:
                    values = _string_list(typed_rule.get(key, []))
                    if values is None:
                        errors.append(
                            ConfigValidationError(
                                key_path=f"documentation.classifications.{category}.{key}",
                                message=f"documentation.classifications.{category}.{key} must be a list of strings",
                            )
                        )

    return _build_validation_result(errors)


def target_exists(target: str, cfg: dict[str, Any]) -> bool:
    typed_cfg = cast(ConfigDict, cfg)
    other_lib_dirs = _object_list(typed_cfg.get("other_lib_dirs", []))
    dirs = [
        Path(str(raw_path))
        for raw_path in (
            typed_cfg.get("program_dir", ""),
            typed_cfg.get("ABB_lib_dir", ""),
            *other_lib_dirs,
        )
        if str(raw_path).strip()
    ]

    mode = str(typed_cfg.get("mode", "official")).strip().lower()
    extensions = [".s", ".x"] if mode == "draft" else [".x"]

    for directory in dirs:
        if not directory.exists():
            continue
        for ext in extensions:
            if (directory / f"{target}{ext}").exists():
                return True

    return False


def validate_loaded_config(cfg: dict[str, Any]) -> ConfigValidationResult:
    errors: list[ConfigValidationError] = []
    typed_cfg = cast(ConfigDict, cfg)

    for name in ("program_dir", "ABB_lib_dir", "icf_dir"):
        raw = str(typed_cfg.get(name, "")).strip()
        if not raw:
            continue
        path = Path(raw)
        if not path.exists():
            errors.append(
                ConfigValidationError(
                    key_path=name,
                    message=f"{name} does not exist: {path}",
                )
            )
            continue
        if not os.access(path, os.R_OK):
            errors.append(
                ConfigValidationError(
                    key_path=name,
                    message=f"{name} not readable: {path}",
                )
            )

    for index, raw_path in enumerate(_object_list(typed_cfg.get("other_lib_dirs", []))):
        path = Path(str(raw_path))
        if path.exists():
            continue
        errors.append(
            ConfigValidationError(
                key_path=f"other_lib_dirs[{index}]",
                message=f"other_lib_dirs entry missing: {path}",
            )
        )

    for index, target in enumerate(_configured_targets(cfg)):
        if target_exists(target, cfg):
            continue
        errors.append(
            ConfigValidationError(
                key_path=f"analyzed_programs_and_libraries[{index}]",
                message=f"{target} (not found)",
            )
        )

    from . import config as config_module

    graphics_rules_path = config_module.get_graphics_rules_path()
    if graphics_rules_path.exists():
        from . import graphics_rules as graphics_rules_module

        try:
            graphics_rules_module.load_graphics_rules(graphics_rules_path)
        except Exception as exc:
            errors.append(
                ConfigValidationError(
                    key_path="graphics_rules_path",
                    message=f"graphics_rules_path invalid: {graphics_rules_path} ({exc})",
                )
            )

    return _build_validation_result(errors)


def validate_effective_config(cfg: dict[str, Any]) -> ConfigValidationResult:
    return _merge_validation_results(validate_config(cfg), validate_loaded_config(cfg))
