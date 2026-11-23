"""Project resolution and validation helpers for the headless CLI."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

from ..cache import cache_dir_location
from ..change_review.settings import review_output_dir_location
from ..config import config_path_location, load_config
from ..config.defaults import DEFAULT_CONFIG
from ..config.string_capacities import resolve_string_capacities
from ..config.types import ConfigDict
from ..project import SLPROJ_FILENAME, SLPROJ_VERSION, discover_project, load_project
from ..project.models import SattLintProjectFile
from ..runs import runs_dir_location
from ._output import CliError
from ._payloads import ConfigInfo, ProjectInfo, ProjectPaths


def resolve_project_file(raw: str | None) -> SattLintProjectFile:
    if raw is None:
        discovered = discover_project()
        if discovered is None:
            raise CliError(
                f"No {SLPROJ_FILENAME} found from the current directory upward. Use --project PATH.",
                code="project_not_found",
                exit_code=2,
            )
        return _load_project(discovered)
    if not raw.strip():
        raise CliError(
            "Project path is empty. Pass a .slproj path or omit --project to discover one.",
            code="usage_error",
            exit_code=2,
        )

    path = Path(raw).expanduser()
    if path.is_dir():
        candidates = sorted(path.glob(f"*{SLPROJ_FILENAME}"))
        if not candidates:
            raise CliError(
                f"No {SLPROJ_FILENAME} found in {path}.",
                code="project_not_found",
                exit_code=2,
            )
        if len(candidates) > 1:
            raise CliError(
                f"Multiple {SLPROJ_FILENAME} files found in {path}; pass the file explicitly.",
                code="project_ambiguous",
                exit_code=2,
                details={"candidates": [str(candidate) for candidate in candidates]},
            )
        return _load_project(candidates[0])
    return _load_project(path)


def _load_project(path: Path) -> SattLintProjectFile:
    try:
        project = load_project(path)
    except FileNotFoundError as exc:
        raise CliError(str(exc), code="project_not_found", exit_code=2) from exc
    except (OSError, ValueError) as exc:
        raise CliError(f"Could not load project: {exc}", code="project_invalid", exit_code=2) from exc
    for warning in project.warnings:
        _write_config_message(f"Warning: {warning}")
    return project


_CONFIG_WARNINGS: list[str] = []


def _write_config_message(message: str) -> None:
    _CONFIG_WARNINGS.append(f"{message}")


def drain_config_warnings() -> tuple[str, ...]:
    warnings = tuple(_CONFIG_WARNINGS)
    _CONFIG_WARNINGS.clear()
    return warnings


def _load_user_config(*, quiet: bool = False) -> ConfigDict:
    """Load the user config used as the base for project settings."""
    path = config_path_location()
    if not path.exists():
        return cast(ConfigDict, deepcopy(DEFAULT_CONFIG))
    try:
        cfg, _ = load_config(path, emit_fn=(lambda _message: None) if quiet else _write_config_message)
    except (OSError, ValueError) as exc:
        raise CliError(f"Could not load user config {path}: {exc}", code="config_invalid", exit_code=2) from exc
    return cfg


def effective_project_config(project: SattLintProjectFile, *, quiet: bool = False) -> ConfigDict:
    return project.to_default_merged_config_dict(_load_user_config(quiet=quiet))


def project_paths(cfg: ConfigDict) -> ProjectPaths:
    return {
        "program_dir": str(cfg.get("program_dir") or ""),
        "ABB_lib_dir": str(cfg.get("ABB_lib_dir") or ""),
        "icf_dir": str(cfg.get("icf_dir") or ""),
        "other_lib_dirs": [str(value) for value in cast(list[object], cfg.get("other_lib_dirs") or [])],
    }


def project_payload(project: SattLintProjectFile, *, quiet: bool = False) -> ProjectInfo:
    cfg = effective_project_config(project, quiet=quiet)
    raw = project.data
    config_path = config_path_location()
    config: ConfigInfo = {"path": str(config_path), "exists": config_path.exists()}
    return {
        "path": str(project.path),
        "root": str(project.root),
        "slproj_version": int(raw.get("slproj_version", SLPROJ_VERSION)),
        "mode": str(raw.get("mode", "official")),
        "targets": list(raw.get("analyzed_programs_and_libraries", [])),
        "analyzers": list(raw.get("analyzers", [])),
        "string_capacities": resolve_string_capacities(cfg).as_dict(),
        "analysis": dict(cfg.get("analysis") or {}),
        "paths": project_paths(cfg),
        "config": config,
        "cache_dir": str(cache_dir_location()),
        "runs_dir": str(runs_dir_location()),
        "review_output_dir": str(review_output_dir_location(cfg)),
    }


__all__ = [
    "drain_config_warnings",
    "effective_project_config",
    "project_paths",
    "project_payload",
    "resolve_project_file",
]
