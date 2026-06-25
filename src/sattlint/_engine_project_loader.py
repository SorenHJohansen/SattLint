"""Recursive SattLine project loader implementation."""

from __future__ import annotations

import importlib
from pathlib import Path
from time import perf_counter

from . import _engine_syntax_helpers as engine_syntax_helpers
from ._engine_loader_base import CircularDependencyError, DependencyVersionCompatibilityError, record_missing_library
from ._engine_loader_lookup import SattLineProjectLoaderLookupMixin
from ._validation_shared import ValidationWarning
from .models.project_graph import ProjectGraph
from .validation import StructuralValidationError

_format_debug_list = engine_syntax_helpers.format_debug_list
_format_debug_missing_entries = engine_syntax_helpers.format_debug_missing_entries
_has_current_local_validation = engine_syntax_helpers.has_current_local_validation
_record_project_failure = engine_syntax_helpers.record_project_failure
_record_project_warning = engine_syntax_helpers.record_project_warning


def _engine_module():
    return importlib.import_module("sattlint.engine")


class SattLineProjectLoader(SattLineProjectLoaderLookupMixin):
    def visit_target(
        self,
        target_name: str,
        graph: ProjectGraph,
        syntax_only: bool,
        *,
        requester_dir: Path | None,
        syntax_check: bool,
    ) -> None:
        self._visit(
            target_name,
            graph,
            syntax_only,
            requester_dir=requester_dir,
            syntax_check=syntax_check,
        )

    def flush_lookup_cache(self) -> None:
        self._flush_lookup_cache()

    def resolve(self, root_name: str, strict: bool = False, *, syntax_check: bool = False) -> ProjectGraph:
        if self.scan_root_only:
            return self._resolve_root_only(root_name, strict)
        self._update_status(f"Loading {root_name}: resolving dependency graph")
        self.dbg(f"Resolving root: {root_name}")
        graph = ProjectGraph()
        previous_root_key = getattr(self, "_active_root_key", None)
        self._active_root_key = root_name.casefold()
        try:
            self._visit(root_name, graph, strict, requester_dir=self.program_dir, syntax_check=syntax_check)
        finally:
            self._flush_lookup_cache()
            self._active_root_key = previous_root_key
        self.dbg(_format_debug_list("Resolved ASTs", graph.ast_by_name.keys()))
        if graph.missing:
            self.dbg(_format_debug_missing_entries(graph.missing))
        return graph

    def _resolve_root_only(self, root_name: str, strict: bool) -> ProjectGraph:
        graph = ProjectGraph()
        validation_warnings: list[ValidationWarning] = []

        def record_validation_warnings() -> None:
            for warning in validation_warnings:
                _record_project_warning(graph, root_name, warning)
            validation_warnings.clear()

        try:
            engine_module = _engine_module()
            attach_graphics_companion = engine_module._attach_graphics_companion

            self._update_status(f"Loading {root_name}: locating source file")
            code_path = self._find_code(root_name)

            if not code_path:
                record_missing_library(
                    graph,
                    name=root_name,
                    mode=f"mode={self.mode.value}",
                    strict=strict,
                )
                return graph

            try:
                basepicture = self._load_or_parse_for_owner(code_path, owner_name=root_name)
            except Exception as ex:
                if strict:
                    raise
                _record_project_failure(graph, root_name, ex)
                return graph

            try:
                if basepicture is None:
                    message = f"{root_name} transformed to no BasePicture (parse/transform issue?)"
                    if strict:
                        raise RuntimeError(message)
                    graph.missing.append(message)
                    return graph
                self._update_status(f"Loading {root_name}: validating {code_path.name}")
                validation_started_at = perf_counter()
                engine_module.validate_transformed_basepicture(
                    basepicture,
                    allow_unresolved_external_datatypes=True if self.refresh_mode == "ast-only" else not strict,
                    enforce_unique_submodule_names=False,
                    allow_parameterless_module_mappings=True,
                    warn_unknown_parameter_targets=self.refresh_mode != "ast-only",
                    warn_incompatible_parameter_mappings=self.refresh_mode != "ast-only",
                    warning_sink=validation_warnings.append,
                )
                self._record_stage_timing(root_name, "validate", validation_started_at)
                record_validation_warnings()
                graph.ast_by_name[root_name] = basepicture
                if self.refresh_mode == "ast-only":
                    return graph
                graphics_started_at = perf_counter()

                def _root_status_cb(msg: str) -> None:
                    self._update_status(f"Loading {root_name}: {msg}")

                if attach_graphics_companion(
                    basepicture,
                    code_path=code_path,
                    mode=self.mode,
                    graph=graph,
                    owner_name=root_name,
                    timing_sink=self._graphics_timing_sink,
                    status_callback=_root_status_cb,
                ):
                    self._ast_cache.save(code_path, self.mode.value, basepicture)
                self._record_stage_timing(root_name, "attach_graphics", graphics_started_at)
                library_name = self._record_library_name(root_name, code_path)
                self._update_status(f"Loading {root_name}: indexing definitions")
                index_started_at = perf_counter()
                graph.index_from_basepic(basepicture, source_path=code_path, library_name=library_name)
                self._record_stage_timing(root_name, "index", index_started_at)
                return graph
            except Exception as ex:
                record_validation_warnings()
                if strict:
                    raise
                _record_project_failure(graph, root_name, ex)
                return graph
        finally:
            self._flush_lookup_cache()

    def _visit(  # noqa: PLR0915
        self,
        name: str,
        graph: ProjectGraph,
        strict: bool,
        *,
        requester_dir: Path | None,
        syntax_check: bool = False,
    ) -> None:
        key = name.lower()
        root_key = getattr(self, "_active_root_key", None)
        engine_module = _engine_module()
        attach_graphics_companion = engine_module._attach_graphics_companion
        collect_dependency_version_conflicts = engine_module._collect_dependency_version_conflicts

        if key in self._visited:
            return

        if key in self._visit_stack:
            cycle_start_idx = self._visit_stack.index(key)
            cycle_path = list(self._visit_stack[cycle_start_idx:])
            raise CircularDependencyError(name, cycle_path)

        self._visit_stack.append(key)

        try:
            root_code_path: Path | None = None
            if strict and syntax_check and key == root_key:
                self._update_status(f"Loading {name}: running syntax check")
                root_code_path = self._find_code_with_context(name, requester_dir=requester_dir)
                if root_code_path is not None:
                    engine_module.raise_syntax_validation_failure(
                        engine_module.validate_single_file_syntax(root_code_path, mode=self.mode)
                    )

            self._update_status(f"Loading {name}: reading dependency list")
            deps_path = self._find_deps_with_context(name, requester_dir=requester_dir)
            dep_names = self._read_deps(deps_path) if deps_path else []
            dependency_requester = deps_path.parent if deps_path is not None else requester_dir
            self._prefetch_dependency_candidates(dep_names, requester_dir=dependency_requester)

            for index, dep in enumerate(dep_names, start=1):
                self._update_status(f"Loading {name}: resolving dependency {index}/{len(dep_names)} {dep}")
                self._visit(dep, graph, strict, requester_dir=dependency_requester, syntax_check=syntax_check)

            dep_libs: list[str] = []
            for dep in dep_names:
                dep_bp = graph.ast_by_name.get(dep)
                dependency_library_name = self._dependency_library_name(graph, dep, dep_bp)
                if dependency_library_name:
                    dep_libs.append(dependency_library_name)

            self._update_status(f"Loading {name}: locating source file")
            code_path = root_code_path or self._find_code_with_context(name, requester_dir=requester_dir)
            if code_path is not None:
                if engine_syntax_helpers.is_expected_unavailable_library(name):
                    reason = engine_syntax_helpers.expected_unavailable_library_reason(name)
                    graph.unavailable_libraries.add(name.casefold())
                    _record_project_warning(
                        graph, name, f"unavailable library: {reason or 'expected proprietary dependency'}"
                    )
                    return
                try:
                    validation_warnings: list[ValidationWarning] = []
                    basepicture = self._load_or_parse_for_owner(code_path, owner_name=name)
                    if basepicture is None:
                        message = f"{name} transform produced no BasePicture (skipped)"
                        if strict:
                            raise RuntimeError(message)
                        graph.missing.append(message)
                        return
                    try:
                        self._update_status(f"Loading {name}: validating {code_path.name}")
                        validation_started_at = perf_counter()
                        if key != root_key and _has_current_local_validation(basepicture):
                            engine_module.validate_transformed_basepicture_dependency_context(
                                basepicture,
                                external_datatypes=()
                                if self.refresh_mode == "ast-only"
                                else tuple(graph.datatype_defs.values()),
                                external_moduletype_defs=()
                                if self.refresh_mode == "ast-only"
                                else tuple(graph.moduletype_defs.values()),
                                allow_parameterless_module_mappings=True,
                                warn_unknown_parameter_targets=self.refresh_mode != "ast-only",
                                warn_incompatible_parameter_mappings=self.refresh_mode != "ast-only",
                                warning_sink=validation_warnings.append,
                            )
                        else:
                            engine_module.validate_transformed_basepicture(
                                basepicture,
                                external_datatypes=()
                                if self.refresh_mode == "ast-only"
                                else tuple(graph.datatype_defs.values()),
                                external_moduletype_defs=()
                                if self.refresh_mode == "ast-only"
                                else tuple(graph.moduletype_defs.values()),
                                allow_unresolved_external_datatypes=True
                                if self.refresh_mode == "ast-only"
                                else not strict,
                                enforce_unique_submodule_names=False,
                                allow_parameterless_module_mappings=True,
                                warn_unknown_parameter_targets=self.refresh_mode != "ast-only",
                                warn_incompatible_parameter_mappings=self.refresh_mode != "ast-only",
                                warning_sink=validation_warnings.append,
                            )
                        self._record_stage_timing(name, "validate", validation_started_at)
                    except StructuralValidationError as ex:
                        if key == root_key:
                            raise
                        _record_project_warning(graph, name, f"validation warning: {ex}")
                    for warning in validation_warnings:
                        _record_project_warning(graph, name, warning)
                    self._update_status(f"Loading {name}: validation complete")
                    graph.ast_by_name[name] = basepicture
                    if self.refresh_mode == "ast-only":
                        return
                    self._update_status(f"Loading {name}: checking graphics companion")
                    self._update_status(f"Loading {name}: processing graphics companion")

                    def _status_cb(msg: str) -> None:
                        self._update_status(f"Loading {name}: {msg}")

                    if attach_graphics_companion(
                        basepicture,
                        code_path=code_path,
                        mode=self.mode,
                        graph=graph,
                        owner_name=name,
                        timing_sink=self._graphics_timing_sink,
                        status_callback=_status_cb,
                    ):
                        self._update_status(f"Loading {name}: saving AST cache")
                        self._ast_cache.save(code_path, self.mode.value, basepicture)
                    self._update_status(f"Loading {name}: recording library")
                    library_name = self._record_library_name(name, code_path)
                    self._update_status(f"Loading {name}: checking version conflicts")
                    version_conflicts = collect_dependency_version_conflicts(
                        graph,
                        basepicture,
                        library_name=library_name,
                        source_path=code_path,
                    )
                    if version_conflicts:
                        if strict:
                            raise DependencyVersionCompatibilityError(version_conflicts)
                        for conflict in version_conflicts:
                            _record_project_warning(
                                graph,
                                name,
                                f"version compatibility warning: {conflict}",
                            )
                    self._update_status(f"Loading {name}: adding deps")
                    graph.add_library_dependencies(library_name, dep_libs)
                    self._update_status(f"Loading {name}: indexing definitions")
                    index_started_at = perf_counter()
                    graph.index_from_basepic(basepicture, source_path=code_path, library_name=library_name)
                    self._record_stage_timing(name, "index", index_started_at)
                except Exception as ex:
                    for warning in locals().get("validation_warnings", []):
                        _record_project_warning(graph, name, warning)
                    if strict:
                        raise
                    _record_project_failure(graph, name, ex)
            else:
                vendor_code = self._find_vendor_code(name)
                vendor_deps = self._find_vendor_deps(name)
                if vendor_code or vendor_deps:
                    graph.ignored_vendor.append(f"{name} (vendor: {vendor_code or vendor_deps})")
                    graph.unavailable_libraries.add(name.lower())
                else:
                    requester_name = self._visit_stack[-2] if len(self._visit_stack) > 1 else None
                    record_missing_library(
                        graph,
                        name=name,
                        mode=self.mode.value,
                        strict=strict,
                        requester=requester_name,
                    )
        finally:
            self._visit_stack.remove(key)
            self._visited.add(key)
