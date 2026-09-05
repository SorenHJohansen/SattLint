"""Parsing and project-loading engine for SattLine sources."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from lark import Lark
from sattline_parser import parse_source_file as parser_core_parse_source_file
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.api import describe_parse_error, read_text_with_fallback
from sattline_parser.models.ast_model import BasePicture
from sattline_parser.preprocessing import is_compressed, preprocess_sl_text
from sattline_parser.transformer.sl_transformer import SLTransformer

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
from .models.project_graph import merge_project_basepicture as _merge_project_basepicture_core
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
    # Raw-parse helper for analyzer unit tests and tooling that build an
    # unvalidated AST on purpose. Validation is load-path-mandatory in
    # project/loader.py; this surface stays parse-only by design.
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
    return _merge_project_basepicture_core(root_bp, graph)


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
    "graphics_ext",
    "graphics_ext_candidates",
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
