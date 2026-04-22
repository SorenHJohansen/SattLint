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
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
)
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
            if isinstance(node, (SFCAlternative, SFCParallel)):
                count += max(0, len(node.branches or []) - 1)
                for branch in node.branches or []:
                    count += self._count_sequence_nodes(
                        module_path=module_path,
                        sequence_name=sequence_name,
                        nodes=branch,
                    )
                continue
            if isinstance(node, (SFCSubsequence, SFCTransitionSub)):
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
        if isinstance(node, tuple) and node:
            tag = node[0]
            if tag == const.GRAMMAR_VALUE_IF:
                _if_tag, branches, else_block = node
                count = len(branches or [])
                for condition, branch_statements in branches or []:
                    count += self._count_node(condition)
                    count += self._count_statement_list(branch_statements or [])
                count += self._count_statement_list(else_block or [])
                return count
            if tag == const.KEY_TERNARY:
                _ternary_tag, branches, else_expr = node
                count = len(branches or [])
                for condition, then_expr in branches or []:
                    count += self._count_node(condition)
                    count += self._count_node(then_expr)
                count += self._count_node(else_expr)
                return count
            if tag == const.KEY_ASSIGN:
                _assign_tag, target, expr = node
                return self._count_node(target) + self._count_node(expr)
            if tag == const.KEY_FUNCTION_CALL:
                _call_tag, _function_name, args = node
                return sum(self._count_node(argument) for argument in args or [])
            if tag in (const.KEY_COMPARE, const.KEY_ADD, const.KEY_MUL):
                return sum(self._count_node(child) for child in node[1:])
            if tag in (const.KEY_PLUS, const.KEY_MINUS, const.GRAMMAR_VALUE_NOT):
                return self._count_node(node[1])
            if tag in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
                children = node[1] or []
                return max(0, len(children) - 1) + sum(
                    self._count_node(child) for child in children
                )
            return sum(self._count_node(child) for child in node[1:])
        if isinstance(node, list):
            return sum(self._count_node(item) for item in node)
        if hasattr(node, "children"):
            return sum(self._count_node(child) for child in getattr(node, "children", []))
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
