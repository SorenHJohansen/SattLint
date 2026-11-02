"""Project resolution and validation helpers for the headless CLI."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from ..cache import get_cache_dir
from ..change_review.settings import resolve_review_output_dir
from ..config import get_config_path
from ..config.types import ConfigDict
from ..project import SLPROJ_FILENAME, discover_project, load_project
from ..project.models import SattLintProjectFile
from ..runs import get_runs_dir
from ._output import CliError
from ._payloads import ConfigInfo, ProjectInfo, ProjectPaths


def resolve_project_file(raw: str | None) -> SattLintProjectFile:
    if raw is None or not raw.strip():
        discovered = discover_project()
        if discovered is None:
            raise CliError(
                f"No {SLPROJ_FILENAME} found from the current directory upward. Use --project PATH.",
                code="project_not_found",
                exit_code=2,
            )
        return _load_project(discovered)

    path = Path(raw).expanduser()
    if path.is_dir():
        candidates = sorted(path.glob(f"*{SLPROJ_FILENAME}"))
        default_project = path / SLPROJ_FILENAME
        if default_project.is_file() and default_project not in candidates:
            candidates.insert(0, default_project)
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
        return load_project(path)
    except FileNotFoundError as exc:
        raise CliError(str(exc), code="project_not_found", exit_code=2) from exc
    except (OSError, ValueError) as exc:
        raise CliError(f"Could not load project: {exc}", code="project_invalid", exit_code=2) from exc


def effective_project_config(project: SattLintProjectFile) -> ConfigDict:
    return project.to_default_merged_config_dict()


def project_paths(cfg: ConfigDict) -> ProjectPaths:
    return {
        "program_dir": str(cfg.get("program_dir") or ""),
        "ABB_lib_dir": str(cfg.get("ABB_lib_dir") or ""),
        "icf_dir": str(cfg.get("icf_dir") or ""),
        "other_lib_dirs": [str(value) for value in cast(list[object], cfg.get("other_lib_dirs") or [])],
    }


def project_payload(project: SattLintProjectFile) -> ProjectInfo:
    cfg = effective_project_config(project)
    raw = project.data
    config_path = get_config_path()
    config: ConfigInfo = {"path": str(config_path), "exists": config_path.exists()}
    return {
        "path": str(project.path),
        "root": str(project.root),
        "slproj_version": int(raw.get("slproj_version", 1)),
        "mode": str(raw.get("mode", "official")),
        "targets": list(raw.get("analyzed_programs_and_libraries", [])),
        "analysis": dict(raw.get("analysis", {})),
        "paths": project_paths(cfg),
        "config": config,
        "cache_dir": str(get_cache_dir()),
        "runs_dir": str(get_runs_dir()),
        "review_output_dir": str(resolve_review_output_dir(cfg)),
    }


__all__ = [
    "effective_project_config",
    "project_paths",
    "project_payload",
    "resolve_project_file",
]
