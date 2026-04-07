from __future__ import annotations

from dataclasses import dataclass

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
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    Variable,
)
from ..resolution.common import format_moduletype_label, resolve_moduletype_def_strict, varname_base, varname_full
from .framework import Issue, SimpleReport


_OPMESSAGE_NAME = "OPMessage"
_OPMESSAGE_LIB = "NNESystem"
_MES_BATCH_CONTROL_NAME = "MES_BatchControl"
_MES_BATCH_CONTROL_LIB = "NNEMESIFLib"


@dataclass(frozen=True)
class _ParameterValue:
    status: str
    value: object | None = None
    source: str | None = None


class SpecComplianceAnalyzer:
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

        self._check_basepicture_code(self.bp.modulecode, root_path)
        self._check_module_code(self.bp.modulecode, root_path)
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

    def _check_basepicture_code(
        self,
        modulecode: ModuleCode | None,
        module_path: list[str],
    ) -> None:
        if not self._has_code(modulecode):
            return
        self._issues.append(
            Issue(
                kind="spec.basepicture_direct_code",
                message="BasePicture contains direct code. The engineering spec only allows base-picture code inside a frame module.",
                module_path=module_path.copy(),
            )
        )

    def _has_code(self, modulecode: ModuleCode | None) -> bool:
        if modulecode is None:
            return False
        return bool(modulecode.equations or modulecode.sequences)

    def _walk_moduletype_def(
        self,
        moduletype: ModuleTypeDef,
        root_path: list[str],
        base_env: dict[str, Variable],
    ) -> None:
        path = root_path + [moduletype.name]
        env = self._merge_env(base_env, moduletype.moduleparameters)
        env = self._merge_env(env, moduletype.localvariables)
        self._check_module_code(moduletype.modulecode, path)
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
                self._check_module_code(child.modulecode, child_path)
                self._walk_modules(
                    child.submodules or [],
                    parent_path=child_path,
                    env=child_env,
                    current_library=current_library,
                )
                continue

            if isinstance(child, FrameModule):
                self._check_module_code(child.modulecode, child_path)
                self._walk_modules(
                    child.submodules or [],
                    parent_path=child_path,
                    env=env,
                    current_library=current_library,
                )
                continue

            if isinstance(child, ModuleTypeInstance):
                self._check_instance_contracts(
                    child,
                    module_path=child_path,
                    env=env,
                    current_library=current_library,
                )

    def _check_module_code(self, modulecode: ModuleCode | None, module_path: list[str]) -> None:
        if modulecode is None:
            return
        for sequence in modulecode.sequences or []:
            self._check_sequence(sequence, module_path)

    def _check_sequence(self, sequence: Sequence, module_path: list[str]) -> None:
        for node in self._iter_sequence_nodes(sequence.code or []):
            if isinstance(node, SFCStep) and not node.name.startswith("ST_"):
                self._issues.append(
                    Issue(
                        kind="spec.sequence_step_prefix",
                        message=(
                            f"Sequence step {node.name!r} must start with 'ST_' according to the engineering spec."
                        ),
                        module_path=module_path.copy(),
                        data={"sequence": sequence.name, "step": node.name},
                    )
                )
            if isinstance(node, SFCTransition):
                if not node.name:
                    self._issues.append(
                        Issue(
                            kind="spec.transition_name_missing",
                            message=(
                                f"A transition in sequence {sequence.name!r} is missing a name. All transitions must be named."
                            ),
                            module_path=module_path.copy(),
                            data={"sequence": sequence.name},
                        )
                    )
                    continue
                if not node.name.startswith("TR_"):
                    self._issues.append(
                        Issue(
                            kind="spec.transition_prefix",
                            message=(
                                f"Transition {node.name!r} must start with 'TR_' according to the engineering spec."
                            ),
                            module_path=module_path.copy(),
                            data={"sequence": sequence.name, "transition": node.name},
                        )
                    )

    def _iter_sequence_nodes(self, nodes: list[object]):
        for node in nodes:
            yield node
            if isinstance(node, (SFCAlternative, SFCParallel)):
                for branch in node.branches or []:
                    yield from self._iter_sequence_nodes(branch)
            elif isinstance(node, SFCSubsequence):
                yield from self._iter_sequence_nodes(node.body or [])
            elif isinstance(node, SFCTransitionSub):
                yield from self._iter_sequence_nodes(node.body or [])

    def _check_instance_contracts(
        self,
        inst: ModuleTypeInstance,
        module_path: list[str],
        env: dict[str, Variable],
        current_library: str | None,
    ) -> None:
        mt_def = self._resolve_moduletype(inst, current_library)

        if self._matches_moduletype(inst, mt_def, _OPMESSAGE_NAME, _OPMESSAGE_LIB):
            use_signature = self._get_parameter_value(inst, mt_def, env, "UseSignature")
            if use_signature.status == "resolved" and use_signature.value is True:
                self._issues.append(
                    Issue(
                        kind="spec.opmessage_use_signature",
                        message=(
                            "NNESystem:OPMessage must not enable UseSignature=True. "
                            f"Resolved value from {use_signature.source}."
                        ),
                        module_path=module_path.copy(),
                        data={"instance": inst.header.name, "moduletype": inst.moduletype_name},
                    )
                )

        if not self._matches_moduletype(inst, mt_def, _MES_BATCH_CONTROL_NAME, _MES_BATCH_CONTROL_LIB):
            return

        if inst.header.name != _MES_BATCH_CONTROL_NAME:
            self._issues.append(
                Issue(
                    kind="spec.mes_batch_control_name",
                    message=(
                        "NNEMESIFLib:MES_BatchControl instance name must be exactly 'MES_BatchControl'."
                    ),
                    module_path=module_path.copy(),
                    data={"instance": inst.header.name},
                )
            )

        self._check_required_parameter(
            inst,
            mt_def,
            env,
            module_path,
            parameter_name="Max_TRY",
            expected_value=10,
            issue_kind="spec.mes_batch_control_max_try",
        )
        self._check_required_parameter(
            inst,
            mt_def,
            env,
            module_path,
            parameter_name="Repeat_TRY",
            expected_value=20,
            issue_kind="spec.mes_batch_control_repeat_try",
        )

    def _check_required_parameter(
        self,
        inst: ModuleTypeInstance,
        mt_def: ModuleTypeDef | None,
        env: dict[str, Variable],
        module_path: list[str],
        parameter_name: str,
        expected_value: object,
        issue_kind: str,
    ) -> None:
        parameter_value = self._get_parameter_value(inst, mt_def, env, parameter_name)
        if parameter_value.status == "resolved":
            if parameter_value.value == expected_value:
                return
            self._issues.append(
                Issue(
                    kind=issue_kind,
                    message=(
                        f"{inst.moduletype_name} parameter {parameter_name} must resolve to {expected_value!r}, "
                        f"but resolved to {parameter_value.value!r} from {parameter_value.source}."
                    ),
                    module_path=module_path.copy(),
                    data={
                        "instance": inst.header.name,
                        "parameter": parameter_name,
                        "expected": expected_value,
                        "actual": parameter_value.value,
                        "status": parameter_value.status,
                    },
                )
            )
            return

        if parameter_value.status == "not_configured":
            self._issues.append(
                Issue(
                    kind=issue_kind,
                    message=(
                        f"{inst.moduletype_name} parameter {parameter_name} is not configured with a default or explicit mapping."
                    ),
                    module_path=module_path.copy(),
                    data={
                        "instance": inst.header.name,
                        "parameter": parameter_name,
                        "expected": expected_value,
                        "status": parameter_value.status,
                    },
                )
            )
            return

        if parameter_value.status == "unresolved_mapping":
            message = (
                f"{inst.moduletype_name} parameter {parameter_name} is mapped, "
                "but the configured value could not be resolved statically."
            )
        else:
            message = (
                f"{inst.moduletype_name} parameter {parameter_name} could not be verified "
                "because its definition or configured value is unavailable."
            )

        self._issues.append(
            Issue(
                kind=issue_kind,
                message=message,
                module_path=module_path.copy(),
                data={
                    "instance": inst.header.name,
                    "parameter": parameter_name,
                    "expected": expected_value,
                    "status": parameter_value.status,
                },
            )
        )

    def _matches_moduletype(
        self,
        inst: ModuleTypeInstance,
        mt_def: ModuleTypeDef | None,
        expected_name: str,
        expected_lib: str,
    ) -> bool:
        if inst.moduletype_name.casefold() != expected_name.casefold():
            return False
        if mt_def is None or not mt_def.origin_lib:
            return True
        return mt_def.origin_lib.casefold() == expected_lib.casefold()

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
    ) -> _ParameterValue | None:
        if mapping.is_source_global:
            return None

        if mapping.source_type == const.KEY_VALUE:
            return _ParameterValue(
                status="resolved",
                value=mapping.source_literal,
                source="literal parameter mapping",
            )

        full_ref = varname_full(mapping.source)
        if not full_ref:
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


def analyze_spec_compliance(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
) -> SimpleReport:
    _ = debug
    analyzer = SpecComplianceAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    )
    analyzer.run()
    return SimpleReport(name=base_picture.header.name, issues=analyzer.issues)
