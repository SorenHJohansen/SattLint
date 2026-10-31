"""Temporary parity snapshot for the parser switchover.

This is a development helper, not shipped package code. It loads one real
project through the current SattLint stack and serialises the observable state
so the same snapshot can be taken after the parser switchover and diffed.

Usage::

    python scripts/parity_snapshot.py --target KaHAApplSupportLib --out /tmp/before.json

The snapshot covers every loaded program's name, origin, library, dependency
list, moduletype and datatype definitions, graphics model, plus the project's
library edges, validation warnings, and load failures.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import cast

from sattline_parser.models.ast_model import BasePicture

from sattlint.application.project import load_project
from sattlint.config import get_config_path, load_config
from sattlint.models.project_graph import ProjectGraph
from sattlint.project.parser_adapter import read_dependency_names


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in cast("dict[object, object]", value).items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_jsonable(item) for item in cast("list[object]", list(value))]
    return repr(value)


def _source_for(graph: ProjectGraph, name: str) -> Path | None:
    matches = sorted(path for path in graph.source_files if path.stem.casefold() == name.casefold())
    return matches[0] if matches else None


def _dependencies(source: Path | None) -> list[str]:
    if source is None:
        return []
    for extension in (".l", ".z"):
        candidate = source.with_suffix(extension)
        if candidate.exists():
            return list(read_dependency_names(candidate))
    return []


def _graphics(bp: BasePicture) -> dict[str, object]:
    return {
        "file": bp.graphics_file,
        "bindings": [_jsonable(binding) for binding in bp.graphics_bindings],
        "messages": [_jsonable(message) for message in bp.graphics_messages],
        "composite_records": [_jsonable(record) for record in bp.graphics_composite_records],
        "picture_display_records": [_jsonable(record) for record in bp.graphics_picture_display_records],
    }


def _program(graph: ProjectGraph, name: str, bp: BasePicture) -> dict[str, object]:
    source = _source_for(graph, name)
    return {
        "name": name,
        "header": bp.header.name,
        "origin_file": bp.origin_file,
        "origin_lib": bp.origin_lib,
        "source": str(source) if source is not None else None,
        "dependencies": _dependencies(source),
        "moduletypes": [
            {
                "name": moduletype.name,
                "datecode": moduletype.datecode,
                "origin_file": moduletype.origin_file,
                "origin_lib": moduletype.origin_lib,
            }
            for moduletype in bp.moduletype_defs
        ],
        "datatypes": [
            {
                "name": datatype.name,
                "datecode": datatype.datecode,
                "origin_file": datatype.origin_file,
                "origin_lib": datatype.origin_lib,
            }
            for datatype in bp.datatype_defs
        ],
        "graphics": _graphics(bp),
    }


def snapshot(target: str) -> dict[str, object]:
    cfg, _created = load_config(get_config_path())
    root_bp, graph = load_project(cfg, target, use_cache=False)
    return {
        "target": target,
        "root": {
            "header": root_bp.header.name,
            "origin_file": root_bp.origin_file,
            "origin_lib": root_bp.origin_lib,
            "library": graph.root_library_name_for_basepicture(root_bp),
        },
        "programs": [_program(graph, name, bp) for name, bp in sorted(graph.ast_by_name.items())],
        "library_dependencies": {
            library: sorted(dependencies) for library, dependencies in sorted(graph.library_dependencies.items())
        },
        "warnings": list(graph.warnings),
        "warning_notices": [
            {"program": program, "notice": _jsonable(notice)} for program, notice in graph.warning_notices
        ],
        "failures": {name: _jsonable(failure) for name, failure in sorted(graph.failures.items())},
        "missing": sorted(graph.missing),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", help="configured target to load (default: first target)")
    parser.add_argument("--out", type=Path, default=Path("parity-snapshot.json"))
    args = parser.parse_args(argv)

    cfg, _created = load_config(get_config_path())
    target = args.target or cast("list[str]", cfg["analyzed_programs_and_libraries"])[0]
    document = snapshot(target)
    args.out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(cast('list[object]', document['programs']))} programs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
