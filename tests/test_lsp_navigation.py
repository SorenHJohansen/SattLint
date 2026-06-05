"""Navigation-focused LSP tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import SourceSpan
from sattlint.core.semantic import SymbolDefinition
from sattlint.editor_api import load_source_snapshot, load_workspace_snapshot
from sattlint_lsp.document_state import DocumentState
from sattlint_lsp.local_parser import FullDocumentParserAdapter
from sattlint_lsp.server import (
    _overlay_definition_candidates,
    collect_local_definition_locations,
    on_definition,
    on_hover,
    on_references,
    resolve_definition_path,
)
from tests.helpers.lsp_support import (
    StaticSymbolSnapshot,
    snapshot_bundle,
    snapshot_bundle_for_paths,
    source_with_basepicture_direct_code,
    source_with_unused_variable,
    write_text,
)


def test_overlay_definition_candidates_prefers_dirty_buffer_symbol(tmp_path):
    source = """
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

    edited_source = source.replace("Dv: integer := 0;", "Renamed: integer := 0;").replace("Dv = 1;", "Renamed = 1;")

    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)
    workspace_snapshot = load_workspace_snapshot(
        entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False
    )
    bundle = snapshot_bundle(workspace_snapshot, entry_file)
    local_snapshot = load_source_snapshot(entry_file, edited_source)
    target_line = edited_source.splitlines().index("        Renamed = 1;")
    target_column = edited_source.splitlines()[target_line].index("Renamed")

    definitions = _overlay_definition_candidates(
        bundle,
        document_path=entry_file,
        source_text=edited_source,
        line=target_line,
        column=target_column,
        local_snapshot=local_snapshot,
    )

    assert len(definitions) == 1
    assert definitions[0].canonical_path.endswith("Renamed")


def test_on_hover_falls_back_to_local_snapshot_when_workspace_snapshot_fails(monkeypatch, tmp_path):
    source = """
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

    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)
    document = SimpleNamespace(uri=entry_file.resolve().as_uri(), source=source, version=1)
    fake_ls = SimpleNamespace(
        workspace=SimpleNamespace(get_text_document=lambda uri: document),
        document_states={},
        local_parser=FullDocumentParserAdapter(),
        settings=SimpleNamespace(max_completion_items=20),
    )
    target_line = source.splitlines().index("        Dv = 1;")
    params = SimpleNamespace(
        text_document=SimpleNamespace(uri=document.uri),
        position=SimpleNamespace(
            line=target_line,
            character=source.splitlines()[target_line].index("Dv"),
        ),
    )

    monkeypatch.setattr("sattlint_lsp._server_document._load_snapshot_bundle", lambda ls, path, **kwargs: None)

    hover = on_hover(cast(Any, fake_ls), cast(Any, params))

    assert hover is not None
    hover_text = cast(Any, hover).contents.value
    assert "Dv" in hover_text
    assert "integer" in hover_text


def test_on_hover_returns_none_for_invalid_params() -> None:
    def fail_if_called(_uri: str):
        raise AssertionError("invalid hover params should not reach workspace lookup")

    fake_ls = SimpleNamespace(workspace=SimpleNamespace(get_text_document=fail_if_called))
    params = SimpleNamespace(
        text_document=SimpleNamespace(uri=None),
        position=SimpleNamespace(line=0, character=0),
    )

    assert on_hover(cast(Any, fake_ls), cast(Any, params)) is None


def test_on_references_falls_back_to_local_snapshot_when_workspace_snapshot_fails(monkeypatch, tmp_path):
    source = """
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
        Dv = Dv;
