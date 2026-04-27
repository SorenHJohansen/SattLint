"""Tests for LSP entry-file resolution, diagnostic publishing (syntax and semantic), module-path inference, completion candidates, and definition/reference resolution."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattlint.analyzers.registry import get_declared_lsp_analyzer_keys
from sattlint.core.diagnostics import SemanticDiagnostic
from sattlint.editor_api import load_workspace_snapshot
from sattlint_lsp.local_parser import FullDocumentParserAdapter
from sattlint_lsp.server import (
    LspSettings,
    SattLineLanguageServer,
    SnapshotBundle,
    _load_snapshot_bundle,
    _publish_diagnostics,
    build_source_path_index,
    collect_completion_candidates,
    collect_local_completion_candidates,
    collect_local_definition_locations,
    collect_semantic_diagnostics,
    collect_syntax_diagnostics,
    infer_module_path_from_source,
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
