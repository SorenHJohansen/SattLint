from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from ..grammar import constants as const
from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    SingleModule,
    Variable,
)
from ..resolution.common import (
    format_moduletype_label,
    resolve_moduletype_def_strict,
    varname_base,
    varname_full,
)
from .framework import Issue, format_report_header

_TAG_PARAMETER_NAMES: tuple[str, ...] = (
    "tag",
    "alarmtag",
    "eventtag",
)
_PRIORITY_PARAMETER_NAMES: tuple[str, ...] = (
    "priority",
    "severity",
)
_CONDITION_PARAMETER_NAMES: tuple[str, ...] = (
    "condition",
    "alarmcondition",
    "enablemodule",
    "enable",
    "active",
    "trigger",
)
_ISSUE_LABELS = {
    "alarm.duplicate_tag": "Duplicate alarm tags",
    "alarm.duplicate_condition": "Duplicate alarm conditions",
    "alarm.conflicting_priority": "Conflicting alarm priorities",
    "alarm.never_cleared": "Never-cleared alarm writes",
}


@dataclass(frozen=True)
class _ParameterValue:
    status: str
    value: object | None = None
    source: str | None = None
    signature: str | None = None


@dataclass(frozen=True)
class _AlarmCandidate:
    module_path: list[str]
    instance_name: str
    moduletype_label: str
    tag_key: str | None
    tag_display: str | None
    priority_key: str | None
    priority_display: str | None
    condition_key: str | None
    condition_display: str | None


