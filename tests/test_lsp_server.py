from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from lsprotocol.types import Position, Range

from sattlint.editor_api import load_workspace_snapshot
from sattlint_lsp.document_state import DocumentState, apply_content_changes
from sattlint_lsp.local_parser import DocumentParseResult, FullDocumentParserAdapter, IncrementalParseState
from sattlint_lsp.server import (
    _get_or_build_local_snapshot,
    _overlay_definition_candidates,
    _publish_diagnostics,
    collect_completion_candidates,
    collect_local_completion_candidates,
    collect_local_definition_locations,
    collect_semantic_diagnostics,
    collect_syntax_diagnostics,
    build_source_path_index,
    infer_module_path_from_source,
    resolve_entry_file,
    resolve_definition_path,
    SnapshotBundle,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_resolve_entry_file_prefers_program_document(tmp_path):
    entry = tmp_path / "Programs" / "Main.s"
    _write_text(entry, '"x"\n"y"\n"z"\n')

    resolved = resolve_entry_file(entry, workspace_root=tmp_path)

    assert resolved == entry.resolve()


def test_resolve_entry_file_uses_configured_root_for_library_document(tmp_path):
    entry = tmp_path / "Programs" / "Main.s"
    library = tmp_path / "Libs" / "Support.l"
    _write_text(entry, '"x"\n"y"\n"z"\n')
    _write_text(library, "dep\n")

    resolved = resolve_entry_file(
        library,
        workspace_root=tmp_path,
        configured_entry_file="Programs/Main.s",
    )

    assert resolved == entry.resolve()


def test_collect_syntax_diagnostics_reports_comment_violation(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    (* comment outside a block *)
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        1;
ENDDEF (*BasePicture*);
""".strip()

    diagnostics = collect_syntax_diagnostics(tmp_path / "Program.s", source)

    assert len(diagnostics) == 1
    assert "only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks" in diagnostics[0].message


def test_collect_syntax_diagnostics_reports_multiple_comment_violations(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    (* first comment outside a block *)
    (* second comment outside a block *)
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dv = 1;
ENDDEF (*BasePicture*);
""".strip()

    diagnostics = collect_syntax_diagnostics(tmp_path / "Program.s", source)

    assert len(diagnostics) == 2
    assert all(
        "only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_collect_syntax_diagnostics_reports_multiple_parse_errors_by_reparsing(tmp_path):
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
        Dv = ;
        Other = ;
ENDDEF (*BasePicture*);
""".strip()

    diagnostics = collect_syntax_diagnostics(tmp_path / "Program.s", source)

    assert len(diagnostics) >= 2


def test_collect_syntax_diagnostics_reports_builtin_datatype_typo(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    si: intege;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()

    diagnostics = collect_syntax_diagnostics(tmp_path / "Program.s", source)

    assert len(diagnostics) == 1
    assert "did you mean 'integer'" in diagnostics[0].message
    assert diagnostics[0].range.start.line == 5
    assert diagnostics[0].range.start.character == 4


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
    _write_text(entry_file, source)
    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)

    line_index = editing_source.splitlines().index("            Lo")
    items = collect_completion_candidates(snapshot, editing_source, line=line_index, column=len("            Lo"), limit=20)
    labels = {item.label for item in items}

    assert "LocalVar" in labels


def test_publish_diagnostics_skips_semantic_analysis_for_clean_did_change(monkeypatch, tmp_path):
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

    published = []
    fake_ls = SimpleNamespace(
        settings=SimpleNamespace(enable_variable_diagnostics=True),
        document_states={},
        local_parser=FullDocumentParserAdapter(),
        text_document_publish_diagnostics=lambda params: published.append(params),
    )
    fake_document = SimpleNamespace(
        uri="file:///Program/Main.s",
        source=source,
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("semantic snapshot loading should be skipped for didChange")

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: tmp_path / "Program" / "Main.s")
    monkeypatch.setattr("sattlint_lsp.server._load_snapshot_bundle", fail_if_called)
    monkeypatch.setattr(
        "sattlint_lsp.local_parser.build_source_snapshot_from_basepicture",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("syntax-only didChange should not build a local snapshot")),
    )

    _publish_diagnostics(cast(Any, fake_ls), cast(Any, fake_document), include_semantic=False)

    assert len(published) == 1
    assert published[0].diagnostics == []


def test_publish_diagnostics_skips_comment_validation_for_did_change(monkeypatch, tmp_path):
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
    (* comment outside a block *)
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dv = 1;
ENDDEF (*BasePicture*);
""".strip()

    published = []
    fake_ls = SimpleNamespace(
        settings=SimpleNamespace(enable_variable_diagnostics=True),
        document_states={},
        local_parser=FullDocumentParserAdapter(),
        text_document_publish_diagnostics=lambda params: published.append(params),
    )
    fake_document = SimpleNamespace(
        uri="file:///Program/Main.s",
        source=source,
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: tmp_path / "Program" / "Main.s")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("comment validation should be skipped for didChange")

    monkeypatch.setattr("sattlint_lsp.local_parser.find_disallowed_comments", fail_if_called)

    _publish_diagnostics(
        cast(Any, fake_ls),
        cast(Any, fake_document),
        include_semantic=False,
        include_comment_validation=False,
    )

    assert len(published) == 1
    assert published[0].diagnostics == []


def test_publish_diagnostics_includes_semantic_analysis_when_requested(monkeypatch, tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    UnusedVar: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()

    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, source)
    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=True)
    by_name, by_key = build_source_path_index(snapshot.project_graph.source_files)
    bundle = SnapshotBundle(snapshot=snapshot, source_paths_by_name=by_name, source_paths_by_key=by_key)

    published = []
    fake_ls = SimpleNamespace(
        settings=SimpleNamespace(enable_variable_diagnostics=True),
        document_states={},
        local_parser=FullDocumentParserAdapter(),
        text_document_publish_diagnostics=lambda params: published.append(params),
    )
    fake_document = SimpleNamespace(
        uri=entry_file.resolve().as_uri(),
        source=source,
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: entry_file)
    monkeypatch.setattr("sattlint_lsp.server._load_snapshot_bundle", lambda ls, path: bundle)

    _publish_diagnostics(cast(Any, fake_ls), cast(Any, fake_document))

    assert len(published) == 1
    assert any(diagnostic.message.startswith("Unused variable") for diagnostic in published[0].diagnostics)


def test_collect_semantic_diagnostics_maps_unused_issue_to_source_file(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    UnusedVar: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()

    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, source)
    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=True)
    by_name, by_key = build_source_path_index(snapshot.project_graph.source_files)
    bundle = SnapshotBundle(snapshot=snapshot, source_paths_by_name=by_name, source_paths_by_key=by_key)

    diagnostics = collect_semantic_diagnostics(bundle, entry_file)
    target = next(d for d in diagnostics if d.message.startswith("Unused variable"))

    assert target.range.start.line == 5
    assert target.range.start.character == 4


def test_resolve_definition_path_prefers_loaded_source_index(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dv: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip()

    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, source)
    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)
    by_name, by_key = build_source_path_index(snapshot.project_graph.source_files)
    bundle = SnapshotBundle(snapshot=snapshot, source_paths_by_name=by_name, source_paths_by_key=by_key)
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
    _write_text(entry_file, source)

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
    _write_text(entry_file, source)

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