ENDDEF (*BasePicture*);
""".strip()

    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)
    document = SimpleNamespace(uri=entry_file.resolve().as_uri(), source=source, version=1)
    fake_ls = SimpleNamespace(
        workspace=SimpleNamespace(get_text_document=lambda uri: document),
        document_states={},
        local_parser=FullDocumentParserAdapter(),
        settings=SimpleNamespace(max_completion_items=20),
    )
    target_line = source.splitlines().index("        Dv = Dv;")
    params = SimpleNamespace(
        text_document=SimpleNamespace(uri=document.uri),
        position=SimpleNamespace(
            line=target_line,
            character=source.splitlines()[target_line].rindex("Dv"),
        ),
        context=SimpleNamespace(includeDeclaration=True),
    )

    monkeypatch.setattr("sattlint_lsp._server_document._load_snapshot_bundle", lambda ls, path, **kwargs: None)

    locations = on_references(cast(Any, fake_ls), cast(Any, params))

    assert locations is not None
    assert len(locations) == 3
    assert all(location.uri.casefold() == document.uri.casefold() for location in locations)


def test_on_references_ignores_ambiguous_same_name_workspace_matches_for_dirty_document(monkeypatch, tmp_path):
    source = source_with_basepicture_direct_code()
    edited_source = source.replace("Dv: integer := 0;", "Renamed: integer := 0;").replace(
        "        Dv = 1;",
        "        Renamed = Renamed;",
    )

    entry_file = tmp_path / "Program" / "Main.s"
    support_file = tmp_path / "Libs" / "Support" / "Main.s"
    backup_file = tmp_path / "Libs" / "Backup" / "Main.s"
    write_text(entry_file, source)
    write_text(support_file, source)
    write_text(backup_file, source)

    document = SimpleNamespace(uri=entry_file.resolve().as_uri(), source=source, version=1)
    fake_ls = SimpleNamespace(
        workspace=SimpleNamespace(get_text_document=lambda uri: document),
        document_states={
            document.uri: DocumentState(
                uri=document.uri,
                path=entry_file,
                version=2,
                text=edited_source,
                is_dirty=True,
            )
        },
        local_parser=FullDocumentParserAdapter(),
        settings=SimpleNamespace(max_completion_items=20),
    )
    target_line = edited_source.splitlines().index("        Renamed = Renamed;")
    params = SimpleNamespace(
        text_document=SimpleNamespace(uri=document.uri),
        position=SimpleNamespace(
            line=target_line,
            character=edited_source.splitlines()[target_line].rindex("Renamed"),
        ),
        context=SimpleNamespace(includeDeclaration=False),
    )
    workspace_definition = SymbolDefinition(
        canonical_path="BasePicture.Renamed",
        kind="local",
        datatype="integer",
        declaration_module_path=("BasePicture",),
        display_module_path=("BasePicture",),
        source_file="Main.s",
        declaration_span=SourceSpan(5, 4),
    )
    fake_bundle = snapshot_bundle_for_paths(
        StaticSymbolSnapshot(
            definitions=(workspace_definition,),
            references=(
                SimpleNamespace(
                    canonical_path="BasePicture.Renamed",
                    source_file="Main.s",
                    source_library=None,
                    line=40,
                    column=8,
                    length=len("Renamed"),
                    text="Renamed",
                ),
            ),
        ),
        entry_file,
        support_file,
        backup_file,
    )

    monkeypatch.setattr("sattlint_lsp._server_document._load_snapshot_bundle", lambda ls, path, **kwargs: fake_bundle)

    locations = on_references(cast(Any, fake_ls), cast(Any, params))

    assert locations is not None
    assert len(locations) == 2
    assert all(location.uri.casefold() == document.uri.casefold() for location in locations)
    assert max(location.range.start.line for location in locations) < 20


def test_on_definition_falls_back_to_local_snapshot_when_workspace_snapshot_fails(monkeypatch, tmp_path):
    source = source_with_unused_variable("Dv").replace(
        "ENDDEF (*BasePicture*);",
        "ModuleCode\n    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n        Dv = 1;\nENDDEF (*BasePicture*);",
    )

    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)
    document = SimpleNamespace(uri=entry_file.resolve().as_uri(), source=source, version=1)
    fake_ls = SimpleNamespace(
        workspace=SimpleNamespace(get_text_document=lambda uri: document),
        document_states={},
        local_parser=FullDocumentParserAdapter(),
        settings=SimpleNamespace(max_completion_items=20),
    )
    params = SimpleNamespace(
        text_document=SimpleNamespace(uri=document.uri),
        position=SimpleNamespace(
            line=source.splitlines().index("        Dv = 1;"),
            character=source.splitlines()[source.splitlines().index("        Dv = 1;")].index("Dv"),
        ),
    )

    monkeypatch.setattr(
        "sattlint_lsp._server_document._load_snapshot_bundle",
        lambda ls, path: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    locations = on_definition(cast(Any, fake_ls), cast(Any, params))

    assert locations is not None
    assert len(locations) == 1
    assert locations[0].range.start.line == 5


def test_on_definition_ignores_dependency_list_documents(monkeypatch, tmp_path):
    document_path = tmp_path / "Libs" / "Support.l"
    document = SimpleNamespace(uri=document_path.resolve().as_uri(), source="Support\n", version=1)
    fake_ls = SimpleNamespace(
        workspace=SimpleNamespace(get_text_document=lambda uri: document),
        document_states={},
        local_parser=FullDocumentParserAdapter(),
        settings=SimpleNamespace(max_completion_items=20),
    )
    params = SimpleNamespace(
        text_document=SimpleNamespace(uri=document.uri),
        position=SimpleNamespace(line=0, character=0),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dependency lists should not trigger definition analysis")

    monkeypatch.setattr("sattlint_lsp.server._get_or_build_local_snapshot", fail_if_called)

    assert on_definition(cast(Any, fake_ls), cast(Any, params)) is None


def test_resolve_definition_path_prefers_loaded_source_index(tmp_path):
    source = source_with_unused_variable("Dv")
    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)
    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)
    bundle = snapshot_bundle(snapshot, entry_file)
    definition = snapshot.find_definitions("BasePicture.Dv", limit=1)[0]

    assert resolve_definition_path(bundle, definition) == entry_file.resolve()


def test_collect_local_definition_locations_resolves_same_file_symbol(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
    LOCALVARIABLES
        LocalVar: boolean := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            LocalVar = True;
    ENDDEF (*Child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()

    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)
    target_line = source.splitlines().index("            LocalVar = True;")
    target_column = source.splitlines()[target_line].index("LocalVar")

    locations = collect_local_definition_locations(
        entry_file,
        source,
        line=target_line,
        column=target_column,
    )

    assert len(locations) == 1
    assert locations[0].range.start.line == 7
    assert locations[0].range.start.character == 8


def test_collect_local_definition_locations_returns_empty_on_recoverable_snapshot_failure(monkeypatch, tmp_path):
    source = source_with_unused_variable()
    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)

    monkeypatch.setattr(
        "sattlint_lsp._server_helpers.load_source_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("workspace snapshot unavailable")),
    )

    locations = collect_local_definition_locations(
        entry_file,
        source,
        line=0,
        column=0,
    )

    assert locations == []


def test_collect_local_definition_locations_raises_non_recoverable_snapshot_failure(monkeypatch, tmp_path):
    source = source_with_unused_variable()
    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)

    monkeypatch.setattr(
        "sattlint_lsp._server_helpers.load_source_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt("stop")),
    )

    with pytest.raises(KeyboardInterrupt):
        collect_local_definition_locations(
            entry_file,
            source,
            line=0,
            column=0,
        )


def test_navigation_helper_path_coverage() -> None:
    definition = SymbolDefinition(
        canonical_path="BasePicture.Child.LocalVar",
        kind="local",
        datatype="integer",
        declaration_module_path=("BasePicture", "Child"),
        display_module_path=("BasePicture", "Child"),
        field_path="Child.LocalVar",
        declaration_span=SourceSpan(4, 2),
    )

    assert definition.canonical_path.endswith("LocalVar")
