"""Fast structural parity snapshot for the parser switchover.

Development helper, not shipped. Loads one real project with validation off and
serialises the structure that does not depend on rule findings: programs,
libraries, origins, dependencies, definitions, cycles, and graphics. Use
``parity_snapshot.py`` when the full validation snapshot is affordable.

Usage::

    python scripts/parity_structure.py --target KaHAApplSupportLib --out /tmp/before-structure.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any, cast

from sattline_parser.project import LoadMode, LoadValidation, SattLineProject

from sattlint.config import get_config_path, load_config


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


def _roots(cfg: dict[str, Any]) -> list[Path]:
    roots = [Path(str(cfg["program_dir"]))]
    roots.extend(Path(str(path)) for path in cast("list[object]", cfg.get("other_lib_dirs", [])))
    abb = cfg.get("ABB_lib_dir")
    if abb:
        roots.append(Path(str(abb)))
    return roots


def _graphics(program: object) -> dict[str, object]:
    model = getattr(program, "graphics", None)
    if model is None:
        return {"file": None, "bindings": [], "messages": [], "composite_records": [], "picture_display_records": []}
    source_path = getattr(program, "source_path", None)
    format_info = getattr(program, "format", None)
    graphics_ext = getattr(format_info, "graphics_ext", None)
    graphics_file = (
        str(source_path.with_suffix(str(graphics_ext))) if isinstance(source_path, Path) and graphics_ext else None
    )
    return {
        "file": graphics_file,
        "bindings": [_jsonable(item) for item in getattr(model, "bindings", ())],
        "messages": [_jsonable(item) for item in getattr(model, "messages", ())],
        "composite_records": [_jsonable(item) for item in getattr(model, "composite_records", ())],
        "picture_display_records": [_jsonable(item) for item in getattr(model, "picture_display_records", ())],
    }


def _program(program: object) -> dict[str, object]:
    code = program.code
    source_path = getattr(program, "source_path", None)
    resolved_base = getattr(program, "resolved_base", None)
    return {
        "name": program.name,
        "header": code.header.name,
        "origin_file": code.origin_file,
        "origin_lib": code.origin_lib,
        "library": getattr(program, "library", None),
        "resolved_base": str(resolved_base) if isinstance(resolved_base, Path) else None,
        "source": str(source_path) if isinstance(source_path, Path) else None,
        "dependencies": list(getattr(program, "dependencies", ())),
        "moduletypes": [
            {
                "name": moduletype.name,
                "datecode": moduletype.datecode,
                "origin_file": moduletype.origin_file,
                "origin_lib": moduletype.origin_lib,
            }
            for moduletype in code.moduletype_defs
        ],
        "datatypes": [
            {
                "name": datatype.name,
                "datecode": datatype.datecode,
                "origin_file": datatype.origin_file,
                "origin_lib": datatype.origin_lib,
            }
            for datatype in code.datatype_defs
        ],
        "graphics": _graphics(program),
    }


def snapshot(target: str) -> dict[str, object]:
    cfg, _created = load_config(get_config_path())
    mode = LoadMode(str(cfg.get("mode", "draft")))
    project = SattLineProject.load(
        _roots(cast("dict[str, Any]", cfg)),
        mode,
        (target,),
        strict=False,
        validate=LoadValidation.NONE,
    )
    programs = [_program(program) for _, program in sorted(project.programs().items())]
    return {
        "target": target,
        "programs": programs,
        "libraries": list(project.libraries()),
        "cycles": [list(cycle) for cycle in project.cycles()],
        "diagnostics": [
            {
                "kind": diagnostic.kind.value,
                "program": diagnostic.program,
                "detail": diagnostic.detail,
                "path": None if diagnostic.path is None else str(diagnostic.path),
            }
            for diagnostic in project.diagnostics()
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", help="configured target to load (default: first target)")
    parser.add_argument("--out", type=Path, default=Path("parity-structure.json"))
    args = parser.parse_args(argv)

    cfg, _created = load_config(get_config_path())
    target = args.target or cast("list[str]", cfg["analyzed_programs_and_libraries"])[0]
    document = snapshot(target)
    args.out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(cast('list[object]', document['programs']))} programs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
