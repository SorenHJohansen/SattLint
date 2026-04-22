from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from lsprotocol.types import CompletionItem as LspCompletionItem
from lsprotocol.types import CompletionItemKind, Position, Range

from sattlint.analyzers.registry import get_declared_lsp_analyzer_keys
from sattlint.core.diagnostics import SemanticDiagnostic
from sattlint.editor_api import load_workspace_snapshot
from sattlint_lsp.document_state import DocumentState, apply_content_changes
from sattlint_lsp.local_parser import DocumentParseResult, FullDocumentParserAdapter, IncrementalParseState
from sattlint_lsp.server import (
    LspSettings,
    SattLineLanguageServer,
    SnapshotBundle,
    _get_or_build_local_snapshot,
    _invalidate_cached_entries_for_path,
    _load_snapshot_bundle,
    _overlay_definition_candidates,
    _publish_closed_document_diagnostics,
    _publish_diagnostics,
    _publish_workspace_diagnostics_for_paths,
    _semantic_diagnostics_for_path,
    build_source_path_index,
    collect_completion_candidates,
    collect_local_completion_candidates,
    collect_local_definition_locations,
    collect_semantic_diagnostics,
    collect_syntax_diagnostics,
    infer_module_path_from_source,
    on_completion,
    on_definition,
    on_did_close,
    on_hover,
    on_references,
    on_rename,
    resolve_definition_path,
    resolve_entry_file,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _snapshot_bundle(snapshot, entry_file: Path) -> SnapshotBundle:
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


def _record_library_source(record_name: str, field_name: str) -> str:
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


def _program_with_dependency(record_name: str) -> str:
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


def _source_with_unused_variable(variable_name: str = "UnusedVar") -> str:
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


def _contract_library_source() -> str:
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


def _program_with_contract_mismatch_dependency() -> str:
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


def _source_with_basepicture_direct_code() -> str:
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


def test_publish_diagnostics_ignores_dependency_list_documents(monkeypatch, tmp_path):
    published = []
    fake_ls = SimpleNamespace(
        settings=SimpleNamespace(enable_variable_diagnostics=True),
        document_states={"file:///Libs/Support.l": object()},
        local_parser=FullDocumentParserAdapter(),
        text_document_publish_diagnostics=lambda params: published.append(params),
    )
    fake_document = SimpleNamespace(
        uri="file:///Libs/Support.l",
        source="Support\nOtherDep\n",
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: tmp_path / "Libs" / "Support.l")

    _publish_diagnostics(cast(Any, fake_ls), cast(Any, fake_document))

    assert len(published) == 1
    assert published[0].uri == "file:///Libs/Support.l"
    assert published[0].diagnostics == []
    assert "file:///Libs/Support.l" not in fake_ls.document_states


def test_load_snapshot_bundle_prefers_sibling_library_cluster(tmp_path):
    entry_file = tmp_path / "Libs" / "HA" / "ProjectLib" / "Main.s"
    _write_text(entry_file, _program_with_dependency("SupportRec"))
    _write_text(entry_file.with_suffix(".l"), "Support\n")
    _write_text(tmp_path / "Libs" / "HA" / "NNELib" / "Support.s", _record_library_source("SupportRec", "SiblingField"))
    _write_text(tmp_path / "AFallbackLib" / "Support.s", _record_library_source("SupportRec", "FallbackField"))

    fake_ls = SattLineLanguageServer()
    fake_ls.workspace_root = tmp_path
    fake_ls.settings = LspSettings(enable_variable_diagnostics=False)

    bundle = _load_snapshot_bundle(cast(Any, fake_ls), entry_file)

    assert bundle is not None
    assert bundle.snapshot.find_definitions("BasePicture.Dep.SiblingField")
    assert bundle.snapshot.find_definitions("BasePicture.Dep.FallbackField") == []


def test_load_snapshot_bundle_allows_reused_invocation_name_for_moduletype_instance(tmp_path):
    entry_file = tmp_path / "Programs" / "Main.s"
    _write_text(
        entry_file,
        """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 3
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*Child*);
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
""".strip(),
    )

    fake_ls = SattLineLanguageServer()
    fake_ls.workspace_root = tmp_path
    fake_ls.settings = LspSettings(enable_variable_diagnostics=False)

    bundle = _load_snapshot_bundle(cast(Any, fake_ls), entry_file)

    assert bundle is not None


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


def test_collect_syntax_diagnostics_reports_first_parse_error(tmp_path):
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

    assert len(diagnostics) >= 1
    assert "Expected one of:" in diagnostics[0].message
    assert "^" in diagnostics[0].message


def test_collect_syntax_diagnostics_does_not_report_unknown_type_suggestion(tmp_path):
    # validate_transformed_basepicture is intentionally excluded from the local
    # incremental parser (it requires full library context, is slow on large files,
    # and produces false positives for library files). Datatype-typo suggestions
    # are therefore not reported as real-time LSP diagnostics; they are only caught
    # by the CLI syntax-check command and during workspace snapshot loading.
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
    assert len(diagnostics) == 0


def test_lsp_settings_defaults_workspace_diagnostics_off():
    settings = LspSettings.from_initialization_options({})

    assert settings.workspace_diagnostics_mode == "off"


def test_collect_syntax_diagnostics_reports_invalid_sequence_auto_variables(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    si: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION Tr1 WAIT_FOR False
    ENDSEQUENCE
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF CompareGoldens.X THEN
            si = 1;
        ENDIF;
        IF Start.T > 0 THEN
            si = 2;
        ENDIF;
        IF Start.Reset THEN
            si = 3;
        ENDIF;
        IF Start.Hold THEN
            si = 4;
        ENDIF;
ENDDEF (*BasePicture*);
""".strip()

    diagnostics = collect_syntax_diagnostics(tmp_path / "Program.s", source)

    assert len(diagnostics) == 4
    assert any(
        "no sequence step named 'CompareGoldens' exists in this module" in diagnostic.message
        for diagnostic in diagnostics
    )
    assert any("only exposes .T when its sequence enables SeqTimer" in diagnostic.message for diagnostic in diagnostics)
    assert any(
        "only exposes .Reset when its sequence enables SeqControl" in diagnostic.message for diagnostic in diagnostics
    )
    assert any(
        "only exposes .Hold when its sequence enables SeqControl" in diagnostic.message for diagnostic in diagnostics
    )


def test_collect_syntax_diagnostics_allows_valid_sequence_auto_variables(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    si: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION Tr1 WAIT_FOR False
    ENDSEQUENCE
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF Start.X AND Start.T >= 0 AND NOT Start.Reset AND NOT Start.Hold THEN
            si = 1;
        ENDIF;
ENDDEF (*BasePicture*);
""".strip()

    diagnostics = collect_syntax_diagnostics(tmp_path / "Program.s", source)

    assert diagnostics == []


def test_collect_syntax_diagnostics_allows_step_x_without_seqcontrol(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    si: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION Tr1 WAIT_FOR False
    ENDSEQUENCE
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF Start.X THEN
            si = 1;
        ENDIF;
ENDDEF (*BasePicture*);
""".strip()

    diagnostics = collect_syntax_diagnostics(tmp_path / "Program.s", source)

    assert diagnostics == []


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
    items = collect_completion_candidates(
        snapshot, editing_source, line=line_index, column=len("            Lo"), limit=20
    )
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
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("syntax-only didChange should not build a local snapshot")
        ),
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
    bundle = _snapshot_bundle(snapshot, entry_file)

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


def test_publish_diagnostics_limits_workspace_failure_to_active_file(monkeypatch, tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
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
    monkeypatch.setattr(
        "sattlint_lsp.server._load_snapshot_bundle",
        lambda ls, path: (_ for _ in ()).throw(
            type(
                "WorkspaceFailure",
                (RuntimeError,),
                {"line": 11, "column": 24, "length": 12},
            )(
                "Target 'Main' failed parse/transform: root issue\n"
                "Resolved targets (2): Main, Support\n"
                "Unavailable libraries (1):\n"
                "- controllib (expected proprietary dependency)\n"
                "Other dependency issues (1):\n"
                "- Support parse/transform error: dependency issue"
            )
        ),
    )

    _publish_diagnostics(cast(Any, fake_ls), cast(Any, fake_document))

    assert len(published) == 1
    assert len(published[0].diagnostics) == 1
    assert published[0].diagnostics[0].message == "Target 'Main' failed parse/transform: root issue"
    assert published[0].diagnostics[0].range.start.line == 10
    assert published[0].diagnostics[0].range.start.character == 23
    assert published[0].diagnostics[0].range.end.character == 35


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
    bundle = _snapshot_bundle(snapshot, entry_file)

    diagnostics = collect_semantic_diagnostics(cast(Any, bundle), entry_file)
    target = next(d for d in diagnostics if d.message.startswith("Unused variable"))

    assert target.range.start.line == 5
    assert target.range.start.character == 4
    assert target.code == "variables"
    assert "Why it matters:" in target.message
    assert "Suggested fix:" in target.message
    assert "Delete the declaration" in target.message


def test_collect_semantic_diagnostics_preserves_declared_lsp_analyzer_identity(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, _source_with_unused_variable())
    expected = tuple(
        SemanticDiagnostic(
            source_file=entry_file.name,
            source_library=entry_file.parent.name,
            line=index,
            column=1,
            length=1,
            message=f"diagnostic from {analyzer_key}",
            analyzer_key=analyzer_key,
        )
        for index, analyzer_key in enumerate(get_declared_lsp_analyzer_keys(), start=1)
    )
    bundle = SimpleNamespace(
        snapshot=SimpleNamespace(
            semantic_diagnostics_for_path=lambda resolved_path: (
                expected if resolved_path == entry_file.resolve() else ()
            )
        )
    )

    diagnostics = collect_semantic_diagnostics(cast(Any, bundle), entry_file)

    assert [diagnostic.code for diagnostic in diagnostics] == list(get_declared_lsp_analyzer_keys())
    assert all(diagnostic.source == "sattlint" for diagnostic in diagnostics)


def test_collect_semantic_diagnostics_include_actionable_guidance_for_contract_mismatch(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    library_file = tmp_path / "Libs" / "Mismatch.s"
    _write_text(entry_file, _program_with_contract_mismatch_dependency())
    _write_text(entry_file.with_suffix(".l"), "Mismatch\n")
    _write_text(library_file, _contract_library_source())

    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=True)
    bundle = _snapshot_bundle(snapshot, entry_file)

    diagnostics = collect_semantic_diagnostics(bundle, library_file)
    target = next(d for d in diagnostics if d.message.startswith("Cross-module contract mismatch"))

    assert "integer" in target.message
    assert "real" in target.message
    assert "Why it matters:" in target.message
    assert "Suggested fix:" in target.message
    assert "Align the source and target datatypes" in target.message


def test_collect_semantic_diagnostics_include_actionable_guidance_for_spec_compliance_issue(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, _source_with_basepicture_direct_code())

    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=True)
    bundle = _snapshot_bundle(snapshot, entry_file)

    diagnostics = collect_semantic_diagnostics(bundle, entry_file)
    target = next(d for d in diagnostics if d.code == "spec-compliance")

    assert target.message.startswith("BasePicture contains direct code")
    assert "Why it matters:" in target.message
    assert "Suggested fix:" in target.message
    assert "BasePicture code must stay inside frame modules" in target.message


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
    bundle = _snapshot_bundle(snapshot, entry_file)
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

    monkeypatch.setattr(
        "sattlint_lsp.local_parser.build_source_snapshot_from_basepicture", wrapped_build_source_snapshot
    )
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

    _publish_diagnostics(
        cast(Any, fake_ls), cast(Any, document), include_semantic=False, include_comment_validation=False
    )
    syntax_only_result = fake_ls.document_states[uri].analysis_result
    snapshot = _get_or_build_local_snapshot(cast(Any, fake_ls), cast(Any, document), entry_file)

    assert snapshot is expected_snapshot
    assert calls == [
        (False, None),
        (True, syntax_only_result),
    ]


def test_publish_workspace_diagnostics_for_paths_deduplicates_shared_library_diagnostics(tmp_path):
    shared = (tmp_path / "Libs" / "Shared.s").resolve()
    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Unused variable: localvariable",
            severity=1,
            source="sattlint",
        ),
    )
    ls = SattLineLanguageServer()
    ls.workspace_root = tmp_path
    ls.settings = LspSettings(enable_variable_diagnostics=True, workspace_diagnostics_mode="background")
    ls.entry_diagnostics = {
        "entry-a": {shared: (diagnostic,)},
        "entry-b": {shared: (diagnostic,)},
    }

    _publish_workspace_diagnostics_for_paths(ls, {shared})

    assert shared in ls.published_workspace_diagnostics
    assert len(ls.published_workspace_diagnostics[shared]) == 1
    assert ls.published_workspace_diagnostics[shared][0].message.startswith("Unused variable")


def test_publish_closed_document_diagnostics_restores_workspace_diagnostics(tmp_path):
    path = (tmp_path / "Libs" / "Shared.s").resolve()
    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Unused variable",
            severity=1,
            source="sattlint",
        ),
    )
    published = []

    ls = SattLineLanguageServer()
    ls.text_document_publish_diagnostics = lambda params: published.append(params)
    ls.entry_diagnostics = {"entry": {path: (diagnostic,)}}

    _publish_closed_document_diagnostics(ls, path)

    assert len(published) == 1
    assert published[0].uri.casefold() == path.as_uri().casefold()
    assert len(published[0].diagnostics) == 1
    assert published[0].diagnostics[0].message == "Unused variable"
    assert ls.published_workspace_diagnostics[path][0].message == "Unused variable"


def test_publish_closed_document_diagnostics_loads_snapshot_when_cache_is_empty(monkeypatch, tmp_path):
    path = (tmp_path / "Program" / "Main.s").resolve()
    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=1, character=2), end=Position(line=1, character=5)),
            message="Variable is written but never read",
            severity=2,
            source="sattlint",
        ),
    )
    published = []
    fake_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=path,
        cache_key=path.as_posix().casefold(),
        source_files=(path,),
    )

    ls = SattLineLanguageServer()
    ls.text_document_publish_diagnostics = lambda params: published.append(params)

    monkeypatch.setattr("sattlint_lsp.server._load_snapshot_bundle", lambda server, document_path: fake_bundle)
    monkeypatch.setattr("sattlint_lsp.server.collect_semantic_diagnostics", lambda bundle, document_path: [diagnostic])

    _publish_closed_document_diagnostics(ls, path)

    assert len(published) == 1
    assert published[0].uri.casefold() == path.as_uri().casefold()
    assert len(published[0].diagnostics) == 1
    assert published[0].diagnostics[0].message == "Variable is written but never read"
    assert ls.published_workspace_diagnostics[path][0].message == "Variable is written but never read"


def test_semantic_diagnostics_for_path_reuses_bundle_cache(monkeypatch, tmp_path):
    path = (tmp_path / "Program" / "Main.s").resolve()
    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Unused variable",
            severity=1,
            source="sattlint",
        ),
    )
    bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=path,
        cache_key=path.as_posix().casefold(),
        source_files=(path,),
    )
    calls = 0

    def fake_collect(current_bundle, document_path):
        nonlocal calls
        calls += 1
        assert current_bundle is bundle
        assert document_path == path
        return [diagnostic]

    monkeypatch.setattr("sattlint_lsp.server.collect_semantic_diagnostics", fake_collect)

    first = _semantic_diagnostics_for_path(bundle, path)
    second = _semantic_diagnostics_for_path(bundle, path)

    assert len(first) == 1
    assert first is second
    assert first[0].message == "Unused variable"
    assert calls == 1


def test_on_did_close_clears_stale_diagnostics_when_no_workspace_diagnostics_exist(tmp_path):
    path = (tmp_path / "Program" / "Main.s").resolve()
    uri = path.as_uri()
    published = []

    ls = SattLineLanguageServer()
    ls.text_document_publish_diagnostics = lambda params: published.append(params)
    ls.document_states[uri] = DocumentState(
        uri=uri,
        path=path,
        version=2,
        text="Alpha = ;\n",
        is_dirty=True,
    )

    on_did_close(ls, cast(Any, SimpleNamespace(text_document=SimpleNamespace(uri=uri))))

    assert uri not in ls.document_states
    assert len(published) == 1
    assert published[0].uri.casefold() == uri.casefold()
    assert published[0].diagnostics == []


def test_invalidate_cached_entries_for_path_marks_affected_entries_stale(tmp_path):
    entry_a = (tmp_path / "Programs" / "PlantA.s").resolve()
    entry_b = (tmp_path / "Programs" / "PlantB.s").resolve()
    shared = (tmp_path / "Libs" / "Shared.s").resolve()
    other = (tmp_path / "Libs" / "Other.s").resolve()

    diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Unused variable",
            severity=1,
            source="sattlint",
        ),
    )
    key_a = entry_a.as_posix().casefold()
    key_b = entry_b.as_posix().casefold()
    bundle_a = SnapshotBundle(
        snapshot=cast(Any, None),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry_a,
        cache_key=key_a,
        source_files=(entry_a, shared),
    )
    bundle_b = SnapshotBundle(
        snapshot=cast(Any, None),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry_b,
        cache_key=key_b,
        source_files=(entry_b, other),
    )

    ls = SattLineLanguageServer()
    ls.workspace_root = tmp_path
    ls.settings = LspSettings(enable_variable_diagnostics=True, workspace_diagnostics_mode="background")
    ls.snapshot_store.ensure_configured(tmp_path, ls.settings)
    with ls.snapshot_store._lock:
        state_a = ls.snapshot_store._state_for_entry_locked(entry_a)
        state_a.bundle = bundle_a
        state_b = ls.snapshot_store._state_for_entry_locked(entry_b)
        state_b.bundle = bundle_b
        ls.snapshot_store._source_file_to_entry_keys = {
            entry_a: {key_a},
            shared: {key_a},
            entry_b: {key_b},
            other: {key_b},
        }
    ls.entry_diagnostics = {
        key_a: {shared: (diagnostic,)},
        key_b: {other: (diagnostic,)},
    }
    ls.published_workspace_diagnostics = {shared: (diagnostic,), other: (diagnostic,)}

    affected_entries = _invalidate_cached_entries_for_path(ls, shared)

    assert affected_entries == (entry_a,)
    with ls.snapshot_store._lock:
        assert ls.snapshot_store._states[key_a].stale is True
        assert ls.snapshot_store._states[key_b].stale is False
        assert shared in ls.snapshot_store._source_file_to_entry_keys
    assert shared not in ls.published_workspace_diagnostics
    assert other in ls.published_workspace_diagnostics


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
    _write_text(entry_file, source)
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

    monkeypatch.setattr("sattlint_lsp.server._load_snapshot_bundle", lambda ls, path, **kwargs: None)

    hover = on_hover(cast(Any, fake_ls), cast(Any, params))

    assert hover is not None
    hover_text = cast(Any, hover).contents.value
    assert "Dv" in hover_text
    assert "integer" in hover_text


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
    _write_text(entry_file, source)
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

    monkeypatch.setattr("sattlint_lsp.server._load_snapshot_bundle", lambda ls, path, **kwargs: None)

    locations = on_references(cast(Any, fake_ls), cast(Any, params))

    assert locations is not None
    assert len(locations) == 3
    assert all(location.uri.casefold() == document.uri.casefold() for location in locations)


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
    _write_text(entry_file, source)
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

    monkeypatch.setattr("sattlint_lsp.server._load_snapshot_bundle", lambda ls, path, **kwargs: None)

    edit = on_rename(cast(Any, fake_ls), cast(Any, params))

    assert edit is not None
    changes = cast(Any, edit).changes
    assert changes is not None
    matching_uri = next((uri for uri in changes if uri.casefold() == document.uri.casefold()), None)
    assert matching_uri is not None
    assert len(changes[matching_uri]) == 3
    assert all(item.new_text == "Renamed" for item in changes[matching_uri])


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
    workspace_snapshot = load_workspace_snapshot(
        entry_file, workspace_root=tmp_path, collect_variable_diagnostics=False
    )
    bundle = _snapshot_bundle(workspace_snapshot, entry_file)

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


def test_on_definition_falls_back_to_local_snapshot_when_workspace_snapshot_fails(monkeypatch, tmp_path):
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
        "sattlint_lsp.server._load_snapshot_bundle", lambda ls, path: (_ for _ in ()).throw(RuntimeError("boom"))
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
    _write_text(entry_file, source)
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
        "sattlint_lsp.server._load_snapshot_bundle", lambda ls, path: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    result = on_completion(cast(Any, fake_ls), cast(Any, params))

    assert any(item.label == "Dv" for item in result.items)


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
