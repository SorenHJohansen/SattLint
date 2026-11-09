"""Find module types with no consumer invocation in the loaded workspace."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef, ModuleTypeInstance

from ..models.project_graph import ProjectGraph
from ..resolution.common import dedupe_moduletype_defs, select_moduletype_def_strict
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


def analyze_moduletype_usage(
    base_picture: BasePicture,
    analysis_context: AnalysisContext | None = None,
    analyzed_target_is_library: bool = False,
) -> ModuleTypeUsageReport:
    """Count source invocations across the target and its loaded reverse consumers."""
    graph = None if analysis_context is None else analysis_context.graph
    if graph is not None and not isinstance(graph, ProjectGraph):
        raise TypeError("Module-type usage requires a loaded project graph.")
    if graph is not None and graph.missing:
        raise ValueError("Module-type usage is incomplete because dependent source could not be loaded.")
    if analysis_context is not None:
        base_picture = analysis_context.base_picture
        analyzed_target_is_library = analyzed_target_is_library or analysis_context.target_is_library

    pictures = [] if graph is None else list(graph.ast_by_name.values())
    if not any(
        picture is base_picture
        or (
            base_picture.origin_file is not None
            and (picture.origin_file or "").casefold() == base_picture.origin_file.casefold()
            and (picture.origin_lib or "").casefold() == (base_picture.origin_lib or "").casefold()
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
        index[definition.name.casefold()].append(definition)

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
            definition = select_moduletype_def_strict(
                base_picture if isinstance(scope, ModuleTypeDef) else scope,
                module.moduletype_name,
                index.get(module.moduletype_name.casefold(), []),
                current_library=scope.origin_lib,
                current_file=scope.origin_file,
                unavailable_libraries=None if graph is None else graph.unavailable_libraries,
            )
            invocation_key = (
                id(definition),
                (scope.origin_lib or "").casefold(),
                (scope.origin_file or "").casefold(),
                tuple(path[1:]),
            )
            if invocation_key not in seen:
                seen.add(invocation_key)
                invocations[id(definition)].append(_Invocation(scope.origin_file, path))

    is_target_definition = build_target_origin_filter_for_basepicture(
        base_picture, analyzed_target_is_library=analyzed_target_is_library
    )
    issues: list[Issue] = []
    for definition in definitions:
        if not is_target_definition(definition):
            continue
        uses = invocations.get(id(definition), [])
        if (
            len(uses) > 1
            or (uses and not analyzed_target_is_library)
            or (uses and (uses[0].source_file or "").casefold() != (definition.origin_file or "").casefold())
        ):
            continue
        message = (
            f"Module type '{definition.name}' is invoked only in its declaring library and is unused by the scanned programs."
            if uses
            else f"Module type '{definition.name}' has no invocations in the scanned programs or libraries."
        )
        issues.append(
            Issue(
                kind="module.unused_type",
                message=message,
                module_path=uses[0].module_path if uses else [base_picture.header.name, f"TypeDef:{definition.name}"],
                data={
                    "moduletype_name": definition.name,
                    "invocation_count": len(uses),
                    "origin_file": definition.origin_file,
                    "origin_library": definition.origin_lib,
                    "context": f"Module type {definition.name}",
                },
            )
        )
    return ModuleTypeUsageReport(base_picture.header.name, issues)


__all__ = ["ModuleTypeUsageReport", "analyze_moduletype_usage"]
