"""Shared loader state and compatibility helpers for the engine."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from sattline_parser.models.ast_model import BasePicture

from . import _engine_syntax_helpers as engine_syntax_helpers
from ._engine_loader_config import (
    SattLineProjectLoaderConfig,
    SattLineProjectLoaderDependencies,
    SattLineProjectLoaderRuntime,
)
from ._validation_shared import ValidationWarning
from .models.project_graph import ProjectGraph

log = logging.getLogger("SattLint")

CodeMode = engine_syntax_helpers.CodeMode
code_ext = engine_syntax_helpers.code_ext
deps_ext = engine_syntax_helpers.deps_ext
expected_unavailable_library_reason = engine_syntax_helpers.expected_unavailable_library_reason
_has_current_local_validation = engine_syntax_helpers.has_current_local_validation
_mark_local_validation = engine_syntax_helpers.mark_local_validation
_record_project_failure = engine_syntax_helpers.record_project_failure
_record_project_warning = engine_syntax_helpers.record_project_warning


def _engine_module():
    return importlib.import_module("sattlint.engine")


class CircularDependencyError(RuntimeError):
    """Exception raised when circular dependencies are detected."""

    def __init__(self, library: str, cycle_path: list[str]):
        self.library = library
        self.cycle_path = cycle_path
        super().__init__(f"Circular dependency detected: {' -> '.join([*cycle_path, cycle_path[0]])}")


class DependencyVersionCompatibilityError(RuntimeError):
    """Exception raised when conflicting dependency datecodes are detected."""

    def __init__(self, conflicts: list[str]):
        self.conflicts = conflicts
        super().__init__(f"Dependency version compatibility check failed: {'; '.join(conflicts)}")


def ensure_local_validation(
    basepic: BasePicture,
    *,
    warning_sink: list[ValidationWarning] | None = None,
) -> bool:
    engine_module = _engine_module()

    return engine_syntax_helpers.ensure_local_validation(
        basepic,
        warning_sink=warning_sink,
        has_current_local_validation_fn=_has_current_local_validation,
        mark_local_validation_fn=_mark_local_validation,
        validate_transformed_basepicture_locally_fn=engine_module.validate_transformed_basepicture_locally,
    )


def mark_local_validation(basepic: BasePicture) -> BasePicture:
    return _mark_local_validation(basepic)


def record_missing_library(
    graph: ProjectGraph,
    *,
    name: str,
    mode: str,
    strict: bool,
    requester: str | None = None,
) -> None:
    reason = expected_unavailable_library_reason(name)
    if reason:
        graph.unavailable_libraries.add(name.casefold())
        if requester and requester.casefold() != name.casefold():
            _record_project_warning(
                graph,
                requester,
                f"dependency '{name}' unavailable: {reason}",
            )
        else:
            _record_project_warning(graph, name, f"unavailable library: {reason}")
        return

    if requester and requester.casefold() != name.casefold():
        message = f"Missing code file for dependency '{name}' referenced by '{requester}' ({mode})"
    else:
        message = f"Missing code file for '{name}' ({mode})"
    if strict:
        raise FileNotFoundError(message)
    graph.missing.append(message)
    graph.unavailable_libraries.add(name.casefold())


@dataclass(frozen=True)
class PrefetchedDependencyCandidate:
    name: str
    requester_dir: Path | None
    code_path: Path | None
    deps_path: Path | None


@dataclass(frozen=True)
class PrefetchedLoadResult:
    basepicture: BasePicture
    load_or_parse_duration_s: float
    ast_cache_save_required: bool


class DebugMixin:
    debug: bool = False

    def dbg(self, msg: str) -> None:
        if self.debug:
            lines = str(msg).splitlines() or [""]
            for line in lines:
                log.debug(f"[DEBUG] {line}")


class SattLineProjectLoaderBase(DebugMixin):
    def __init__(
        self,
        config: SattLineProjectLoaderConfig,
        *,
        runtime: SattLineProjectLoaderRuntime | None = None,
        dependencies: SattLineProjectLoaderDependencies | None = None,
    ):
        engine_module = _engine_module()

        selected_runtime = SattLineProjectLoaderRuntime() if runtime is None else runtime
        selected_dependencies = SattLineProjectLoaderDependencies() if dependencies is None else dependencies
        self.config = config
        self.program_dir = config.program_dir
        self.other_lib_dirs = list(config.other_lib_dirs)
        self.abb_lib_dir = config.abb_lib_dir
        self.mode = config.mode
        self.scan_root_only = config.scan_root_only
        self.debug = config.debug
        self.contextual_lookup = selected_runtime.contextual_lookup
        self.use_file_ast_cache = config.use_file_ast_cache
        self._status_update_fn = selected_runtime.status_update_fn
        self.refresh_mode = config.refresh_mode
        self._stage_timing_sink = selected_runtime.stage_timing_sink
        self._graphics_timing_sink = selected_runtime.graphics_timing_sink
        self._last_status_message: str | None = None
        self.parser = engine_module.create_sl_parser()
        self.transformer = engine_module.SLTransformer()
        self._visited: set[str] = set()
        self._visit_stack: list[str] = []
        self._ignored_dirs: set[Path] = set()
        if selected_dependencies.cache_manager is None:
            self._cache_dir = engine_module.get_cache_dir()
            self._cache_manager = engine_module.cache_module.get_cache_manager(
                self._cache_dir,
                file_lookup_cache_cls=engine_module.FileLookupCache,
                file_ast_cache_cls=engine_module.FileASTCache,
            )
        else:
            self._cache_manager = selected_dependencies.cache_manager
            self._cache_dir = self._cache_manager.cache_dir
        self._lookup_cache = self._cache_manager.file_lookup_cache
        self._ast_cache = self._cache_manager.file_ast_cache
        self._base_indexes: dict[Path, dict[str, dict[str, Path]]] = {}
        self._lib_by_name: dict[str, str] = {}
        self._prefetched_dependency_candidates: dict[tuple[str, str | None], PrefetchedDependencyCandidate] = {}
        self._prefetched_load_results_by_path: dict[Path, PrefetchedLoadResult] = {}
        self.dbg(f"Selected mode={self.mode.value}, code_ext={code_ext(self.mode)}, deps_ext={deps_ext(self.mode)}")
        self.dbg(f"Programs dir: {self.program_dir}")
        for i, ld in enumerate(self.other_lib_dirs, start=1):
            self.dbg(f"Lib {i}: {ld}")
        self.dbg(f"ABB lib dir: {self.abb_lib_dir}")

    def _record_stage_timing(self, owner_name: str, stage: str, started_at: float) -> None:
        if self._stage_timing_sink is None:
            return
        self._stage_timing_sink(owner_name, stage, perf_counter() - started_at)

    def _record_stage_duration(self, owner_name: str, stage: str, duration: float) -> None:
        if self._stage_timing_sink is None:
            return
        self._stage_timing_sink(owner_name, stage, duration)

    def _update_status(self, message: str) -> None:
        if self._status_update_fn is None:
            return
        text = str(message).strip()
        if not text or text == self._last_status_message:
            return
        self._last_status_message = text
        self._status_update_fn(text)

    def _flush_lookup_cache(self) -> None:
        flush = getattr(self._lookup_cache, "flush", None)
        if callable(flush):
            flush()
