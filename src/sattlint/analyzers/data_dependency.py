from __future__ import annotations

from sattline_parser.models.ast_model import BasePicture

from .framework import Issue, SimpleReport
from .shared._dependency_usage_facts import FactRef, StatementFact, collect_statement_facts


class DataDependencyAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        *,
        unavailable_libraries: set[str] | None = None,
        analyzed_target_is_library: bool = False,
    ) -> None:
        self._base_picture = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._analyzed_target_is_library = analyzed_target_is_library
        self._issues: list[Issue] = []
        self._reported_paths: set[tuple[tuple[str, ...], str, tuple[str, ...]]] = set()
        self._reported_init_hazards: set[tuple[tuple[str, ...], str, str, str]] = set()

    def run(self) -> SimpleReport:
        facts = collect_statement_facts(
            self._base_picture,
            unavailable_libraries=self._unavailable_libraries,
            analyzed_target_is_library=self._analyzed_target_is_library,
        )
        facts_by_module: dict[tuple[str, ...], list[StatementFact]] = {}
        for fact in facts:
            facts_by_module.setdefault(fact.module_path, []).append(fact)
        for module_path, module_facts in facts_by_module.items():
            self._analyze_module(module_path, module_facts)
        return SimpleReport(name=self._base_picture.header.name, issues=self._issues)

    def _analyze_module(
        self,
        module_path: tuple[str, ...],
        facts: list[StatementFact],
    ) -> None:
        initialized_roots: set[tuple[str, ...]] = set()
        paths_by_symbol: dict[tuple[str, ...], dict[tuple[str, ...], tuple[str, ...]]] = {}

        for fact in facts:
            for write in fact.writes:
                target_paths: dict[tuple[str, ...], tuple[str, ...]] = {}
                for read in fact.reads:
                    if self._is_initialization_hazard(read, module_path, initialized_roots):
                        self._report_initialization_hazard(write, read, fact)
                    prior_paths = paths_by_symbol.get(read.root_key, {})
                    if prior_paths:
                        for upstream_key, prior_path in prior_paths.items():
                            target_paths.setdefault(upstream_key, (write.display_name, *prior_path))
                    else:
                        target_paths.setdefault(read.root_key, (write.display_name, read.display_name))

                if target_paths:
                    paths_by_symbol[write.root_key] = target_paths
                    for path in target_paths.values():
                        if len(path) >= 3:
                            self._report_dependency_path(module_path, fact.site, path)
                else:
                    paths_by_symbol.pop(write.root_key, None)
                initialized_roots.add(write.root_key)

    def _is_initialization_hazard(
        self,
        read: FactRef,
        module_path: tuple[str, ...],
        initialized_roots: set[tuple[str, ...]],
    ) -> bool:
        if read.decl_module_path != module_path:
            return False
        if read.is_moduleparameter or read.has_initializer:
            return False
        return read.root_key not in initialized_roots

    def _report_dependency_path(
        self,
        module_path: tuple[str, ...],
        site: str,
        path: tuple[str, ...],
    ) -> None:
        dedupe_key = (module_path, site, tuple(segment.casefold() for segment in path))
        if dedupe_key in self._reported_paths:
            return
        self._reported_paths.add(dedupe_key)
        self._issues.append(
            Issue(
                kind="data_dependency.path",
                message=(f"Dependency path {' -> '.join(repr(segment) for segment in path)} is established in {site}."),
                module_path=list(module_path),
                data={
                    "path": list(path),
                    "site": site,
                    "target": path[0],
                    "source": path[-1],
                },
            )
        )

    def _report_initialization_hazard(
        self,
        write: FactRef,
        read: FactRef,
        fact: StatementFact,
    ) -> None:
        dedupe_key = (
            fact.module_path,
            fact.site,
            write.display_name.casefold(),
            read.display_name.casefold(),
        )
        if dedupe_key in self._reported_init_hazards:
            return
        self._reported_init_hazards.add(dedupe_key)
        self._issues.append(
            Issue(
                kind="data_dependency.initialization_order",
                message=(
                    f"Write to {write.display_name!r} depends on {read.display_name!r} before that value is "
                    f"initialized or written earlier in {fact.site}."
                ),
                module_path=list(fact.module_path),
                data={
                    "target": write.display_name,
                    "source": read.display_name,
                    "site": fact.site,
                },
            )
        )


def analyze_data_dependency(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
) -> SimpleReport:
    return DataDependencyAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    ).run()