@dataclass
class AlarmIntegrityReport:
    basepicture_name: str
    issues: list[Issue]

    @property
    def name(self) -> str:
        return self.basepicture_name

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Alarm integrity", self.basepicture_name, status="ok")
            lines.append("No alarm integrity issues found.")
            return "\n".join(lines)

        counts = Counter(issue.kind for issue in self.issues)
        lines = format_report_header("Alarm integrity", self.basepicture_name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        lines.append("Kinds:")
        for kind, label in _ISSUE_LABELS.items():
            count = counts.get(kind, 0)
            if count:
                lines.append(f"  - {label}: {count}")

        lines.append("")
        lines.append("Findings:")
        for issue in sorted(
            self.issues,
            key=lambda item: (
                item.kind,
                item.module_path or [],
                item.message,
            ),
        ):
            location = ".".join(issue.module_path or [self.basepicture_name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


class AlarmIntegrityAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        unavailable_libraries: set[str] | None = None,
    ) -> None:
        self.bp = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._issues: list[Issue] = []
        self._candidates: list[_AlarmCandidate] = []

    @property
    def issues(self) -> list[Issue]:
        return self._issues

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]
        base_env = self._merge_env({}, self.bp.localvariables)

        self._check_module_code(self.bp.modulecode, root_path, base_env)
        self._walk_modules(
            self.bp.submodules or [],
            parent_path=root_path,
            env=base_env,
            current_library=self.bp.origin_lib,
        )

        for moduletype in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(getattr(moduletype, "origin_file", None)):
                continue
            self._walk_moduletype_def(moduletype, root_path, base_env)

        self._emit_duplicate_tag_issues()
        self._emit_duplicate_condition_issues()
        self._emit_conflicting_priority_issues()
        return self._issues

    def _is_from_root_origin(self, origin_file: str | None) -> bool:
        if not origin_file:
            return True
        root_origin = getattr(self.bp, "origin_file", None)
        if not root_origin:
            return False
        return origin_file.rsplit(".", 1)[0].casefold() == root_origin.rsplit(".", 1)[0].casefold()

    def _merge_env(
        self,
        parent_env: dict[str, Variable],
        variables: list[Variable] | None,
    ) -> dict[str, Variable]:
        merged = dict(parent_env)
        for variable in variables or []:
            merged[variable.name.casefold()] = variable
        return merged

    def _walk_moduletype_def(
        self,
        moduletype: ModuleTypeDef,
        root_path: list[str],
        base_env: dict[str, Variable],
    ) -> None:
        path = [*root_path, f"TypeDef:{moduletype.name}"]
        env = self._merge_env(base_env, moduletype.moduleparameters)
        env = self._merge_env(env, moduletype.localvariables)
        self._check_module_code(moduletype.modulecode, path, env)
        self._walk_modules(
            moduletype.submodules or [],
            parent_path=path,
            env=env,
            current_library=moduletype.origin_lib or self.bp.origin_lib,
        )

    def _walk_modules(
        self,
        children: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_path: list[str],
        env: dict[str, Variable],
        current_library: str | None,
    ) -> None:
        for child in children:
            child_path = [*parent_path, child.header.name]
            if isinstance(child, SingleModule):
                child_env = self._merge_env(env, child.moduleparameters)
                child_env = self._merge_env(child_env, child.localvariables)
                self._check_module_code(child.modulecode, child_path, child_env)
                self._walk_modules(
                    child.submodules or [],
                    parent_path=child_path,
                    env=child_env,
                    current_library=current_library,
                )
                continue

            if isinstance(child, FrameModule):
                self._check_module_code(child.modulecode, child_path, env)
                self._walk_modules(
                    child.submodules or [],
                    parent_path=child_path,
                    env=env,
                    current_library=current_library,
                )
                continue

            candidate = self._collect_alarm_candidate(
                child,
                module_path=child_path,
                env=env,
                current_library=current_library,
            )
            if candidate is not None:
                self._candidates.append(candidate)

    def _collect_alarm_candidate(
        self,
        inst: ModuleTypeInstance,
        module_path: list[str],
        env: dict[str, Variable],
        current_library: str | None,
    ) -> _AlarmCandidate | None:
        mt_def = self._resolve_moduletype(inst, current_library)
        parameter_names = self._parameter_names(inst, mt_def)
        if not any(name in parameter_names for name in _TAG_PARAMETER_NAMES):
            return None
        if not any(name in parameter_names for name in _PRIORITY_PARAMETER_NAMES + _CONDITION_PARAMETER_NAMES):
            return None

        tag_name = self._pick_parameter_name(parameter_names, _TAG_PARAMETER_NAMES)
        priority_name = self._pick_parameter_name(parameter_names, _PRIORITY_PARAMETER_NAMES)
        condition_name = self._pick_parameter_name(parameter_names, _CONDITION_PARAMETER_NAMES)

        tag_value = self._get_parameter_value(inst, mt_def, env, tag_name) if tag_name else _ParameterValue("unknown")
        priority_value = (
            self._get_parameter_value(inst, mt_def, env, priority_name) if priority_name else _ParameterValue("unknown")
        )
        condition_value = (
            self._get_parameter_value(inst, mt_def, env, condition_name)
            if condition_name
            else _ParameterValue("unknown")
        )

        tag_key = self._tag_key(tag_value)
        priority_key = self._priority_key(priority_value)
        condition_key = self._condition_key(condition_value)

        if tag_key is None and priority_key is None and condition_key is None:
            return None

        moduletype_label = format_moduletype_label(mt_def) if mt_def is not None else inst.moduletype_name
        return _AlarmCandidate(
            module_path=module_path.copy(),
            instance_name=inst.header.name,
            moduletype_label=moduletype_label,
            tag_key=tag_key,
            tag_display=self._tag_display(tag_value),
            priority_key=priority_key,
            priority_display=self._value_display(priority_value),
            condition_key=condition_key,
            condition_display=self._condition_display(condition_value),
        )

    def _resolve_moduletype(
        self,
        inst: ModuleTypeInstance,
        current_library: str | None,
    ) -> ModuleTypeDef | None:
        try:
            return resolve_moduletype_def_strict(
                self.bp,
                inst.moduletype_name,
                current_library=current_library,
                unavailable_libraries=self._unavailable_libraries,
            )
        except ValueError:
            return None

    def _parameter_names(
        self,
        inst: ModuleTypeInstance,
        mt_def: ModuleTypeDef | None,
    ) -> set[str]:
        names = (
            {variable.name.casefold() for variable in (mt_def.moduleparameters or [])} if mt_def is not None else set()
        )
        for mapping in inst.parametermappings or []:
            target_name = varname_base(mapping.target)
            if target_name:
                names.add(target_name)
        return names

    def _pick_parameter_name(
        self,
        available: set[str],
        wanted_names: tuple[str, ...],
    ) -> str | None:
        for name in wanted_names:
            if name in available:
                return name
        return None

    def _get_parameter_value(
        self,
        inst: ModuleTypeInstance,
        mt_def: ModuleTypeDef | None,
        env: dict[str, Variable],
        parameter_name: str,
    ) -> _ParameterValue:
        mapping = self._find_parameter_mapping(inst.parametermappings, parameter_name)
        if mapping is not None:
            resolved = self._resolve_mapping_value(mapping, env)
            if resolved is not None:
                return resolved
            return _ParameterValue(status="unresolved_mapping")

        if mt_def is None:
            return _ParameterValue(status="unknown")

        param = self._find_variable(mt_def.moduleparameters, parameter_name)
        if param is None:
            return _ParameterValue(status="unknown")
        if param.init_value is not None:
            return _ParameterValue(
                status="resolved",
                value=param.init_value,
                source=f"default parameter value on {format_moduletype_label(mt_def)}",
                signature=self._literal_signature(param.init_value),
            )
        return _ParameterValue(status="not_configured")

    def _find_parameter_mapping(
        self,
        mappings: list[ParameterMapping] | None,
        parameter_name: str,
    ) -> ParameterMapping | None:
        wanted = parameter_name.casefold()
        for mapping in mappings or []:
            target_name = varname_base(mapping.target)
            if target_name == wanted:
                return mapping
        return None

    def _resolve_mapping_value(
        self,
        mapping: ParameterMapping,
        env: dict[str, Variable],
    ) -> _ParameterValue | None:
        if mapping.source_type == const.KEY_VALUE:
            return _ParameterValue(
                status="resolved",
                value=mapping.source_literal,
                source="literal parameter mapping",
                signature=self._literal_signature(mapping.source_literal),
            )

        full_ref = varname_full(mapping.source)
        if not full_ref:
            return None

        signature = full_ref.casefold()
        if mapping.is_source_global:
            return _ParameterValue(
                status="reference",
                source=f"GLOBAL {full_ref}",
                signature=signature,
            )

        if "." not in full_ref and ":" not in full_ref:
            variable = env.get(full_ref.casefold())
            if variable is not None and variable.init_value is not None:
                return _ParameterValue(
                    status="resolved",
                    value=variable.init_value,
                    source=f"init value of variable {variable.name}",
                    signature=signature,
                )

        return _ParameterValue(
            status="reference",
            source=f"mapped variable reference {full_ref}",
            signature=signature,
        )

    def _find_variable(
        self,
        variables: list[Variable] | None,
        wanted_name: str,
    ) -> Variable | None:
        wanted = wanted_name.casefold()
        for variable in variables or []:
            if variable.name.casefold() == wanted:
                return variable
        return None

    def _tag_key(self, value: _ParameterValue) -> str | None:
        if isinstance(value.value, str) and value.value.strip():
            return f"tag:{value.value.strip().casefold()}"
        if value.signature:
            return f"ref:{value.signature}"
        return None

    def _tag_display(self, value: _ParameterValue) -> str | None:
        if isinstance(value.value, str) and value.value.strip():
            return value.value.strip()
        if value.source:
            return value.source
        return value.signature

    def _priority_key(self, value: _ParameterValue) -> str | None:
        if value.value is not None:
            return self._literal_signature(value.value)
        return None

    def _condition_key(self, value: _ParameterValue) -> str | None:
        if value.signature is None:
            return None
        if value.signature in {"literal:true", "literal:false", "literal:none"}:
            return None
        return value.signature

    def _condition_display(self, value: _ParameterValue) -> str | None:
        if value.source:
            return value.source
        return value.signature

    def _value_display(self, value: _ParameterValue) -> str | None:
        if value.value is not None:
            return repr(value.value)
        return value.source or value.signature

    def _literal_signature(self, value: object | None) -> str:
        if isinstance(value, str):
            return f"literal:{value.strip().casefold()}"
        return f"literal:{value!r}"

    def _emit_duplicate_tag_issues(self) -> None:
        by_tag: dict[str, list[_AlarmCandidate]] = defaultdict(list)
        for candidate in self._candidates:
            if candidate.tag_key is not None:
                by_tag[candidate.tag_key].append(candidate)

        for candidates in by_tag.values():
            if len(candidates) < 2:
                continue
            tag_label = candidates[0].tag_display or "<unresolved tag>"
            locations = self._location_list(candidates)
            for candidate in candidates:
                self._issues.append(
                    Issue(
                        kind="alarm.duplicate_tag",
                        message=(
                            f"Alarm tag {tag_label!r} is configured more than once across alarm sources: {locations}."
                        ),
                        module_path=candidate.module_path.copy(),
                        data={
                            "tag": tag_label,
                            "locations": locations,
                        },
                    )
                )

    def _emit_duplicate_condition_issues(self) -> None:
        by_condition: dict[str, list[_AlarmCandidate]] = defaultdict(list)
        for candidate in self._candidates:
            if candidate.condition_key is not None:
                by_condition[candidate.condition_key].append(candidate)

        for candidates in by_condition.values():
            if len(candidates) < 2:
                continue
            condition_label = candidates[0].condition_display or "<unresolved condition>"
            locations = self._location_list(candidates)
            for candidate in candidates:
                self._issues.append(
                    Issue(
                        kind="alarm.duplicate_condition",
                        message=(
                            f"Alarm condition {condition_label!r} is reused by multiple alarm sources: {locations}."
                        ),
                        module_path=candidate.module_path.copy(),
                        data={
                            "condition": condition_label,
                            "locations": locations,
                        },
                    )
                )

    def _emit_conflicting_priority_issues(self) -> None:
        by_tag: dict[str, list[_AlarmCandidate]] = defaultdict(list)
        by_condition: dict[str, list[_AlarmCandidate]] = defaultdict(list)
        for candidate in self._candidates:
            if candidate.priority_key is None:
                continue
            if candidate.tag_key is not None:
                by_tag[candidate.tag_key].append(candidate)
            if candidate.condition_key is not None:
                by_condition[candidate.condition_key].append(candidate)

        seen_groups: set[tuple[str, tuple[tuple[str, ...], ...]]] = set()

        for scope_name, groups in (("tag", by_tag), ("condition", by_condition)):
            for scope_key, candidates in groups.items():
                priorities = {candidate.priority_key for candidate in candidates if candidate.priority_key is not None}
                if len(candidates) < 2 or len(priorities) < 2:
                    continue

                group_id = (
                    scope_name,
                    tuple(sorted(tuple(candidate.module_path) for candidate in candidates)),
                )
                if group_id in seen_groups:
                    continue
                seen_groups.add(group_id)

                if scope_name == "tag":
                    scope_label = candidates[0].tag_display or scope_key
                    detail = f"Alarm tag {scope_label!r}"
                else:
                    scope_label = candidates[0].condition_display or scope_key
                    detail = f"Alarm condition {scope_label!r}"

                priorities_label = ", ".join(
                    sorted({candidate.priority_display or "<unknown priority>" for candidate in candidates})
                )
                locations = self._location_list(candidates)
                for candidate in candidates:
                    self._issues.append(
                        Issue(
                            kind="alarm.conflicting_priority",
                            message=(
                                f"{detail} is configured with conflicting priorities or severities ({priorities_label}) across: {locations}."
                            ),
                            module_path=candidate.module_path.copy(),
                            data={
                                "scope": scope_name,
                                "scope_value": scope_label,
                                "priorities": sorted(priorities),
                                "locations": locations,
                            },
                        )
                    )

    def _check_module_code(
        self,
        modulecode: ModuleCode | None,
        module_path: list[str],
        env: dict[str, Variable],
    ) -> None:
        if modulecode is None:
            return

        writes: dict[str, dict[str, Any]] = {}
        for statement in self._iter_modulecode_statements(modulecode):
            self._collect_boolean_writes(statement, env, writes)

        for entry in writes.values():
            values = entry["values"]
            if True not in values or False in values:
                continue
            self._issues.append(
                Issue(
                    kind="alarm.never_cleared",
                    message=(
                        f"Alarm variable {entry['display']!r} is only written with True and is never explicitly cleared to False in this scope."
                    ),
                    module_path=module_path.copy(),
                    data={"variable": entry["display"]},
                )
            )

    def _iter_modulecode_statements(self, modulecode: ModuleCode) -> list[Any]:
        statements: list[Any] = []
        for equation in modulecode.equations or []:
            statements.extend(equation.code or [])
        for sequence in modulecode.sequences or []:
            statements.extend(self._iter_sequence_statements(sequence))
        return statements

    def _iter_sequence_statements(self, sequence: Sequence) -> list[Any]:
        statements: list[Any] = []
        for node in sequence.code or []:
            statements.extend(self._iter_sequence_node_statements(node))
        return statements

    def _iter_sequence_node_statements(self, node: Any) -> list[Any]:
        if isinstance(node, SFCStep):
            return [*(node.code.enter or []), *(node.code.active or []), *(node.code.exit or [])]
        if isinstance(node, SFCAlternative | SFCParallel):
            branch_statements: list[Any] = []
            for branch in node.branches or []:
                for child in branch:
                    branch_statements.extend(self._iter_sequence_node_statements(child))
            return branch_statements
        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            nested_statements: list[Any] = []
            for child in node.body or []:
                nested_statements.extend(self._iter_sequence_node_statements(child))
            return nested_statements
        return []

    def _collect_boolean_writes(
        self,
        obj: Any,
        env: dict[str, Variable],
        writes: dict[str, dict[str, Any]],
    ) -> None:
        if obj is None:
            return

        if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
            for child in getattr(obj, "children", []):
                self._collect_boolean_writes(child, env, writes)
            return

        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
            _if_tag, branches, else_block = obj
            for condition, branch_statements in branches or []:
                self._collect_boolean_writes(condition, env, writes)
                for statement in branch_statements or []:
                    self._collect_boolean_writes(statement, env, writes)
            for statement in else_block or []:
                self._collect_boolean_writes(statement, env, writes)
            return

        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
            _assign, target, expr = obj
            self._record_boolean_write(target, expr, env, writes)
            self._collect_boolean_writes(expr, env, writes)
            return

        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
            _call, function_name, args = obj
            if (function_name or "").casefold() == "setbooleanvalue" and len(args or []) >= 2:
                self._record_boolean_write(args[0], args[1], env, writes)
            for argument in args or []:
                self._collect_boolean_writes(argument, env, writes)
            return

        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_TERNARY:
            _ternary, branches, else_expr = obj
            for condition, then_expr in branches or []:
                self._collect_boolean_writes(condition, env, writes)
                self._collect_boolean_writes(then_expr, env, writes)
            self._collect_boolean_writes(else_expr, env, writes)
            return

        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, const.KEY_ADD, const.KEY_MUL):
            for child in obj[1:]:
                self._collect_boolean_writes(child, env, writes)
            return

        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_PLUS, const.KEY_MINUS, const.GRAMMAR_VALUE_NOT):
            self._collect_boolean_writes(obj[1], env, writes)
            return

        if isinstance(obj, tuple) and obj and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
            for child in obj[1] or []:
                self._collect_boolean_writes(child, env, writes)
            return

        if isinstance(obj, list):
            for item in obj:
                self._collect_boolean_writes(item, env, writes)
            return

        if hasattr(obj, "children"):
            for child in getattr(obj, "children", []):
                self._collect_boolean_writes(child, env, writes)

    def _record_boolean_write(
        self,
        target: Any,
        expr: Any,
        env: dict[str, Variable],
        writes: dict[str, dict[str, Any]],
    ) -> None:
        target_ref = varname_full(target)
        if not target_ref:
            return
        if not self._looks_like_alarm_reference(target_ref, env):
            return
        bool_value = self._as_bool_literal(expr)
        if bool_value is None:
            return

        entry = writes.setdefault(
            target_ref.casefold(),
            {"display": target_ref, "values": set()},
        )
        entry["values"].add(bool_value)

    def _looks_like_alarm_reference(
        self,
        target_ref: str,
        env: dict[str, Variable],
    ) -> bool:
        base_name = target_ref.split(".", 1)[0]
        variable = env.get(base_name.casefold())
        if variable is None:
            return False
        datatype_text = variable.datatype_text.casefold()
        if datatype_text != "boolean":
            return False
        return "alarm" in target_ref.casefold()

    def _as_bool_literal(self, expr: Any) -> bool | None:
        if isinstance(expr, bool):
            return expr
        return None

    def _location_list(self, candidates: list[_AlarmCandidate]) -> list[str]:
        return sorted({".".join(candidate.module_path) for candidate in candidates})


def analyze_alarm_integrity(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
) -> AlarmIntegrityReport:
    _ = debug
    analyzer = AlarmIntegrityAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    )
    analyzer.run()
    return AlarmIntegrityReport(
        basepicture_name=base_picture.header.name,
        issues=analyzer.issues,
    )
