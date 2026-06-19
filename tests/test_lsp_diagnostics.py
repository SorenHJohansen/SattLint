# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
"""Tests for LSP entry-file resolution and diagnostics.

Covers syntax and semantic publishing, module-path inference,
completion candidates, and definition/reference resolution.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from lsprotocol.types import CompletionItem as LspCompletionItem
from lsprotocol.types import CompletionItemKind, Diagnostic, DiagnosticSeverity, Position, Range

from sattline_parser.models.ast_model import Simple_DataType, SourceSpan, Variable
from sattlint.analyzers.framework import Issue
from sattlint.core.diagnostics import (
    DroppedDiagnosticIssue,
    SemanticDiagnostic,
    project_report_issues,
    project_variable_issues,
)
from sattlint.core.semantic import SymbolDefinition, SymbolReference
from sattlint.editor_api import load_workspace_snapshot
from sattlint.reporting.variables_report import IssueKind, VariableIssue
from sattlint_lsp import _server_helpers as lsp_helpers
from sattlint_lsp.local_parser import FullDocumentParserAdapter
from sattlint_lsp.server import (
    LspSettings,
    SattLineLanguageServer,
    SnapshotBundle,
    _load_snapshot_bundle,
    _publish_diagnostics,
    build_source_path_index,
    collect_semantic_diagnostics,
    collect_syntax_diagnostics,
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

    monkeypatch.setattr(
        "sattlint_lsp._server_document._document_path", lambda document: tmp_path / "Libs" / "Support.l"
    )

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


def test_collect_syntax_diagnostics_preserves_original_column_after_inline_comment(tmp_path):
    source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    DemoValue: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        DemoValue = 1; (* inline comment *) ???
ENDDEF (*BasePicture*);
""".strip()

    diagnostics = collect_syntax_diagnostics(tmp_path / "Program.s", source)

    assert len(diagnostics) >= 1
    assert diagnostics[0].range.start.line == 10
    assert diagnostics[0].range.start.character == source.splitlines()[10].index("?")
    assert "(* inline comment *) ???" in diagnostics[0].message


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


def test_collect_syntax_diagnostics_reports_invalid_sequence_scope_auto_variables(tmp_path):
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
        IF MainSeq.Reset THEN
            si = 1;
        ENDIF;
        IF MainSeq.Hold THEN
            si = 2;
        ENDIF;
