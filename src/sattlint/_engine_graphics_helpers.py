"""Graphics companion helpers for the engine."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.api import read_text_with_fallback
from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import BasePicture

from ._picture_display_path_runtime import correlate_composite_records
from ._validation_shared import ValidationNotice
from .models.project_graph import ProjectGraph
from .picture_display_paths import (
    PictureDisplayOccurrence,
    correlate_picture_display_records,
    diagnose_picture_display_paths,
    format_picture_display_path_diagnostic,
)
from .validation import validate_transformed_basepicture

_GraphicsCompanionSignature = tuple[str, int, int]
_GraphicsWarningContextFileSignature = tuple[str, int | None, int | None]
_GraphicsWarningContextSignature = tuple[
    tuple[_GraphicsWarningContextFileSignature, ...],
    tuple[str, ...],
    tuple[str, ...],
]


def _normalized_mode_value(mode: object | None) -> str | None:
    if mode is None:
        return None
    raw_mode = getattr(mode, "value", mode)
    mode_text = str(raw_mode).strip().lower()
    return mode_text or None


def resolve_graphics_companion_path(
    source_path: Path,
    *,
    mode: object | None = None,
) -> Path | None:
    target_path = Path(source_path)
    if target_path.suffix.lower() in {".g", ".y"}:
        return target_path

    resolved_mode = _normalized_mode_value(mode)
    if resolved_mode == "official" or target_path.suffix.lower() == ".x":
        candidate_extensions = (".y",)
    else:
        candidate_extensions = (".g", ".y")

    for extension in candidate_extensions:
        candidate = target_path.with_suffix(extension)
        if candidate.exists():
            return candidate

    return None


def _graphics_companion_signature(path: Path) -> _GraphicsCompanionSignature | None:
    try:
        stat_result = path.stat()
    except OSError:
        return None
    return (str(path), stat_result.st_mtime_ns, stat_result.st_size)


def _cached_graphics_companion_signature(bp: BasePicture) -> _GraphicsCompanionSignature | None:
    raw_signature = getattr(bp, "graphics_companion_signature", None)
    if not isinstance(raw_signature, tuple):
        return None
    signature = cast(tuple[object, ...], raw_signature)
    if len(signature) != 3:
        return None
    path_text, mtime_ns, size = signature
    if not isinstance(path_text, str) or not isinstance(mtime_ns, int) or not isinstance(size, int):
        return None
    return (path_text, mtime_ns, size)


def _cached_graphics_warning_notices(bp: BasePicture) -> tuple[ValidationNotice, ...] | None:
    raw_notices = getattr(bp, "graphics_warning_notices", None)
    if isinstance(raw_notices, tuple):
        notices = cast(tuple[object, ...], raw_notices)
    elif isinstance(raw_notices, list):
        notices = tuple(cast(list[object], raw_notices))
    else:
        return None
    if not all(isinstance(notice, ValidationNotice) for notice in notices):
        return None
    return cast(tuple[ValidationNotice, ...], notices)


def _cached_graphics_warning_context_signature(bp: BasePicture) -> _GraphicsWarningContextSignature | None:
    raw_signature = getattr(bp, "graphics_warning_context_signature", None)
    if not isinstance(raw_signature, tuple):
        return None
    signature = cast(tuple[object, ...], raw_signature)
    if len(signature) != 3:
        return None
    source_files, ast_names, unavailable_libraries = signature
    if not isinstance(source_files, tuple):
        return None
    if not isinstance(ast_names, tuple):
        return None
    if not isinstance(unavailable_libraries, tuple):
        return None
    return cast(_GraphicsWarningContextSignature, (source_files, ast_names, unavailable_libraries))


def _graphics_warning_context_file_signature(path: Path) -> _GraphicsWarningContextFileSignature:
    try:
        stat_result = path.stat()
    except OSError:
        return (str(path), None, None)
    return (str(path), stat_result.st_mtime_ns, stat_result.st_size)


def _graphics_warning_context_signature(graph: ProjectGraph) -> _GraphicsWarningContextSignature:
    source_files = tuple(sorted(_graphics_warning_context_file_signature(path) for path in graph.source_files))
    ast_names = tuple(sorted(name.casefold() for name in graph.ast_by_name))
    unavailable_libraries = tuple(sorted(name.casefold() for name in graph.unavailable_libraries))
    return (source_files, ast_names, unavailable_libraries)


def _has_attached_graphics_companion(bp: BasePicture) -> bool:
    return (
        getattr(bp, "graphics_file", None) is not None
        or bool(getattr(bp, "graphics_messages", ()))
        or bool(getattr(bp, "graphics_composite_records", ()))
        or bool(getattr(bp, "graphics_picture_display_records", ()))
        or bool(getattr(bp, "graphics_picture_display_occurrences", ()))
        or bool(getattr(bp, "graphics_warning_notices", ()))
        or _cached_graphics_companion_signature(bp) is not None
        or _cached_graphics_warning_context_signature(bp) is not None
    )


def _clear_attached_graphics_companion(bp: BasePicture) -> bool:
    changed = False
    defaults: tuple[tuple[str, object], ...] = (
        ("graphics_file", None),
        ("graphics_bindings", []),
        ("graphics_messages", []),
        ("graphics_composite_records", []),
        ("graphics_composite_occurrences", []),
        ("graphics_picture_display_records", []),
        ("graphics_picture_display_occurrences", []),
        ("graphics_warning_notices", ()),
        ("graphics_warning_context_signature", None),
        ("graphics_companion_signature", None),
    )
    for attribute, default in defaults:
        if not hasattr(bp, attribute):
            setattr(bp, attribute, default)
            changed = True
            continue
        if getattr(bp, attribute, default) == default:
            continue
        setattr(bp, attribute, default)
        changed = True
    return changed


def graphics_companion_needs_refresh(
    bp: BasePicture,
    *,
    code_path: Path,
    mode: object,
) -> bool:
    from . import engine as engine_module  # noqa: PLC0415

    companion_path = engine_module.resolve_graphics_companion_path(code_path, mode=mode)
    if companion_path is None or companion_path == code_path:
        return _has_attached_graphics_companion(bp)

    signature = _graphics_companion_signature(companion_path)
    return not (
        signature is not None
        and getattr(bp, "graphics_file", None) == companion_path.name
        and _cached_graphics_companion_signature(bp) == signature
    )


def picture_display_path_warnings(
    base_picture: BasePicture,
    occurrences: tuple[PictureDisplayOccurrence, ...],
    *,
    graph: ProjectGraph | None = None,
) -> tuple[ValidationNotice, ...]:
    diagnostics = diagnose_picture_display_paths(base_picture, occurrences, graph=graph)
    return tuple(
        ValidationNotice(
            message=format_picture_display_path_diagnostic(diagnostic),
            line=diagnostic.path_row.span.line,
            column=diagnostic.path_row.span.column,
            length=len(diagnostic.path_row.raw_text),
        )
        for diagnostic in diagnostics
    )


def attach_graphics_companion(
    bp: BasePicture,
    *,
    code_path: Path,
    mode: object,
    graph: ProjectGraph,
    owner_name: str,
    timing_sink: Callable[[str, str, float], None] | None = None,
) -> bool:
    from . import engine as engine_module  # noqa: PLC0415

    engine_module_any: Any = engine_module
    record_project_warning = cast(
        Callable[[ProjectGraph, str, ValidationNotice | str], None],
        engine_module_any._record_project_warning,
    )

    def _record_timing(phase_name: str, started_at: float) -> None:
        if timing_sink is None:
            return
        timing_sink(owner_name, phase_name, perf_counter() - started_at)

    resolve_started_at = perf_counter()
    companion_path = engine_module.resolve_graphics_companion_path(code_path, mode=mode)
    _record_timing("resolve-companion-path", resolve_started_at)
    if companion_path is None or companion_path == code_path:
        return _clear_attached_graphics_companion(bp)

    signature_started_at = perf_counter()
    signature = _graphics_companion_signature(companion_path)
    _record_timing("graphics-signature", signature_started_at)
    refreshed = False
    if not (
        signature is not None
        and getattr(bp, "graphics_file", None) == companion_path.name
        and _cached_graphics_companion_signature(bp) == signature
    ):
        bp_any: Any = bp
        validate_started_at = perf_counter()
        result = engine_module.validate_graphics_file(companion_path)
        _record_timing("validate-graphics-file", validate_started_at)
        bp.graphics_file = companion_path.name
        bp.graphics_bindings = list(getattr(result, "bindings", ()))
        bp.graphics_messages = list(result.messages)
        bp.graphics_composite_records = list(getattr(result, "composite_records", ()))
        composite_started_at = perf_counter()
        bp.graphics_composite_occurrences = list(
            correlate_composite_records(bp, tuple(getattr(result, "composite_records", ())), graph=graph)
        )
        _record_timing("correlate-composites", composite_started_at)
        bp.graphics_picture_display_records = list(getattr(result, "picture_display_records", ()))
        picture_display_started_at = perf_counter()
        bp.graphics_picture_display_occurrences = list(
            correlate_picture_display_records(
                bp,
                tuple(getattr(result, "picture_display_records", ())),
                graph=graph,
            )
        )
        _record_timing("correlate-picture-display", picture_display_started_at)
        bp_any.graphics_companion_signature = signature
        refreshed = True

    warning_context_signature = _graphics_warning_context_signature(graph)
    warning_notices = None if refreshed else _cached_graphics_warning_notices(bp)
    if warning_notices is None or _cached_graphics_warning_context_signature(bp) != warning_context_signature:
        bp_any: Any = bp
        warnings_started_at = perf_counter()
        warning_notices = picture_display_path_warnings(
            bp,
            tuple(getattr(bp, "graphics_picture_display_occurrences", ())),
            graph=graph,
        )
        _record_timing("picture-display-warnings", warnings_started_at)
        bp_any.graphics_warning_notices = warning_notices
        bp_any.graphics_warning_context_signature = warning_context_signature

    for warning in warning_notices:
        record_project_warning(graph, owner_name, warning)

    for message in getattr(bp, "graphics_messages", ()):
        record_project_warning(
            graph,
            owner_name,
            ValidationNotice(
                message=f"graphics validation {message.severity}: {message.message}",
                line=message.line,
                column=message.column,
                length=message.length,
            ),
        )
    return refreshed


def graphics_source_context_path(graphics_path: Path) -> Path | None:
    suffix = graphics_path.suffix.lower()
    candidates = (".s", ".x") if suffix == ".g" else (".x", ".s")
    for candidate_suffix in candidates:
        candidate = graphics_path.with_suffix(candidate_suffix)
        if candidate.exists():
            return candidate
    return None


def load_picture_display_source_context(source_path: Path) -> BasePicture | None:
    try:
        source_text = read_text_with_fallback(source_path)
        if is_compressed(source_text):
            source_text, _ = preprocess_sl_text(source_text)
        basepic = parser_core_parse_source_text(source_text)
        validate_transformed_basepicture(
            basepic,
            allow_old_state_assignment=source_path.suffix.lower() in {".x", ".z"},
            allow_unresolved_external_datatypes=source_path.suffix.lower() in {".x", ".z"},
        )
        return basepic
    except Exception:  # noqa: BLE001
        return None
