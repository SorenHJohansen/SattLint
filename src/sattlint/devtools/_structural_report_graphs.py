"""Workspace graph input and report helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, cast


def _structural_entry_files(
    workspace_root: Path,
    program_files: tuple[Path, ...],
) -> tuple[Path, ...]:
    from sattlint.devtools import structural_reports as structural_reports_module

    scoped_files = tuple(
        path
        for path in program_files
        if any(
            path.resolve().is_relative_to((workspace_root / relative_root).resolve())
            for relative_root in structural_reports_module.STRUCTURAL_ENTRY_ROOTS
        )
    )
    return scoped_files or program_files


def _structural_report_discovery(workspace_root: Path, discovery: Any) -> Any:
    from sattlint.devtools import structural_reports as structural_reports_module

    selected_program_files = structural_reports_module._structural_entry_files(
        workspace_root,
        tuple(discovery.program_files),
    )
    if selected_program_files == tuple(discovery.program_files):
        return discovery
    return type(discovery)(
        workspace_root=discovery.workspace_root,
        source_dirs=discovery.source_dirs,
        program_files=selected_program_files,
        dependency_files=discovery.dependency_files,
        abb_lib_dir=discovery.abb_lib_dir,
        program_files_by_stem=discovery.program_files_by_stem,
        dependency_files_by_stem=discovery.dependency_files_by_stem,
    )


def collect_workspace_graph_inputs(workspace_root: Path) -> Any:
    from sattlint.devtools import structural_reports as structural_reports_module

    discovery = structural_reports_module.discover_workspace_sources(workspace_root)
    snapshots: list[Any] = []
    failures: list[dict[str, Any]] = []

    for entry_file in discovery.program_files:
        try:
            snapshot = structural_reports_module.load_workspace_snapshot(
                entry_file,
                workspace_root=workspace_root,
                collect_variable_diagnostics=False,
                _analysis_provider=structural_reports_module.build_variable_semantic_artifacts,
            )
        except Exception as exc:
            failures.append(
                {
                    "entry_file": structural_reports_module.sanitize_path_for_report(
                        entry_file,
                        repo_root=workspace_root,
                    ),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            continue
        snapshots.append(snapshot)

    return structural_reports_module.WorkspaceGraphInputs(
        discovery=discovery,
        snapshots=snapshots,
        snapshot_failures=failures,
    )


def _accumulate_dependency_graph_snapshot(
    snapshot: Any,
    *,
    workspace_root: Path,
    node_index: dict[str, dict[str, Any]],
    edge_index: dict[tuple[str, str], dict[str, Any]],
) -> None:
    from sattlint.devtools import structural_reports as structural_reports_module

    entry_file = structural_reports_module.sanitize_path_for_report(snapshot.entry_file, repo_root=workspace_root)
    for source, targets in sorted(snapshot.project_graph.library_dependencies.items()):
        node_index.setdefault(source, {"id": source, "kind": "library"})
        for target in sorted(targets):
            node_index.setdefault(target, {"id": target, "kind": "library"})
            key = (source.casefold(), target.casefold())
            edge = edge_index.setdefault(
                key,
                {
                    "source": source,
                    "target": target,
                    "kind": "depends_on",
                    "entries": set(),
                },
            )
            edge["entries"].add(entry_file)


def _iter_snapshot_accesses_by_definition(
    snapshot: Any,
) -> Iterator[tuple[Any, tuple[Any, ...] | list[Any]]]:
    iterator = getattr(snapshot, "iter_access_events_by_definition", None)
    if callable(iterator):
        iterable = cast(Iterable[tuple[Any, tuple[Any, ...] | list[Any]]], iterator(roots_only=True))
        yield from iterable
        return

    for definition in snapshot.definitions:
        if definition.field_path is not None:
            continue
        yield definition, snapshot.find_accesses_to(definition)


def _accumulate_call_graph_snapshot(
    snapshot: Any,
    *,
    workspace_root: Path,
    node_index: dict[str, dict[str, Any]],
    edge_index: dict[tuple[str, str], dict[str, Any]],
) -> None:
    from sattlint.devtools import structural_reports as structural_reports_module

    entry_file = structural_reports_module.sanitize_path_for_report(snapshot.entry_file, repo_root=workspace_root)
    root_module = getattr(snapshot.base_picture, "name", snapshot.entry_file.stem)
    for definition, accesses in structural_reports_module._iter_snapshot_accesses_by_definition(snapshot):
        target_path = definition.declaration_module_path or (root_module,)
        target_module = ".".join(target_path)
        node_index.setdefault(target_module.casefold(), {"id": target_module, "kind": "module"})

        for access in accesses:
            source_path = access.use_module_path or (root_module,)
            source_module = ".".join(source_path)
            node_index.setdefault(source_module.casefold(), {"id": source_module, "kind": "module"})

            key = (source_module.casefold(), target_module.casefold())
            edge = edge_index.setdefault(
                key,
                {
                    "source": source_module,
                    "target": target_module,
                    "kind": "module-access",
                    "reads": 0,
                    "writes": 0,
                    "symbols": set(),
                    "entries": set(),
                },
            )
            access_kind = getattr(access.kind, "value", access.kind)
            if access_kind == "read":
                edge["reads"] += 1
            elif access_kind == "write":
                edge["writes"] += 1
            edge["symbols"].add(definition.canonical_path)
            edge["entries"].add(entry_file)


def _build_dependency_graph_report(
    *,
    workspace_root: Path,
    discovery: Any,
    node_index: dict[str, dict[str, Any]],
    edge_index: dict[tuple[str, str], dict[str, Any]],
    snapshot_count: int,
    snapshot_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module

    edges = [
        {
            "source": edge["source"],
            "target": edge["target"],
            "kind": edge["kind"],
            "entries": sorted(edge["entries"]),
        }
        for edge in sorted(
            edge_index.values(),
            key=lambda item: (item["source"].casefold(), item["target"].casefold()),
        )
    ]

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "workspace_root": structural_reports_module.sanitize_path_for_report(
            workspace_root,
            repo_root=workspace_root,
        ),
        "source_files": {
            "program_files": [
                structural_reports_module.sanitize_path_for_report(path, repo_root=workspace_root)
                for path in discovery.program_files
            ],
            "dependency_files": [
                structural_reports_module.sanitize_path_for_report(path, repo_root=workspace_root)
                for path in discovery.dependency_files
            ],
        },
        "nodes": sorted(node_index.values(), key=lambda item: item["id"].casefold()),
        "edges": edges,
        "snapshot_count": snapshot_count,
        "snapshot_failures": snapshot_failures,
    }


def _build_call_graph_report(
    *,
    workspace_root: Path,
    node_index: dict[str, dict[str, Any]],
    edge_index: dict[tuple[str, str], dict[str, Any]],
    snapshot_count: int,
    snapshot_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module

    edges = [
        {
            "source": edge["source"],
            "target": edge["target"],
            "kind": edge["kind"],
            "reads": edge["reads"],
            "writes": edge["writes"],
            "access_count": edge["reads"] + edge["writes"],
            "symbol_count": len(edge["symbols"]),
            "symbols": sorted(edge["symbols"]),
            "entries": sorted(edge["entries"]),
        }
        for edge in sorted(
            edge_index.values(),
            key=lambda item: (item["source"].casefold(), item["target"].casefold()),
        )
    ]

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "workspace_root": structural_reports_module.sanitize_path_for_report(
            workspace_root,
            repo_root=workspace_root,
        ),
        "graph_kind": "module-access",
        "nodes": sorted(node_index.values(), key=lambda item: item["id"].casefold()),
        "edges": edges,
        "snapshot_count": snapshot_count,
        "snapshot_failures": snapshot_failures,
    }


def _should_emit_snapshot_progress(index: int, total: int) -> bool:
    if total <= 10:
        return True
    if index in {1, total}:
        return True
    return index % 10 == 0


def _stream_workspace_graph_reports(
    workspace_root: Path,
    *,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    from sattlint.devtools import structural_reports as structural_reports_module

    full_discovery = structural_reports_module.discover_workspace_sources(workspace_root)
    discovery = structural_reports_module._structural_report_discovery(workspace_root, full_discovery)
    snapshot_failures: list[dict[str, Any]] = []
    dependency_node_index: dict[str, dict[str, Any]] = {}
    dependency_edge_index: dict[tuple[str, str], dict[str, Any]] = {}
    call_node_index: dict[str, dict[str, Any]] = {}
    call_edge_index: dict[tuple[str, str], dict[str, Any]] = {}
    total_program_files = len(discovery.program_files)
    snapshot_count = 0

    for index, entry_file in enumerate(discovery.program_files, start=1):
        sanitized_entry = structural_reports_module.sanitize_path_for_report(entry_file, repo_root=workspace_root)
        sanitized_entry = sanitized_entry or entry_file.name
        if progress_callback is not None and structural_reports_module._should_emit_snapshot_progress(
            index,
            total_program_files,
        ):
            progress_callback(f"Structural: loading {index}/{total_program_files} {sanitized_entry}")
        try:
            snapshot = structural_reports_module.load_workspace_snapshot(
                entry_file,
                workspace_root=workspace_root,
                discovery=full_discovery,
                collect_variable_diagnostics=False,
                _analysis_provider=structural_reports_module.build_variable_semantic_artifacts,
            )
        except Exception as exc:
            snapshot_failures.append(
                {
                    "entry_file": sanitized_entry,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            if progress_callback is not None:
                progress_callback(
                    f"Structural: failed {index}/{total_program_files} {sanitized_entry} ({type(exc).__name__})"
                )
            continue

        snapshot_count += 1
        structural_reports_module._accumulate_dependency_graph_snapshot(
            snapshot,
            workspace_root=workspace_root,
            node_index=dependency_node_index,
            edge_index=dependency_edge_index,
        )
        structural_reports_module._accumulate_call_graph_snapshot(
            snapshot,
            workspace_root=workspace_root,
            node_index=call_node_index,
            edge_index=call_edge_index,
        )

    graph_inputs = structural_reports_module.WorkspaceGraphInputs(
        discovery=discovery,
        snapshots=[],
        snapshot_failures=snapshot_failures,
    )
    dependency_graph_report = structural_reports_module._build_dependency_graph_report(
        workspace_root=workspace_root,
        discovery=discovery,
        node_index=dependency_node_index,
        edge_index=dependency_edge_index,
        snapshot_count=snapshot_count,
        snapshot_failures=snapshot_failures,
    )
    call_graph_report = structural_reports_module._build_call_graph_report(
        workspace_root=workspace_root,
        node_index=call_node_index,
        edge_index=call_edge_index,
        snapshot_count=snapshot_count,
        snapshot_failures=snapshot_failures,
    )
    return graph_inputs, dependency_graph_report, call_graph_report


def collect_dependency_graph_report(
    workspace_root: Path,
    *,
    graph_inputs: Any = None,
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module

    resolved_inputs = structural_reports_module._normalize_graph_inputs(graph_inputs, workspace_root=workspace_root)

    node_index: dict[str, dict[str, Any]] = {}
    edge_index: dict[tuple[str, str], dict[str, Any]] = {}

    for snapshot in resolved_inputs.snapshots:
        structural_reports_module._accumulate_dependency_graph_snapshot(
            snapshot,
            workspace_root=workspace_root,
            node_index=node_index,
            edge_index=edge_index,
        )

    return structural_reports_module._build_dependency_graph_report(
        workspace_root=workspace_root,
        discovery=resolved_inputs.discovery,
        node_index=node_index,
        edge_index=edge_index,
        snapshot_count=len(resolved_inputs.snapshots),
        snapshot_failures=resolved_inputs.snapshot_failures,
    )


def collect_call_graph_report(
    workspace_root: Path,
    *,
    graph_inputs: Any = None,
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module

    resolved_inputs = structural_reports_module._normalize_graph_inputs(graph_inputs, workspace_root=workspace_root)

    node_index: dict[str, dict[str, Any]] = {}
    edge_index: dict[tuple[str, str], dict[str, Any]] = {}

    for snapshot in resolved_inputs.snapshots:
        structural_reports_module._accumulate_call_graph_snapshot(
            snapshot,
            workspace_root=workspace_root,
            node_index=node_index,
            edge_index=edge_index,
        )

    return structural_reports_module._build_call_graph_report(
        workspace_root=workspace_root,
        node_index=node_index,
        edge_index=edge_index,
        snapshot_count=len(resolved_inputs.snapshots),
        snapshot_failures=resolved_inputs.snapshot_failures,
    )


__all__ = [
    "_accumulate_call_graph_snapshot",
    "_accumulate_dependency_graph_snapshot",
    "_build_call_graph_report",
    "_build_dependency_graph_report",
    "_iter_snapshot_accesses_by_definition",
    "_should_emit_snapshot_progress",
    "_stream_workspace_graph_reports",
    "_structural_entry_files",
    "_structural_report_discovery",
    "collect_call_graph_report",
    "collect_dependency_graph_report",
    "collect_workspace_graph_inputs",
]
