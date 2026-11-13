from __future__ import annotations

from typing import cast

from sattlint.parser_api import (
    Assignment,
    BasePicture,
    BinOp,
    BoolOp,
    Compare,
    FrameModule,
    FuncCall,
    FuncCallStmt,
    IfStmt,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    NotOp,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    TernaryOp,
    UnaryOp,
    VarRef,
)

from ..config.analysis import (
    DEFAULT_CYCLOMATIC_EQUATION_BLOCK_THRESHOLD as DEFAULT_EQUATION_BLOCK_COMPLEXITY_THRESHOLD,
)
from ..config.analysis import (
    DEFAULT_CYCLOMATIC_MODULE_THRESHOLD as DEFAULT_MODULE_COMPLEXITY_THRESHOLD,
)
from ..config.analysis import (
    DEFAULT_CYCLOMATIC_STEP_THRESHOLD as DEFAULT_STEP_COMPLEXITY_THRESHOLD,
)
from ..config.analysis import (
    cyclomatic_equation_block_threshold,
    cyclomatic_module_threshold,
    cyclomatic_step_threshold,
)
from .framework import Issue, SimpleReport
from .shared._walk_utils import iter_nested_modules
from .shared.target_origin import build_target_origin_filter_for_basepicture

__all__ = [
    "DEFAULT_EQUATION_BLOCK_COMPLEXITY_THRESHOLD",
    "DEFAULT_MODULE_COMPLEXITY_THRESHOLD",
    "DEFAULT_STEP_COMPLEXITY_THRESHOLD",
    "CyclomaticComplexityAnalyzer",
    "analyze_cyclomatic_complexity",
]


class CyclomaticComplexityAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        *,
        module_threshold: int | None = None,
        step_threshold: int | None = None,
        equation_block_threshold: int | None = None,
        analyzed_target_is_library: bool = False,
        config: dict[str, object] | None = None,
    ) -> None:
        self.bp = base_picture
        self._module_threshold = cyclomatic_module_threshold(config) if module_threshold is None else module_threshold
        self._step_threshold = cyclomatic_step_threshold(config) if step_threshold is None else step_threshold
        self._equation_block_threshold = (
            cyclomatic_equation_block_threshold(config)
            if equation_block_threshold is None
            else equation_block_threshold
        )
        self._analyzed_target_is_library = analyzed_target_is_library
        self._issues: list[Issue] = []

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]
        self._record_scope_complexity_issue(
            module_path=root_path,
            scope_kind="program",
            modulecode=self.bp.modulecode,
        )
        moduletype_filter = build_target_origin_filter_for_basepicture(
            self.bp,
            analyzed_target_is_library=self._analyzed_target_is_library,
        )
        for moduletype in self.bp.moduletype_defs or []:
            if not moduletype_filter(moduletype):
                continue
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
        self._record_scope_complexity_issue(
            module_path=module_path,
            scope_kind="module type",
            modulecode=moduletype.modulecode,
        )
        self._walk_modules(moduletype.submodules or [], parent_path=module_path)

    def _walk_modules(
        self,
        modules: list[SingleModule | FrameModule | ModuleTypeInstance],
        *,
        parent_path: list[str],
    ) -> None:
        for module, module_path in iter_nested_modules(modules, parent_path=parent_path):
            if isinstance(module, ModuleTypeInstance):
                continue
            self._record_scope_complexity_issue(
                module_path=module_path,
                scope_kind="module",
                modulecode=module.modulecode,
            )

    def _record_scope_complexity_issue(
        self,
        *,
        module_path: list[str],
        scope_kind: str,
        modulecode: ModuleCode | None,
    ) -> None:
        if modulecode is None:
            return
        complexity = self._modulecode_complexity(module_path, modulecode)
        if complexity <= self._module_threshold:
            return
        scope_label = ".".join(module_path)
        self._issues.append(
            Issue(
                kind="module.cyclomatic_complexity",
                message=(
                    f"{scope_kind.capitalize()} {scope_label!r} has cyclomatic complexity {complexity}, "
                    f"exceeding threshold {self._module_threshold}."
                ),
                module_path=module_path.copy(),
                data={
                    "scope": scope_kind,
                    "complexity": complexity,
                    "threshold": self._module_threshold,
                    "site": scope_label,
                    "context": f"complexity {complexity} > {self._module_threshold}",
                },
            )
        )

    def _modulecode_complexity(
        self,
        module_path: list[str],
        modulecode: ModuleCode,
    ) -> int:
        complexity = 1
        for equation in modulecode.equationblocks or []:
            equation_name = getattr(equation, "name", "") or "<unnamed>"
            self._record_equation_block_complexity_issue(
                module_path=module_path,
                equation_name=equation_name,
                equation_code=cast(list[object], equation.code or []),
            )
            complexity += self._count_statement_list(cast(list[object], equation.code or []))
        for sequence in modulecode.sequences or []:
            complexity += self._count_sequence_nodes(
                module_path=module_path,
                sequence_name=sequence.name or "",
                nodes=cast(list[object], sequence.code or []),
            )
        return complexity

    def _record_equation_block_complexity_issue(
        self,
        *,
        module_path: list[str],
        equation_name: str,
        equation_code: list[object],
    ) -> None:
        equation_complexity = 1 + self._count_statement_list(equation_code)
        if equation_complexity <= self._equation_block_threshold:
            return
        self._issues.append(
            Issue(
                kind="equation.cyclomatic_complexity",
                message=(
                    f"Equation block {equation_name!r} at {'.'.join(module_path)!r} "
                    f"has cyclomatic complexity {equation_complexity}, exceeding threshold {self._equation_block_threshold}."
                ),
                module_path=module_path.copy(),
                data={
                    "scope": "equation-block",
                    "equation": equation_name,
                    "complexity": equation_complexity,
                    "threshold": self._equation_block_threshold,
                    "site": f"EQ:{equation_name}",
                    "context": f"complexity {equation_complexity} > {self._equation_block_threshold}",
                },
            )
        )

    def _count_sequence_nodes(
        self,
        *,
        module_path: list[str],
        sequence_name: str,
        nodes: list[object],
    ) -> int:
        count = 0
        for node in nodes:
            if isinstance(node, SFCStep):
                step_complexity = 1 + self._count_statement_list(
                    [*(node.code.enter or []), *(node.code.active or []), *(node.code.exit or [])]
                )
                if step_complexity > self._step_threshold:
                    self._issues.append(
                        Issue(
                            kind="step.cyclomatic_complexity",
                            message=(
                                f"Step {node.name!r} in sequence {sequence_name!r} at {'.'.join(module_path)!r} "
                                f"has cyclomatic complexity {step_complexity}, exceeding threshold {self._step_threshold}."
                            ),
                            module_path=module_path.copy(),
                            data={
                                "scope": "step",
                                "sequence": sequence_name,
                                "step": node.name,
                                "complexity": step_complexity,
                                "threshold": self._step_threshold,
                                "site": f"SQ:{sequence_name} > STEP:{node.name}",
                                "context": f"complexity {step_complexity} > {self._step_threshold}",
                            },
                        )
                    )
                count += step_complexity - 1
                continue
            if isinstance(node, SFCTransition):
                count += 1 + self._count_node(node.condition)
                continue
            if isinstance(node, SFCAlternative | SFCParallel):
                count += max(0, len(node.branches or []) - 1)
                for branch in node.branches or []:
                    count += self._count_sequence_nodes(
                        module_path=module_path,
                        sequence_name=sequence_name,
                        nodes=cast(list[object], branch),
                    )
                continue
            if isinstance(node, SFCSubsequence | SFCTransitionSub):
                count += self._count_sequence_nodes(
                    module_path=module_path,
                    sequence_name=sequence_name,
                    nodes=cast(list[object], node.body or []),
                )
        return count

    def _count_statement_list(self, statements: list[object]) -> int:
        return sum(self._count_node(statement) for statement in statements)

    def _count_node(self, node: object) -> int:
        if node is None:
            return 0
        if isinstance(node, IfStmt):
            count = len(node.branches)
            for condition, body in node.branches:
                count += self._count_node(condition)
                count += self._count_statement_list(list(body))
            if node.else_block is not None:
                count += self._count_statement_list(list(node.else_block))
            return count
        if isinstance(node, TernaryOp):
            count = len(node.branches)
            for condition, then_expr in node.branches:
                count += self._count_node(condition)
                count += self._count_node(then_expr)
            count += self._count_node(node.else_expr)
            return count
        if isinstance(node, Assignment):
            return self._count_node(node.target) + self._count_node(node.value)
        if isinstance(node, FuncCallStmt):
            return self._count_node(node.call)
        if isinstance(node, FuncCall):
            return sum(self._count_node(argument) for argument in node.args)
        if isinstance(node, BoolOp):
            return max(0, len(node.operands) - 1) + sum(self._count_node(child) for child in node.operands)
        if isinstance(node, NotOp):
            return self._count_node(node.operand)
        if isinstance(node, Compare | BinOp):
            return self._count_node(node.left) + self._count_node(node.right)
        if isinstance(node, UnaryOp):
            return self._count_node(node.operand)
        if isinstance(node, VarRef):
            return 0
        if isinstance(node, list):
            return sum(self._count_node(item) for item in cast(list[object], node))
        return 0


def analyze_cyclomatic_complexity(
    base_picture: BasePicture,
    *,
    module_threshold: int | None = None,
    step_threshold: int | None = None,
    equation_block_threshold: int | None = None,
    analyzed_target_is_library: bool = False,
    config: dict[str, object] | None = None,
) -> SimpleReport:
    analyzer = CyclomaticComplexityAnalyzer(
        base_picture,
        module_threshold=module_threshold,
        step_threshold=step_threshold,
        equation_block_threshold=equation_block_threshold,
        analyzed_target_is_library=analyzed_target_is_library,
        config=config,
    )
    return SimpleReport(name=base_picture.header.name, issues=analyzer.run())
