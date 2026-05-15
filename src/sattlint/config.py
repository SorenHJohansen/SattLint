"""Configuration management for SattLint."""

from __future__ import annotations

import os
import tomllib
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import tomli_w

from .types import TargetName

_DOCUMENTATION_RULE_LIST_KEYS = (
    "name_contains",
    "label_equals",
    "desc_name_contains",
    "desc_label_equals",
)

_DOCUMENTATION_CATEGORY_KEYS = (
    "em",
    "ops",
    "rp",
    "ep",
    "up",
)

_DOCUMENTATION_LEGACY_RULE_KEYS = {
    "moduletype_name_contains": "name_contains",
    "moduletype_label_equals": "label_equals",
    "descendant_moduletype_name_contains": "desc_name_contains",
    "descendant_moduletype_label_equals": "desc_label_equals",
}

_DOCUMENTATION_LEGACY_CATEGORY_KEYS = {
    "equipment_modules": "em",
    "operations": "ops",
    "recipe_parameters": "rp",
    "engineering_parameters": "ep",
    "user_parameters": "up",
}

_NAMING_STYLE_KEYS = (
    "infer",
    "pascal",
    "camel",
    "snake",
    "upper_snake",
    "lower",
    "upper",
)

_NAMING_RULE_TARGETS = (
    "variables",
    "modules",
    "instances",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "analyzed_programs_and_libraries": [],
    "mode": "official",
    "scan_root_only": False,
    "fast_cache_validation": True,
    "debug": False,
    "program_dir": "",
    "ABB_lib_dir": "",
    "icf_dir": "",
    "other_lib_dirs": [],
    "analysis": {
        "sfc": {
            "mutually_exclusive_steps": [],
            "step_contracts": {},
        },
        "naming": {
            "variables": {"style": "infer", "allow": []},
            "modules": {"style": "infer", "allow": []},
            "instances": {"style": "infer", "allow": []},
        },
        "rule_profiles": {
            "active": "default",
            "profiles": {
                "default": {
                    "description": "Balanced default analyzer profile.",
                    "disabled_rules": [],
                    "severity_overrides": {},
                    "confidence_overrides": {},
                },
                "strict-pharma": {
                    "description": "Promotes style and maintainability drift during regulated review.",
                    "disabled_rules": [],
                    "severity_overrides": {
                        "semantic.naming-inconsistent-style": "error",
                        "semantic.cyclomatic-complexity.module": "error",
                        "semantic.cyclomatic-complexity.step": "error",
                    },
                    "confidence_overrides": {},
                },
                "legacy-plant": {
                    "description": "Suppresses style-heavy advisories while preserving contract and correctness findings.",
                    "disabled_rules": [
                        "semantic.naming-role-mismatch",
                        "semantic.naming-inconsistent-style",
                        "semantic.cyclomatic-complexity.module",
                        "semantic.cyclomatic-complexity.step",
                        "semantic.loop-output-refactor",
                    ],
                    "severity_overrides": {},
                    "confidence_overrides": {},
                },
            },
        },
    },
    "documentation": {
        "classifications": {
            "em": {
                "name_contains": [],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": ["nnestruct:EquipModCoordinate"],
            },
            "ops": {
                "name_contains": [],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": ["NNEMESIFLib:MES_StateControl"],
            },
            "rp": {
                "name_contains": ["RecPar"],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": [],
            },
            "ep": {
                "name_contains": ["EngPar"],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": [],
            },
            "up": {
                "name_contains": ["UsrPar"],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": [],
            },
        },
    },
}


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
            continue
        merged[key] = value
    return merged


