"""Reset contamination detection for SattLine modules.

A variable is 'reset contaminated' when it is written during a run condition
(i.e. when a sequence's .Reset flag is False) but not reset across all reset
paths. This means the variable can retain stale state across equipment resets.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import cast

from sattlint.parser_api import (
    Assignment,
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    Variable,
    VarRef,
    walk,
)

from ...reporting.variables_report import ResetContaminationIssue, VariableIssue
from ...resolution.common import resolve_moduletype_def_strict
from ...resolution.paths import path_startswith_casefold
from ...types import VariableId
from ..framework import AnalysisSharedArtifacts, BasePictureAnalyzer
from ..shared.variable_utils import matches_root_origin, same_origin_file_stem
from ._reset_latching import check_for_modulecode_latching
from ._reset_path_collection import collect_paths_in_modulecode, path_covers_write
from ._reset_path_state import PathCollectionDebug, WriteMap

__all__ = [
    "ResetContaminationAnalyzer",
    "WriteMap",
    "detect_implicit_latching",
    "detect_reset_contamination",
    "is_from_root_origin",
]


class ResetContaminationAnalyzer(BasePictureAnalyzer):
    """Class-backed owner for reset-contamination scans and helper traversal."""

    _visited_typedef_keys: set[tuple[str, str, str]]
    _active_typedef_keys: set[tuple[str, str, str]]

    @staticmethod
    def _should_analyze_path(path: list[str], limit_to_module_path: list[str] | None) -> bool:
        if limit_to_module_path is None:
            return True
        return path_startswith_casefold(limit_to_module_path, path) or path_startswith_casefold(
            path, limit_to_module_path
        )

    @staticmethod
    def _build_local_env(
        owner: object,
        moduleparameters: list[Variable] | None,
        localvariables: list[Variable] | None,
        *,
        shared_artifacts: AnalysisSharedArtifacts | None = None,
    ) -> dict[str, Variable]:
        if shared_artifacts is not None:
            cached = shared_artifacts.local_variable_envs.get(id(owner))
            if cached is not None:
                return cached

        env: dict[str, Variable] = {}
        for var in moduleparameters or []:
            env[var.name.casefold()] = var
        for var in localvariables or []:
            env[var.name.casefold()] = var

        if shared_artifacts is not None:
            shared_artifacts.local_variable_envs[id(owner)] = env
            shared_artifacts.counters.local_env_builds += 1
        return env

    @staticmethod
    def _check_for_single(
        mod: SingleModule,
        path: list[str],
        issues: list[VariableIssue],
        *,
        check_fn: Callable[..., None],
        shared_artifacts: AnalysisSharedArtifacts | None = None,
    ) -> None:
        if mod.modulecode is None:
            return
        env = ResetContaminationAnalyzer._build_local_env(
            mod,
            mod.moduleparameters,
            mod.localvariables,
            shared_artifacts=shared_artifacts,
        )
        check_fn(mod.modulecode, env, path, issues)

    def _check_for_typedef(
        self,
        mt: ModuleTypeDef,
        path: list[str],
        issues: list[VariableIssue],
        limit_to_module_path: list[str] | None,
        *,
        check_fn: Callable[..., None],
        shared_artifacts: AnalysisSharedArtifacts | None = None,
    ) -> None:
        key = (mt.name.casefold(), (mt.origin_file or "").casefold(), (mt.origin_lib or "").casefold())
        visited = cast("set[tuple[str, str, str]] | None", getattr(self, "_visited_typedef_keys", None))
        if visited is not None and key in visited:
            return
        active = cast("set[tuple[str, str, str]] | None", getattr(self, "_active_typedef_keys", None))
        if active is not None and key in active:
            return
        if visited is not None:
            visited.add(key)
        if active is None:
            active = set[tuple[str, str, str]]()
            self._active_typedef_keys = active
        active.add(key)
        try:
            self._check_for_typedef_body(
                mt,
                key,
                path,
                issues,
                limit_to_module_path,
                check_fn=check_fn,
                shared_artifacts=shared_artifacts,
            )
        finally:
            active.discard(key)

    def _check_for_typedef_body(
        self,
        mt: ModuleTypeDef,
        key: tuple[str, str, str],
        path: list[str],
        issues: list[VariableIssue],
        limit_to_module_path: list[str] | None,
        *,
        check_fn: Callable[..., None],
        shared_artifacts: AnalysisSharedArtifacts | None = None,
    ) -> None:
        del key
        if mt.modulecode is not None and self._should_analyze_path(path, limit_to_module_path):
            env = ResetContaminationAnalyzer._build_local_env(
                mt,
                mt.moduleparameters,
                mt.localvariables,
                shared_artifacts=shared_artifacts,
            )
            check_fn(mt.modulecode, env, path, issues)
        for child in mt.submodules or []:
            self._collect_from_module(
                child,
                path,
                issues,
                limit_to_module_path,
                check_fn=check_fn,
                shared_artifacts=shared_artifacts,
            )

    def _collect_from_module(
        self,
        mod: SingleModule | FrameModule | ModuleTypeInstance,
        path: list[str],
        issues: list[VariableIssue],
        limit_to_module_path: list[str] | None,
        *,
        check_fn: Callable[..., None],
        shared_artifacts: AnalysisSharedArtifacts | None = None,
    ) -> None:
        if isinstance(mod, ModuleTypeInstance):
            mod_path = [*path, mod.header.name]
            try:
                moduletype = resolve_moduletype_def_strict(self.bp, mod.moduletype_name)
            except ValueError:
                return
            if not self._typedef_is_from_root(moduletype):
                return
            self._check_for_typedef(
                moduletype,
                mod_path,
                issues,
                limit_to_module_path,
                check_fn=check_fn,
                shared_artifacts=shared_artifacts,
            )
            return

        if isinstance(mod, SingleModule):
            mod_path = [*path, mod.header.name]
            if ResetContaminationAnalyzer._should_analyze_path(mod_path, limit_to_module_path):
                ResetContaminationAnalyzer._check_for_single(
                    mod,
                    mod_path,
                    issues,
                    check_fn=check_fn,
                    shared_artifacts=shared_artifacts,
                )
            for child in mod.submodules or []:
                self._collect_from_module(
                    child,
                    mod_path,
                    issues,
                    limit_to_module_path,
                    check_fn=check_fn,
                    shared_artifacts=shared_artifacts,
                )
            return

        # FrameModule (and any remaining transparent container).
        mod_path = [*path, mod.header.name]
        for child in mod.submodules or []:
            self._collect_from_module(
                child,
                mod_path,
                issues,
                limit_to_module_path,
                check_fn=check_fn,
                shared_artifacts=shared_artifacts,
            )

    @staticmethod
    def _check_for_modulecode(
        modulecode: ModuleCode,
        env: dict[str, Variable],
        path: list[str],
        issues: list[VariableIssue],
        *,
        path_debug: PathCollectionDebug | None = None,
    ) -> None:
        sequences = list(modulecode.sequences or [])
        if not sequences:
            return

        var_refs = ResetContaminationAnalyzer._collect_var_refs(modulecode)
        for seq in sequences:
            seq_name = getattr(seq, "name", "")
            if not seq_name:
                continue
            reset_ref = f"{seq_name}.Reset"
            reset_ref_cf = reset_ref.casefold()
            if reset_ref_cf not in var_refs:
                continue

            reset_old_vars = ResetContaminationAnalyzer._collect_reset_old_vars(modulecode, reset_ref_cf)
            reset_old_cf = {name.casefold() for name in reset_old_vars}
            path_states = collect_paths_in_modulecode(
                modulecode,
                env,
                reset_ref_cf,
                reset_old_cf,
                path_debug=path_debug,
            )
            if path_debug is not None:
                path_debug.emit(
                    "modulecode-path-summary",
                    module_path=path,
                    sequence_name=seq_name,
                    path_count=len(path_states),
                    reset_path_count=sum(1 for state in path_states if state.reset_state == "reset"),
                    run_write_count=sum(len(state.run_writes) for state in path_states),
                )

            run_writes: WriteMap = {}
            for state in path_states:
                run_writes.update(state.run_writes)

            if not run_writes:
                continue

            reset_paths = [state for state in path_states if state.reset_state == "reset"]

            for key, (var, field_path) in sorted(run_writes.items(), key=lambda item: (item[0][0], item[0][1])):
                var_key, _field_key = key
                if var_key in reset_old_cf:
                    continue
                if reset_paths and all(path_covers_write(state.reset_writes, key) for state in reset_paths):
                    continue

                issues.append(
                    ResetContaminationIssue(
                        module_path=path.copy(),
                        variable=var,
                        role="localvariable",
                        field_path=field_path or None,
                        sequence_name=seq_name,
                        reset_variable=VariableId(reset_ref),
                    )
                )

    @staticmethod
    def _collect_var_refs(modulecode: ModuleCode) -> set[str]:
        return {
            event.node.name.casefold()
            for event in walk(modulecode)
            if isinstance(event.node, VarRef) and event.node.name
        }

    @staticmethod
    def _collect_reset_old_vars(modulecode: ModuleCode, reset_ref_cf: str) -> set[str]:
        reset_old_vars: set[str] = set()
        for event in walk(modulecode):
            obj = event.node
            if not isinstance(obj, Assignment):
                continue
            value = obj.value
            if isinstance(value, VarRef) and value.name and value.name.casefold() == reset_ref_cf:
                reset_old_vars.add(obj.target.name)
        return reset_old_vars

    def _typedef_is_from_root(self, moduletype: ModuleTypeDef) -> bool:
        """Whether a module type definition belongs to the analyzed target.

        A definition without an origin file is only treated as root-owned when
        its library also matches, so a dependency typedef that lost its origin
        file during the merge is not reported under the program.
        """
        return matches_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(self.bp, "origin_file", None),
            analyzed_target_is_library=getattr(self, "_analyzed_target_is_library", False),
            origin_lib=getattr(moduletype, "origin_lib", None),
            root_origin_lib=getattr(self.bp, "origin_lib", None),
        )

    def detect_reset_contamination(
        self,
        issues: list[VariableIssue],
        limit_to_module_path: list[str] | None = None,
        *,
        debug: bool = False,
        trace_fn: Callable[..., None] | None = None,
        shared_artifacts: AnalysisSharedArtifacts | None = None,
        analyzed_target_is_library: bool = False,
    ) -> None:
        """Scan all SingleModules and ModuleTypeDefs for reset-contaminated variables."""
        self._analyzed_target_is_library = analyzed_target_is_library
        self._visited_typedef_keys = set()
        self._active_typedef_keys = set()
        path_debug = PathCollectionDebug(enabled=debug, trace_fn=trace_fn)
        reset_check = partial(self._check_for_modulecode, path_debug=path_debug)

        for mod in self.bp.submodules or []:
            self._collect_from_module(
                mod,
                self.root_path,
                issues,
                limit_to_module_path,
                check_fn=reset_check,
                shared_artifacts=shared_artifacts,
            )

        if limit_to_module_path is not None:
            return

        for mt in self.bp.moduletype_defs or []:
            if not self._typedef_is_from_root(mt):
                continue
            td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]
            self._check_for_typedef(
                mt,
                td_path,
                issues,
                limit_to_module_path,
                check_fn=reset_check,
                shared_artifacts=shared_artifacts,
            )

    def detect_implicit_latching(
        self,
        issues: list[VariableIssue],
        limit_to_module_path: list[str] | None = None,
        *,
        shared_artifacts: AnalysisSharedArtifacts | None = None,
        analyzed_target_is_library: bool = False,
    ) -> None:
        """Scan module code for boolean latch patterns across branches and steps."""
        self._analyzed_target_is_library = analyzed_target_is_library
        self._visited_typedef_keys = set()
        self._active_typedef_keys = set()

        if self.bp.modulecode is not None and self._should_analyze_path(self.root_path, limit_to_module_path):
            env = self._build_local_env(self.bp, None, self.bp.localvariables, shared_artifacts=shared_artifacts)
            check_for_modulecode_latching(self.bp.modulecode, env, self.root_path, issues)

        for mod in self.bp.submodules or []:
            self._collect_from_module(
                mod,
                self.root_path,
                issues,
                limit_to_module_path,
                check_fn=check_for_modulecode_latching,
                shared_artifacts=shared_artifacts,
            )

        if limit_to_module_path is not None:
            return

        for mt in self.bp.moduletype_defs or []:
            if not self._typedef_is_from_root(mt):
                continue
            td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]
            self._check_for_typedef(
                mt,
                td_path,
                issues,
                limit_to_module_path,
                check_fn=check_for_modulecode_latching,
                shared_artifacts=shared_artifacts,
            )


def detect_reset_contamination(
    bp: BasePicture,
    issues: list[VariableIssue],
    limit_to_module_path: list[str] | None = None,
    *,
    debug: bool = False,
    trace_fn: Callable[..., None] | None = None,
    shared_artifacts: AnalysisSharedArtifacts | None = None,
    analyzed_target_is_library: bool = False,
) -> None:
    analyzer = ResetContaminationAnalyzer(bp)
    analyzer.detect_reset_contamination(
        issues,
        limit_to_module_path,
        debug=debug,
        trace_fn=trace_fn,
        shared_artifacts=shared_artifacts,
        analyzed_target_is_library=analyzed_target_is_library,
    )


def detect_implicit_latching(
    bp: BasePicture,
    issues: list[VariableIssue],
    limit_to_module_path: list[str] | None = None,
    *,
    shared_artifacts: AnalysisSharedArtifacts | None = None,
    analyzed_target_is_library: bool = False,
) -> None:
    analyzer = ResetContaminationAnalyzer(bp)
    analyzer.detect_implicit_latching(
        issues,
        limit_to_module_path,
        shared_artifacts=shared_artifacts,
        analyzed_target_is_library=analyzed_target_is_library,
    )


def is_from_root_origin(origin_file: str | None, root_origin: str | None) -> bool:
    return same_origin_file_stem(origin_file, root_origin)
