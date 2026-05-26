"""Dependency compatibility helpers for the engine."""

from __future__ import annotations

from pathlib import Path

from sattline_parser.models.ast_model import BasePicture

from .models.project_graph import ProjectGraph


def collect_dependency_version_conflicts(
    graph: ProjectGraph,
    bp: BasePicture,
    *,
    library_name: str,
    source_path: Path,
) -> list[str]:
    conflicts: list[str] = []
    source_label = f"{library_name}/{source_path.name}"

    existing_moduletype_versions: dict[str, set[int]] = {}
    existing_moduletype_sources: dict[tuple[str, int], set[str]] = {}
    for existing in graph.moduletype_defs.values():
        if existing.datecode is None:
            continue
        name_key = existing.name.casefold()
        existing_moduletype_versions.setdefault(name_key, set()).add(existing.datecode)
        origin_label = f"{existing.origin_lib or 'unknown'}/{existing.origin_file or '?'}"
        existing_moduletype_sources.setdefault((name_key, existing.datecode), set()).add(origin_label)

    for moduletype in bp.moduletype_defs:
        if moduletype.datecode is None:
            continue
        name_key = moduletype.name.casefold()
        known_versions = existing_moduletype_versions.get(name_key)
        if not known_versions or moduletype.datecode in known_versions:
            continue
        existing_detail = ", ".join(
            f"{version} in {', '.join(sorted(existing_moduletype_sources.get((name_key, version), {'unknown/?'})))}"
            for version in sorted(known_versions)
        )
        conflicts.append(
            f"moduletype '{moduletype.name}' datecode {moduletype.datecode} in {source_label} "
            f"conflicts with {existing_detail}"
        )

    existing_datatype_versions: dict[str, set[int]] = {}
    existing_datatype_sources: dict[tuple[str, int], set[str]] = {}
    for existing in graph.datatype_defs.values():
        if existing.datecode is None:
            continue
        name_key = existing.name.casefold()
        existing_datatype_versions.setdefault(name_key, set()).add(existing.datecode)
        origin_label = f"{existing.origin_lib or 'unknown'}/{existing.origin_file or '?'}"
        existing_datatype_sources.setdefault((name_key, existing.datecode), set()).add(origin_label)

    for datatype in bp.datatype_defs:
        if datatype.datecode is None:
            continue
        name_key = datatype.name.casefold()
        known_versions = existing_datatype_versions.get(name_key)
        if not known_versions or datatype.datecode in known_versions:
            continue
        existing_detail = ", ".join(
            f"{version} in {', '.join(sorted(existing_datatype_sources.get((name_key, version), {'unknown/?'})))}"
            for version in sorted(known_versions)
        )
        conflicts.append(
            f"datatype '{datatype.name}' datecode {datatype.datecode} in {source_label} "
            f"conflicts with {existing_detail}"
        )

    return conflicts
