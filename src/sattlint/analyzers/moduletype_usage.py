"""Find module types that no consumer of their declaring unit can reach."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sattlint.parser_api import BasePicture, ModuleTypeDef, ModuleTypeInstance

from ..models.project_graph import ProjectGraph
from ..resolution.common import dedupe_moduletype_defs, select_moduletype_def_strict
from ..utils.casefolding import unit_equal, unit_key
from .framework import AnalysisContext, Issue, format_report_header
from .shared._walk_utils import iter_nested_modules
from .shared.target_origin import build_target_origin_filter_for_basepicture


@dataclass
class ModuleTypeUsageReport:
    name: str
    issues: list[Issue]

    def summary(self) -> str:
        lines = format_report_header("Module-type usage", self.name, status="issues" if self.issues else "ok")
        if not self.issues:
            lines.append("No unused module types found.")
        for issue in self.issues:
            lines.append(f"  - [{'.'.join(issue.module_path or [self.name])}] {issue.message}")
        return "\n".join(lines)


@dataclass(frozen=True)
class _Invocation:
    source_file: str | None
    module_path: list[str]


def _collect_definitions(
    base_picture: BasePicture,
    graph: ProjectGraph | None,
) -> tuple[list[BasePicture], list[ModuleTypeDef], dict[str, list[ModuleTypeDef]]]:
    pictures = [] if graph is None else list(graph.ast_by_name.values())
    if not any(
        picture is base_picture
        or (
            base_picture.origin_file is not None
            and unit_equal(picture.origin_file or "", base_picture.origin_file)
            and unit_equal(picture.origin_lib or "", base_picture.origin_lib or "")
        )
        for picture in pictures
    ):
        pictures.append(base_picture)
    definitions = dedupe_moduletype_defs(
        [definition for picture in [base_picture, *pictures] for definition in picture.moduletype_defs]
        + ([] if graph is None else list(graph.moduletype_defs.values()))
    )
    index: dict[str, list[ModuleTypeDef]] = defaultdict(list)
    for definition in definitions:
        index[unit_key(definition.name)].append(definition)
    return pictures, definitions, index


def _collect_invocations(
    base_picture: BasePicture,
    graph: ProjectGraph | None,
    *,
    pictures: list[BasePicture],
    definitions: list[ModuleTypeDef],
    index: dict[str, list[ModuleTypeDef]],
    target_type_names: set[str],
) -> dict[int, list[_Invocation]]:
    invocations: dict[int, list[_Invocation]] = defaultdict(list)
    seen: set[tuple[int, str, str, tuple[str, ...]]] = set()
    scopes: list[BasePicture | ModuleTypeDef] = [*pictures, *definitions]
    for scope in scopes:
        scope_path = (
            [base_picture.header.name, f"TypeDef:{scope.name}"]
            if isinstance(scope, ModuleTypeDef)
            else [scope.header.name]
        )
        for module, path in iter_nested_modules(scope.submodules, parent_path=scope_path):
            if not isinstance(module, ModuleTypeInstance):
                continue
            if graph is not None and unit_key(module.moduletype_name) not in target_type_names:
                continue
            definition = select_moduletype_def_strict(
                base_picture if isinstance(scope, ModuleTypeDef) else scope,
                module.moduletype_name,
                index.get(unit_key(module.moduletype_name), []),
                current_library=scope.origin_lib,
                current_file=scope.origin_file,
                unavailable_libraries=None if graph is None else graph.unavailable_libraries,
                library_dependencies=None if graph is None else graph.library_dependencies,
                source_dependencies=None if graph is None else graph.source_dependencies,
            )
            invocation_key = (
                id(definition),
                unit_key(scope.origin_lib or ""),
                unit_key(scope.origin_file or ""),
                tuple(path[1:]),
            )
            if invocation_key not in seen:
                seen.add(invocation_key)
                invocations[id(definition)].append(_Invocation(scope.origin_file, path))
    return invocations


def analyze_moduletype_usage(
    base_picture: BasePicture,
    analysis_context: AnalysisContext | None = None,
    analyzed_target_is_library: bool = False,
) -> ModuleTypeUsageReport:
    """Report target module types that no consumer can reach."""
    graph = None if analysis_context is None else analysis_context.graph
    if graph is not None and not isinstance(graph, ProjectGraph):
        raise TypeError("Module-type usage requires a loaded project graph.")
    if analysis_context is not None:
        base_picture = analysis_context.base_picture
        analyzed_target_is_library = analyzed_target_is_library or analysis_context.target_is_library

    if graph is not None and graph.missing:
        target_name = Path(base_picture.origin_file).stem if base_picture.origin_file else base_picture.header.name
        target_name = unit_key(target_name)
        downstream: set[str] = set()
        pending = list(graph.source_dependencies.get(target_name, set()))
        while pending:
            dependency = unit_key(pending.pop())
            if dependency == target_name or dependency in downstream:
                continue
            downstream.add(dependency)
            pending.extend(graph.source_dependencies.get(dependency, set()))
        unavailable = {unit_key(name) for name in graph.unavailable_libraries}
        if graph.failures or not unavailable or not unavailable.issubset(downstream):
            raise ValueError("Module-type usage is incomplete because consumer source could not be loaded.")

    pictures, definitions, index = _collect_definitions(base_picture, graph)

    is_target_definition = build_target_origin_filter_for_basepicture(
        base_picture, analyzed_target_is_library=analyzed_target_is_library
    )
    target_type_names = {unit_key(definition.name) for definition in definitions if is_target_definition(definition)}
    invocations = _collect_invocations(
        base_picture,
        graph,
        pictures=pictures,
        definitions=definitions,
        index=index,
        target_type_names=target_type_names,
    )
    consumer_units = _consumer_units(graph)

    issues: list[Issue] = []
    for definition in definitions:
        if not is_target_definition(definition):
            continue
        # A private definition states its own contract: file scope only. A
        # consumer outside the file can never legally invoke it, so the lack of
        # one proves nothing.
        if definition.is_private:
            continue
        uses = invocations.get(id(definition), [])
        declaring_file = definition.origin_file or ""
        # Any invocation outside the declaring unit is a real use, wherever it
        # lives. A single such use is enough; the consumer set is not guaranteed
        # to be complete, so absence of more proof is not evidence.
        if any(not unit_equal(use.source_file or "", declaring_file) for use in uses):
            continue
        # In-file use says nothing about whether the declaring unit publishes
        # the type. A library instantiating its own type proves only that the
        # library is self-consistent; its consumers decide whether the type has
        # an audience.
        if consumer_units.get(_declaring_unit_key(definition), set()):
            continue
        issues.append(_unused_type_issue(definition, uses, base_picture.header.name))
    return ModuleTypeUsageReport(base_picture.header.name, issues)


def _consumer_units(graph: ProjectGraph | None) -> dict[str, set[str]]:
    """Reverse the unit-level dependency edges into ``unit -> its consumers``."""
    consumers: dict[str, set[str]] = defaultdict(set)
    if graph is None:
        return consumers
    for source, dependencies in graph.source_dependencies.items():
        source_key = unit_key(source)
        for dependency in dependencies:
            dependency_key = unit_key(dependency)
            if dependency_key != source_key:
                consumers[dependency_key].add(source_key)
    return consumers


def _declaring_unit_key(definition: ModuleTypeDef) -> str:
    """The dependency-edge key of the unit that declares ``definition``.

    Dependency sidecars name programs, while a definition records the source
    file it came from, so the file stem is the shared identity. A definition
    without a source file has no unit identity the edges can match.
    """
    if definition.origin_file:
        return unit_key(Path(definition.origin_file).stem)
    return ""


def _declaring_unit_label(definition: ModuleTypeDef) -> str:
    if definition.origin_file:
        return definition.origin_file
    if definition.origin_lib:
        return f"library {definition.origin_lib}"
    return "an unknown declaring unit"


def _unused_type_issue(
    definition: ModuleTypeDef,
    uses: list[_Invocation],
    root_name: str,
) -> Issue:
    declaring_unit = _declaring_unit_label(definition)
    message = (
        f"Module type '{definition.name}' is invoked only in its declaring unit "
        f"'{declaring_unit}', which has no consumer in the scanned workspace."
        if uses
        else f"Module type '{definition.name}' has no invocations and its declaring unit "
        f"'{declaring_unit}' has no consumer in the scanned workspace."
    )
    return Issue(
        kind="module.unused_type",
        message=message,
        module_path=uses[0].module_path if uses else [root_name, f"TypeDef:{definition.name}"],
        data={
            "moduletype_name": definition.name,
            "invocation_count": len(uses),
            "origin_file": definition.origin_file,
            "origin_library": definition.origin_lib,
            "context": f"Module type {definition.name}",
        },
    )


__all__ = ["ModuleTypeUsageReport", "analyze_moduletype_usage"]
