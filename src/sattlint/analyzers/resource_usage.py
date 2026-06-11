from __future__ import annotations

from dataclasses import dataclass

from sattline_parser.models.ast_model import BasePicture

from .framework import Issue, SimpleReport
from .scan_loop_resource_usage import analyze_scan_loop_resource_usage
from .shared._dependency_usage_facts import CallFact, FactRef, StatementFact, collect_statement_facts


@dataclass(frozen=True)
class _ResourceCallSpec:
    operation: str
    resource_kind: str
    handle_index: int


@dataclass(frozen=True)
class _ActiveResource:
    resource_kind: str
    handle_name: str
    call_name: str
    site: str


_RESOURCE_CALL_SPECS: dict[str, _ResourceCallSpec] = {
    "opendevice": _ResourceCallSpec(operation="acquire", resource_kind="device", handle_index=1),
    "openreadfile": _ResourceCallSpec(operation="acquire", resource_kind="file", handle_index=0),
    "openwritefile": _ResourceCallSpec(operation="acquire", resource_kind="file", handle_index=0),
    "closedevice": _ResourceCallSpec(operation="release", resource_kind="device", handle_index=0),
    "closefile": _ResourceCallSpec(operation="release", resource_kind="file", handle_index=0),
}


class ResourceUsageAnalyzer:
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
        self._reported_release_without_acquire: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_acquire_without_release: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_leaks: set[tuple[tuple[str, ...], str]] = set()

    def run(self) -> SimpleReport:
        self._issues.extend(analyze_scan_loop_resource_usage(self._base_picture).issues)
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
        active_resources: dict[tuple[str, ...], _ActiveResource] = {}
        for fact in facts:
            for call in fact.calls:
                spec = _RESOURCE_CALL_SPECS.get(call.function_name.casefold())
                if spec is None or spec.handle_index >= len(call.args):
                    continue
                handle = call.args[spec.handle_index]
                if handle is None or not self._is_locally_owned(handle, module_path):
                    continue
                if spec.operation == "acquire":
                    current = active_resources.get(handle.root_key)
                    if current is not None:
                        self._report_acquire_without_release(module_path, fact.site, handle, call, current)
                    active_resources[handle.root_key] = _ActiveResource(
                        resource_kind=spec.resource_kind,
                        handle_name=handle.display_name,
                        call_name=call.function_name,
                        site=fact.site,
                    )
                    continue

                current = active_resources.pop(handle.root_key, None)
                if current is None:
                    self._report_release_without_acquire(module_path, fact.site, handle, call)

        for resource in active_resources.values():
            self._report_leak(module_path, resource)

    def _is_locally_owned(self, handle: FactRef, module_path: tuple[str, ...]) -> bool:
        return handle.decl_module_path == module_path and not handle.is_moduleparameter

    def _report_release_without_acquire(
        self,
        module_path: tuple[str, ...],
        site: str,
        handle: FactRef,
        call: CallFact,
    ) -> None:
        dedupe_key = (module_path, site, handle.display_name.casefold())
        if dedupe_key in self._reported_release_without_acquire:
            return
        self._reported_release_without_acquire.add(dedupe_key)
        self._issues.append(
            Issue(
                kind="resource_usage.release_without_acquire",
                message=(
                    f"Resource handle {handle.display_name!r} is released via {call.function_name!r} in {site} "
                    "without a matching prior acquire in this scope."
                ),
                module_path=list(module_path),
                data={"handle": handle.display_name, "call": call.function_name, "site": site},
            )
        )

    def _report_acquire_without_release(
        self,
        module_path: tuple[str, ...],
        site: str,
        handle: FactRef,
        call: CallFact,
        current: _ActiveResource,
    ) -> None:
        dedupe_key = (module_path, site, handle.display_name.casefold())
        if dedupe_key in self._reported_acquire_without_release:
            return
        self._reported_acquire_without_release.add(dedupe_key)
        self._issues.append(
            Issue(
                kind="resource_usage.acquire_without_release",
                message=(
                    f"Resource handle {handle.display_name!r} is reacquired via {call.function_name!r} in {site} "
                    f"before the previous {current.resource_kind} acquire from {current.call_name!r} at {current.site} is released."
                ),
                module_path=list(module_path),
                data={
                    "handle": handle.display_name,
                    "call": call.function_name,
                    "site": site,
                    "previous_call": current.call_name,
                    "previous_site": current.site,
                },
            )
        )

    def _report_leak(
        self,
        module_path: tuple[str, ...],
        resource: _ActiveResource,
    ) -> None:
        dedupe_key = (module_path, resource.handle_name.casefold())
        if dedupe_key in self._reported_leaks:
            return
        self._reported_leaks.add(dedupe_key)
        self._issues.append(
            Issue(
                kind="resource_usage.leaked_resource",
                message=(
                    f"Resource handle {resource.handle_name!r} acquired via {resource.call_name!r} at {resource.site} "
                    "is never released in this scope."
                ),
                module_path=list(module_path),
                data={
                    "handle": resource.handle_name,
                    "call": resource.call_name,
                    "site": resource.site,
                    "resource_kind": resource.resource_kind,
                },
            )
        )


def analyze_resource_usage(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
) -> SimpleReport:
    return ResourceUsageAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    ).run()
