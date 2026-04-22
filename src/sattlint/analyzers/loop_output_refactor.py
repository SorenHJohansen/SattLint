from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    SFCTransitionSub,
    SingleModule,
)

from .. import constants as const
from ..core.ast_tools import iter_variable_refs
from .framework import Issue, SimpleReport


@dataclass(frozen=True)
class _ExecutionBlock:
    block_id: int
    module_path: tuple[str, ...]
    label: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]


class LoopOutputRefactorAnalyzer:
    def __init__(self, base_picture: BasePicture) -> None:
        self.bp = base_picture
        self._issues: list[Issue] = []
        self._next_block_id = 0

    def run(self) -> SimpleReport:
        root_path = [self.bp.header.name]
        self._scan_modulecode(root_path, self.bp.modulecode)
        for moduletype in self.bp.moduletype_defs or []:
            self._scan_moduletype(moduletype, root_path)
        self._scan_modules(self.bp.submodules or [], root_path)
        return SimpleReport(name=self.bp.header.name, issues=self._issues)

    def _scan_moduletype(self, moduletype: ModuleTypeDef, parent_path: list[str]) -> None:
        module_path = [*parent_path, moduletype.name]
        self._scan_modulecode(module_path, moduletype.modulecode)
        self._scan_modules(moduletype.submodules or [], module_path)

    def _scan_modules(
        self,
        modules: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_path: list[str],
    ) -> None:
        for module in modules:
            if isinstance(module, ModuleTypeInstance):
                continue
            module_path = [*parent_path, module.header.name]
            self._scan_modulecode(module_path, module.modulecode)
            self._scan_modules(module.submodules or [], module_path)

    def _scan_modulecode(self, module_path: list[str], modulecode: ModuleCode | None) -> None:
        if modulecode is None:
            return
        blocks = self._collect_execution_blocks(module_path, modulecode)
        if len(blocks) < 2:
            return

        adjacency: dict[int, set[int]] = {block.block_id: set() for block in blocks}
        edge_variables: dict[tuple[int, int], tuple[str, ...]] = {}
        for source in blocks:
            source_writes = set(source.writes)
            if not source_writes:
                continue
            for target in blocks:
                if source.block_id == target.block_id:
                    continue
                shared_variables = tuple(sorted(source_writes & set(target.reads)))
                if not shared_variables:
                    continue
                adjacency[source.block_id].add(target.block_id)
                edge_variables[(source.block_id, target.block_id)] = shared_variables

        block_by_id = {block.block_id: block for block in blocks}
        for component in self._strongly_connected_components(adjacency):
            if len(component) < 2:
                continue
            cycle_blocks = sorted(
                (block_by_id[block_id] for block_id in component),
                key=lambda block: block.block_id,
            )
            dependencies = [
                {
                    "from": block_by_id[source].label,
                    "to": block_by_id[target].label,
                    "variables": list(edge_variables[(source, target)]),
                }
                for source in component
                for target in adjacency[source]
                if target in component and (source, target) in edge_variables
            ]
            dependencies.sort(key=lambda item: (item["from"], item["to"]))
            dependency_variables = sorted(
                {
                    variable
                    for dependency in dependencies
                    for variable in dependency["variables"]
                }
            )
            block_labels = [block.label for block in cycle_blocks]
            loop_text = self._format_loop_text(cycle_blocks, dependencies)
            self._issues.append(
                Issue(
                    kind="sorting.loop_output_refactor",
                    message=(
                        f"Dependency loop across sorted blocks in {'.'.join(module_path)!r}: "
                        f"{', '.join(block_labels)}."
                    ),
                    module_path=module_path.copy(),
                    data={
                        "blocks": block_labels,
                        "dependencies": dependencies,
                        "dependency_variables": dependency_variables,
                        "loop_text": loop_text,
                    },
                )
            )

    def _collect_execution_blocks(self, module_path: list[str], modulecode: ModuleCode) -> list[_ExecutionBlock]:
        blocks: list[_ExecutionBlock] = []
        for equation in modulecode.equations or []:
            blocks.append(
                self._make_block(
                    module_path,
                    f"EquationBlock {equation.name!r}",
                    equation.code or [],
                )
            )
        for sequence in modulecode.sequences or []:
            self._collect_sequence_blocks(module_path, sequence.name, sequence.code or [], blocks)
        return blocks

    def _collect_sequence_blocks(
        self,
        module_path: list[str],
        sequence_name: str,
        nodes: list[object],
        blocks: list[_ExecutionBlock],
    ) -> None:
        for node in nodes:
            if isinstance(node, SFCStep):
                if node.code.enter:
                    blocks.append(
                        self._make_block(
                            module_path,
                            f"Sequence {sequence_name!r} step {node.name!r} ENTER",
                            node.code.enter,
                        )
                    )
                if node.code.active:
                    blocks.append(
                        self._make_block(
                            module_path,
                            f"Sequence {sequence_name!r} step {node.name!r} ACTIVE",
                            node.code.active,
                        )
                    )
                if node.code.exit:
                    blocks.append(
                        self._make_block(
                            module_path,
                            f"Sequence {sequence_name!r} step {node.name!r} EXIT",
                            node.code.exit,
                        )
                    )
                continue
            if isinstance(node, (SFCAlternative, SFCParallel)):
                for branch in node.branches or []:
                    self._collect_sequence_blocks(module_path, sequence_name, branch, blocks)
                continue
            if isinstance(node, (SFCSubsequence, SFCTransitionSub)):
                self._collect_sequence_blocks(module_path, sequence_name, node.body or [], blocks)

    def _make_block(
        self,
        module_path: list[str],
        label: str,
        statements: list[object],
    ) -> _ExecutionBlock:
        reads: set[str] = set()
        writes: set[str] = set()
        for statement in statements:
            self._collect_statement_io(statement, reads, writes)
        block = _ExecutionBlock(
            block_id=self._next_block_id,
            module_path=tuple(module_path),
            label=label,
            reads=tuple(sorted(reads)),
            writes=tuple(sorted(writes)),
        )
        self._next_block_id += 1
        return block

    def _collect_statement_io(self, node: object, reads: set[str], writes: set[str]) -> None:
        if hasattr(node, "data") and getattr(node, "data", None) == const.KEY_STATEMENT:
            for child in getattr(node, "children", []):
                self._collect_statement_io(child, reads, writes)
            return

        if isinstance(node, tuple) and node:
            tag = node[0]
            if tag == const.KEY_ASSIGN and len(node) >= 3:
                _assign, target, expr = node[:3]
                self._collect_target_writes(target, writes)
                self._collect_expression_reads(expr, reads)
                return
            if tag == const.GRAMMAR_VALUE_IF and len(node) == 3:
                _if_tag, branches, else_block = node
                for condition, branch_statements in branches or []:
                    self._collect_expression_reads(condition, reads)
                    for statement in branch_statements or []:
                        self._collect_statement_io(statement, reads, writes)
                for statement in else_block or []:
                    self._collect_statement_io(statement, reads, writes)
                return

        self._collect_expression_reads(node, reads)

    def _collect_expression_reads(self, node: object, reads: set[str]) -> None:
        for ref in iter_variable_refs(node, key_name=const.KEY_VAR_NAME):
            name = ref.get(const.KEY_VAR_NAME)
            key = _root_variable_key(name)
            if key is not None:
                reads.add(key)

    def _collect_target_writes(self, target: object, writes: set[str]) -> None:
        for ref in iter_variable_refs(target, key_name=const.KEY_VAR_NAME):
            name = ref.get(const.KEY_VAR_NAME)
            key = _root_variable_key(name)
            if key is not None:
                writes.add(key)

    def _strongly_connected_components(self, adjacency: dict[int, set[int]]) -> list[set[int]]:
        index = 0
        indices: dict[int, int] = {}
        lowlinks: dict[int, int] = {}
        stack: list[int] = []
        on_stack: set[int] = set()
        components: list[set[int]] = []

        def visit(node_id: int) -> None:
            nonlocal index
            indices[node_id] = index
            lowlinks[node_id] = index
            index += 1
            stack.append(node_id)
            on_stack.add(node_id)

            for neighbor in adjacency.get(node_id, set()):
                if neighbor not in indices:
                    visit(neighbor)
                    lowlinks[node_id] = min(lowlinks[node_id], lowlinks[neighbor])
                elif neighbor in on_stack:
                    lowlinks[node_id] = min(lowlinks[node_id], indices[neighbor])

            if lowlinks[node_id] != indices[node_id]:
                return

            component: set[int] = set()
            while stack:
                current = stack.pop()
                on_stack.remove(current)
                component.add(current)
                if current == node_id:
                    break
            components.append(component)

        for node_id in adjacency:
            if node_id not in indices:
                visit(node_id)

        return components

    def _format_loop_text(
        self,
        blocks: list[_ExecutionBlock],
        dependencies: list[dict[str, Any]],
    ) -> str:
        lines = ["Loop blocks in encounter order:"]
        for block in blocks:
            read_text = ", ".join(block.reads) if block.reads else "-"
            write_text = ", ".join(block.writes) if block.writes else "-"
            lines.append(f"- {block.label}: reads {read_text}; writes {write_text}")
        lines.append("Internal dependencies:")
        for dependency in dependencies:
            via = ", ".join(dependency["variables"]) if dependency["variables"] else "<unknown>"
            lines.append(f"- {dependency['from']} -> {dependency['to']} via {via}")
        lines.append(
            "At least one dependency in this cycle is delayed by one scan until the participating blocks are reordered or refactored."
        )
        return "\n".join(lines)


def _root_variable_key(raw_name: object) -> str | None:
    if not isinstance(raw_name, str):
        return None
    name = raw_name.split(".", 1)[0].strip()
    if not name:
        return None
    return name.casefold()


def analyze_loop_output_refactor(base_picture: BasePicture) -> SimpleReport:
    return LoopOutputRefactorAnalyzer(base_picture).run()
