# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
"""Rename and completion focused LSP tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from lsprotocol.types import CompletionItem as LspCompletionItem
from lsprotocol.types import CompletionItemKind

from sattlint.editor_api import load_workspace_snapshot
from sattlint_lsp.document_state import DocumentState
from sattlint_lsp.local_parser import FullDocumentParserAdapter
from sattlint_lsp.server import (
    collect_completion_candidates,
    collect_local_completion_candidates,
    infer_module_path_from_source,
    on_completion,
    on_rename,
)
from tests.helpers.lsp_support import (
    StaticSymbolSnapshot,
    snapshot_bundle_for_paths,
    source_with_basepicture_direct_code,
    write_text,
)


def test_on_rename_falls_back_to_local_snapshot_when_workspace_snapshot_fails(monkeypatch, tmp_path):
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
        new_name="Renamed",
    )

    monkeypatch.setattr("sattlint_lsp._server_document._load_snapshot_bundle", lambda ls, path, **kwargs: None)

    edit = on_rename(cast(Any, fake_ls), cast(Any, params))

    assert edit is not None
    changes = cast(Any, edit).changes
    assert changes is not None
    matching_uri = next((uri for uri in changes if uri.casefold() == document.uri.casefold()), None)
    assert matching_uri is not None
    assert len(changes[matching_uri]) == 3
    assert all(item.new_text == "Renamed" for item in changes[matching_uri])


def test_on_rename_returns_none_for_invalid_params(monkeypatch) -> None:
    def fail_if_called(_uri: str):
        raise AssertionError("invalid rename params should not reach workspace lookup")

    fake_ls = SimpleNamespace(workspace=SimpleNamespace(get_text_document=fail_if_called))
    params = SimpleNamespace(
        text_document=SimpleNamespace(uri="file:///tmp/Main.s"),
        position=SimpleNamespace(line=0, character=0),
        new_name=None,
    )

    monkeypatch.setattr(
        "sattlint_lsp.server._validate_rename_target",
        lambda _new_name: (_ for _ in ()).throw(AssertionError("rename target validation should be skipped")),
    )

    assert on_rename(cast(Any, fake_ls), cast(Any, params)) is None


def test_on_completion_falls_back_to_local_snapshot_when_workspace_snapshot_fails(monkeypatch, tmp_path):
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
            character=source.splitlines()[target_line].rindex("Dv") + 2,
        ),
    )

    monkeypatch.setattr("sattlint_lsp.server._get_or_build_local_snapshot", lambda ls, document, path: object())
    monkeypatch.setattr(
        "sattlint_lsp.server.collect_local_completion_candidates",
        lambda *args, **kwargs: [
            LspCompletionItem(label="Dv", kind=CompletionItemKind.Variable),
        ],
    )
    monkeypatch.setattr(
        "sattlint_lsp._server_document._load_snapshot_bundle",
        lambda ls, path: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = on_completion(cast(Any, fake_ls), cast(Any, params))

    assert any(item.label == "Dv" for item in result.items)


def test_on_completion_returns_empty_list_for_invalid_params() -> None:
    def fail_if_called(_uri: str):
        raise AssertionError("invalid completion params should not reach workspace lookup")

    fake_ls = SimpleNamespace(
        workspace=SimpleNamespace(get_text_document=fail_if_called),
        settings=SimpleNamespace(max_completion_items=20),
    )
    params = SimpleNamespace(
        text_document=SimpleNamespace(uri="file:///tmp/Main.s"),
        position=SimpleNamespace(line="zero", character=0),
    )

    result = on_completion(cast(Any, fake_ls), cast(Any, params))

    assert result.items == []


def test_on_rename_ignores_ambiguous_same_name_workspace_references_for_dirty_document(monkeypatch, tmp_path):
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
        new_name="FinalName",
    )
    fake_bundle = snapshot_bundle_for_paths(
        StaticSymbolSnapshot(
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
                SimpleNamespace(
                    canonical_path="BasePicture.Renamed",
                    source_file="Main.s",
                    source_library=None,
                    line=60,
                    column=6,
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

    edit = on_rename(cast(Any, fake_ls), cast(Any, params))

    assert edit is not None
    changes = cast(Any, edit).changes
    assert changes is not None
    assert list(changes) == [document.uri]
    assert len(changes[document.uri]) == 3


def test_on_completion_ignores_dependency_list_documents(monkeypatch, tmp_path):
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
        raise AssertionError("dependency lists should not trigger completion analysis")

    monkeypatch.setattr("sattlint_lsp.server._get_or_build_local_snapshot", fail_if_called)

    result = on_completion(cast(Any, fake_ls), cast(Any, params))

    assert result.items == []


def test_infer_module_path_from_source_tracks_nested_modules():
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            X = 1;
    ENDDEF (*Child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()

    line_index = source.splitlines().index("            X = 1;")

    assert infer_module_path_from_source(source, line_index) == "BasePicture.Child"


def test_collect_completion_candidates_uses_inferred_module_scope(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dv: integer := 0;
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        Param: integer;
    LOCALVARIABLES
        LocalVar: boolean := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            LocalVar = False;
    ENDDEF (*Child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()

    editing_source = source.replace("LocalVar = False;", "Lo")

    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)
    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)

    line_index = editing_source.splitlines().index("            Lo")
    items = collect_completion_candidates(
        snapshot, editing_source, line=line_index, column=len("            Lo"), limit=20
    )
    labels = {item.label for item in items}

    assert "LocalVar" in labels


def test_infer_module_path_from_source_tracks_typedef_modules():
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    Child = MODULEDEFINITION DateCode_ 2
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

    line_index = source.splitlines().index("            LocalVar = True;")

    assert infer_module_path_from_source(source, line_index) == "BasePicture.Child"


def test_collect_local_completion_candidates_uses_typedef_module_scope(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    Child = MODULEDEFINITION DateCode_ 2
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

    editing_source = source.replace("LocalVar = True;", "Local = True;")
    entry_file = tmp_path / "Program" / "Main.s"
    write_text(entry_file, source)

    line_index = editing_source.splitlines().index("            Local = True;")
    items = collect_local_completion_candidates(
        entry_file,
        editing_source,
        line=line_index,
        column=len("            Local"),
        limit=20,
    )
    labels = {item.label for item in items}

    assert "LocalVar" in labels