def test_apply_content_changes_handles_incremental_ranges():
    original = "Alpha = 1;\nBeta = 2;\n"
    updated, ranges = apply_content_changes(
        original,
        [
            SimpleNamespace(
                range=Range(
                    start=Position(line=1, character=0),
                    end=Position(line=1, character=4),
                ),
                text="Gamma",
            )
        ],
    )

    assert updated == "Alpha = 1;\nGamma = 2;\n"
    assert ranges == ((1, 1),)


def test_document_state_apply_changes_preserves_previous_analysis_result(tmp_path):
    state = DocumentState(
        uri="file:///Program/Main.s",
        path=tmp_path / "Program" / "Main.s",
        version=1,
        text="Alpha = 1;\n",
    )
    previous_result = DocumentParseResult(
        syntax_diagnostics=(),
        local_snapshot=None,
        adapter_state={"tree": "old"},
    )
    state.remember_analysis(previous_result, include_comment_validation=False)

    state.apply_changes(
        version=2,
        content_changes=[SimpleNamespace(range=None, text="Beta = 1;\n")],
    )

    assert state.previous_analysis_result is previous_result
    assert state.analysis_result is None
    assert state.changed_line_ranges == ((0, 1),)


def test_collect_local_definition_locations_uses_supplied_snapshot(monkeypatch, tmp_path):
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
    _write_text(entry_file, source)
    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("load_source_snapshot should not be called when a snapshot is supplied")

    monkeypatch.setattr("sattlint_lsp.server.load_source_snapshot", fail_if_called)

    target_line = source.splitlines().index("        Dv = 1;")
    target_column = source.splitlines()[target_line].index("Dv")
    locations = collect_local_definition_locations(
        entry_file,
        source,
        line=target_line,
        column=target_column,
        snapshot=snapshot,
    )

    assert len(locations) == 1
    assert locations[0].range.start.line == 5


