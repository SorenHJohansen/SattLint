"""Validation helpers and defaults for SattLint configuration."""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard, cast

from ..types import TargetName
from .defaults import (
    VALID_TOP_LEVEL_CONFIG_KEYS,
)
from .types import (
    ConfigDict,
    ConfigObjectMap,
    ConfigOverrideDict,
)

VALID_TOP_LEVEL_KEYS = VALID_TOP_LEVEL_CONFIG_KEYS

VALID_ANALYSIS_KEYS: frozenset[str] = frozenset()
VALID_RUN_HISTORY_KEYS = frozenset({"enabled", "limit"})
VALID_OUTPUT_KEYS = frozenset({"retention_lines"})
VALID_REVIEW_KEYS = frozenset({"output_dir"})


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


def _is_config_dict(value: object) -> TypeGuard[ConfigObjectMap]:
    if not isinstance(value, dict):
        return False
    typed_value = cast(dict[object, object], value)
    return all(isinstance(key, str) for key in typed_value)


def _config_dict(value: object) -> ConfigObjectMap | None:
    return value if _is_config_dict(value) else None


def _object_list(value: object) -> list[object]:
    if isinstance(value, list):
        return list(cast(list[object], value))
    if isinstance(value, tuple):
        return list(cast(tuple[object, ...], value))
    return []


def _deep_merge_dict(base: ConfigObjectMap, override: ConfigObjectMap) -> ConfigObjectMap:
    merged = deepcopy(base)
    for key, value in override.items():
        nested_override = _config_dict(value)
        nested_base = _config_dict(merged.get(key))
        if nested_override is not None and nested_base is not None:
            merged[key] = _deep_merge_dict(nested_base, nested_override)
            continue
        merged[key] = value
    return merged


def _strip_section_keys(cfg: ConfigObjectMap, valid_keys: frozenset[str]) -> None:
    for key in list(cfg):
        if key not in valid_keys:
            del cfg[key]


def _strip_unknown_keys(cfg: ConfigOverrideDict) -> None:
    cfg_map = cast(ConfigObjectMap, cfg)

    _strip_section_keys(cfg_map, VALID_TOP_LEVEL_CONFIG_KEYS)

    analysis = _config_dict(cfg_map.get("analysis"))
    if analysis is not None:
        _strip_section_keys(analysis, VALID_ANALYSIS_KEYS)

    run_history = _config_dict(cfg_map.get("run_history"))
    if run_history is not None:
        _strip_section_keys(run_history, VALID_RUN_HISTORY_KEYS)

    output = _config_dict(cfg_map.get("output"))
    if output is not None:
        _strip_section_keys(output, VALID_OUTPUT_KEYS)

    review = _config_dict(cfg_map.get("review"))
    if review is not None:
        _strip_section_keys(review, VALID_REVIEW_KEYS)


def _load_time_config_warnings(cfg: ConfigOverrideDict) -> tuple[ConfigValidationError, ...]:
    del cfg
    return ()


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


def _configured_targets(cfg: ConfigDict | ConfigOverrideDict) -> tuple[TargetName, ...]:
    return tuple(
        TargetName(normalized)
        for raw_target in _object_list(cfg.get("analyzed_programs_and_libraries", []))
        if (normalized := str(raw_target).strip())
    )


def _validation_errors_by_key(validation: ConfigValidationResult) -> dict[str, tuple[str, ...]]:
    errors_by_key: dict[str, list[str]] = {}
    for error in validation.errors:
        errors_by_key.setdefault(error.key_path, []).append(error.message)
    return {key: tuple(messages) for key, messages in errors_by_key.items()}


configured_targets = _configured_targets
validation_errors_by_key = _validation_errors_by_key
deep_merge_dict = _deep_merge_dict
load_time_config_warnings = _load_time_config_warnings
strip_unknown_keys = _strip_unknown_keys


def _none_value_errors(value: object, *, key_path: str) -> list[ConfigValidationError]:
    if value is None:
        return [
            ConfigValidationError(
                key_path=key_path,
                message=f"{key_path} must not be null/None",
            )
        ]

    errors: list[ConfigValidationError] = []
    nested_dict = _config_dict(value)
    if nested_dict is not None:
        for nested_key, nested_value in nested_dict.items():
            errors.extend(_none_value_errors(nested_value, key_path=f"{key_path}.{nested_key}"))
        return errors

    if isinstance(value, (list, tuple)):
        for index, item in enumerate(cast(list[object] | tuple[object, ...], value)):
            errors.extend(_none_value_errors(item, key_path=f"{key_path}[{index}]"))
    return errors


