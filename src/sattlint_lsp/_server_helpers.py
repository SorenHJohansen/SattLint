"""SattLint language-server helper utilities - pure and stateless functions."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, TypeGuard, cast

from lsprotocol.types import (
    Diagnostic,
    DiagnosticSeverity,
    Hover,
    MarkupContent,
    MarkupKind,
    Position,
    Range,
    TextEdit,
)
from pygls import uris
from pygls.workspace import TextDocument

from sattlint.core.semantic import (
    SymbolDefinition,
    discover_workspace_sources,
    load_source_snapshot,
)
from sattlint.engine import CodeMode

from ._server_semantic_cache import semantic_diagnostics_for_path as _cached_semantic_diagnostics_for_path
from .local_parser import IncrementalDocumentParserAdapter

_PROGRAM_SUFFIXES = {".s", ".x"}
_DIAGNOSTIC_SUFFIXES = {".s", ".x", ".g"}
_NAME_PATTERN = r"[0-9A-Za-z_'\u00C0-\u024F]+"
_VALID_IDENTIFIER_RE = re.compile(rf"^(?:'[^']+'|{_NAME_PATTERN})$")
_MODULE_START_RE = re.compile(
    rf"^\s*(?P<name>'[^']+'|{_NAME_PATTERN})\s+Invocation\b.*:\s+MODULEDEFINITION\b",
    re.IGNORECASE,
)
_TYPEDEF_START_RE = re.compile(
    rf"^\s*(?P<name>'[^']+'|{_NAME_PATTERN})\s*=\s*(?:PRIVATE_)?MODULEDEFINITION\b",
    re.IGNORECASE,
)
_ENDDEF_LABEL_RE = re.compile(r"^\s*ENDDEF\b(?:\s*\(\*(?P<label>.*?)\*\))?", re.IGNORECASE)
_INTERACTIVE_SNAPSHOT_WAIT_S = 0.05
_DIAGNOSTIC_SNAPSHOT_WAIT_S = 0.15
_MAX_IDENTIFIER_LENGTH = 20
_DEFAULT_MAX_COMPLETION_ITEMS = 100
_DEFAULT_LOCAL_PARSER = IncrementalDocumentParserAdapter()
_RECOVERABLE_LSP_EXCEPTIONS = (OSError, ValueError, RuntimeError, UnicodeError)
log = logging.getLogger(__name__)


def _is_program_path(path: Path) -> bool:
    return path.suffix.lower() in _PROGRAM_SUFFIXES


def _is_diagnostic_path(path: Path) -> bool:
    return path.suffix.lower() in _DIAGNOSTIC_SUFFIXES


def _cf(value: str) -> str:
    return value.casefold()


def _path_startswith(path: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    if len(prefix) > len(path):
        return False
    return tuple(_cf(part) for part in path[: len(prefix)]) == tuple(_cf(part) for part in prefix)


def _range_from_position(line: int, column: int, length: int) -> Range:
    start = Position(line=max(line - 1, 0), character=max(column - 1, 0))
    end = Position(line=max(line - 1, 0), character=max(column - 1 + max(length, 1), 0))
    return Range(start=start, end=end)


def _range_for_definition(definition: SymbolDefinition) -> Range | None:
    if definition.declaration_span is None:
        return None
    label = definition.field_path.split(".")[-1] if definition.field_path else definition.canonical_path.split(".")[-1]
    return _range_from_position(definition.declaration_span.line, definition.declaration_span.column, len(label))


def _diagnostic_from_message(
    message: str,
    line: int | None,
    column: int | None,
    length: int | None = None,
) -> Diagnostic:
    if line is None or column is None:
        range_ = Range(start=Position(line=0, character=0), end=Position(line=0, character=1))
    else:
        range_ = _range_from_position(line, column, max(length or 8, 1))
    return Diagnostic(range=range_, message=message, severity=DiagnosticSeverity.Error, source="sattlint")


def _root_workspace_failure_message(message: str) -> str:
    lines: list[str] = []
    for raw_line in message.splitlines():
        line = raw_line.strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith(("Resolved targets (", "Unavailable libraries (", "Other dependency issues (", "- ")):
            break
        lines.append(line)
    if lines:
        return "\n".join(lines)
    return message


def _normalize_workspace_diagnostics_mode(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"off", "background"}:
        return normalized
    return "background"


def background_workspace_diagnostics_enabled(ls: Any) -> bool:
    return ls.settings.enable_variable_diagnostics and ls.settings.workspace_diagnostics_mode == "background"


def _identifier_length(name: str) -> int:
    if len(name) >= 2 and name.startswith("'") and name.endswith("'"):
        return len(name[1:-1])
    return len(name)


def _validate_rename_target(new_name: str) -> None:
    if not _VALID_IDENTIFIER_RE.fullmatch(new_name):
        raise ValueError(f"{new_name!r} is not a valid SattLine identifier")
    if _identifier_length(new_name) > _MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"{new_name!r} exceeds the {_MAX_IDENTIFIER_LENGTH} character identifier limit")


def _is_non_negative_int(value: object) -> TypeGuard[int]:
    return type(value) is int and value >= 0


def _validated_text_document_uri(params: Any) -> str | None:
    text_document = getattr(params, "text_document", None)
    uri = getattr(text_document, "uri", None)
    if not isinstance(uri, str) or not uri:
        return None
    return uri


def _validated_text_document_position(params: Any) -> tuple[str, int, int] | None:
    uri = _validated_text_document_uri(params)
    if uri is None:
        return None

    position = getattr(params, "position", None)
    line = getattr(position, "line", None)
    character = getattr(position, "character", None)
    if not _is_non_negative_int(line) or not _is_non_negative_int(character):
        return None
    return uri, line, character


def _validated_open_request(params: Any) -> tuple[str, int, str] | None:
    uri = _validated_text_document_uri(params)
    if uri is None:
        return None

    text_document = getattr(params, "text_document", None)
    version = getattr(text_document, "version", None)
    text = getattr(text_document, "text", None)
    if not _is_non_negative_int(version) or not isinstance(text, str):
        return None
    return uri, version, text


def _validated_change_request(params: Any) -> tuple[str, int, list[Any]] | None:
    uri = _validated_text_document_uri(params)
    if uri is None:
        return None

    text_document = getattr(params, "text_document", None)
    version = getattr(text_document, "version", None)
    content_changes = getattr(params, "content_changes", None)
    if not _is_non_negative_int(version):
        return None
    if content_changes is None:
        normalized_changes: list[Any] = []
    elif isinstance(content_changes, list):
        normalized_changes = cast(list[Any], content_changes)
    elif isinstance(content_changes, tuple):
        normalized_changes = list(cast(tuple[Any, ...], content_changes))
    else:
        return None
    return uri, version, normalized_changes


def _validated_rename_request(params: Any) -> tuple[str, int, int, str] | None:
    position_request = _validated_text_document_position(params)
    if position_request is None:
        return None

    new_name = getattr(params, "new_name", None)
    if not isinstance(new_name, str):
        return None

    uri, line, character = position_request
    return uri, line, character, new_name


@dataclass(frozen=True, slots=True)
class LspSettings:
    entry_file: str | None = None
    mode: str = CodeMode.DRAFT.value
    scan_root_only: bool = False
    enable_variable_diagnostics: bool = True
    workspace_diagnostics_mode: str = "off"
    max_cached_entry_snapshots: int = 2
    max_completion_items: int = _DEFAULT_MAX_COMPLETION_ITEMS

    @staticmethod
    def _positive_int_setting(value: object, *, default: int) -> int:
        if not isinstance(value, int | float | str):
            return default
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    @classmethod
    def from_initialization_options(cls, data: Any) -> LspSettings:
        if not isinstance(data, Mapping):
            return cls()
        settings_data = cast(Mapping[str, object], data)
        raw_entry = str(settings_data.get("entryFile", "")).strip()
        raw_mode = str(settings_data.get("mode", CodeMode.DRAFT.value)).strip().lower() or CodeMode.DRAFT.value
        raw_limit = settings_data.get("maxCompletionItems", _DEFAULT_MAX_COMPLETION_ITEMS)
        raw_cache_limit = settings_data.get("maxCachedEntrySnapshots", 2)
        limit = cls._positive_int_setting(raw_limit, default=_DEFAULT_MAX_COMPLETION_ITEMS)
        cache_limit = cls._positive_int_setting(raw_cache_limit, default=2)
        return cls(
            entry_file=raw_entry or None,
            mode=raw_mode,
            scan_root_only=bool(settings_data.get("scanRootOnly", False)),
            enable_variable_diagnostics=bool(settings_data.get("enableVariableDiagnostics", True)),
            workspace_diagnostics_mode=_normalize_workspace_diagnostics_mode(
                settings_data.get("workspaceDiagnosticsMode", "off")
            ),
            max_cached_entry_snapshots=cache_limit,
            max_completion_items=limit,
        )


def _diagnostic_signature(diagnostic: Diagnostic) -> tuple[int, int, int, int, int, str, str, int]:
    severity = int(diagnostic.severity) if diagnostic.severity is not None else 0
    return (
        diagnostic.range.start.line,
        diagnostic.range.start.character,
        diagnostic.range.end.line,
        diagnostic.range.end.character,
        severity,
        diagnostic.source or "",
        diagnostic.message,
        0,
    )


def _merge_unique_diagnostics(*collections: Sequence[Diagnostic]) -> tuple[Diagnostic, ...]:
    unique: dict[tuple[int, int, int, int, int, str, str, int], Diagnostic] = {}
    for collection in collections:
        for diagnostic in collection:
            unique.setdefault(_diagnostic_signature(diagnostic), diagnostic)
    return tuple(unique[key] for key in sorted(unique))


def _document_uri_for_path(path: Path) -> str:
    resolved = path.resolve()
    return uris.from_fs_path(str(resolved)) or resolved.as_uri()


def resolve_entry_file(
    document_path: Path,
    *,
    workspace_root: Path,
    configured_entry_file: str | None = None,
) -> Path | None:
    suffix = document_path.suffix.lower()
    if suffix in _PROGRAM_SUFFIXES:
        return document_path.resolve()

    if configured_entry_file:
        configured = Path(configured_entry_file)
        candidate = configured if configured.is_absolute() else (workspace_root / configured)
        if candidate.exists() and candidate.suffix.lower() in _PROGRAM_SUFFIXES:
            return candidate.resolve()

    discovery = discover_workspace_sources(workspace_root)
    if len(discovery.program_files) == 1:
        return discovery.program_files[0].resolve()
    return None


def collect_syntax_diagnostics(
    document_path: Path,
    text: str,
    *,
    include_comment_validation: bool = True,
) -> list[Diagnostic]:
    return list(
        _DEFAULT_LOCAL_PARSER.analyze(
            document_path,
            text,
            include_comment_validation=include_comment_validation,
            build_snapshot=False,
        ).syntax_diagnostics
    )


def infer_module_path_from_source(source_text: str, line_number: int) -> str | None:
    stack: list[str] = []
    lines = source_text.splitlines()
    for line in lines[: line_number + 1]:
        module_match = _MODULE_START_RE.match(line)
        if module_match:
            stack.append(module_match.group("name"))
            continue

        typedef_match = _TYPEDEF_START_RE.match(line)
        if typedef_match:
            stack.append(typedef_match.group("name"))
            continue

        enddef_match = _ENDDEF_LABEL_RE.match(line)
        if not enddef_match:
            continue

        label = (enddef_match.group("label") or "").strip()
        if label and stack and _cf(stack[-1]) == _cf(label):
            stack.pop()

    return ".".join(stack) if stack else None


def build_source_path_index(
    paths: set[Path] | tuple[Path, ...],
) -> tuple[dict[str, tuple[Path, ...]], dict[tuple[str, str], Path]]:
    by_name: dict[str, list[Path]] = {}
    by_key: dict[tuple[str, str], Path] = {}
    for path in sorted((item.resolve() for item in paths), key=lambda item: item.as_posix().casefold()):
        file_key = path.name.casefold()
        by_name.setdefault(file_key, []).append(path)
        by_key[(file_key, path.parent.name.casefold())] = path
    return ({name: tuple(items) for name, items in by_name.items()}, by_key)


def _semantic_diagnostics_for_path(bundle: Any, document_path: Path) -> tuple[Diagnostic, ...]:
    return _cached_semantic_diagnostics_for_path(bundle, document_path, collect=collect_semantic_diagnostics)


def _document_path(document: TextDocument) -> Path:
    uri = document.uri or ""
    return Path(uris.to_fs_path(uri) or uri).resolve()


DEFAULT_MAX_COMPLETION_ITEMS = _DEFAULT_MAX_COMPLETION_ITEMS
NAME_PATTERN = _NAME_PATTERN
RECOVERABLE_LSP_EXCEPTIONS = _RECOVERABLE_LSP_EXCEPTIONS
cf = _cf
path_startswith = _path_startswith
range_for_definition = _range_for_definition
range_from_position = _range_from_position


_symbol_helpers = import_module("sattlint_lsp._server_symbol_helpers")
_collect_reference_matches = _symbol_helpers.collect_reference_matches
_definition_locations_from_candidates = _symbol_helpers.definition_locations_from_candidates
_definition_uri = _symbol_helpers.definition_uri
_filter_visible_definitions = _symbol_helpers._filter_visible_definitions
_local_definition_candidates = _symbol_helpers._local_definition_candidates
_merge_completion_items = _symbol_helpers.merge_completion_items
_merge_definitions = _symbol_helpers._merge_definitions
_merge_locations = _symbol_helpers.merge_locations
_merge_references = _symbol_helpers._merge_references
_overlay_definition_candidates = _symbol_helpers.overlay_definition_candidates
_reference_expr_at_position = _symbol_helpers._reference_expr_at_position
_reference_locations_from_matches = _symbol_helpers.reference_locations_from_matches
_resolve_bundle_source_path = _symbol_helpers._resolve_bundle_source_path
_resolve_reference_path = _symbol_helpers._resolve_reference_path
_semantic_completion_kind = _symbol_helpers._semantic_completion_kind
_split_reference_matches = _symbol_helpers._split_reference_matches
collect_completion_candidates = _symbol_helpers.collect_completion_candidates
collect_local_completion_candidates = _symbol_helpers.collect_local_completion_candidates
collect_local_definition_locations = _symbol_helpers.collect_local_definition_locations
collect_semantic_diagnostics = _symbol_helpers.collect_semantic_diagnostics
resolve_definition_path = _symbol_helpers.resolve_definition_path


def _append_workspace_edit(
    changes: dict[str, list[TextEdit]],
    uri: str,
    range_: Range,
    new_text: str,
) -> None:
    changes.setdefault(uri, []).append(TextEdit(range=range_, new_text=new_text))


def _build_hover(definition: SymbolDefinition) -> Hover | None:
    lines = [f"**{definition.canonical_path.split('.')[-1]}**"]
    if definition.datatype:
        lines.append(f"Type: {definition.datatype}")
    lines.append(f"Kind: {definition.kind}")
    lines.append(f"Path: {definition.canonical_path}")
    if definition.display_module_path:
        lines.append(f"Scope: {' -> '.join(definition.display_module_path)}")
    return Hover(contents=MarkupContent(kind=MarkupKind.Markdown, value="\n\n".join(lines)))


DEFAULT_LOCAL_PARSER = _DEFAULT_LOCAL_PARSER
INTERACTIVE_SNAPSHOT_WAIT_S = _INTERACTIVE_SNAPSHOT_WAIT_S
DIAGNOSTIC_SNAPSHOT_WAIT_S = _DIAGNOSTIC_SNAPSHOT_WAIT_S
HELPER_SEAMS = (background_workspace_diagnostics_enabled, load_source_snapshot)
append_workspace_edit = _append_workspace_edit
build_hover = _build_hover
collect_reference_matches = _collect_reference_matches
definition_locations_from_candidates = _definition_locations_from_candidates
split_reference_matches = _split_reference_matches
definition_uri = _definition_uri
diagnostic_from_message = _diagnostic_from_message
diagnostic_signature = _diagnostic_signature
document_path = _document_path
document_uri_for_path = _document_uri_for_path
is_diagnostic_path = _is_diagnostic_path
is_program_path = _is_program_path
local_definition_candidates = _local_definition_candidates
merge_completion_items = _merge_completion_items
merge_locations = _merge_locations
merge_unique_diagnostics = _merge_unique_diagnostics
overlay_definition_candidates = _overlay_definition_candidates
reference_locations_from_matches = _reference_locations_from_matches
resolve_reference_path = _resolve_reference_path
root_workspace_failure_message = _root_workspace_failure_message
semantic_diagnostics_for_path = _semantic_diagnostics_for_path
validate_rename_target = _validate_rename_target
validated_change_request = _validated_change_request
validated_open_request = _validated_open_request
validated_rename_request = _validated_rename_request
validated_text_document_position = _validated_text_document_position
validated_text_document_uri = _validated_text_document_uri
