"""Shared helpers for split LSP tests."""

from __future__ import annotations

from pathlib import Path

from sattlint_lsp.server import SnapshotBundle, build_source_path_index


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def snapshot_bundle(snapshot, entry_file: Path) -> SnapshotBundle:
    source_files = tuple(
        sorted(
            (path.resolve() for path in snapshot.project_graph.source_files),
            key=lambda path: path.as_posix().casefold(),
        )
    )
    by_name, by_key = build_source_path_index(source_files)
    return SnapshotBundle(
        snapshot=snapshot,
        source_paths_by_name=by_name,
        source_paths_by_key=by_key,
        entry_file=entry_file.resolve(),
        cache_key=entry_file.resolve().as_posix().casefold(),
        source_files=source_files,
    )


def record_library_source(record_name: str, field_name: str) -> str:
    return f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    {record_name} = RECORD DateCode_ 2
        {field_name}: integer;
    ENDDEF (*{record_name}*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()


def program_with_dependency(record_name: str) -> str:
    return f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dep: {record_name};
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()


def source_with_unused_variable(variable_name: str = "UnusedVar") -> str:
    return f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    {variable_name}: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()


def contract_library_source() -> str:
    return """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    MismatchType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        ExpectedValue: real;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*MismatchType*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()


def program_with_contract_mismatch_dependency() -> str:
    return """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    SourceValue: integer := 1;
SUBMODULES
    Child Invocation
       ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MismatchType (
    ExpectedValue => SourceValue);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()


def source_with_basepicture_direct_code() -> str:
    return """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dv: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dv = 1;
ENDDEF (*BasePicture*);
""".strip()
