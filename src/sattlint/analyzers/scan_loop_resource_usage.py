from __future__ import annotations

from ..grammar import constants as const
from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    SingleModule,
)
from .framework import Issue, SimpleReport
from .sattline_builtins import get_function_signature


class ScanLoopResourceUsageAnalyzer:
    def __init__(self, base_picture: BasePicture) -> None:
        self.bp = base_picture
        self._issues: list[Issue] = []

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]
        self._scan_modulecode(root_path, self.bp.modulecode)
        for moduletype in self.bp.moduletype_defs or []:
            self._walk_moduletype(moduletype, parent_path=root_path)
        self._walk_modules(self.bp.submodules or [], parent_path=root_path)
        return self._issues

    def _walk_moduletype(
        self,
        moduletype: ModuleTypeDef,
        *,
        parent_path: list[str],
    ) -> None:
        module_path = [*parent_path, moduletype.name]
        self._scan_modulecode(module_path, moduletype.modulecode)
        self._walk_modules(moduletype.submodules or [], parent_path=module_path)

    def _walk_modules(
        self,
        modules: list[SingleModule | FrameModule | ModuleTypeInstance],
        *,
        parent_path: list[str],
    ) -> None:
        for module in modules:
            if isinstance(module, ModuleTypeInstance):
                continue
            module_path = [*parent_path, module.header.name]
            self._scan_modulecode(module_path, module.modulecode)
            self._walk_modules(module.submodules or [], parent_path=module_path)

    def _scan_modulecode(
        self,
        module_path: list[str],
        modulecode: ModuleCode | None,
    ) -> None:
        if modulecode is None:
            return
        for equation in modulecode.equations or []:
            context = f"equation block {equation.name!r}"
            for statement in equation.code or []:
                self._scan_node(statement, module_path=module_path, context=context)
        for sequence in modulecode.sequences or []:
            self._scan_sequence_nodes(
                module_path=module_path,
                sequence_name=sequence.name,
                nodes=sequence.code or [],
            )

    def _scan_sequence_nodes(
        self,
        *,
        module_path: list[str],
        sequence_name: str,
        nodes: list[object],
    ) -> None:
        for node in nodes:
            if isinstance(node, SFCStep):
                context = f"active code of step {node.name!r} in sequence {sequence_name!r}"
                for statement in node.code.active or []:
                    self._scan_node(statement, module_path=module_path, context=context)
                continue
            if isinstance(node, SFCAlternative | SFCParallel):
                for branch in node.branches or []:
                    self._scan_sequence_nodes(
                        module_path=module_path,
                        sequence_name=sequence_name,
                        nodes=branch,
                    )
                continue
            if isinstance(node, SFCSubsequence | SFCTransitionSub):
                self._scan_sequence_nodes(
                    module_path=module_path,
                    sequence_name=sequence_name,
                    nodes=node.body or [],
                )

    def _scan_node(
        self,
        node: object,
        *,
        module_path: list[str],
        context: str,
    ) -> None:
        if node is None:
            return
        if isinstance(node, tuple) and node:
            if node[0] == const.KEY_FUNCTION_CALL and len(node) == 3:
                _call_tag, function_name, args = node
                signature = get_function_signature(str(function_name))
                if signature is not None and not signature.precision_scangroup:
                    self._issues.append(
                        Issue(
                            kind="scan_cycle.resource_usage",
                            message=(
                                f"Call {str(function_name)!r} is not precision-scan-safe and should not run in {context} "
                                f"at {'.'.join(module_path)!r}."
                            ),
                            module_path=module_path.copy(),
                            data={
                                "call": signature.name,
                                "context": context,
                                "precision_scangroup": signature.precision_scangroup,
                            },
                        )
                    )
                for argument in args or []:
                    self._scan_node(argument, module_path=module_path, context=context)
                return
            for child in node[1:]:
                self._scan_node(child, module_path=module_path, context=context)
            return
        if isinstance(node, list):
            for item in node:
                self._scan_node(item, module_path=module_path, context=context)
            return
        if hasattr(node, "children"):
            for child in getattr(node, "children", []):
                self._scan_node(child, module_path=module_path, context=context)


def analyze_scan_loop_resource_usage(base_picture: BasePicture) -> SimpleReport:
    analyzer = ScanLoopResourceUsageAnalyzer(base_picture)
    return SimpleReport(name=base_picture.header.name, issues=analyzer.run())
