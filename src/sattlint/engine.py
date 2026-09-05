"""Parsing and project-loading engine for SattLine sources."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path

from lark import Lark
from sattline_parser import parse_source_file as parser_core_parse_source_file
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.api import describe_parse_error, read_text_with_fallback
from sattline_parser.models.ast_model import BasePicture, DataType, ModuleTypeDef
from sattline_parser.preprocessing import is_compressed, preprocess_sl_text
from sattline_parser.transformer.sl_transformer import SLTransformer

from .core.libraries import expected_unavailable_library_reason, is_expected_unavailable_library
from .core.syntax import (
    CodeMode,
    SyntaxValidationResult,
    code_ext,
    create_sl_parser,
    deps_ext,
    graphics_ext,
    graphics_ext_candidates,
    normalize_code_mode,
    raise_syntax_validation_failure,
)
from .core.syntax import (
    extract_error_position as _extract_error_position,
)
from .core.syntax import (
    graphics_validation_to_syntax_result as _graphics_validation_to_syntax_result,
)
from .core.syntax import (
    load_source_text as _load_source_text_core,
)
from .core.syntax import (
    parse_source_file as _parse_source_file_core,
)
from .core.syntax import (
    parse_source_text as _parse_source_text_core,
)
from .core.syntax import (
    validate_single_file_syntax as _validate_single_file_syntax_core,
)
from .graphics.graphics_context_helpers import graphics_source_context_path as _graphics_source_context_path
from .graphics.graphics_context_helpers import (
    load_picture_display_source_context as _load_picture_display_source_context,
)
from .graphics.graphics_context_helpers import picture_display_path_warnings as _picture_display_path_warnings
from .graphics.graphics_context_helpers import resolve_graphics_companion_path
from .graphics.picture_display_paths import correlate_picture_display_records
from .graphics.validation import validate_graphics_file
from .models.project_graph import ProjectGraph
from .project.loader import SattLineProjectLoader
from .project.loader_base import CircularDependencyError, DependencyVersionCompatibilityError
from .project.loader_config import (
    ContextualFileLookup,
    GraphicsLoadTimingSink,
    LoadStageTimingSink,
    SattLineProjectLoaderConfig,
    SattLineProjectLoaderDependencies,
    SattLineProjectLoaderRuntime,
    build_project_loader_from_type,
    validate_loader_config,
)
from .project.loading import is_within_directory
from .utils.text_processing import find_disallowed_comments
from .validation import (
    LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION,
    StructuralValidationError,
    validate_transformed_basepicture,
    validate_transformed_basepicture_dependency_context,
    validate_transformed_basepicture_locally,
)
from .validation.shared import ValidationNotice, coerce_validation_notice


def build_project_loader(
    cfg: Mapping[str, object],
    *,
    contextual_lookup: ContextualFileLookup | None = None,
    use_file_ast_cache: bool = True,
    status_update_fn: Callable[[str], None] | None = None,
    refresh_mode: str = "full",
    stage_timing_sink: LoadStageTimingSink | None = None,
    graphics_timing_sink: GraphicsLoadTimingSink | None = None,
    dependencies: SattLineProjectLoaderDependencies | None = None,
) -> SattLineProjectLoader:
    return build_project_loader_from_type(
        SattLineProjectLoader,
        cfg,
        contextual_lookup=contextual_lookup,
        use_file_ast_cache=use_file_ast_cache,
        status_update_fn=status_update_fn,
        refresh_mode=refresh_mode,
        stage_timing_sink=stage_timing_sink,
        graphics_timing_sink=graphics_timing_sink,
        dependencies=dependencies,
    )


def load_project_graph(
    cfg: Mapping[str, object],
    target_name: str,
    *,
    contextual_lookup: ContextualFileLookup | None = None,
    use_file_ast_cache: bool = True,
    status_update_fn: Callable[[str], None] | None = None,
    refresh_mode: str = "full",
    stage_timing_sink: LoadStageTimingSink | None = None,
    graphics_timing_sink: GraphicsLoadTimingSink | None = None,
    dependencies: SattLineProjectLoaderDependencies | None = None,
    strict: bool = False,
) -> tuple[SattLineProjectLoader, BasePicture | None, ProjectGraph]:
    loader = build_project_loader(
        cfg,
        contextual_lookup=contextual_lookup,
        use_file_ast_cache=use_file_ast_cache,
        status_update_fn=status_update_fn,
        refresh_mode=refresh_mode,
        stage_timing_sink=stage_timing_sink,
        graphics_timing_sink=graphics_timing_sink,
        dependencies=dependencies,
    )
    graph = loader.resolve(target_name, strict=strict)
    root_bp = graph.ast_by_name.get(target_name)
    return loader, root_bp, graph


def _load_source_text(
    code_path: Path,
    *,
    debug: Callable[[str], None] | None = None,
) -> str:
    return _load_source_text_core(
        code_path,
        debug=debug,
        read_text_with_fallback_fn=read_text_with_fallback,
        is_compressed_fn=is_compressed,
        preprocess_sl_text_fn=preprocess_sl_text,
    )


def parse_source_text(
    src: str,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    return _parse_source_text_core(
        src,
        parser=parser,
        transformer=transformer,
        debug=debug,
        parser_core_parse_source_text_fn=parser_core_parse_source_text,
        validate_transformed_basepicture_fn=validate_transformed_basepicture,
    )


def parse_source_file(
    code_path: Path,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    return _parse_source_file_core(
        code_path,
        parser=parser,
        transformer=transformer,
        debug=debug,
        parser_core_parse_source_file_fn=parser_core_parse_source_file,
        validate_transformed_basepicture_fn=lambda _bp: None,
    )


def validate_single_file_syntax(
    code_path: Path,
    *,
    mode: CodeMode | str | None = None,
) -> SyntaxValidationResult:
    return _validate_single_file_syntax_core(
        code_path,
        mode=mode,
        load_source_text_fn=_load_source_text,
        find_disallowed_comments_fn=find_disallowed_comments,
        parser_core_parse_source_text_fn=parser_core_parse_source_text,
        validate_transformed_basepicture_fn=validate_transformed_basepicture,
        describe_parse_error_fn=describe_parse_error,
        validate_graphics_file_fn=validate_graphics_file,
        graphics_source_context_path_fn=_graphics_source_context_path,
        load_picture_display_source_context_fn=_load_picture_display_source_context,
        correlate_picture_display_records_fn=correlate_picture_display_records,
        picture_display_path_warnings_fn=_picture_display_path_warnings,
        resolve_graphics_companion_path_fn=resolve_graphics_companion_path,
        extract_error_position_fn=_extract_error_position,
        graphics_validation_to_syntax_result_fn=_graphics_validation_to_syntax_result,
        coerce_validation_notice_fn=coerce_validation_notice,
    )


def merge_project_basepicture(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
    merged_datatypes: list[DataType] = list(graph.datatype_defs.values())
    merged_modtypes: list[ModuleTypeDef] = list(graph.moduletype_defs.values())
    lib_deps = {lib: sorted(deps) for lib, deps in (graph.library_dependencies or {}).items()}
    return replace(
        root_bp,
        datatype_defs=merged_datatypes,
        moduletype_defs=merged_modtypes,
        library_dependencies=lib_deps,
    )


def _get_dump_dir() -> Path:
    dump_dir = Path.home() / ".sattlint" / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    return dump_dir


def dump_parse_tree(project: tuple[BasePicture, ProjectGraph]) -> None:
    from datetime import datetime  # noqa: PLC0415

    project_bp, _graph = project
    if project_bp.parse_tree is None:
        print("❌ No parse tree available for the root program.")
        return

    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"parse_tree_{project_bp.header.name}_{timestamp}.txt"
    filename.write_text(project_bp.parse_tree.pretty(), encoding="utf-8")
    print(f"\n✔ Parse tree saved to: {filename}")
    print()


def dump_ast(project: tuple[BasePicture, ProjectGraph]) -> None:
    from datetime import datetime  # noqa: PLC0415

    project_bp, _graph = project
    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"ast_{project_bp.header.name}_{timestamp}.txt"
    filename.write_text(str(project_bp), encoding="utf-8")
    print(f"\n✔ AST saved to: {filename}")
    print()


def dump_dependency_graph(project: tuple[BasePicture, ProjectGraph]) -> None:
    from datetime import datetime  # noqa: PLC0415

    project_bp, graph = project
    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"dependency_graph_{project_bp.header.name}_{timestamp}.txt"

    lines = ["--- Dependency Graph ---"]
    lines.append(f"Programs/Libraries parsed: {len(graph.ast_by_name)}")
    for name in sorted(graph.ast_by_name.keys()):
        bp = graph.ast_by_name[name]
        origin_info = f" (from {bp.origin_lib}/{bp.origin_file})" if bp.origin_lib or bp.origin_file else ""
        lines.append(f"  • {name}{origin_info}")

    if graph.datatype_defs:
        lines.append(f"\nDataType Definitions: {len(graph.datatype_defs)}")
        for name in sorted(graph.datatype_defs.keys()):
            dt = graph.datatype_defs[name]
            origin_info = f" (from {dt.origin_lib}/{dt.origin_file})" if dt.origin_lib or dt.origin_file else ""
            lines.append(f"  • {name}{origin_info}")

    if graph.moduletype_defs:
        lines.append(f"\nModuleType Definitions: {len(graph.moduletype_defs)}")
        for (_lib_key, _name_key, _file_key), mt in sorted(graph.moduletype_defs.items()):
            display = f"{mt.origin_lib}:{mt.name}" if mt.origin_lib else mt.name
            origin_info = f" (from {mt.origin_lib}/{mt.origin_file})" if mt.origin_lib or mt.origin_file else ""
            lines.append(f"  • {display}{origin_info}")

    if graph.library_dependencies:
        lines.append("\nLibrary dependencies:")
        for lib, deps in sorted(graph.library_dependencies.items()):
            dep_list = ", ".join(sorted(deps)) if deps else "<none>"
            lines.append(f"  • {lib} -> {dep_list}")

    if graph.missing:
        lines.append(f"\nMissing/Unresolved: {len(graph.missing)}")
        for msg in graph.missing:
            lines.append(f"  ⚠ {msg}")

    if graph.warnings:
        lines.append(f"\nWarnings: {len(graph.warnings)}")
        for msg in graph.warnings:
            lines.append(f"  ⚠ {msg}")

    if graph.ignored_vendor:
        lines.append(f"\nIgnored Vendor: {len(graph.ignored_vendor)}")
        for msg in graph.ignored_vendor:
            lines.append(f"  ⓘ {msg}")

    filename.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✔ Dependency graph saved to: {filename}")
    print()


__all__ = [
    "LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION",
    "CircularDependencyError",
    "CodeMode",
    "ContextualFileLookup",
    "DependencyVersionCompatibilityError",
    "GraphicsLoadTimingSink",
    "LoadStageTimingSink",
    "SattLineProjectLoader",
    "SattLineProjectLoaderConfig",
    "SattLineProjectLoaderDependencies",
    "SattLineProjectLoaderRuntime",
    "StructuralValidationError",
    "SyntaxValidationResult",
    "ValidationNotice",
    "build_project_loader",
    "code_ext",
    "create_sl_parser",
    "deps_ext",
    "dump_ast",
    "dump_dependency_graph",
    "dump_parse_tree",
    "expected_unavailable_library_reason",
    "graphics_ext",
    "graphics_ext_candidates",
    "is_expected_unavailable_library",
    "is_within_directory",
    "load_project_graph",
    "merge_project_basepicture",
    "normalize_code_mode",
    "parse_source_file",
    "parse_source_text",
    "raise_syntax_validation_failure",
    "resolve_graphics_companion_path",
    "validate_loader_config",
    "validate_single_file_syntax",
    "validate_transformed_basepicture",
    "validate_transformed_basepicture_dependency_context",
    "validate_transformed_basepicture_locally",
]
