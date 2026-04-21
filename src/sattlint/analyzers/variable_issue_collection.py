"""Issue collection helpers for the variable usage analyzer."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Union

from ..models.ast_model import (
    FrameModule,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution import AccessKind

_HIGH_FAN_IN_OUT_THRESHOLD = 3


def _add_issue(
    self,
    kind: IssueKind,
    path: list[str],
    variable: Variable,
    role: str,
    field_path: str | None = None,
) -> None:
    self._append_issue(
        VariableIssue(
            kind=kind,
            module_path=path.copy(),
            variable=variable,
            role=role,
            field_path=field_path,
        )
    )


def _iter_variables_for_datatype_field_analysis(
    self,
) -> list[tuple[list[str], Variable, str]]:
    variables: list[tuple[list[str], Variable, str]] = []

    bp_path = [self.bp.header.name]
    for variable in self.bp.localvariables or []:
        variables.append((bp_path.copy(), variable, "localvariable"))

    def _collect_from_module(
        mod: Union[SingleModule, FrameModule, ModuleTypeInstance],
        path: list[str],
    ) -> None:
        if isinstance(mod, SingleModule):
            my_path = path + [mod.header.name]
            for variable in mod.moduleparameters or []:
                variables.append((my_path.copy(), variable, "moduleparameter"))
            for variable in mod.localvariables or []:
                variables.append((my_path.copy(), variable, "localvariable"))
            for child in mod.submodules or []:
                _collect_from_module(child, my_path)
        elif isinstance(mod, FrameModule):
            my_path = path + [mod.header.name]
            for child in mod.submodules or []:
                _collect_from_module(child, my_path)

    for mod in self.bp.submodules or []:
        _collect_from_module(mod, bp_path)

    if self._limit_to_module_path is None:
        for mt in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(getattr(mt, "origin_file", None)):
                continue
            td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]
            for variable in mt.moduleparameters or []:
                variables.append((td_path.copy(), variable, "moduleparameter"))
            for variable in mt.localvariables or []:
                variables.append((td_path.copy(), variable, "localvariable"))

    return variables


def _add_unused_datatype_field_issues(self) -> None:
    datatype_state: dict[str, dict[str, Any]] = {}

    for datatype in self.bp.datatype_defs or []:
        if not self._is_from_root_origin(getattr(datatype, "origin_file", None)):
            continue
        leaf_paths = {
            ".".join(field_path)
            for field_path in self.type_graph.iter_leaf_field_paths(datatype.name)
            if field_path
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

    for path, variable, role in self._iter_variables_for_datatype_field_analysis():
        if isinstance(variable.datatype, Simple_DataType):
            continue

        state = datatype_state.get(variable.datatype_text.casefold())
        if state is None:
            continue

        if (
            self._analyzed_target_is_library
            and role == "moduleparameter"
            and any(segment.startswith("TypeDef:") for segment in path)
        ):
            state["externally_open"] = True

        usage = self._get_usage(variable)
        if usage.usage_locations:
            state["has_whole_access"] = True

        for field_path in list((usage.field_reads or {}).keys()) + list(
            (usage.field_writes or {}).keys()
        ):
            normalized = ".".join(
                segment for segment in field_path.split(".") if segment
            )
            if normalized:
                state["accessed_prefixes"].add(normalized.casefold())

    for state in datatype_state.values():
        if state["externally_open"] or state["has_whole_access"]:
            continue

        accessed_prefixes = state["accessed_prefixes"]
        if not accessed_prefixes:
            continue

        for leaf_path in sorted(state["leaf_paths"]):
            leaf_key = leaf_path.casefold()
            if any(
                leaf_key == accessed_prefix
                or leaf_key.startswith(f"{accessed_prefix}.")
                for accessed_prefix in accessed_prefixes
            ):
                continue

            self._append_issue(
                VariableIssue(
                    kind=IssueKind.UNUSED_DATATYPE_FIELD,
                    module_path=list(state["module_path"]),
                    variable=None,
                    datatype_name=state["datatype_name"],
                    role="datatype field",
                    field_path=leaf_path,
                )
            )


def _add_hidden_global_coupling_issues(self) -> None:
    if self._analyzed_target_is_library:
        self._trace("hidden-global-coupling-scan", added_issue_count=0)
        return

    root_prefix = (self.bp.header.name.casefold(),)
    added_issue_count = 0

    for variable in self.bp.localvariables or []:
        variable_prefix = root_prefix + (variable.name.casefold(),)
        access_by_module: dict[tuple[str, ...], set[AccessKind]] = defaultdict(set)
        display_paths: dict[tuple[str, ...], tuple[str, ...]] = {}

        for event in self.access_graph.events:
            path_key = event.canonical_path.key()
            if len(path_key) < len(variable_prefix):
                continue
            if path_key[: len(variable_prefix)] != variable_prefix:
                continue
            if len(event.use_module_path) <= 1:
                continue

            module_key = tuple(segment.casefold() for segment in event.use_module_path)
            access_by_module[module_key].add(event.kind)
            display_paths.setdefault(module_key, tuple(event.use_module_path))

        if len(access_by_module) < 2:
            continue

        if not any(AccessKind.WRITE in kinds for kinds in access_by_module.values()):
            continue

        module_summaries: list[str] = []
        for module_key in sorted(access_by_module):
            kinds = access_by_module[module_key]
            labels = "/".join(kind.value for kind in sorted(kinds, key=lambda kind: kind.value))
            display_path = display_paths.get(module_key, module_key)
            module_summaries.append(f"{'.'.join(display_path[1:])} ({labels})")

        self._append_issue(
            VariableIssue(
                kind=IssueKind.HIDDEN_GLOBAL_COUPLING,
                module_path=[self.bp.header.name],
                variable=variable,
                role=(
                    "hidden global coupling across modules: "
                    + ", ".join(module_summaries)
                ),
            )
        )
        added_issue_count += 1

    self._trace("hidden-global-coupling-scan", added_issue_count=added_issue_count)


def _add_high_fan_in_out_issues(self) -> None:
    if self._analyzed_target_is_library:
        self._trace("high-fan-in-out-scan", added_issue_count=0)
        return

    root_prefix = (self.bp.header.name.casefold(),)
    added_issue_count = 0

    for variable in self.bp.localvariables or []:
        variable_prefix = root_prefix + (variable.name.casefold(),)
        reader_modules: set[tuple[str, ...]] = set()
        writer_modules: set[tuple[str, ...]] = set()
        display_paths: dict[tuple[str, ...], tuple[str, ...]] = {}

        for event in self.access_graph.events:
            path_key = event.canonical_path.key()
            if len(path_key) < len(variable_prefix):
                continue
            if path_key[: len(variable_prefix)] != variable_prefix:
                continue
            if len(event.use_module_path) <= 1:
                continue

            module_key = tuple(segment.casefold() for segment in event.use_module_path)
            display_paths.setdefault(module_key, tuple(event.use_module_path))
            if event.kind is AccessKind.READ:
                reader_modules.add(module_key)
            elif event.kind is AccessKind.WRITE:
                writer_modules.add(module_key)

        if (
            len(reader_modules) < _HIGH_FAN_IN_OUT_THRESHOLD
            and len(writer_modules) < _HIGH_FAN_IN_OUT_THRESHOLD
        ):
            continue

        role_parts: list[str] = []
        if len(reader_modules) >= _HIGH_FAN_IN_OUT_THRESHOLD:
            reader_labels = [
                ".".join(display_paths.get(module_key, module_key)[1:])
                for module_key in sorted(reader_modules)
            ]
            role_parts.append(
                f"high fan-in with {len(reader_modules)} readers: "
                + ", ".join(reader_labels)
            )
        if len(writer_modules) >= _HIGH_FAN_IN_OUT_THRESHOLD:
            writer_labels = [
                ".".join(display_paths.get(module_key, module_key)[1:])
                for module_key in sorted(writer_modules)
            ]
            role_parts.append(
                f"high fan-out with {len(writer_modules)} writers: "
                + ", ".join(writer_labels)
            )

        self._append_issue(
            VariableIssue(
                kind=IssueKind.HIGH_FAN_IN_OUT,
                module_path=[self.bp.header.name],
                variable=variable,
                role="; ".join(role_parts),
            )
        )
        added_issue_count += 1

    self._trace("high-fan-in-out-scan", added_issue_count=added_issue_count)


def _add_global_scope_minimization_issues(self) -> None:
    if self._analyzed_target_is_library:
        self._trace("global-scope-minimization-scan", added_issue_count=0)
        return

    root_prefix = (self.bp.header.name.casefold(),)
    added_issue_count = 0

    for variable in self.bp.localvariables or []:
        variable_prefix = root_prefix + (variable.name.casefold(),)
        access_module_keys: set[tuple[str, ...]] = set()
        display_paths: dict[tuple[str, ...], tuple[str, ...]] = {}

        for event in self.access_graph.events:
            path_key = event.canonical_path.key()
            if len(path_key) < len(variable_prefix):
                continue
            if path_key[: len(variable_prefix)] != variable_prefix:
                continue

            module_key_parts = [str(segment).casefold() for segment in event.use_module_path]
            module_key: tuple[str, ...] = tuple(module_key_parts)
            if len(module_key) <= 1:
                access_module_keys = set()
                break

            access_module_keys.add(module_key)
            display_path: tuple[str, ...] = tuple(str(segment) for segment in event.use_module_path)
            display_paths.setdefault(
                module_key,
                display_path,
            )

        if not access_module_keys:
            continue

        common_prefix = list(next(iter(access_module_keys)))
        for module_key in access_module_keys:
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

        candidate_scope = ".".join(
            display_paths.get(tuple(common_prefix), tuple(common_prefix))[1:]
        )
        access_summaries = [
            ".".join(display_paths.get(module_key, module_key)[1:])
            for module_key in sorted(access_module_keys)
        ]

        self._append_issue(
            VariableIssue(
                kind=IssueKind.GLOBAL_SCOPE_MINIMIZATION,
                module_path=[self.bp.header.name],
                variable=variable,
                role=(
                    f"global scope can be reduced to module subtree {candidate_scope}: "
                    + ", ".join(access_summaries)
                ),
            )
        )
        added_issue_count += 1

    self._trace(
        "global-scope-minimization-scan",
        added_issue_count=added_issue_count,
    )


def _add_magic_number_issue(
    self,
    path: list[str],
    value: int | float,
    span: SourceSpan | None,
) -> None:
    if value == 0:
        return

    self._append_issue(
        VariableIssue(
            kind=IssueKind.MAGIC_NUMBER,
            module_path=path.copy(),
            variable=None,
            role="literal",
            literal_value=value,
            literal_span=span,
            site=self._site_str(),
        )
    )


def _collect_issues_from_module(
    self,
    mod: Union[SingleModule, FrameModule, ModuleTypeInstance],
    path: list[str],
) -> None:
    if isinstance(mod, SingleModule):
        my_path = path + [mod.header.name]
        for variable in mod.moduleparameters or []:
            usage = self._get_usage(variable)
            if usage.is_unused:
                self._add_issue(
                    IssueKind.UNUSED, my_path, variable, role="moduleparameter"
                )
                continue
            procedure_status = self._procedure_status_issue(variable, usage)
            if procedure_status is not None:
                status_role, field_path = procedure_status
                self._add_issue(
                    IssueKind.PROCEDURE_STATUS,
                    my_path,
                    variable,
                    role=status_role,
                    field_path=field_path,
                )
                continue
            elif usage.is_display_only:
                self._add_issue(
                    IssueKind.UI_ONLY, my_path, variable, role="moduleparameter"
                )
            elif (
                usage.read
                and usage.written
                and not self._has_output_effect(variable, my_path)
                and not self._has_procedure_status_binding(variable)
            ):
                self._add_issue(
                    IssueKind.WRITE_WITHOUT_EFFECT,
                    my_path,
                    variable,
                    role="moduleparameter",
                )
        for variable in mod.localvariables or []:
            usage = self._get_usage(variable)
            if usage.is_unused:
                self._add_issue(IssueKind.UNUSED, my_path, variable, role="localvariable")
                continue
            procedure_status = self._procedure_status_issue(variable, usage)
            if procedure_status is not None:
                status_role, field_path = procedure_status
                self._add_issue(
                    IssueKind.PROCEDURE_STATUS,
                    my_path,
                    variable,
                    role=status_role,
                    field_path=field_path,
                )
                continue
            elif usage.is_display_only:
                self._add_issue(IssueKind.UI_ONLY, my_path, variable, role="localvariable")
            elif (
                usage.is_read_only
                and not bool(variable.const)
                and self._is_const_candidate(variable)
            ):
                self._add_issue(
                    IssueKind.READ_ONLY_NON_CONST, my_path, variable, role="localvariable"
                )
            elif usage.written and not usage.read:
                self._add_issue(IssueKind.NEVER_READ, my_path, variable, role="localvariable")
            elif (
                usage.read
                and usage.written
                and not self._has_output_effect(variable, my_path)
                and not self._has_procedure_status_binding(variable)
            ):
                self._add_issue(
                    IssueKind.WRITE_WITHOUT_EFFECT,
                    my_path,
                    variable,
                    role="localvariable",
                )
        for child in mod.submodules or []:
            self._collect_issues_from_module(child, my_path)

    elif isinstance(mod, FrameModule):
        my_path = path + [mod.header.name]
        for child in mod.submodules or []:
            self._collect_issues_from_module(child, my_path)

    elif isinstance(mod, ModuleTypeInstance):
        return
