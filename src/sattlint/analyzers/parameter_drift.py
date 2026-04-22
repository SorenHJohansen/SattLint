from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

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
from .framework import Issue, SimpleReport


@dataclass(frozen=True)
class _ParameterValue:
    status: str
    value: object | None = None
    source: str | None = None
    signature: str | None = None


@dataclass(frozen=True)
class _InstanceParameterValue:
    module_path: list[str]
    moduletype_label: str
    parameter_name: str
    value_display: str
    value_signature: str


class ParameterDriftAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        unavailable_libraries: set[str] | None = None,
    ) -> None:
        self.bp = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._issues: list[Issue] = []
        self._parameter_values: dict[tuple[str, str], list[_InstanceParameterValue]] = defaultdict(list)

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]
        base_env = self._merge_env({}, self.bp.localvariables)
        self._walk_modules(self.bp.submodules or [], parent_path=root_path, env=base_env)
        self._emit_parameter_drift_issues()
        return self._issues

    def _walk_modules(
        self,
        modules: list[SingleModule | FrameModule | ModuleTypeInstance],
        *,
        parent_path: list[str],
        env: dict[str, Variable],
    ) -> None:
        for module in modules:
            module_path = [*parent_path, module.header.name]
            if isinstance(module, ModuleTypeInstance):
                self._collect_instance_parameter_values(module, module_path, env)
                continue
            if isinstance(module, SingleModule):
                nested_env = self._merge_env(env, module.moduleparameters)
                nested_env = self._merge_env(nested_env, module.localvariables)
                self._walk_modules(module.submodules or [], parent_path=module_path, env=nested_env)
                continue
            if isinstance(module, FrameModule):
                self._walk_modules(module.submodules or [], parent_path=module_path, env=env)

    def _collect_instance_parameter_values(
        self,
        inst: ModuleTypeInstance,
        module_path: list[str],
        env: dict[str, Variable],
    ) -> None:
        try:
            mt_def = resolve_moduletype_def_strict(
                self.bp,
                inst.moduletype_name,
                current_library=getattr(inst, "origin_lib", None),
                unavailable_libraries=self._unavailable_libraries,
            )
        except ValueError:
            mt_def = None

        moduletype_label = format_moduletype_label(mt_def) if mt_def is not None else inst.moduletype_name
        parameter_names = self._parameter_names(inst, mt_def)
        for parameter_name in parameter_names:
            value = self._get_parameter_value(inst, mt_def, env, parameter_name)
            if value.status != "resolved" or not value.signature:
                continue
            self._parameter_values[(moduletype_label.casefold(), parameter_name.casefold())].append(
                _InstanceParameterValue(
                    module_path=module_path.copy(),
                    moduletype_label=moduletype_label,
                    parameter_name=parameter_name,
                    value_display=self._value_display(value),
                    value_signature=value.signature,
                )
            )

    def _parameter_names(
        self,
        inst: ModuleTypeInstance,
        mt_def: ModuleTypeDef | None,
    ) -> tuple[str, ...]:
        names_by_key: dict[str, str] = {}
        for mapping in inst.parametermappings or []:
            target_name = self._mapping_parameter_name(mapping)
            if target_name:
                names_by_key.setdefault(target_name.casefold(), target_name)
        for parameter in mt_def.moduleparameters if mt_def is not None else []:
            if parameter.init_value is not None:
                names_by_key.setdefault(parameter.name.casefold(), parameter.name)
        return tuple(names_by_key[key] for key in sorted(names_by_key))

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

        parameter = self._find_variable(mt_def.moduleparameters, parameter_name)
        if parameter is None or parameter.init_value is None:
            return _ParameterValue(status="unknown")
        return _ParameterValue(
            status="resolved",
            value=parameter.init_value,
            source=f"default parameter value on {format_moduletype_label(mt_def)}",
            signature=self._literal_signature(parameter.init_value),
        )

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

    def _mapping_parameter_name(self, mapping: ParameterMapping) -> str | None:
        target_name = varname_full(mapping.target)
        if not target_name:
            return None
        return target_name.split(".", 1)[0]

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
        if not full_ref or mapping.is_source_global:
            return None
        if "." in full_ref or ":" in full_ref:
            return None

        variable = env.get(full_ref.casefold())
        if variable is None or variable.init_value is None:
            return None
        return _ParameterValue(
            status="resolved",
            value=variable.init_value,
            source=f"init value of variable {variable.name}",
            signature=self._literal_signature(variable.init_value),
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

    def _merge_env(
        self,
        env: dict[str, Variable],
        variables: list[Variable] | None,
    ) -> dict[str, Variable]:
        merged = dict(env)
        for variable in variables or []:
            merged[variable.name.casefold()] = variable
        return merged

    def _value_display(self, value: _ParameterValue) -> str:
        if value.value is not None:
            return repr(value.value)
        return value.source or "<unresolved>"

    def _literal_signature(self, value: object | None) -> str:
        if isinstance(value, str):
            return f"literal:{value.strip().casefold()}"
        return f"literal:{value!r}"

    def _emit_parameter_drift_issues(self) -> None:
        for values in self._parameter_values.values():
            if len(values) < 2:
                continue
            distinct_signatures = {value.value_signature for value in values}
            if len(distinct_signatures) < 2:
                continue

            moduletype_label = values[0].moduletype_label
            parameter_name = values[0].parameter_name
            locations = ", ".join(
                f"{'.'.join(value.module_path)}={value.value_display}"
                for value in sorted(values, key=lambda item: (item.module_path, item.value_display))
            )
            for value in values:
                self._issues.append(
                    Issue(
                        kind="module.parameter_drift",
                        message=(
                            f"Module type {moduletype_label!r} parameter {parameter_name!r} varies across instances: {locations}."
                        ),
                        module_path=value.module_path.copy(),
                        data={
                            "moduletype": moduletype_label,
                            "parameter": parameter_name,
                            "locations": locations,
                        },
                    )
                )


def analyze_parameter_drift(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
) -> SimpleReport:
    analyzer = ParameterDriftAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    )
    return SimpleReport(name=base_picture.header.name, issues=analyzer.run())
