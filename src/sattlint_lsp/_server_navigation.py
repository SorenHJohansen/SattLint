"""Navigation-oriented LSP request handlers."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from lsprotocol.types import DefinitionParams, Hover, HoverParams, Location, ReferenceParams

from sattlint.core.semantic import SymbolDefinition

from ._server_document import resolve_symbol_context as _resolve_symbol_context
from ._server_helpers import build_hover as _build_hover
from ._server_helpers import collect_local_definition_locations
from ._server_helpers import collect_reference_matches as _collect_reference_matches
from ._server_helpers import definition_locations_from_candidates as _definition_locations_from_candidates
from ._server_helpers import definition_uri as _definition_uri
from ._server_helpers import is_program_path as _is_program_path
from ._server_helpers import merge_locations as _merge_locations
from ._server_helpers import range_for_definition as _range_for_definition
from ._server_helpers import reference_locations_from_matches as _reference_locations_from_matches
from ._server_helpers import validated_text_document_position as _validated_text_document_position

if TYPE_CHECKING:
    from .server import SattLineLanguageServer
    from .workspace_store import SnapshotBundle


def handle_definition(ls: SattLineLanguageServer, params: DefinitionParams) -> list[Location] | None:
    request = _validated_text_document_position(params)
    if request is None:
        return None

    document_uri, line, character = request
    document = ls.workspace.get_text_document(document_uri)
    document_path, source_text, local_snapshot, bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=line,
        column=character,
    )
    if not _is_program_path(document_path):
        return None

    if bundle is None:
        local_locations = collect_local_definition_locations(
            document_path,
            source_text,
            line=line,
            column=character,
            snapshot=local_snapshot,
        )
        return local_locations or None

    locations = _definition_locations_from_candidates(
        candidates,
        bundle=bundle,
        local_snapshot=local_snapshot,
        active_document_path=document_path,
    )
    return locations or None


def handle_hover(ls: SattLineLanguageServer, params: HoverParams) -> Hover | None:
    request = _validated_text_document_position(params)
    if request is None:
        return None

    document_uri, line, character = request
    document = ls.workspace.get_text_document(document_uri)
    document_path, _source_text, _local_snapshot, _bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=line,
        column=character,
    )
    if not _is_program_path(document_path) or not candidates:
        return None
    return _build_hover(candidates[0])


def handle_references(ls: SattLineLanguageServer, params: ReferenceParams) -> list[Location] | None:
    request = _validated_text_document_position(params)
    if request is None:
        return None

    document_uri, line, character = request
    document = ls.workspace.get_text_document(document_uri)
    document_path, _source_text, local_snapshot, bundle, candidates = _resolve_symbol_context(
        ls,
        document,
        line=line,
        column=character,
    )
    if not _is_program_path(document_path) or not candidates:
        return None

    references = _collect_reference_matches(bundle, local_snapshot, candidates)
    locations = _reference_locations_from_matches(
        references,
        bundle=bundle,
        active_document_path=document_path,
    )
    ref_context = getattr(params, "context", None)
    if getattr(ref_context, "include_declaration", False) or getattr(ref_context, "includeDeclaration", False):
        declaration_locations = _declaration_locations(candidates, bundle_path=document_path, bundle=bundle)
        locations = _merge_locations(declaration_locations, locations)
    return locations or None


def _declaration_locations(
    candidates: Sequence[SymbolDefinition], *, bundle_path: Path, bundle: SnapshotBundle | None
) -> list[Location]:
    declaration_locations: list[Location] = []
    for definition in candidates:
        target_range = _range_for_definition(definition)
        target_uri = _definition_uri(definition, bundle=bundle, active_document_path=bundle_path)
        if target_range is None or target_uri is None:
            continue
        declaration_locations.append(Location(uri=target_uri, range=target_range))
    return declaration_locations


declaration_locations = _declaration_locations