def test_get_or_build_local_snapshot_reuses_cached_version(monkeypatch, tmp_path):
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
    _write_text(entry_file, source)
    uri = entry_file.resolve().as_uri()
    document = SimpleNamespace(uri=uri, source=source, version=3)
    fake_ls = SimpleNamespace(document_states={}, workspace_root=tmp_path)

    calls = 0

    def wrapped_build_source_snapshot(*args, **kwargs):
        nonlocal calls
        calls += 1
        from sattlint.editor_api import build_source_snapshot_from_basepicture as real_build_source_snapshot

        return real_build_source_snapshot(*args, **kwargs)

    monkeypatch.setattr("sattlint_lsp.local_parser.build_source_snapshot_from_basepicture", wrapped_build_source_snapshot)
    fake_ls.local_parser = FullDocumentParserAdapter()

    first = _get_or_build_local_snapshot(cast(Any, fake_ls), cast(Any, document), entry_file)
    second = _get_or_build_local_snapshot(cast(Any, fake_ls), cast(Any, document), entry_file)

    assert first is not None
    assert second is first
    assert calls == 1


def test_get_or_build_local_snapshot_upgrades_prior_syntax_only_analysis(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    uri = entry_file.resolve().as_uri()
    text = "Alpha = 1;\n"
    document = SimpleNamespace(uri=uri, source=text, version=1)
    expected_snapshot = cast(Any, object())
    calls: list[tuple[bool, DocumentParseResult | None]] = []

    class RecordingParser:
        def analyze(
            self,
            document_path: Path,
            current_text: str,
            *,
            include_comment_validation: bool = True,
            build_snapshot: bool = True,
            previous_result: DocumentParseResult | None = None,
            changed_line_ranges: tuple[tuple[int, int], ...] = (),
        ) -> DocumentParseResult:
            calls.append((build_snapshot, previous_result))
            assert document_path == entry_file
            assert current_text == text
            assert include_comment_validation is False
            assert changed_line_ranges == ()
            if build_snapshot:
                return DocumentParseResult(syntax_diagnostics=(), local_snapshot=expected_snapshot)
            return DocumentParseResult(syntax_diagnostics=(), local_snapshot=None)

    fake_ls = SimpleNamespace(
        document_states={},
        local_parser=RecordingParser(),
        text_document_publish_diagnostics=lambda params: None,
    )

    _publish_diagnostics(cast(Any, fake_ls), cast(Any, document), include_semantic=False, include_comment_validation=False)
    syntax_only_result = fake_ls.document_states[uri].analysis_result
    snapshot = _get_or_build_local_snapshot(cast(Any, fake_ls), cast(Any, document), entry_file)

    assert snapshot is expected_snapshot
    assert calls == [
        (False, None),
        (True, syntax_only_result),
    ]


def test_get_or_build_local_snapshot_passes_previous_result_and_changed_ranges_to_adapter(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    uri = entry_file.resolve().as_uri()
    original_text = "Alpha = 1;\n"
    updated_text = "Beta = 1;\n"
    document = SimpleNamespace(uri=uri, source=updated_text, version=2)
    state = DocumentState(uri=uri, path=entry_file, version=1, text=original_text)
    previous_result = DocumentParseResult(
        syntax_diagnostics=(),
        local_snapshot=None,
        adapter_state={"tree": "old"},
    )
    state.remember_analysis(previous_result, include_comment_validation=False)
    state.apply_changes(
        version=2,
        content_changes=[
            SimpleNamespace(
                range=Range(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=5),
                ),
                text="Beta",
            )
        ],
        fallback_text=updated_text,
    )

    expected_snapshot = cast(Any, object())
    captured: dict[str, Any] = {}

    class RecordingParser:
        def analyze(
            self,
            document_path: Path,
            text: str,
            *,
            include_comment_validation: bool = True,
            build_snapshot: bool = True,
            previous_result: DocumentParseResult | None = None,
            changed_line_ranges: tuple[tuple[int, int], ...] = (),
        ) -> DocumentParseResult:
            captured["document_path"] = document_path
            captured["text"] = text
            captured["include_comment_validation"] = include_comment_validation
            captured["build_snapshot"] = build_snapshot
            captured["previous_result"] = previous_result
            captured["changed_line_ranges"] = changed_line_ranges
            return DocumentParseResult(syntax_diagnostics=(), local_snapshot=expected_snapshot)

    fake_ls = SimpleNamespace(
        document_states={uri: state},
        local_parser=RecordingParser(),
    )

    snapshot = _get_or_build_local_snapshot(cast(Any, fake_ls), cast(Any, document), entry_file)

    assert snapshot is expected_snapshot
    assert captured["document_path"] == entry_file
    assert captured["text"] == updated_text
    assert captured["include_comment_validation"] is False
    assert captured["build_snapshot"] is True
    assert captured["previous_result"] is previous_result
    assert captured["changed_line_ranges"] == state.changed_line_ranges


def test_incremental_parser_reuses_prefix_checkpoint_after_edit(tmp_path):
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

    updated_source = source.replace("Dv = 1;", "Dv = 2;")
    changed_line = updated_source.splitlines().index("        Dv = 2;")
    adapter = FullDocumentParserAdapter()
    document_path = tmp_path / "Program" / "Main.s"

    first = adapter.analyze(document_path, source, build_snapshot=False, include_comment_validation=False)
    second = adapter.analyze(
        document_path,
        updated_source,
        build_snapshot=False,
        include_comment_validation=False,
        previous_result=first,
        changed_line_ranges=((changed_line, changed_line),),
    )

    assert second.syntax_diagnostics == ()
    assert isinstance(second.adapter_state, IncrementalParseState)
    assert second.adapter_state.reused_prefix_char_pos > 0
    assert second.adapter_state.reused_prefix_line <= (changed_line + 1)


def test_incremental_parser_reuses_same_version_base_picture_for_snapshot_upgrade(monkeypatch, tmp_path):
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

    adapter = FullDocumentParserAdapter()
    document_path = tmp_path / "Program" / "Main.s"
    syntax_only = adapter.analyze(document_path, source, build_snapshot=False, include_comment_validation=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("same-version snapshot upgrade should reuse the cached BasePicture")

    monkeypatch.setattr(adapter, "_parse_incrementally", fail_if_called)

    upgraded = adapter.analyze(
        document_path,
        source,
        build_snapshot=True,
        include_comment_validation=False,
        previous_result=syntax_only,
        changed_line_ranges=(),
    )

    assert upgraded.syntax_diagnostics == ()
    assert upgraded.local_snapshot is not None


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
    _write_text(entry_file, source)
    workspace_snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False)
    by_name, by_key = build_source_path_index(workspace_snapshot.project_graph.source_files)
    bundle = SnapshotBundle(snapshot=workspace_snapshot, source_paths_by_name=by_name, source_paths_by_key=by_key)

    from sattlint.editor_api import load_source_snapshot

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
