from __future__ import annotations

from collections import defaultdict
from collections.abc import Set
from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
)

from ..resolution import AccessKind, decorate_segment
from ..resolution.common import resolve_moduletype_def_strict
from ..resolution.paths import CanonicalPath
from ..resolution.scope import ScopeContext
from .framework import AnalysisContext, Issue, empty_issues, format_report_header
from .sfc._sfc_guard_logic import conflict_rep, paths_conflict
from .shared.variable_utils import mapping_target_name
from .variables import VariablesAnalyzer
from .variables._variables_mapping_refs import mapping_source_ref
from .variables._variables_picture_display_support import build_typedef_root_context

_SAME_CYCLE_SHARED_ACCESS_KIND = "same_cycle_shared_access_hazard"
_SAME_CYCLE_PARALLEL_READ_WRITE_KIND = "same_cycle_parallel_read_write_hazard"
_SAME_CYCLE_PARALLEL_WRITE_KIND = "sfc_parallel_write_race"


type ParallelKey = tuple[tuple[str, ...], str, int]


@dataclass(frozen=True, slots=True)
class _CycleEvent:
    kind: AccessKind
    canonical_path: CanonicalPath
    decl_module_path: tuple[str, ...]
    access_module_path: tuple[str, ...]
    site: str
    order: int


@dataclass(frozen=True, slots=True)
class _ParallelMeta:
    module_path: list[str]
    sequence_name: str
    parallel_id: int