def validate_config(cfg: ConfigDict | ConfigOverrideDict) -> ConfigValidationResult:
    errors: list[ConfigValidationError] = []

    for key, value in cast(ConfigObjectMap, cfg).items():
        if key not in VALID_TOP_LEVEL_KEYS:
            errors.append(
                ConfigValidationError(
                    key_path=key,
                    message=f"Unknown config key '{key}'. Expected one of: {', '.join(sorted(VALID_TOP_LEVEL_KEYS))}",
                )
            )
        errors.extend(_none_value_errors(value, key_path=key))

    mode = cfg.get("mode")
    if mode is not None and mode not in {"official", "draft"}:
        errors.append(
            ConfigValidationError(
                key_path="mode",
                message=f"Invalid mode '{mode}'. Expected 'official' or 'draft'.",
            )
        )

    run_history_value = cfg.get("run_history")
    run_history = _config_dict(run_history_value)
    if run_history_value is not None and run_history is None:
        errors.append(
            ConfigValidationError(
                key_path="run_history",
                message="run_history must be a table/object.",
            )
        )
    elif run_history is not None:
        for key in run_history:
            if key not in VALID_RUN_HISTORY_KEYS:
                errors.append(
                    ConfigValidationError(
                        key_path=f"run_history.{key}",
                        message=f"Unknown run_history key '{key}'. Expected one of: {', '.join(sorted(VALID_RUN_HISTORY_KEYS))}",
                    )
                )

        enabled = run_history.get("enabled", True)
        if not isinstance(enabled, bool):
            errors.append(
                ConfigValidationError(
                    key_path="run_history.enabled",
                    message="run_history.enabled must be a boolean",
                )
            )

        limit = run_history.get("limit", 50)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            errors.append(
                ConfigValidationError(
                    key_path="run_history.limit",
                    message="run_history.limit must be a positive integer",
                )
            )

    output_value = cfg.get("output")
    output = _config_dict(output_value)
    if output_value is not None and output is None:
        errors.append(
            ConfigValidationError(
                key_path="output",
                message="output must be a table/object.",
            )
        )
    elif output is not None:
        for key in output:
            if key not in VALID_OUTPUT_KEYS:
                errors.append(
                    ConfigValidationError(
                        key_path=f"output.{key}",
                        message=f"Unknown output key '{key}'. Expected one of: {', '.join(sorted(VALID_OUTPUT_KEYS))}",
                    )
                )

        retention_lines = output.get("retention_lines", 4000)
        if not isinstance(retention_lines, int) or isinstance(retention_lines, bool) or retention_lines <= 0:
            errors.append(
                ConfigValidationError(
                    key_path="output.retention_lines",
                    message="output.retention_lines must be a positive integer",
                )
            )

    review_value = cfg.get("review")
    review = _config_dict(review_value)
    if review_value is not None and review is None:
        errors.append(
            ConfigValidationError(
                key_path="review",
                message="review must be a table/object.",
            )
        )
    elif review is not None:
        for key in review:
            if key not in VALID_REVIEW_KEYS:
                errors.append(
                    ConfigValidationError(
                        key_path=f"review.{key}",
                        message=f"Unknown review key '{key}'. Expected one of: {', '.join(sorted(VALID_REVIEW_KEYS))}",
                    )
                )

        output_dir = review.get("output_dir", "")
        if not isinstance(output_dir, str | Path):
            errors.append(
                ConfigValidationError(
                    key_path="review.output_dir",
                    message="review.output_dir must be a directory path string.",
                )
            )

    analysis_value = cfg.get("analysis")
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

    return _build_validation_result(errors)


def target_exists(target: str, cfg: ConfigDict | ConfigOverrideDict) -> bool:
    other_lib_dirs = _object_list(cfg.get("other_lib_dirs", []))
    dirs = [
        Path(str(raw_path))
        for raw_path in (
            cfg.get("program_dir", ""),
            cfg.get("ABB_lib_dir", ""),
            *other_lib_dirs,
        )
        if str(raw_path).strip()
    ]

    mode = str(cfg.get("mode", "official")).strip().lower()
    # Canonical draft/official code-extension mapping lives in core/syntax.py
    # (code_ext / code_ext_candidates); config validation cannot import it
    # without creating an import cycle, so the candidates are kept in sync here.
    extensions = [".s", ".x"] if mode == "draft" else [".x"]

    for directory in dirs:
        if not directory.exists():
            continue
        for ext in extensions:
            if (directory / f"{target}{ext}").exists():
                return True

    return False


def validate_loaded_config(cfg: ConfigDict) -> ConfigValidationResult:
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

    for index, raw_path in enumerate(_object_list(cfg.get("other_lib_dirs", []))):
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

    return _build_validation_result(errors)


def validate_effective_config(cfg: ConfigDict) -> ConfigValidationResult:
    return _merge_validation_results(validate_config(cfg), validate_loaded_config(cfg))
