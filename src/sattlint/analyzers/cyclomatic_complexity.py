from __future__ import annotations

from typing import cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
)

from ..grammar import constants as const
from .framework import Issue, SimpleReport

DEFAULT_MODULE_COMPLEXITY_THRESHOLD = 10
DEFAULT_STEP_COMPLEXITY_THRESHOLD = 6


class CyclomaticComplexityAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        *,
        module_threshold: int = DEFAULT_MODULE_COMPLEXITY_THRESHOLD,
        step_threshold: int = DEFAULT_STEP_COMPLEXITY_THRESHOLD,
    ) -> None:
        self.bp = base_picture
        self._module_threshold = module_threshold
        self._step_threshold = step_threshold
        self._issues: list[Issue] = []

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]
        self._record_scope_complexity_issue(
            module_path=root_path,
            scope_kind="program",
            modulecode=self.bp.modulecode,
        )
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
        for module in modules:
            if isinstance(module, ModuleTypeInstance):
                continue
            module_path = [*parent_path, module.header.name]
            self._record_scope_complexity_issue(
                module_path=module_path,
                scope_kind="module",
                modulecode=module.modulecode,
            )
            self._walk_modules(module.submodules or [], parent_path=module_path)

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
                },
            )
        )

    def _modulecode_complexity(
        self,
        module_path: list[str],
        modulecode: ModuleCode,
    ) -> int:
        complexity = 1
        for equation in modulecode.equations or []:
            complexity += self._count_statement_list(equation.code or [])
        for sequence in modulecode.sequences or []:
            complexity += self._count_sequence_nodes(
                module_path=module_path,
                sequence_name=sequence.name,
                nodes=sequence.code or [],
            )
        return complexity

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
                        nodes=branch,
                    )
                continue
            if isinstance(node, SFCSubsequence | SFCTransitionSub):
                count += self._count_sequence_nodes(
                    module_path=module_path,
                    sequence_name=sequence_name,
                    nodes=node.body or [],
                )
        return count

    def _count_statement_list(self, statements: list[object]) -> int:
        return sum(self._count_node(statement) for statement in statements)

    def _count_node(self, node: object) -> int:
        if node is None:
            return 0
        if isinstance(node, tuple):
            items = cast(tuple[object, ...], node)
            if not items:
                return 0
            tag = items[0]
            if tag == const.GRAMMAR_VALUE_IF and len(items) == 3:
                raw_branches = items[1]
                else_block = items[2]
                if_branches: list[tuple[object, list[object]]] = []
                if isinstance(raw_branches, list):
                    for branch in cast(list[object], raw_branches):
                        if not isinstance(branch, tuple):
                            continue
                        branch_items = cast(tuple[object, ...], branch)
                        if len(branch_items) != 2 or not isinstance(branch_items[1], list):
                            continue
                        if_branches.append((branch_items[0], cast(list[object], branch_items[1])))
                count = len(if_branches)
                for condition, branch_statements in if_branches:
                    count += self._count_node(condition)
                    count += self._count_statement_list(branch_statements)
                if isinstance(else_block, list):
                    count += self._count_statement_list(cast(list[object], else_block))
                return count
            if tag == const.KEY_TERNARY and len(items) == 3:
                raw_branches = items[1]
                else_expr = items[2]
                ternary_branches: list[tuple[object, object]] = []
                if isinstance(raw_branches, list):
                    for branch in cast(list[object], raw_branches):
                        if not isinstance(branch, tuple):
                            continue
                        branch_items = cast(tuple[object, ...], branch)
                        if len(branch_items) != 2:
                            continue
                        ternary_branches.append((branch_items[0], branch_items[1]))
                count = len(ternary_branches)
                for condition, then_expr in ternary_branches:
                    count += self._count_node(condition)
                    count += self._count_node(then_expr)
                count += self._count_node(else_expr)
                return count
            if tag == const.KEY_ASSIGN and len(items) == 3:
                target = items[1]
                expr = items[2]
                return self._count_node(target) + self._count_node(expr)
            if tag == const.KEY_FUNCTION_CALL and len(items) == 3:
                raw_args = items[2]
                if isinstance(raw_args, list):
                    return sum(self._count_node(argument) for argument in cast(list[object], raw_args))
                if isinstance(raw_args, tuple):
                    return sum(self._count_node(argument) for argument in cast(tuple[object, ...], raw_args))
                return 0
            if tag in (const.KEY_COMPARE, const.KEY_ADD, const.KEY_MUL):
                return sum(self._count_node(child) for child in items[1:])
            if tag in (const.KEY_PLUS, const.KEY_MINUS, const.GRAMMAR_VALUE_NOT):
                return self._count_node(items[1]) if len(items) > 1 else 0
            if tag in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND) and len(items) > 1:
                raw_children = items[1]
                children: list[object] = []
                if isinstance(raw_children, list):
                    children = cast(list[object], raw_children)
                elif isinstance(raw_children, tuple):
                    children = list(cast(tuple[object, ...], raw_children))
                return max(0, len(children) - 1) + sum(self._count_node(child) for child in children)
            return sum(self._count_node(child) for child in items[1:])
        if isinstance(node, list):
            return sum(self._count_node(item) for item in cast(list[object], node))
        raw_children = getattr(node, "children", None)
        if isinstance(raw_children, list):
            child_nodes = cast(list[object], raw_children)
            return sum(self._count_node(child) for child in child_nodes)
        if isinstance(raw_children, tuple):
            child_nodes = cast(tuple[object, ...], raw_children)
            return sum(self._count_node(child) for child in child_nodes)
        return 0


def analyze_cyclomatic_complexity(
    base_picture: BasePicture,
    *,
    module_threshold: int = DEFAULT_MODULE_COMPLEXITY_THRESHOLD,
    step_threshold: int = DEFAULT_STEP_COMPLEXITY_THRESHOLD,
) -> SimpleReport:
    analyzer = CyclomaticComplexityAnalyzer(
        base_picture,
        module_threshold=module_threshold,
        step_threshold=step_threshold,
    )
    return SimpleReport(name=base_picture.header.name, issues=analyzer.run())
