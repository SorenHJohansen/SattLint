"""Tests for LSP document state and request handlers.

Covers incremental parsing, local snapshots, workspace diagnostics,
and hover, reference, rename, definition, and completion handlers.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from lsprotocol.types import Position, Range

from sattlint.editor_api import load_workspace_snapshot
from sattlint_lsp.document_state import DocumentState, apply_content_changes
from sattlint_lsp.local_parser import DocumentParseResult, FullDocumentParserAdapter, IncrementalParseState
from sattlint_lsp.server import (
    SnapshotBundle,
    _get_or_build_local_snapshot,
    _publish_diagnostics,
    build_source_path_index,
    collect_local_definition_locations,
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

    monkeypatch.setattr("sattlint_lsp._server_helpers.load_source_snapshot", fail_if_called)

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
        from sattlint.core.semantic import build_source_snapshot_from_basepicture as real_build_source_snapshot

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


# --- document_state.py: apply_content_changes no-range (full replace),
#     apply_changes fallback, has_analysis branches ---
def test_apply_content_changes_full_replace_when_no_range():
    from types import SimpleNamespace

    from sattlint_lsp.document_state import apply_content_changes

    change = SimpleNamespace(text="new full content\nsecond line", range=None)
    result_text, ranges = apply_content_changes("old text", [change])
    assert result_text == "new full content\nsecond line"
    assert ranges == ((0, 1),)


def test_apply_content_changes_empty_list_returns_original():
    from sattlint_lsp.document_state import apply_content_changes

    result_text, ranges = apply_content_changes("original", [])
    assert result_text == "original"
    assert ranges == ()


def test_document_state_has_analysis_checks_version_and_flags(tmp_path):
    from sattlint_lsp.document_state import DocumentState

    state = DocumentState(uri="file:///test.s", path=tmp_path / "test.s", version=3, text="content")
    # No analysis stored yet
    assert state.has_analysis(include_comment_validation=False) is False

    # Simulate analysis stored at version 3
    state.analysis_version = 3
    state.analysis_includes_comment_validation = False
    assert state.has_analysis(include_comment_validation=False) is True
    assert state.has_analysis(include_comment_validation=True) is False
    assert state.has_analysis(include_comment_validation=False, require_snapshot=True) is False


def test_document_state_replace_text_clears_analysis(tmp_path):
    from sattlint_lsp.document_state import DocumentState

    state = DocumentState(uri="file:///test.s", path=tmp_path / "test.s", version=1, text="old")
    state.analysis_version = 1
    state.replace_text(version=2, text="new text", is_dirty=True)
    assert state.text == "new text"
    assert state.version == 2
    assert state.analysis_version == -1


def test_document_state_apply_changes_fallback_on_error(tmp_path):
    from types import SimpleNamespace

    from sattlint_lsp.document_state import DocumentState

    state = DocumentState(uri="file:///test.s", path=tmp_path / "test.s", version=1, text="original")
    # Pass a malformed change that triggers fallback
    bad_change = SimpleNamespace(
        text="X",
        range=SimpleNamespace(
            start=SimpleNamespace(line=-999, character=-999),
            end=SimpleNamespace(line=-999, character=-999),
        ),
    )
    fallback = "fallback text"
    state.apply_changes(version=2, content_changes=[bad_change], fallback_text=fallback)
    # Should use fallback since offset calculation fails
    assert state.version == 2
    assert state.is_dirty is True


def test_server_document_helpers_track_state_paths_and_source_text(tmp_path):
    from sattlint_lsp._server_document import (
        _document_state_for_path,
        _ensure_document_paths,
        _record_document_change,
        _source_text_for_document,
    )

    path = (tmp_path / "Program" / "Main.s").resolve()
    moved_path = (tmp_path / "Program" / "Renamed.s").resolve()
    uri = path.as_uri()
    document = cast(Any, SimpleNamespace(uri=uri, source="document text", version=1))
    ls = cast(Any, SimpleNamespace(document_states={}, document_paths=None))

    assert _document_state_for_path(ls, path) is None
    assert _source_text_for_document(ls, document) == "document text"

    document_paths = _ensure_document_paths(ls)
    assert document_paths == {}
    assert ls.document_paths is document_paths

    created = _record_document_change(
        ls,
        path,
        uri=uri,
        version=1,
        content_changes=[SimpleNamespace(range=None, text="created text")],
        fallback_text="fallback text",
    )

    assert created.text == "created text"
    assert created.version == 1
    assert ls.document_paths[path] == uri
    assert _document_state_for_path(ls, path) is created
    assert _source_text_for_document(ls, document) == "created text"

    ls.document_paths[path] = uri
    created.path = path

    updated = _record_document_change(
        ls,
        moved_path,
        uri=uri,
        version=2,
        content_changes=[SimpleNamespace(range=None, text="moved text")],
        fallback_text="fallback text",
    )

    assert updated is created
    assert updated.path == moved_path
    assert updated.text == "moved text"
    assert path not in ls.document_paths
    assert ls.document_paths[moved_path] == uri


# --- core/document.py: LineIndex methods ---
def test_line_index_line_start_offset_edge_cases():
    from sattlint.core.document import LineIndex

    idx = LineIndex.from_text("Hello\nWorld\n")
    assert idx.line_start_offset(0) == 0
    assert idx.line_start_offset(1) == 6
    assert idx.line_start_offset(-1) == 0
    assert idx.line_start_offset(100) == len("Hello\nWorld\n")


def test_line_index_line_text_strips_newlines():
    from sattlint.core.document import LineIndex

    idx = LineIndex.from_text("Line1\r\nLine2\nLine3")
    assert idx.line_text(0) == "Line1"
    assert idx.line_text(1) == "Line2"
    assert idx.line_text(2) == "Line3"
    assert idx.line_text(-1) == ""


def test_line_index_position_to_offset_basics():
    from sattlint.core.document import LineIndex

    idx = LineIndex.from_text("Hello\nWorld")
    assert idx.position_to_offset(0, 0) == 0
    assert idx.position_to_offset(0, 5) == 5
    assert idx.position_to_offset(1, 0) == 6
    assert idx.position_to_offset(100, 0) == len("Hello\nWorld")


def test_utf16_index_to_codepoint_offset():
    from sattlint.core.document import utf16_index_to_codepoint_offset

    assert utf16_index_to_codepoint_offset("abc", 0) == 0
    assert utf16_index_to_codepoint_offset("abc", 2) == 2
    assert utf16_index_to_codepoint_offset("abc", 100) == 3