def _normalize_documentation_rule_keys(config: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(config)
    documentation = normalized.get("documentation")
    if not isinstance(documentation, dict):
        return normalized

    classifications = documentation.get("classifications")
    if not isinstance(classifications, dict):
        return normalized

    for legacy_key, short_key in _DOCUMENTATION_LEGACY_CATEGORY_KEYS.items():
        if legacy_key not in classifications:
            continue
        legacy_rule = classifications.pop(legacy_key)
        if short_key in classifications:
            continue
        classifications[short_key] = legacy_rule

    for rule in classifications.values():
        if not isinstance(rule, dict):
            continue
        for legacy_key, short_key in _DOCUMENTATION_LEGACY_RULE_KEYS.items():
            if legacy_key not in rule:
                continue
            legacy_values = rule.pop(legacy_key)
            if short_key in rule:
                continue
            rule[short_key] = legacy_values

    return normalized


def get_documentation_config(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    documentation_defaults = cast(dict[str, Any], deepcopy(DEFAULT_CONFIG["documentation"]))
    if not cfg:
        return documentation_defaults

    cfg = _normalize_documentation_rule_keys(cfg)

    if "documentation" in cfg and isinstance(cfg.get("documentation"), dict):
        override = cfg.get("documentation", {})
    else:
        override = cfg
    if not isinstance(override, dict):
        return documentation_defaults
    return _deep_merge_dict(documentation_defaults, override)


def get_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    cfg_dir = base / "sattlint"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.toml"


def get_graphics_rules_path(config_path: Path | None = None) -> Path:
    resolved_config_path = config_path or get_config_path()
    return resolved_config_path.with_name("graphics_rules.json")


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
    return tuple(
        TargetName(normalized)
        for raw_target in cfg.get("analyzed_programs_and_libraries", [])
        if (normalized := str(raw_target).strip())
    )


def _validation_errors_by_key(validation: ConfigValidationResult) -> dict[str, tuple[str, ...]]:
    errors_by_key: dict[str, list[str]] = {}
    for error in validation.errors:
        errors_by_key.setdefault(error.key_path, []).append(error.message)
    return {key: tuple(messages) for key, messages in errors_by_key.items()}


def validate_config(cfg: dict[str, Any]) -> ConfigValidationResult:
    errors: list[ConfigValidationError] = []

    for key in cfg:
        if key not in VALID_TOP_LEVEL_KEYS:
            errors.append(
                ConfigValidationError(
                    key_path=key,
                    message=f"Unknown config key '{key}'. Expected one of: {', '.join(sorted(VALID_TOP_LEVEL_KEYS))}",
                )
            )

    mode = cfg.get("mode")
    if mode is not None and mode not in {"official", "draft"}:
        errors.append(
            ConfigValidationError(
                key_path="mode",
                message=f"Invalid mode '{mode}'. Expected 'official' or 'draft'.",
            )
        )

    analysis = cfg.get("analysis")
    if analysis is not None and not isinstance(analysis, dict):
        errors.append(
            ConfigValidationError(
                key_path="analysis",
                message="analysis must be a table/object.",
            )
        )
    elif isinstance(analysis, dict):
        for key in analysis:
            if key not in VALID_ANALYSIS_KEYS:
                errors.append(
                    ConfigValidationError(
                        key_path=f"analysis.{key}",
                        message=f"Unknown analysis key '{key}'. Expected one of: {', '.join(sorted(VALID_ANALYSIS_KEYS))}",
                    )
                )

        naming = analysis.get("naming")
        if naming is not None and isinstance(naming, dict):
            for target in naming:
                if target not in VALID_NAMING_TARGETS:
                    errors.append(
                        ConfigValidationError(
                            key_path=f"analysis.naming.{target}",
                            message=f"Unknown naming target '{target}'. Expected one of: {', '.join(sorted(VALID_NAMING_TARGETS))}",
                        )
                    )
            for target in _NAMING_RULE_TARGETS:
                target_rule = naming.get(target, {})
                if not isinstance(target_rule, dict):
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

                allow = target_rule.get("allow", [])
                if not isinstance(allow, list) or not all(isinstance(item, str) for item in allow):
                    errors.append(
                        ConfigValidationError(
                            key_path=f"analysis.naming.{target}.allow",
                            message=f"analysis.naming.{target}.allow must be a list of strings",
                        )
                    )

        sfc = analysis.get("sfc")
        if sfc is not None and not isinstance(sfc, dict):
            errors.append(
                ConfigValidationError(
                    key_path="analysis.sfc",
                    message="analysis.sfc must be a table/object",
                )
            )
        elif isinstance(sfc, dict):
            step_groups = sfc.get("mutually_exclusive_steps", [])
            if not isinstance(step_groups, list):
                errors.append(
                    ConfigValidationError(
                        key_path="analysis.sfc.mutually_exclusive_steps",
                        message="analysis.sfc.mutually_exclusive_steps must be a list",
                    )
                )

            step_contracts = sfc.get("step_contracts", {})
            if not isinstance(step_contracts, dict):
                errors.append(
                    ConfigValidationError(
                        key_path="analysis.sfc.step_contracts",
                        message="analysis.sfc.step_contracts must be a table/object",
                    )
                )
            else:
                for step_name, contract in step_contracts.items():
                    if not isinstance(step_name, str) or not step_name.strip():
                        errors.append(
                            ConfigValidationError(
                                key_path="analysis.sfc.step_contracts",
                                message="analysis.sfc.step_contracts keys must be non-empty strings",
                            )
                        )
                        continue
                    if not isinstance(contract, dict):
                        errors.append(
                            ConfigValidationError(
                                key_path=f"analysis.sfc.step_contracts.{step_name}",
                                message=f"analysis.sfc.step_contracts.{step_name} must be a table/object",
                            )
                        )
                        continue
                    for key in ("required_enter_writes", "required_exit_writes"):
                        values = contract.get(key, [])
                        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                            errors.append(
                                ConfigValidationError(
                                    key_path=f"analysis.sfc.step_contracts.{step_name}.{key}",
                                    message=(
                                        f"analysis.sfc.step_contracts.{step_name}.{key} must be a list of strings"
                                    ),
                                )
                            )

        if naming is not None and not isinstance(naming, dict):
            errors.append(
                ConfigValidationError(
                    key_path="analysis.naming",
                    message="analysis.naming must be a table/object",
                )
            )

    documentation = cfg.get("documentation")
    if documentation is not None and not isinstance(documentation, dict):
        errors.append(
            ConfigValidationError(
                key_path="documentation",
                message="documentation must be a table/object.",
            )
        )
    elif isinstance(documentation, dict):
        classifications = documentation.get("classifications", {})
        if not isinstance(classifications, dict) or not classifications:
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
                if not isinstance(rule, dict):
                    errors.append(
                        ConfigValidationError(
                            key_path=f"documentation.classifications.{category}",
                            message=f"documentation.classifications.{category} must be a table/object",
                        )
                    )
                    continue
                for key in _DOCUMENTATION_RULE_LIST_KEYS:
                    values = rule.get(key, [])
                    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                        errors.append(
                            ConfigValidationError(
                                key_path=f"documentation.classifications.{category}.{key}",
                                message=(f"documentation.classifications.{category}.{key} must be a list of strings"),
                            )
                        )

    return _build_validation_result(errors)


def validate_loaded_config(cfg: dict[str, Any]) -> ConfigValidationResult:
    errors: list[ConfigValidationError] = []

    for name in ("program_dir", "ABB_lib_dir", "icf_dir"):
        raw = str(cfg.get(name, "")).strip()
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

    for index, raw_path in enumerate(cfg.get("other_lib_dirs", [])):
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

    graphics_rules_path = get_graphics_rules_path()
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


def load_config(path: Path) -> tuple[dict, bool]:
    if not path.exists():
        print(f"⚠ No config found, creating default: {path}")
        cfg = deepcopy(DEFAULT_CONFIG)
        save_config(path, cfg)
        return cfg, True

    with path.open("rb") as f:
        cfg = tomllib.load(f)

    cfg = _normalize_documentation_rule_keys(cfg)

    validation = validate_config(cfg)
    if not validation.passed:
        for error in validation.errors:
            print(f"⚠ Config warning [{error.key_path}]: {error.message}")

    merged = _deep_merge_dict(DEFAULT_CONFIG, cfg)
    merged.pop("ignore_ABB_lib", None)
    return merged, False


def save_config(path: Path, cfg: dict) -> None:
    def normalize(v):
        if isinstance(v, Path):
            return str(v)
        if isinstance(v, list | tuple):
            return [normalize(x) for x in v]
        if isinstance(v, dict):
            return {k: normalize(x) for k, x in v.items()}
        if v is None:
            raise ValueError("Cannot serialize None to TOML. Provide a default value or omit the key.")
        return v

    with path.open("wb") as f:
        tomli_w.dump(normalize(cfg), f)


def target_exists(target: str, cfg: dict) -> bool:
    dirs = [
        Path(cfg["program_dir"]),
        Path(cfg["ABB_lib_dir"]),
        *[Path(p) for p in cfg["other_lib_dirs"]],
    ]

    extensions = [".s", ".x"] if cfg["mode"] == "draft" else [".x"]

    for d in dirs:
        if not d.exists():
            continue
        for ext in extensions:
            if (d / f"{target}{ext}").exists():
                return True

    return False


def self_check(cfg: dict) -> bool:
    from ._config_self_check import self_check as _self_check

    return _self_check(cfg)