ENDDEF (*BasePicture*);
""".strip()

    diagnostics = collect_syntax_diagnostics(tmp_path / "Program.s", source)

    assert len(diagnostics) == 2
    assert any(
        "sequence 'MainSeq' only exposes .Reset when it enables SeqControl" in diagnostic.message
        for diagnostic in diagnostics
    )
    assert any(
        "sequence 'MainSeq' only exposes .Hold when it enables SeqControl" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_collect_syntax_diagnostics_allows_valid_sequence_scope_auto_variables(tmp_path):
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
    SEQUENCE MainSeq (SeqControl) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION Tr1 WAIT_FOR False
    ENDSEQUENCE
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF NOT MainSeq.Reset AND NOT MainSeq.Hold THEN
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

    monkeypatch.setattr(
        "sattlint_lsp._server_document._document_path", lambda document: tmp_path / "Program" / "Main.s"
    )
    monkeypatch.setattr("sattlint_lsp._server_document._load_snapshot_bundle", fail_if_called)
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

    monkeypatch.setattr(
        "sattlint_lsp._server_document._document_path", lambda document: tmp_path / "Program" / "Main.s"
    )

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

    monkeypatch.setattr("sattlint_lsp._server_document._document_path", lambda document: entry_file)
    monkeypatch.setattr("sattlint_lsp._server_document._load_snapshot_bundle", lambda ls, path: bundle)

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

    monkeypatch.setattr(
        "sattlint_lsp._server_document._document_path", lambda document: tmp_path / "Program" / "Main.s"
    )
    monkeypatch.setattr(
        "sattlint_lsp._server_document._load_snapshot_bundle",
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
    from sattlint.analyzers.registry import get_declared_lsp_analyzer_keys  # noqa: PLC0415

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


def test_project_report_issues_records_missing_module_site_drop():
    issue = Issue(kind="spec.issue", message="missing site", module_path=["BasePicture", "Ghost"])

    result = project_report_issues((issue,), {}, analyzer_key="spec-compliance")

    assert result.diagnostics_by_file == {}
    assert result.dropped_issues == (
        DroppedDiagnosticIssue(
            analyzer_key="spec-compliance",
            reason="missing-module-site",
            module_path=("BasePicture", "Ghost"),
            message="missing site",
        ),
    )


def test_project_variable_issues_records_missing_definition_drop():
    issue = VariableIssue(
        kind=IssueKind.UNUSED,
        module_path=["BasePicture"],
        variable=Variable(name="MissingVar", datatype=Simple_DataType.INTEGER),
    )

    result = project_variable_issues((issue,), {})

    assert result.diagnostics_by_file == {}
    assert len(result.dropped_issues) == 1
    assert result.dropped_issues[0].analyzer_key == "variables"
    assert result.dropped_issues[0].reason == "missing-definition"
    assert result.dropped_issues[0].module_path == ("BasePicture",)
    assert result.dropped_issues[0].variable_name == "MissingVar"


def test_load_workspace_snapshot_exposes_semantic_projection_drops(monkeypatch, tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    _write_text(entry_file, _source_with_unused_variable())

    fake_analyzer = SimpleNamespace(
        spec=SimpleNamespace(
            key="fake-lsp",
            run=lambda _context: SimpleNamespace(
                issues=[Issue(kind="fake.rule", message="dropped issue", module_path=["BasePicture", "MissingModule"])]
            ),
        ),
        delivery=SimpleNamespace(lsp_exposed=True),
    )

    monkeypatch.setattr(
        "sattlint.analyzers.registry.get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=(fake_analyzer,)),
    )

    snapshot = load_workspace_snapshot(entry_file, workspace_root=tmp_path, collect_variable_diagnostics=True)

    assert snapshot.semantic_diagnostic_drops() == (
        DroppedDiagnosticIssue(
            analyzer_key="fake-lsp",
            reason="missing-module-site",
            module_path=("BasePicture", "MissingModule"),
            message="dropped issue",
        ),
    )


def test_lsp_helper_request_validation_covers_valid_and_invalid_shapes():
    assert lsp_helpers._validated_text_document_uri(SimpleNamespace(text_document=SimpleNamespace(uri=""))) is None
    assert (
        lsp_helpers._validated_text_document_uri(SimpleNamespace(text_document=SimpleNamespace(uri="file:///Main.s")))
        == "file:///Main.s"
    )

    valid_position = SimpleNamespace(
        text_document=SimpleNamespace(uri="file:///Main.s"),
        position=SimpleNamespace(line=3, character=4),
    )
    assert lsp_helpers._validated_text_document_position(valid_position) == ("file:///Main.s", 3, 4)
    assert (
        lsp_helpers._validated_text_document_position(
            SimpleNamespace(
                text_document=SimpleNamespace(uri="file:///Main.s"),
                position=SimpleNamespace(line=-1, character=4),
            )
        )
        is None
    )

    valid_open = SimpleNamespace(
        text_document=SimpleNamespace(uri="file:///Main.s", version=2, text="abc"),
    )
    assert lsp_helpers._validated_open_request(valid_open) == ("file:///Main.s", 2, "abc")
    assert (
        lsp_helpers._validated_open_request(
            SimpleNamespace(text_document=SimpleNamespace(uri="file:///Main.s", version="2", text="abc"))
        )
        is None
    )

    valid_change = SimpleNamespace(
        text_document=SimpleNamespace(uri="file:///Main.s", version=4),
        content_changes=(SimpleNamespace(text="x"),),
    )
    change_request = lsp_helpers._validated_change_request(valid_change)
    assert change_request is not None
    assert change_request[0] == "file:///Main.s"
    assert change_request[1] == 4
    assert len(change_request[2]) == 1
    assert change_request[2][0].text == "x"
    assert (
        lsp_helpers._validated_change_request(
            SimpleNamespace(text_document=SimpleNamespace(uri="file:///Main.s", version=4), content_changes="bad")
        )
        is None
    )

    valid_rename = SimpleNamespace(
        text_document=SimpleNamespace(uri="file:///Main.s"),
        position=SimpleNamespace(line=0, character=0),
        new_name="Renamed",
    )
    assert lsp_helpers._validated_rename_request(valid_rename) == ("file:///Main.s", 0, 0, "Renamed")
    assert (
        lsp_helpers._validated_rename_request(
            SimpleNamespace(
                text_document=SimpleNamespace(uri="file:///Main.s"),
                position=SimpleNamespace(line=0, character=0),
                new_name=1,
            )
        )
        is None
    )


def test_lsp_workspace_diagnostics_mode_and_rename_target_validation():
    assert lsp_helpers._normalize_workspace_diagnostics_mode("off") == "off"
    assert lsp_helpers._normalize_workspace_diagnostics_mode("background") == "background"
    assert lsp_helpers._normalize_workspace_diagnostics_mode("unexpected") == "background"

    lsp_helpers._validate_rename_target("OkName")
    lsp_helpers._validate_rename_target("'Quoted Name'")

    with pytest.raises(ValueError, match="valid SattLine identifier"):
        lsp_helpers._validate_rename_target("bad name with spaces")
    with pytest.raises(ValueError, match="exceeds"):
        lsp_helpers._validate_rename_target("ABCDEFGHIJKLMNOPQRSTU")


def test_lsp_helper_path_range_and_message_utilities_cover_edge_cases(tmp_path):
    assert lsp_helpers._is_program_path(Path("Main.S"))
    assert lsp_helpers._is_diagnostic_path(Path("Main.G"))
    assert lsp_helpers._path_startswith(("BasePicture", "Child"), ("basepicture",))
    assert not lsp_helpers._path_startswith(("BasePicture",), ("BasePicture", "Child"))

    no_span_definition = SymbolDefinition(
        canonical_path="BasePicture.Child.LocalVar",
        kind="local",
        datatype="integer",
        declaration_module_path=("BasePicture", "Child"),
        display_module_path=("BasePicture", "Child"),
        declaration_span=None,
    )
    assert lsp_helpers._range_for_definition(no_span_definition) is None

    field_definition = SymbolDefinition(
        canonical_path="BasePicture.Child.LocalVar",
        kind="local",
        datatype="integer",
        declaration_module_path=("BasePicture", "Child"),
        display_module_path=("BasePicture", "Child"),
        field_path="Child.LocalVar",
        declaration_span=SourceSpan(4, 2),
    )
    field_range = lsp_helpers._range_for_definition(field_definition)
    assert field_range is not None
    assert field_range.start.line == 3
    assert field_range.start.character == 1
    assert field_range.end.character == 9

    default_diagnostic = lsp_helpers._diagnostic_from_message("broken", None, None)
    assert default_diagnostic.severity == DiagnosticSeverity.Error
    assert default_diagnostic.range.start.line == 0
    assert default_diagnostic.range.end.character == 1

    explicit_diagnostic = lsp_helpers._diagnostic_from_message("broken", 2, 3)
    assert explicit_diagnostic.range.start.line == 1
    assert explicit_diagnostic.range.start.character == 2
    assert explicit_diagnostic.range.end.character == 10

    failure_message = "\n\n  Root cause\nResolved targets (2)\n- LibA\n"
    assert lsp_helpers._root_workspace_failure_message(failure_message) == "Root cause"
    assert lsp_helpers._root_workspace_failure_message("\n\n") == "\n\n"

    document_path = tmp_path / "Program" / "Main.s"
    _write_text(document_path, '"x"\n"y"\n"z"\n')
    assert lsp_helpers._document_uri_for_path(document_path).casefold() == document_path.resolve().as_uri().casefold()


def test_lsp_helper_request_settings_and_merge_helpers_cover_optional_branches(tmp_path):  # noqa: PLR0915
    assert lsp_helpers._validated_text_document_uri(SimpleNamespace(text_document=SimpleNamespace(uri=1))) is None
    assert (
        lsp_helpers._validated_text_document_position(
            SimpleNamespace(
                text_document=SimpleNamespace(uri="file:///Main.s"),
                position=SimpleNamespace(line=1, character="bad"),
            )
        )
        is None
    )
    assert lsp_helpers._validated_change_request(
        SimpleNamespace(
            text_document=SimpleNamespace(uri="file:///Main.s", version=4),
            content_changes=None,
        )
    ) == ("file:///Main.s", 4, [])
    assert (
        lsp_helpers._validated_rename_request(
            SimpleNamespace(
                text_document=SimpleNamespace(uri="file:///Main.s"),
                position=SimpleNamespace(line=-1, character=0),
                new_name="Renamed",
            )
        )
        is None
    )

    assert LspSettings.from_initialization_options(None) == LspSettings()

    settings = LspSettings.from_initialization_options(
        {
            "entryFile": " Program/Main.s ",
            "mode": " RELEASE ",
            "scanRootOnly": 1,
            "enableVariableDiagnostics": 0,
            "workspaceDiagnosticsMode": " OFF ",
            "maxCachedEntrySnapshots": "0",
            "maxCompletionItems": "0",
        }
    )
    assert settings.entry_file == "Program/Main.s"
    assert settings.mode == "release"
    assert settings.scan_root_only is True
    assert settings.enable_variable_diagnostics is False
    assert settings.workspace_diagnostics_mode == "off"
    assert settings.max_cached_entry_snapshots == 1
    assert settings.max_completion_items == 1
    assert LspSettings.from_initialization_options({"maxCompletionItems": "bad"}).max_completion_items == 100
    assert LspSettings.from_initialization_options({"maxCachedEntrySnapshots": "bad"}).max_cached_entry_snapshots == 2

    diagnostic_b = Diagnostic(
        range=Range(start=Position(line=3, character=0), end=Position(line=3, character=1)),
        message="later",
        severity=DiagnosticSeverity.Warning,
        source="sattlint",
    )
    diagnostic_a = Diagnostic(
        range=Range(start=Position(line=1, character=0), end=Position(line=1, character=1)),
        message="earlier",
        severity=DiagnosticSeverity.Warning,
        source="sattlint",
    )
    merged_diagnostics = lsp_helpers._merge_unique_diagnostics((diagnostic_b,), (diagnostic_a, diagnostic_a))
    assert tuple(d.message for d in merged_diagnostics) == ("earlier", "later")

    local_definition = SymbolDefinition(
        canonical_path="BasePicture.Child.LocalVar",
        kind="local",
        datatype="integer",
        declaration_module_path=("BasePicture", "Child"),
        display_module_path=("BasePicture", "Child"),
        source_file="Main.s",
        source_library="Program",
        declaration_span=SourceSpan(4, 2),
    )
    parent_definition = SymbolDefinition(
        canonical_path="BasePicture.Child.LocalVar",
        kind="local",
        datatype="integer",
        declaration_module_path=("BasePicture",),
        display_module_path=("BasePicture",),
        source_file="Main.s",
        source_library="Program",
        declaration_span=SourceSpan(4, 2),
    )
    unrelated_definition = SymbolDefinition(
        canonical_path="Elsewhere.Value",
        kind="local",
        datatype="integer",
        declaration_module_path=("Elsewhere",),
        display_module_path=("Elsewhere",),
        source_file="Other.s",
        source_library="Program",
        declaration_span=SourceSpan(8, 4),
    )
    assert lsp_helpers._filter_visible_definitions([parent_definition, local_definition], "BasePicture.Child") == [
        local_definition,
        parent_definition,
    ]
    assert lsp_helpers._filter_visible_definitions([unrelated_definition], "BasePicture.Child") == [
        unrelated_definition
    ]

    assert lsp_helpers._reference_expr_at_position("Alpha.Beta = 1;", line=0, column=6) == "Alpha.Beta"
    assert lsp_helpers._reference_expr_at_position("Alpha.Beta = 1;", line=0, column=20) is None
    assert lsp_helpers._reference_expr_at_position("Alpha.Beta = 1;", line=2, column=0) is None

    assert lsp_helpers._semantic_completion_kind("local") == CompletionItemKind.Variable
    assert lsp_helpers._semantic_completion_kind("field") == CompletionItemKind.Field
    assert lsp_helpers._semantic_completion_kind("frame") == CompletionItemKind.Module
    assert lsp_helpers._semantic_completion_kind("other") == CompletionItemKind.Text

    primary_path = tmp_path / "Program" / "Main.s"
    alternate_path = tmp_path / "Libs" / "Support" / "Main.s"
    extra_path = tmp_path / "Libs" / "Backup" / "Main.s"
    _write_text(primary_path, '"x"\n"y"\n"z"\n')
    _write_text(alternate_path, '"x"\n"y"\n"z"\n')
    _write_text(extra_path, '"x"\n"y"\n"z"\n')
    direct_bundle = cast(
        Any,
        SimpleNamespace(
            source_paths_by_key={("main.s", "program"): primary_path.resolve()},
            source_paths_by_name={"main.s": (primary_path.resolve(), alternate_path.resolve())},
        ),
    )
    unique_bundle = cast(
        Any,
        SimpleNamespace(
            source_paths_by_key={},
            source_paths_by_name={"single.s": (alternate_path.resolve(),)},
        ),
    )
    ambiguous_bundle = cast(
        Any,
        SimpleNamespace(
            source_paths_by_key={},
            source_paths_by_name={"main.s": (primary_path.resolve(), alternate_path.resolve())},
        ),
    )
    assert lsp_helpers._resolve_bundle_source_path(direct_bundle, "Main.s", "Program") == primary_path.resolve()
    assert lsp_helpers._resolve_bundle_source_path(unique_bundle, "Single.s", None) == alternate_path.resolve()
    assert lsp_helpers._resolve_bundle_source_path(ambiguous_bundle, "Main.s", None) is None

    duplicate_definition = SymbolDefinition(
        canonical_path="basepicture.child.localvar",
        kind="local",
        datatype="integer",
        declaration_module_path=("BasePicture", "Child"),
        display_module_path=("BasePicture", "Child"),
        source_file="Main.s",
        source_library="Program",
        declaration_span=SourceSpan(4, 2),
    )
    merged_definitions = lsp_helpers._merge_definitions(
        [local_definition], [duplicate_definition, unrelated_definition]
    )
    assert merged_definitions == [local_definition, unrelated_definition]

    preferred_item = LspCompletionItem(label="Beta", kind=CompletionItemKind.Field)
    fallback_item = LspCompletionItem(label="alpha", kind=CompletionItemKind.Variable)
    duplicate_item = LspCompletionItem(label="Alpha", kind=CompletionItemKind.Variable)
    merged_items = lsp_helpers._merge_completion_items([preferred_item], [fallback_item, duplicate_item], limit=2)
    assert [(item.label, item.kind) for item in merged_items] == [
        ("alpha", CompletionItemKind.Variable),
        ("Beta", CompletionItemKind.Field),
    ]

    local_reference = SymbolReference(
        canonical_path="BasePicture.Child.LocalVar",
        source_file="Main.s",
        source_library="Program",
        line=9,
        column=13,
        length=8,
        text="LocalVar",
    )
    duplicate_reference = SymbolReference(
        canonical_path="basepicture.child.localvar",
        source_file="main.s",
        source_library="program",
        line=9,
        column=13,
        length=8,
        text="LocalVar",
    )
    external_reference = SymbolReference(
        canonical_path="Elsewhere.Value",
        source_file="Other.s",
        source_library="Support",
        line=4,
        column=2,
        length=5,
        text="Value",
    )
    merged_references = lsp_helpers._merge_references([local_reference], [duplicate_reference, external_reference])
    assert merged_references == [local_reference, external_reference]


def test_lsp_helper_location_and_edit_helpers_cover_local_workspace_and_missing_targets(tmp_path):
    active_document = tmp_path / "Program" / "Main.s"
    dependency_document = tmp_path / "Libs" / "Support" / "Dep.s"
    _write_text(active_document, '"x"\n"y"\n"z"\n')
    _write_text(dependency_document, '"x"\n"y"\n"z"\n')
    active_uri = active_document.resolve().as_uri()
    dependency_uri = dependency_document.resolve().as_uri()

    bundle = cast(
        Any,
        SimpleNamespace(
            source_paths_by_key={("dep.s", "support"): dependency_document.resolve()},
            source_paths_by_name={"dep.s": (dependency_document.resolve(),)},
        ),
    )

    local_definition = SymbolDefinition(
        canonical_path="BasePicture.LocalVar",
        kind="local",
        datatype="integer",
        declaration_module_path=("BasePicture",),
        display_module_path=("BasePicture",),
        source_file="Main.s",
        source_library="Program",
        declaration_span=SourceSpan(3, 5),
    )
    dependency_definition = SymbolDefinition(
        canonical_path="Support.Value",
        kind="field",
        datatype="integer",
        declaration_module_path=("Support",),
        display_module_path=("Support",),
        source_file="Dep.s",
        source_library="Support",
        declaration_span=SourceSpan(6, 3),
    )
    no_span_definition = SymbolDefinition(
        canonical_path="Missing.Value",
        kind="field",
        datatype="integer",
        declaration_module_path=("Missing",),
        display_module_path=("Missing",),
        source_file="Missing.s",
        source_library="Support",
        declaration_span=None,
    )
    unresolved_definition = SymbolDefinition(
        canonical_path="Unknown.Value",
        kind="field",
        datatype="integer",
        declaration_module_path=("Unknown",),
        display_module_path=("Unknown",),
        source_file="Unknown.s",
        source_library="Support",
        declaration_span=SourceSpan(1, 1),
    )

    definition_locations = lsp_helpers._definition_locations_from_candidates(
        [no_span_definition, local_definition, dependency_definition, unresolved_definition],
        bundle=bundle,
        local_snapshot=cast(Any, object()),
        active_document_path=active_document,
    )
    assert [location.uri.casefold() for location in definition_locations] == [
        active_uri.casefold(),
        dependency_uri.casefold(),
    ]

    local_reference = SymbolReference(
        canonical_path="BasePicture.LocalVar",
        source_file="Main.s",
        source_library="Program",
        line=7,
        column=3,
        length=8,
        text="LocalVar",
    )
    dependency_reference = SymbolReference(
        canonical_path="Support.Value",
        source_file="Dep.s",
        source_library="Support",
        line=2,
        column=1,
        length=5,
        text="Value",
    )
    missing_reference = SymbolReference(
        canonical_path="Missing.Value",
        source_file="Missing.s",
        source_library="Support",
        line=1,
        column=1,
        length=5,
        text="Value",
    )
    reference_locations = lsp_helpers._reference_locations_from_matches(
        [local_reference, dependency_reference, missing_reference],
        bundle=bundle,
        active_document_path=active_document,
    )
    assert [location.uri.casefold() for location in reference_locations] == [
        active_uri.casefold(),
        dependency_uri.casefold(),
    ]

    merged_locations = lsp_helpers._merge_locations(
        [reference_locations[1]], [reference_locations[0], reference_locations[1]]
    )
    assert merged_locations == [reference_locations[1], reference_locations[0]]

    local_definition_uri = lsp_helpers._definition_uri(
        local_definition, bundle=None, active_document_path=active_document
    )
    assert local_definition_uri is not None
    assert local_definition_uri.casefold() == active_uri.casefold()
    assert lsp_helpers._definition_uri(dependency_definition, bundle=None, active_document_path=active_document) is None
    dependency_definition_uri = lsp_helpers._definition_uri(
        dependency_definition, bundle=bundle, active_document_path=active_document
    )
    assert dependency_definition_uri is not None
    assert dependency_definition_uri.casefold() == dependency_uri.casefold()

    workspace_edits: dict[str, list[Any]] = {}
    edit_range = Range(start=Position(line=0, character=0), end=Position(line=0, character=1))
    lsp_helpers._append_workspace_edit(workspace_edits, active_uri, edit_range, "A")
    lsp_helpers._append_workspace_edit(workspace_edits, active_uri, edit_range, "B")
    assert [edit.new_text for edit in workspace_edits[active_uri]] == ["A", "B"]

    hover = lsp_helpers._build_hover(dependency_definition)
    assert hover is not None
    hover_contents = cast(Any, hover.contents)
    assert "**Value**" in hover_contents.value
    assert "Kind: field" in hover_contents.value
    assert "Path: Support.Value" in hover_contents.value
