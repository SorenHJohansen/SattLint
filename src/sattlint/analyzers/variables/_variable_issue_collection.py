"""Issue collection helpers for the variable usage analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)

from ...reporting.variables_report import IssueKind, VariableIssue
from ...resolution import AccessEvent, AccessKind
from ...resolution.common import resolve_moduletype_def_strict
from ._variable_module_issue_scan import collect_issues_from_module

if TYPE_CHECKING:
    from . import VariablesAnalyzer

__all__ = [
    "VariablesIssueCollectionMixin",
    "_add_field_usage_asymmetry_issues",
    "_add_global_scope_minimization_issues",
    "_add_hidden_global_coupling_issues",
    "_add_high_fan_in_out_issues",
    "_add_issue",
    "_add_magic_number_issue",
    "_add_unused_datatype_field_issues",
    "_build_root_variable_access_summaries",
    "_collect_issues_from_module",
    "_iter_variables_for_datatype_field_analysis",
]

_HIGH_FAN_IN_OUT_THRESHOLD = 3


def _empty_access_by_module() -> dict[tuple[str, ...], set[AccessKind]]:
    return {}


def _empty_display_paths() -> dict[tuple[str, ...], tuple[str, ...]]:
    return {}


def _empty_module_key_set() -> set[tuple[str, ...]]:
    return set()


@dataclass
class _RootVariableAccessSummary:
    access_by_module: dict[tuple[str, ...], set[AccessKind]] = field(default_factory=_empty_access_by_module)
    display_paths: dict[tuple[str, ...], tuple[str, ...]] = field(default_factory=_empty_display_paths)
    reader_modules: set[tuple[str, ...]] = field(default_factory=_empty_module_key_set)
    writer_modules: set[tuple[str, ...]] = field(default_factory=_empty_module_key_set)
    access_module_keys: set[tuple[str, ...]] = field(default_factory=_empty_module_key_set)
    has_root_level_access: bool = False


def _iter_access_graph_by_path_items(
    self: VariablesAnalyzer,
) -> list[tuple[tuple[str, ...], list[AccessEvent]]]:
    indexed_events = getattr(self.access_graph, "by_path_key", None)
    if isinstance(indexed_events, dict):
        return list(cast(dict[tuple[str, ...], list[AccessEvent]], indexed_events).items())

    fallback_index: dict[tuple[str, ...], list[AccessEvent]] = {}
    for event in getattr(self.access_graph, "events", ()):
        typed_event = cast(AccessEvent, event)
        fallback_index.setdefault(typed_event.canonical_path.key(), []).append(typed_event)
    return list(fallback_index.items())


def _build_root_variable_access_summaries(
    self: VariablesAnalyzer,
) -> dict[str, _RootVariableAccessSummary]:
    state: Any = self
    cache_token = (id(self.access_graph), len(getattr(self.access_graph, "events", ())))
    cached_token = cast(tuple[int, int] | None, getattr(state, "_root_variable_access_summary_cache_token", None))
    cached_summaries = cast(
        dict[str, _RootVariableAccessSummary],
        getattr(state, "_root_variable_access_summary_cache", {}),
    )
    if cached_token == cache_token:
        return cached_summaries

    root_key = self.bp.header.name.casefold()
    root_variables = {variable.name.casefold() for variable in self.bp.localvariables or []}
    summaries: dict[str, _RootVariableAccessSummary] = {}

    for path_key, events in _iter_access_graph_by_path_items(self):
        if len(path_key) < 2 or path_key[0] != root_key:
            continue

        variable_key = path_key[1]
        if variable_key not in root_variables:
            continue

        summary = summaries.setdefault(variable_key, _RootVariableAccessSummary())
        for event in events:
            module_key = tuple(str(segment).casefold() for segment in event.use_module_path)
            if len(module_key) <= 1:
                summary.has_root_level_access = True
                continue

            summary.access_module_keys.add(module_key)
            summary.display_paths.setdefault(module_key, tuple(str(segment) for segment in event.use_module_path))
            summary.access_by_module.setdefault(module_key, set()).add(event.kind)
            if event.kind is AccessKind.READ:
                summary.reader_modules.add(module_key)
            elif event.kind is AccessKind.WRITE:
                summary.writer_modules.add(module_key)

    state._root_variable_access_summary_cache_token = cache_token
    state._root_variable_access_summary_cache = summaries
    return summaries


def _record_nested_datatype_access(
    self: VariablesAnalyzer,
    datatype_state: dict[str, dict[str, Any]],
    variable: Variable,
    field_path: str,
) -> None:
    segments = [segment for segment in field_path.split(".") if segment]
    if not segments:
        return

    current_type: Simple_DataType | str = variable.datatype
    for index, segment in enumerate(segments):
        if isinstance(current_type, Simple_DataType):
            return

        record_type = self.type_graph.record(str(current_type))
        if record_type is None:
            return

        field_def = record_type.fields_by_key.get(segment.casefold())
        if field_def is None:
            return

        current_type = field_def.datatype
        if isinstance(current_type, Simple_DataType):
            return

        state = datatype_state.get(str(current_type).casefold())
        if state is None:
            continue

        remaining_path = ".".join(segments[index + 1 :])
        if remaining_path:
            state["accessed_prefixes"].add(remaining_path.casefold())
        else:
            state["has_whole_access"] = True


def _add_issue(
    self: VariablesAnalyzer,
    kind: IssueKind,
    path: list[str],
    variable: Variable,
    role: str,
    field_path: str | None = None,
) -> None:
    self.append_issue(
        VariableIssue(
            kind=kind,
            module_path=path.copy(),
            variable=variable,
            role=role,
            field_path=field_path,
        )
    )


def _selected_issue_kinds(self: VariablesAnalyzer) -> frozenset[IssueKind] | set[IssueKind] | None:
    return cast(frozenset[IssueKind] | set[IssueKind] | None, getattr(self, "_selected_issue_kinds", None))


def _should_collect_issue_kind(self: VariablesAnalyzer, kind: IssueKind) -> bool:
    selected_kinds = _selected_issue_kinds(self)
    return selected_kinds is None or kind in selected_kinds


def _normalize_field_path(field_path: str) -> str:
    return ".".join(segment for segment in field_path.split(".") if segment)


def _expand_field_usage_to_leaf_keys(
    leaf_paths_by_key: dict[str, str],
    field_paths: dict[str, list[list[str]]],
) -> tuple[set[str], bool]:
    matched_leaf_keys: set[str] = set()
    has_whole_access = False

    for raw_field_path in field_paths:
        normalized = _normalize_field_path(raw_field_path)
        if not normalized:
            has_whole_access = True
            continue

        normalized_key = normalized.casefold()
        matched = {
            leaf_key
            for leaf_key in leaf_paths_by_key
            if leaf_key == normalized_key or leaf_key.startswith(f"{normalized_key}.")
        }
        matched_leaf_keys.update(matched)

    return matched_leaf_keys, has_whole_access


def _add_field_usage_asymmetry_issues(self: VariablesAnalyzer) -> None:
    collect_field_read_only = _should_collect_issue_kind(self, IssueKind.FIELD_READ_ONLY)
    collect_field_never_read = _should_collect_issue_kind(self, IssueKind.FIELD_NEVER_READ)
    if not collect_field_read_only and not collect_field_never_read:
        return

    for path, variable, role, root_owned_decl in _iter_variables_for_datatype_field_analysis(self):
        if isinstance(variable.datatype, Simple_DataType):
            continue

        if (
            self.analyzed_target_is_library
            and root_owned_decl
            and role == "moduleparameter"
            and any(segment.startswith("TypeDef:") for segment in path)
        ):
            continue

        leaf_paths = {
            ".".join(field_path)
            for field_path in self.type_graph.iter_leaf_field_paths(variable.datatype_text)
            if field_path
        }
        if not leaf_paths:
            continue

        usage = self.get_usage(variable)
        if usage.usage_locations:
            continue

        leaf_paths_by_key = {leaf_path.casefold(): leaf_path for leaf_path in leaf_paths}
        read_leaf_keys, has_whole_field_read = _expand_field_usage_to_leaf_keys(
            leaf_paths_by_key,
            usage.field_reads,
        )
        write_leaf_keys, has_whole_field_write = _expand_field_usage_to_leaf_keys(
            leaf_paths_by_key,
            usage.field_writes,
        )
        if has_whole_field_read or has_whole_field_write:
            continue

        if collect_field_read_only:
            for leaf_key in sorted(read_leaf_keys - write_leaf_keys):
                _add_issue(
                    self,
                    IssueKind.FIELD_READ_ONLY,
                    path,
                    variable,
                    role,
                    field_path=leaf_paths_by_key[leaf_key],
                )

        if collect_field_never_read:
            for leaf_key in sorted(write_leaf_keys - read_leaf_keys):
                _add_issue(
                    self,
                    IssueKind.FIELD_NEVER_READ,
                    path,
                    variable,
                    role,
                    field_path=leaf_paths_by_key[leaf_key],
                )


def _iter_variables_for_datatype_field_analysis(
    self: VariablesAnalyzer,
) -> list[tuple[list[str], Variable, str, bool]]:
    variables: list[tuple[list[str], Variable, str, bool]] = []
    seen_variable_ids: set[int] = set()

    def _append_variable(path: list[str], variable: Variable, role: str, root_owned: bool) -> None:
        variable_id = id(variable)
        if variable_id in seen_variable_ids:
            return
        seen_variable_ids.add(variable_id)
        variables.append((path.copy(), variable, role, root_owned))

    bp_path = [self.bp.header.name]
    for variable in self.bp.localvariables or []:
        _append_variable(bp_path, variable, "localvariable", True)

    def _collect_from_module(
        mod: SingleModule | FrameModule | ModuleTypeInstance,
        path: list[str],
    ) -> None:
        if isinstance(mod, SingleModule):
            my_path = [*path, mod.header.name]
            for variable in mod.moduleparameters or []:
                _append_variable(my_path, variable, "moduleparameter", True)
            for variable in mod.localvariables or []:
                _append_variable(my_path, variable, "localvariable", True)
            for child in mod.submodules or []:
                _collect_from_module(child, my_path)
        elif isinstance(mod, FrameModule):
            my_path = [*path, mod.header.name]
            for child in mod.submodules or []:
                _collect_from_module(child, my_path)

    for mod in self.bp.submodules or []:
        _collect_from_module(mod, bp_path)

    if self.limit_to_module_path is None:
        for mt in self.bp.moduletype_defs or []:
            root_owned = self.is_from_root_origin(
                getattr(mt, "origin_file", None),
                getattr(mt, "origin_lib", None),
            )
            if not root_owned and not (self.analyzed_target_is_library and self.include_dependency_moduletype_usage):
                continue
            td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]
            for variable in mt.moduleparameters or []:
                _append_variable(td_path, variable, "moduleparameter", root_owned)
            for variable in mt.localvariables or []:
                _append_variable(td_path, variable, "localvariable", root_owned)

    for module_path, context in self.contexts_by_module_path.items():
        path = list(module_path)
        param_mapping_keys = set(getattr(context, "param_mappings", {}).keys())
        for variable_name, variable in getattr(context, "env", {}).items():
            role = "moduleparameter" if variable_name in param_mapping_keys else "localvariable"
            root_owned = self.is_from_root_origin(
                getattr(variable, "origin_file", None),
                getattr(variable, "origin_lib", None),
            )
            _append_variable(path, variable, role, root_owned)

    return variables


def _add_unused_datatype_field_issues(self: VariablesAnalyzer) -> None:
    datatype_state: dict[str, dict[str, Any]] = {}

    for datatype in self.bp.datatype_defs or []:
        if not self.is_from_root_origin(
            getattr(datatype, "origin_file", None),
            getattr(datatype, "origin_lib", None),
        ):
            continue
        leaf_paths = {
            ".".join(field_path) for field_path in self.type_graph.iter_leaf_field_paths(datatype.name) if field_path
        }
        if not leaf_paths:
            continue
        datatype_state.setdefault(
            datatype.name.casefold(),
            {
                "datatype_name": datatype.name,
                "module_path": [self.bp.header.name, f"DataType:{datatype.name}"],
                "leaf_paths": leaf_paths,
                "accessed_prefixes": set(),
                "has_whole_access": False,
                "externally_open": False,
            },
        )

    if not datatype_state:
        return

    for path, variable, role, root_owned_decl in _iter_variables_for_datatype_field_analysis(self):
        if isinstance(variable.datatype, Simple_DataType):
            continue

        state = datatype_state.get(variable.datatype_text.casefold())
        if state is None:
            continue

        if (
            self.analyzed_target_is_library
            and root_owned_decl
            and role == "moduleparameter"
            and any(segment.startswith("TypeDef:") for segment in path)
        ):
            state["externally_open"] = True

        usage = self.get_usage(variable)
        if usage.usage_locations:
            state["has_whole_access"] = True

        for field_path in list((usage.field_reads or {}).keys()) + list((usage.field_writes or {}).keys()):
            normalized = ".".join(segment for segment in field_path.split(".") if segment)
            if normalized:
                state["accessed_prefixes"].add(normalized.casefold())
                _record_nested_datatype_access(self, datatype_state, variable, normalized)

    for state in datatype_state.values():
        if state["externally_open"] or state["has_whole_access"]:
            continue

        accessed_prefixes = state["accessed_prefixes"]
        if not accessed_prefixes:
            continue

        for leaf_path in sorted(state["leaf_paths"]):
            leaf_key = leaf_path.casefold()
            if any(
                leaf_key == accessed_prefix or leaf_key.startswith(f"{accessed_prefix}.")
                for accessed_prefix in accessed_prefixes
            ):
                continue

            self.append_issue(
                VariableIssue(
                    kind=IssueKind.UNUSED_DATATYPE_FIELD,
                    module_path=list(state["module_path"]),
                    variable=None,
                    datatype_name=state["datatype_name"],
                    role="datatype field",
                    field_path=leaf_path,
                )
            )


def _add_hidden_global_coupling_issues(self: VariablesAnalyzer) -> None:
    if self.analyzed_target_is_library:
        self.trace("hidden-global-coupling-scan", added_issue_count=0)
        return

    added_issue_count = 0
    summaries = _build_root_variable_access_summaries(self)

    for variable in self.bp.localvariables or []:
        summary = summaries.get(variable.name.casefold())
        if summary is None:
            continue

        if len(summary.access_by_module) < 2:
            continue

        if not any(AccessKind.WRITE in kinds for kinds in summary.access_by_module.values()):
            continue

        module_summaries: list[str] = []
        for module_key in sorted(summary.access_by_module):
            kinds = summary.access_by_module[module_key]
            labels = "/".join(kind.value for kind in sorted(kinds, key=lambda kind: kind.value))
            display_path = summary.display_paths.get(module_key, module_key)
            module_summaries.append(f"{'.'.join(display_path[1:])} ({labels})")

        self.append_issue(
            VariableIssue(
                kind=IssueKind.HIDDEN_GLOBAL_COUPLING,
                module_path=[self.bp.header.name],
                variable=variable,
                role=("hidden global coupling across modules: " + ", ".join(module_summaries)),
            )
        )
        added_issue_count += 1

    self.trace("hidden-global-coupling-scan", added_issue_count=added_issue_count)


def _add_high_fan_in_out_issues(self: VariablesAnalyzer) -> None:
    if self.analyzed_target_is_library:
        self.trace("high-fan-in-out-scan", added_issue_count=0)
        return

    added_issue_count = 0
    summaries = _build_root_variable_access_summaries(self)

    for variable in self.bp.localvariables or []:
        summary = summaries.get(variable.name.casefold())
        if summary is None:
            continue

        if (
            len(summary.reader_modules) < _HIGH_FAN_IN_OUT_THRESHOLD
            and len(summary.writer_modules) < _HIGH_FAN_IN_OUT_THRESHOLD
        ):
            continue

        role_parts: list[str] = []
        if len(summary.reader_modules) >= _HIGH_FAN_IN_OUT_THRESHOLD:
            reader_labels = [
                ".".join(summary.display_paths.get(module_key, module_key)[1:])
                for module_key in sorted(summary.reader_modules)
            ]
            role_parts.append(f"high fan-in with {len(summary.reader_modules)} readers: " + ", ".join(reader_labels))
        if len(summary.writer_modules) >= _HIGH_FAN_IN_OUT_THRESHOLD:
            writer_labels = [
                ".".join(summary.display_paths.get(module_key, module_key)[1:])
                for module_key in sorted(summary.writer_modules)
            ]
            role_parts.append(f"high fan-out with {len(summary.writer_modules)} writers: " + ", ".join(writer_labels))

        self.append_issue(
            VariableIssue(
                kind=IssueKind.HIGH_FAN_IN_OUT,
                module_path=[self.bp.header.name],
                variable=variable,
                role="; ".join(role_parts),
            )
        )
        added_issue_count += 1

    self.trace("high-fan-in-out-scan", added_issue_count=added_issue_count)


def _add_global_scope_minimization_issues(self: VariablesAnalyzer) -> None:
    if self.analyzed_target_is_library:
        self.trace("global-scope-minimization-scan", added_issue_count=0)
        return

    added_issue_count = 0
    summaries = _build_root_variable_access_summaries(self)

    for variable in self.bp.localvariables or []:
        summary = summaries.get(variable.name.casefold())
        if summary is None or summary.has_root_level_access:
            continue

        if not summary.access_module_keys:
            continue

        common_prefix = list(next(iter(summary.access_module_keys)))
        for module_key in summary.access_module_keys:
            shared_len = 0
            while (
                shared_len < len(common_prefix)
                and shared_len < len(module_key)
                and common_prefix[shared_len] == module_key[shared_len]
            ):
                shared_len += 1
            common_prefix = common_prefix[:shared_len]
            if len(common_prefix) <= 1:
                break

        if len(common_prefix) <= 1:
            continue

        candidate_scope = ".".join(summary.display_paths.get(tuple(common_prefix), tuple(common_prefix))[1:])
        access_summaries = [
            ".".join(summary.display_paths.get(module_key, module_key)[1:])
            for module_key in sorted(summary.access_module_keys)
        ]

        self.append_issue(
            VariableIssue(
                kind=IssueKind.GLOBAL_SCOPE_MINIMIZATION,
                module_path=[self.bp.header.name],
                variable=variable,
                role=(
                    f"global scope can be reduced to module subtree {candidate_scope}: " + ", ".join(access_summaries)
                ),
            )
        )
        added_issue_count += 1

    self.trace(
        "global-scope-minimization-scan",
        added_issue_count=added_issue_count,
    )


def _add_magic_number_issue(
    self: VariablesAnalyzer,
    path: list[str],
    value: int | float,
    span: SourceSpan | None,
) -> None:
    if value == 0:
        return

    self.append_issue(
        VariableIssue(
            kind=IssueKind.MAGIC_NUMBER,
            module_path=path.copy(),
            variable=None,
            role="literal",
            literal_value=value,
            literal_span=span,
            site=self.site_str(),
        )
    )


def _collect_issues_from_module(
    self: VariablesAnalyzer,
    mod: SingleModule | FrameModule | ModuleTypeInstance,
    path: list[str],
    current_library: str | None = None,
) -> None:
    collect_issues_from_module(
        self,
        mod,
        path,
        current_library=current_library,
        resolve_moduletype_def=resolve_moduletype_def_strict,
    )


class VariablesIssueCollectionMixin:
    def _add_field_usage_asymmetry_issues(self: Any) -> None:
        _add_field_usage_asymmetry_issues(self)

    def _build_root_variable_access_summaries(self: Any) -> dict[str, _RootVariableAccessSummary]:
        return _build_root_variable_access_summaries(self)

    def _add_issue(
        self: Any,
        kind: IssueKind,
        path: list[str],
        variable: Variable,
        role: str,
        field_path: str | None = None,
    ) -> None:
        _add_issue(self, kind, path, variable, role, field_path)

    def _iter_variables_for_datatype_field_analysis(
        self: Any,
    ) -> list[tuple[list[str], Variable, str, bool]]:
        return _iter_variables_for_datatype_field_analysis(self)

    def _add_unused_datatype_field_issues(self: Any) -> None:
        _add_unused_datatype_field_issues(self)

    def _add_hidden_global_coupling_issues(self: Any) -> None:
        _add_hidden_global_coupling_issues(self)

    def _add_high_fan_in_out_issues(self: Any) -> None:
        _add_high_fan_in_out_issues(self)

    def _add_global_scope_minimization_issues(self: Any) -> None:
        _add_global_scope_minimization_issues(self)

    def _add_magic_number_issue(
        self: Any,
        path: list[str],
        value: int | float,
        span: SourceSpan | None,
    ) -> None:
        _add_magic_number_issue(self, path, value, span)

    def _collect_issues_from_module(
        self: Any,
        mod: SingleModule | FrameModule | ModuleTypeInstance,
        path: list[str],
        current_library: str | None = None,
    ) -> None:
        _collect_issues_from_module(self, mod, path, current_library)
