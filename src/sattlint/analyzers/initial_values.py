from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..grammar import constants as const
from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
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


_PARAMETER_CATEGORY_MARKERS = {
    "recipe": ("recpar",),
    "engineering": ("engpar",),
}
_VALUE_PARAMETER_NAMES = {
    "value",
    "default",
    "defaultvalue",
    "initialvalue",
    "initvalue",
    "boolvalue",
    "intvalue",
    "realvalue",
    "stringvalue",
    "recipevalue",
    "engineeringvalue",
    "setpoint",
}
_VALUE_PARAMETER_ALLOWLIST = {
    "allow",
    "colours",
    "description",
    "digits",
    "format",
    "headername",
    "maxvalue",
    "medianame",
    "minvalue",
    "name",
    "nextview",
    "opmax",
    "opmin",
    "p",
    "precision",
    "programname",
    "sectionname",
    "unit",
    "visible",
}
_CATEGORY_LABELS = {
    "recipe": "Recipe parameters",
    "engineering": "Engineering parameters",
}


@dataclass(frozen=True)
class _ParameterValue:
    status: str
    value: object | None = None
    source: str | None = None


@dataclass
class InitialValueReport:
    name: str
    issues: list[Issue] = field(default_factory=list)

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header(
                "Initial value validation",
                self.name,
                status="ok",
            )
            lines.append("No missing recipe or engineering parameter defaults found.")
            return "\n".join(lines)

        lines = format_report_header(
            "Initial value validation",
            self.name,
            status="issues",
        )
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        lines.append("Kinds:")
        counts = Counter(
            str((issue.data or {}).get("parameter_category", "unknown"))
            for issue in self.issues
        )
        for category in ("recipe", "engineering"):
            count = counts.get(category, 0)
            if count:
                lines.append(f"  - {_CATEGORY_LABELS[category]}: {count}")

        lines.append("")
        lines.append("Findings:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


class InitialValueAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        unavailable_libraries: set[str] | None = None,
    ) -> None:
        self.bp = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._issues: list[Issue] = []

    @property
    def issues(self) -> list[Issue]:
        return self._issues

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]
        base_env = self._merge_env({}, self.bp.localvariables)

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

        return self._issues

    def _is_from_root_origin(self, origin_file: str | None) -> bool:
        if not origin_file:
            return True
        root_origin = getattr(self.bp, "origin_file", None)
        if not root_origin:
            return False
        return (
            origin_file.rsplit(".", 1)[0].casefold()
            == root_origin.rsplit(".", 1)[0].casefold()
        )

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
        path = root_path + [f"TypeDef:{moduletype.name}"]
        env = self._merge_env(base_env, moduletype.moduleparameters)
        env = self._merge_env(env, moduletype.localvariables)
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
            child_path = parent_path + [child.header.name]
            if isinstance(child, SingleModule):
                child_env = self._merge_env(env, child.moduleparameters)
                child_env = self._merge_env(child_env, child.localvariables)
                self._walk_modules(
                    child.submodules or [],
                    parent_path=child_path,
                    env=child_env,
                    current_library=current_library,
                )
                continue

            if isinstance(child, FrameModule):
                self._walk_modules(
                    child.submodules or [],
                    parent_path=child_path,
                    env=env,
                    current_library=current_library,
                )
                continue

            self._check_instance_initial_values(
                child,
                module_path=child_path,
                env=env,
                current_library=current_library,
            )

    def _check_instance_initial_values(
        self,
        inst: ModuleTypeInstance,
        module_path: list[str],
        env: dict[str, Variable],
        current_library: str | None,
    ) -> None:
        mt_def = self._resolve_moduletype(inst, current_library)
        parameter_category = self._parameter_category(inst, mt_def)
        if parameter_category is None:
            return

        required_parameters = self._required_parameter_names(inst, mt_def)
        if not required_parameters:
            return

        statuses: dict[str, str] = {}
        for parameter_name in required_parameters:
            parameter_value = self._get_parameter_value(inst, mt_def, env, parameter_name)
            statuses[parameter_name] = parameter_value.status
            if parameter_value.status == "resolved":
                return

        moduletype_label = format_moduletype_label(mt_def) if mt_def is not None else inst.moduletype_name
        self._issues.append(
            Issue(
                kind="initial-values.missing_required_default",
                message=self._build_missing_value_message(
                    parameter_category,
                    inst,
                    moduletype_label,
                    statuses,
                ),
                module_path=module_path.copy(),
                data={
                    "parameter_category": parameter_category,
                    "instance": inst.header.name,
                    "moduletype": inst.moduletype_name,
                    "moduletype_label": moduletype_label,
                    "required_parameters": required_parameters,
                    "parameter_statuses": statuses,
                },
            )
        )

    def _build_missing_value_message(
        self,
        parameter_category: str,
        inst: ModuleTypeInstance,
        moduletype_label: str,
        statuses: dict[str, str],
    ) -> str:
        category_label = "Recipe parameter" if parameter_category == "recipe" else "Engineering parameter"
        parameter_list = ", ".join(sorted(statuses))
        if any(status == "unresolved_mapping" for status in statuses.values()):
            detail = "the configured mapping does not resolve to a literal or initialized variable"
        elif any(status == "unknown" for status in statuses.values()):
            detail = "the parameter definition could not be verified"
        else:
            detail = "no default or explicit initialized mapping is configured"
        return (
            f"{category_label} {inst.header.name!r} ({moduletype_label}) is missing a required initial value; "
            f"checked {parameter_list} and {detail}."
        )

    def _parameter_category(
        self,
        inst: ModuleTypeInstance,
        mt_def: ModuleTypeDef | None,
    ) -> str | None:
        candidates = [inst.moduletype_name]
        if mt_def is not None:
            candidates.append(mt_def.name)
            candidates.append(format_moduletype_label(mt_def))

        for candidate in candidates:
            candidate_cf = candidate.casefold()
            for category, markers in _PARAMETER_CATEGORY_MARKERS.items():
                if any(marker in candidate_cf for marker in markers):
                    return category
        return None

    def _required_parameter_names(
        self,
        inst: ModuleTypeInstance,
        mt_def: ModuleTypeDef | None,
    ) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()

        for variable in mt_def.moduleparameters or [] if mt_def is not None else []:
            normalized = variable.name.casefold()
            if normalized in seen:
                continue
            names.append(variable.name)
            seen.add(normalized)

        for mapping in inst.parametermappings or []:
            target_name = varname_base(mapping.target)
            if not target_name:
                continue
            normalized = target_name.casefold()
            if normalized in seen:
                continue
            names.append(target_name)
            seen.add(normalized)

        return [
            name
            for name in names
            if self._looks_like_required_value_parameter(name)
        ]

    def _looks_like_required_value_parameter(self, name: str) -> bool:
        normalized = name.casefold()
        if normalized in _VALUE_PARAMETER_ALLOWLIST:
            return False
        if normalized in _VALUE_PARAMETER_NAMES:
            return True
        return normalized.endswith("value") and normalized not in _VALUE_PARAMETER_ALLOWLIST

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

    def _get_parameter_value(
        self,
        inst: ModuleTypeInstance,
        mt_def: ModuleTypeDef | None,
        env: dict[str, Variable],
        parameter_name: str,
    ) -> _ParameterValue:
        mapping = self._find_parameter_mapping(inst.parametermappings, parameter_name)
        if mapping is not None:
            return self._resolve_mapping_value(mapping, env)

        if mt_def is None:
            return _ParameterValue(status="unknown")

        param = self._find_variable(mt_def.moduleparameters, parameter_name)
        if param is None:
            return _ParameterValue(status="unknown")
        if param.init_value is not None:
            label = format_moduletype_label(mt_def)
            return _ParameterValue(
                status="resolved",
                value=param.init_value,
                source=f"default parameter value on {label}",
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
    ) -> _ParameterValue:
        if mapping.source_type == const.KEY_VALUE:
            if mapping.source_literal is None:
                return _ParameterValue(status="unresolved_mapping")
            return _ParameterValue(
                status="resolved",
                value=mapping.source_literal,
                source="literal parameter mapping",
            )

        full_ref = varname_full(mapping.source)
        if not full_ref:
            return _ParameterValue(status="unknown")
        if "." in full_ref or ":" in full_ref:
            return _ParameterValue(
                status="unresolved_mapping",
                source=f"mapping from {full_ref}",
            )

        variable = env.get(full_ref.casefold())
        if variable is None or variable.init_value is None:
            return _ParameterValue(
                status="unresolved_mapping",
                source=f"mapping from {full_ref}",
            )

        return _ParameterValue(
            status="resolved",
            value=variable.init_value,
            source=f"init value of variable {variable.name}",
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


def analyze_initial_values(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
) -> InitialValueReport:
    _ = debug
    analyzer = InitialValueAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    )
    return InitialValueReport(name=base_picture.header.name, issues=analyzer.run())