@dataclass
class SameCycleReport:
    name: str
    issues: list[Issue] = field(default_factory=empty_issues)

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Same-cycle hazards", self.name, status="ok")
            lines.append("No same-cycle hazards found.")
            return "\n".join(lines)

        lines = format_report_header("Same-cycle hazards", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        lines.append("Findings:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


class SameCycleAnalyzer(VariablesAnalyzer):
    def __init__(
        self,
        base_picture: BasePicture,
        *,
        debug: bool = False,
        unavailable_libraries: set[str] | None = None,
        analyzed_target_is_library: bool = False,
        selected_issue_kinds: Set[str] | None = None,
        shared_artifacts: Any | None = None,
    ) -> None:
        super().__init__(
            base_picture,
            debug=debug,
            fail_loudly=False,
            unavailable_libraries=unavailable_libraries,
            analyzed_target_is_library=analyzed_target_is_library,
            include_dependency_moduletype_usage=analyzed_target_is_library,
            build_anytype_contracts=False,
            shared_artifacts=shared_artifacts,
        )
        self._selected_same_cycle_issue_kinds = (
            None if selected_issue_kinds is None else frozenset(selected_issue_kinds)
        )
        self._report_issues: list[Issue] = []
        self._events: list[_CycleEvent] = []
        self._parallel_events: dict[ParallelKey, dict[int, list[_CycleEvent]]] = {}
        self._parallel_meta: dict[ParallelKey, _ParallelMeta] = {}
        self._parallel_stack: list[tuple[ParallelKey, int]] = []
        self._parallel_counter = 0
        self._current_order = 0
        self._current_seq_name = "<unnamed>"
        self._active_typedefs: set[str] = set()
        self._dependency_param_usage_cache: dict[
            tuple[str, str, str],
            tuple[frozenset[str], frozenset[str]],
        ] = {}

    # pyright: ignore[reportIncompatibleMethodOverride]
    def run(  # type: ignore[override]
        self,
        apply_alias_back_propagation: bool = True,
        limit_to_module_path: list[str] | None = None,
    ) -> SameCycleReport:
        root_context = self.context_builder.build_for_basepicture()
        root_path = [self.bp.header.name]
        self._contexts_by_module_path[tuple(root_path)] = root_context
        self._walk_module_code(self.bp.modulecode, root_context, root_path)
        self._walk_modules(self.bp.submodules or [], root_context, root_path)

        for moduletype in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(
                getattr(moduletype, "origin_file", None),
                getattr(moduletype, "origin_lib", None),
            ):
                continue
            path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
            context = build_typedef_root_context(self, moduletype, path)
            self._walk_root_typedef(moduletype, context, path)

        self._collect_parallel_branch_hazards()
        self._collect_shared_access_hazards()
        self._report_issues.sort(
            key=lambda issue: (
                issue.kind,
                tuple(issue.module_path or ()),
                issue.message,
            )
        )
        return SameCycleReport(name=self.bp.header.name, issues=self._report_issues)

    def _record_assignment_effect_flow(self, target_ref: str, expr: Any, context: ScopeContext) -> None:
        del target_ref, expr, context

    def _record_function_call_effect_flow(
        self,
        fn_name: str | None,
        args: list[Any],
        context: ScopeContext,
    ) -> None:
        del fn_name, args, context

    def _mark_var_by_basename(
        self,
        base_name: str | None,
        env: dict[str, Any],
        path: list[str],
        *,
        is_ui_read: bool = False,
    ) -> None:
        del env
        if not base_name:
            return
        context = self._contexts_by_module_path.get(tuple(path))
        if context is None:
            return
        self._mark_ref_access(base_name, context, path, AccessKind.READ, is_ui_read=is_ui_read)

    def _mark_ref_access(
        self,
        full_ref: str,
        context: ScopeContext,
        path: list[str],
        kind: AccessKind,
        *,
        is_ui_read: bool = False,
    ) -> None:
        del is_ui_read
        variable, field_path, decl_module_path, _decl_display = context.resolve_variable(full_ref)
        if variable is None:
            return

        canonical = CanonicalPath(
            (
                *decl_module_path,
                variable.name,
                *(part for part in field_path.split(".") if part),
            )
        )
        self._current_order += 1
        event = _CycleEvent(
            kind=kind,
            canonical_path=canonical,
            decl_module_path=tuple(decl_module_path),
            access_module_path=tuple(path),
            site=self._site_str(),
            order=self._current_order,
        )
        self._events.append(event)

        for parallel_key, branch_index in self._parallel_stack:
            branch_events = self._parallel_events.setdefault(parallel_key, {})
            branch_events.setdefault(branch_index, []).append(event)

    def _should_collect_issue_kind(self, *issue_kinds: str) -> bool:
        if self._selected_same_cycle_issue_kinds is None:
            return True
        return any(issue_kind in self._selected_same_cycle_issue_kinds for issue_kind in issue_kinds)

    def _child_display_path(
        self,
        child: SingleModule | FrameModule | ModuleTypeInstance,
        parent_context: ScopeContext,
    ) -> list[str]:
        child_name = child.header.name
        if isinstance(child, SingleModule):
            return [*parent_context.display_module_path, decorate_segment(child_name, "SM")]
        if isinstance(child, FrameModule):
            return [*parent_context.display_module_path, decorate_segment(child_name, "FM")]
        return [
            *parent_context.display_module_path,
            decorate_segment(child_name, "MT", moduletype_name=child.moduletype_name),
        ]

    def _walk_modules(
        self,
        children: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_context: ScopeContext,
        parent_path: list[str],
    ) -> None:
        for child in children:
            child_path = [*parent_path, child.header.name]
            child_display_path = self._child_display_path(child, parent_context)
            if isinstance(child, SingleModule):
                child_context = self.context_builder.build_for_single(
                    child,
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )
                self._contexts_by_module_path[tuple(child_path)] = child_context
                self._walk_module_code(child.modulecode, child_context, child_path)
                self._walk_modules(child.submodules or [], child_context, child_path)
                continue

            if isinstance(child, FrameModule):
                frame_context = self.repath_context(
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )
                self._contexts_by_module_path[tuple(child_path)] = frame_context
                self._walk_module_code(child.modulecode, frame_context, child_path)
                self._walk_modules(child.submodules or [], frame_context, child_path)
                continue

            self._walk_moduletype_instance(child, parent_context, child_path, child_display_path)

    def _walk_root_typedef(
        self,
        moduletype: ModuleTypeDef,
        context: ScopeContext,
        module_path: list[str],
    ) -> None:
        typedef_key = moduletype.name.casefold()
        if typedef_key in self._active_typedefs:
            return
        self._active_typedefs.add(typedef_key)
        try:
            self._walk_module_code(moduletype.modulecode, context, module_path)
            self._walk_modules(moduletype.submodules or [], context, module_path)
        finally:
            self._active_typedefs.discard(typedef_key)

    def _walk_moduletype_instance(
        self,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext,
        child_path: list[str],
        child_display_path: list[str],
    ) -> None:
        try:
            moduletype = resolve_moduletype_def_strict(
                self.bp,
                instance.moduletype_name,
                current_library=parent_context.current_library,
                unavailable_libraries=self.unavailable_libraries,
            )
        except ValueError:
            return

        if not self._is_from_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(moduletype, "origin_lib", None),
        ):
            self._record_dependency_mapping_accesses(instance, moduletype, parent_context, child_path)
            return

        typedef_key = moduletype.name.casefold()
        if typedef_key in self._active_typedefs:
            return

        context = self.context_builder.build_for_typedef(
            moduletype,
            instance,
            parent_context,
            module_path=child_path,
            display_module_path=child_display_path,
        )
        self._contexts_by_module_path[tuple(child_path)] = context
        self._active_typedefs.add(typedef_key)
        try:
            self._walk_module_code(moduletype.modulecode, context, child_path)
            self._walk_modules(moduletype.submodules or [], context, child_path)
        finally:
            self._active_typedefs.discard(typedef_key)

    def _record_dependency_mapping_accesses(
        self,
        instance: ModuleTypeInstance,
        moduletype: ModuleTypeDef,
        parent_context: ScopeContext,
        child_path: list[str],
    ) -> None:
        reads, writes = self._dependency_parameter_usage(moduletype)
        if not reads and not writes:
            return

        for mapping in instance.parametermappings or []:
            source_ref = mapping_source_ref(mapping)
            target_name = mapping_target_name(mapping)
            if source_ref is None or target_name is None:
                continue

            target_key = target_name.casefold()
            if target_key in reads:
                self._mark_ref_access(source_ref, parent_context, child_path, AccessKind.READ)
            if target_key in writes:
                self._mark_ref_access(source_ref, parent_context, child_path, AccessKind.WRITE)

    def _dependency_parameter_usage(
        self,
        moduletype: ModuleTypeDef,
    ) -> tuple[frozenset[str], frozenset[str]]:
        cache_key = (
            moduletype.name.casefold(),
            (getattr(moduletype, "origin_lib", None) or "").casefold(),
            (getattr(moduletype, "origin_file", None) or "").casefold(),
        )
        cached = self._dependency_param_usage_cache.get(cache_key)
        if cached is not None:
            return cached

        temp_analyzer = VariablesAnalyzer(
            self.bp,
            debug=self.debug,
            fail_loudly=False,
            unavailable_libraries=self.unavailable_libraries,
            analyzed_target_is_library=self.analyzed_target_is_library,
            include_dependency_moduletype_usage=True,
            build_anytype_contracts=False,
            shared_artifacts=self._shared_artifacts,
        )
        context_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
        temp_context = build_typedef_root_context(temp_analyzer, moduletype, context_path)
        with temp_analyzer.divert_issue_collection():
            temp_analyzer.analyze_typedef_with_context(moduletype, temp_context, context_path)

        mt_key = moduletype.name.lower()
        usage = (
            frozenset(name.casefold() for name in temp_analyzer.param_reads_by_typedef.get(mt_key, set())),
            frozenset(name.casefold() for name in temp_analyzer.param_writes_by_typedef.get(mt_key, set())),
        )
        self._dependency_param_usage_cache[cache_key] = usage
        return usage

    def _walk_module_code(
        self,
        modulecode: ModuleCode | None,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        if modulecode is None:
            return

        for sequence in modulecode.sequences or []:
            label = f"SEQ:{getattr(sequence, 'name', '<unnamed>')}"
            self._push_site(label)
            try:
                self._walk_sequence(sequence, context, path)
            finally:
                self._pop_site()

        for equation in modulecode.equations or []:
            label = f"EQ:{getattr(equation, 'name', '<unnamed>')}"
            self._push_site(label)
            try:
                for statement in equation.code or []:
                    self._walk_stmt_or_expr(statement, context, path)
            finally:
                self._pop_site()

    def _walk_sequence(self, sequence: Sequence, context: ScopeContext, path: list[str]) -> None:
        previous_seq_name = self._current_seq_name
        self._current_seq_name = getattr(sequence, "name", "<unnamed>")
        try:
            self._walk_sequence_nodes(sequence.code or [], context, path)
        finally:
            self._current_seq_name = previous_seq_name

    def _walk_sequence_nodes(
        self,
        nodes: list[object],
        context: ScopeContext,
        path: list[str],
    ) -> None:
        for node in nodes:
            if isinstance(node, SFCStep):
                self._walk_step(node, context, path)
                continue

            if isinstance(node, SFCTransition):
                self._push_site(f"TRANS:{node.name or '<unnamed>'}")
                try:
                    self._walk_stmt_or_expr(node.condition, context, path)
                finally:
                    self._pop_site()
                continue

            if isinstance(node, SFCAlternative):
                for branch_index, branch in enumerate(node.branches or []):
                    self._push_site(f"ALT:BRANCH:{branch_index}")
                    try:
                        self._walk_sequence_nodes(branch or [], context, path)
                    finally:
                        self._pop_site()
                continue

            if isinstance(node, SFCParallel):
                self._walk_parallel(node, context, path)
                continue

            if isinstance(node, SFCSubsequence):
                self._push_site(f"SUBSEQ:{getattr(node, 'name', '<unnamed>')}")
                try:
                    self._walk_sequence_nodes(node.body or [], context, path)
                finally:
                    self._pop_site()
                continue

            if isinstance(node, SFCTransitionSub):
                self._push_site(f"TRANS-SUB:{getattr(node, 'name', '<unnamed>')}")
                try:
                    self._walk_sequence_nodes(node.body or [], context, path)
                finally:
                    self._pop_site()
                continue

            if isinstance(node, (SFCFork, SFCBreak)):
                continue

    def _walk_step(self, step: SFCStep, context: ScopeContext, path: list[str]) -> None:
        base = f"STEP:{step.name}"
        for phase, statements in (
            ("ENTER", step.code.enter or []),
            ("ACTIVE", step.code.active or []),
            ("EXIT", step.code.exit or []),
        ):
            self._push_site(f"{base}:{phase}")
            try:
                for statement in statements:
                    self._walk_stmt_or_expr(statement, context, path)
            finally:
                self._pop_site()

    def _walk_parallel(self, node: SFCParallel, context: ScopeContext, path: list[str]) -> None:
        self._parallel_counter += 1
        parallel_id = self._parallel_counter
        parallel_key: ParallelKey = (tuple(path), self._current_seq_name, parallel_id)
        self._parallel_meta.setdefault(
            parallel_key,
            _ParallelMeta(
                module_path=path.copy(),
                sequence_name=self._current_seq_name,
                parallel_id=parallel_id,
            ),
        )

        for branch_index, branch in enumerate(node.branches or []):
            self._push_site(f"PAR:BLOCK:{parallel_id}")
            self._push_site(f"PAR:BRANCH:{branch_index}")
            self._parallel_stack.append((parallel_key, branch_index))
            try:
                self._walk_sequence_nodes(branch or [], context, path)
            finally:
                self._parallel_stack.pop()
                self._pop_site()
                self._pop_site()

    def _collect_parallel_branch_hazards(self) -> None:
        for parallel_key, branch_events in self._parallel_events.items():
            write_conflicts: dict[tuple[str, ...], CanonicalPath] = {}
            read_write_conflicts: dict[tuple[str, ...], CanonicalPath] = {}
            branch_ids = sorted(branch_events)
            for index, left_branch in enumerate(branch_ids):
                for right_branch in branch_ids[index + 1 :]:
                    for left_event in branch_events[left_branch]:
                        for right_event in branch_events[right_branch]:
                            if not paths_conflict(left_event.canonical_path, right_event.canonical_path):
                                continue
                            representative = conflict_rep(left_event.canonical_path, right_event.canonical_path)
                            if left_event.kind is AccessKind.WRITE and right_event.kind is AccessKind.WRITE:
                                write_conflicts.setdefault(representative.key(), representative)
                                continue
                            if AccessKind.WRITE in {left_event.kind, right_event.kind}:
                                read_write_conflicts.setdefault(representative.key(), representative)

            for conflict_key in tuple(write_conflicts):
                read_write_conflicts.pop(conflict_key, None)

            meta = self._parallel_meta.get(parallel_key)
            sequence_name = meta.sequence_name if meta is not None else "<unnamed>"
            module_path = meta.module_path if meta is not None else list(parallel_key[0])
            parallel_id = meta.parallel_id if meta is not None else None

            if write_conflicts and self._should_collect_issue_kind(_SAME_CYCLE_PARALLEL_WRITE_KIND):
                conflict_list = sorted(str(path) for path in write_conflicts.values())
                preview = self._preview_list(conflict_list)
                self._report_issues.append(
                    Issue(
                        kind=_SAME_CYCLE_PARALLEL_WRITE_KIND,
                        message=(
                            f"Parallel branches in sequence {sequence_name!r} write to the same variable(s): {preview}"
                        ),
                        module_path=module_path,
                        data={
                            "sequence": sequence_name,
                            "parallel_id": parallel_id,
                            "conflicts": conflict_list,
                        },
                    )
                )

            if read_write_conflicts and self._should_collect_issue_kind(_SAME_CYCLE_PARALLEL_READ_WRITE_KIND):
                conflict_list = sorted(str(path) for path in read_write_conflicts.values())
                preview = self._preview_list(conflict_list)
                self._report_issues.append(
                    Issue(
                        kind=_SAME_CYCLE_PARALLEL_READ_WRITE_KIND,
                        message=(
                            f"Parallel branches in sequence {sequence_name!r} both read and write the same variable(s): {preview}"
                        ),
                        module_path=module_path,
                        data={
                            "sequence": sequence_name,
                            "parallel_id": parallel_id,
                            "conflicts": conflict_list,
                        },
                    )
                )

    def _collect_shared_access_hazards(self) -> None:
        if not self._should_collect_issue_kind(_SAME_CYCLE_SHARED_ACCESS_KIND):
            return

        grouped: dict[
            tuple[str, ...],
            tuple[
                CanonicalPath, tuple[str, ...], dict[tuple[str, ...], set[AccessKind]], dict[tuple[str, ...], set[str]]
            ],
        ] = {}

        for index, left_event in enumerate(self._events):
            for right_event in self._events[index + 1 :]:
                if left_event.access_module_path == right_event.access_module_path:
                    continue
                if not paths_conflict(left_event.canonical_path, right_event.canonical_path):
                    continue
                if AccessKind.WRITE not in {left_event.kind, right_event.kind}:
                    continue

                representative = conflict_rep(left_event.canonical_path, right_event.canonical_path)
                conflict_key = representative.key()
                if conflict_key not in grouped:
                    grouped[conflict_key] = (
                        representative,
                        left_event.decl_module_path,
                        defaultdict(set),
                        defaultdict(set),
                    )

                _representative, _decl_path, actions, sites = grouped[conflict_key]
                for event in (left_event, right_event):
                    actions[event.access_module_path].add(event.kind)
                    if event.site:
                        sites[event.access_module_path].add(event.site)

        for representative, decl_module_path, actions, sites in sorted(
            grouped.values(),
            key=lambda item: str(item[0]),
        ):
            if not any(AccessKind.READ in kinds for kinds in actions.values()):
                continue
            if not any(AccessKind.WRITE in kinds for kinds in actions.values()):
                continue

            access_summaries = [
                self._format_access_summary(module_path, actions[module_path])
                for module_path in sorted(actions, key=self._module_path_sort_key)
            ]
            self._report_issues.append(
                Issue(
                    kind=_SAME_CYCLE_SHARED_ACCESS_KIND,
                    message=(
                        f"Variable {str(representative)!r} is read and written in the same scan across modules: "
                        f"{'; '.join(access_summaries)}"
                    ),
                    module_path=list(decl_module_path),
                    data={
                        "symbol": str(representative),
                        "decl_module_path": list(decl_module_path),
                        "accesses": [
                            {
                                "module_path": list(module_path),
                                "kinds": self._kind_labels(actions[module_path]),
                                "sites": sorted(site for site in sites[module_path] if site),
                            }
                            for module_path in sorted(actions, key=self._module_path_sort_key)
                        ],
                    },
                )
            )

    def _kind_labels(self, kinds: set[AccessKind]) -> list[str]:
        labels: list[str] = []
        if AccessKind.READ in kinds:
            labels.append("read")
        if AccessKind.WRITE in kinds:
            labels.append("write")
        return labels

    def _format_access_summary(self, module_path: tuple[str, ...], kinds: set[AccessKind]) -> str:
        location = self._relative_module_label(module_path)
        return f"{location} ({'/'.join(self._kind_labels(kinds))})"

    def _relative_module_label(self, module_path: tuple[str, ...]) -> str:
        if len(module_path) == 0:
            return ""
        if len(module_path) == 1:
            return module_path[0]
        return ".".join(module_path[1:])

    def _module_path_sort_key(self, module_path: tuple[str, ...]) -> tuple[int, tuple[str, ...]]:
        return (len(module_path), tuple(segment.casefold() for segment in module_path))

    def _preview_list(self, values: list[str]) -> str:
        preview = ", ".join(values[:6])
        if len(values) <= 6:
            return preview
        return f"{preview}, ... (+{len(values) - 6} more)"


def analyze_same_cycle(
    base_picture: BasePicture,
    analysis_context: AnalysisContext | None = None,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
    selected_issue_kinds: Set[str] | None = None,
) -> SameCycleReport:
    analyzer = SameCycleAnalyzer(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
        selected_issue_kinds=selected_issue_kinds,
        shared_artifacts=(analysis_context.shared_artifacts if analysis_context is not None else None),
    )
    return analyzer.run()


__all__ = [
    "SameCycleAnalyzer",
    "SameCycleReport",
    "analyze_same_cycle",
]
