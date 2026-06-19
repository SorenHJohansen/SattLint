# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
"""Focused coverage tests for document and LSP document-state helpers."""

from types import SimpleNamespace
from typing import Any, cast

from lsprotocol.types import Position, Range

from sattlint_lsp.document_state import DocumentState
from sattlint_lsp.local_parser import FullDocumentParserAdapter
from sattlint_lsp.server import _publish_diagnostics
from tests.helpers.lsp_support import source_with_unused_variable


def test_line_index_position_to_offset_handles_empty_line_starts():
    from sattlint.core.document import LineIndex  # noqa: PLC0415

    idx = LineIndex(text="ignored", line_starts=())

    assert idx.position_to_offset(0, 3) == 0


def test_merge_line_ranges_sorts_merges_and_keeps_non_adjacent_ranges():
    from sattlint_lsp.document_state import _merge_line_ranges  # noqa: PLC0415

    assert _merge_line_ranges([]) == ()
    assert _merge_line_ranges([(4, 4), (-2, 0), (2, 3), (7, 7)]) == ((0, 0), (2, 4), (7, 7))


def test_document_state_apply_changes_falls_back_to_existing_text_without_explicit_fallback(tmp_path):
    state = DocumentState(uri="file:///test.s", path=tmp_path / "test.s", version=1, text="original")

    class BrokenLineIndex:
        text = "original"

        def position_to_offset(self, _line: int, _character: int) -> int:
            raise TypeError("bad change")

    state.line_index = cast(Any, BrokenLineIndex())

    state.apply_changes(
        version=2,
        content_changes=[
            SimpleNamespace(
                text="unused",
                range=Range(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=1),
                ),
            )
        ],
    )

    assert state.text == "original"
    assert state.changed_line_ranges == ()
    assert state.version == 2
    assert state.is_dirty is True


def test_document_state_remember_local_snapshot_stores_analysis_result(tmp_path):
    state = DocumentState(uri="file:///test.s", path=tmp_path / "test.s", version=1, text="content")
    state.syntax_diagnostics = ("warning",)
    snapshot = cast(Any, object())

    state.remember_local_snapshot(snapshot)

    assert state.local_snapshot is snapshot
    assert state.local_snapshot_version == 1
    assert state.analysis_result is not None
    assert state.analysis_result.local_snapshot is snapshot
    assert state.analysis_result.syntax_diagnostics == ("warning",)
    assert state.analysis_version == 1
    assert state.analysis_has_snapshot is True


def test_server_document_helper_edges_cover_false_background_mode_existing_open_and_typeerror_fallback(
    monkeypatch, tmp_path
):
    from sattlint_lsp._server_document import (  # noqa: PLC0415
        _background_workspace_diagnostics_enabled,
        _load_snapshot_bundle_compat,
        _record_document_open,
    )

    disabled_ls = cast(
        Any,
        SimpleNamespace(
            settings=SimpleNamespace(enable_variable_diagnostics=False, workspace_diagnostics_mode="background")
        ),
    )
    foreground_ls = cast(
        Any,
        SimpleNamespace(
            settings=SimpleNamespace(enable_variable_diagnostics=True, workspace_diagnostics_mode="foreground")
        ),
    )

    assert _background_workspace_diagnostics_enabled(disabled_ls) is False
    assert _background_workspace_diagnostics_enabled(foreground_ls) is False

    original_path = (tmp_path / "Program" / "Main.s").resolve()
    moved_path = (tmp_path / "Program" / "Renamed.s").resolve()
    uri = original_path.as_uri()
    existing = DocumentState(uri=uri, path=original_path, version=1, text="old")
    ls = cast(Any, SimpleNamespace(document_states={uri: existing}, document_paths={original_path: uri}))

    reopened = _record_document_open(ls, moved_path, uri=uri, version=2, text="new")

    assert reopened is existing
    assert reopened.path == moved_path
    assert reopened.text == "new"
    assert reopened.is_dirty is False
    assert original_path not in ls.document_paths
    assert ls.document_paths[moved_path] == uri

    monkeypatch.setattr(
        "sattlint_lsp._server_document._load_snapshot_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TypeError("boom")),
    )

    assert _load_snapshot_bundle_compat(ls, moved_path) is None
    try:
        _load_snapshot_bundle_compat(ls, moved_path, raise_on_error=True)
    except TypeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected the compatibility helper to re-raise non-compat TypeError")


def test_publish_diagnostics_ignores_dependency_list_documents_and_clears_tracked_path(monkeypatch, tmp_path):
    path = (tmp_path / "Libs" / "Support.l").resolve()
    uri = path.as_uri()
    published = []
    fake_ls = SimpleNamespace(
        settings=SimpleNamespace(enable_variable_diagnostics=True),
        document_states={uri: SimpleNamespace(path=path)},
        document_paths={path: uri},
        local_parser=FullDocumentParserAdapter(),
        text_document_publish_diagnostics=lambda params: published.append(params),
    )
    fake_document = SimpleNamespace(uri=uri, source="Support\n")

    monkeypatch.setattr("sattlint_lsp._server_document._document_path", lambda document: path)

    _publish_diagnostics(cast(Any, fake_ls), cast(Any, fake_document))

    assert path not in fake_ls.document_paths
    assert published[0].diagnostics == []


def test_publish_diagnostics_reports_syntax_errors_without_loading_workspace_snapshot(monkeypatch, tmp_path):
    source = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ModuleCode",
            "    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :",
            "        Dv = ;",
            "ENDDEF (*BasePicture*);",
        ]
    )

    published = []
    fake_ls = SimpleNamespace(
        settings=SimpleNamespace(enable_variable_diagnostics=True),
        document_states={},
        local_parser=FullDocumentParserAdapter(),
        text_document_publish_diagnostics=lambda params: published.append(params),
    )
    fake_document = SimpleNamespace(uri="file:///Program/Main.s", source=source)

    monkeypatch.setattr(
        "sattlint_lsp._server_document._document_path", lambda document: tmp_path / "Program" / "Main.s"
    )
    monkeypatch.setattr(
        "sattlint_lsp._server_document._load_snapshot_bundle_compat",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("syntax diagnostics should return first")),
    )

    _publish_diagnostics(cast(Any, fake_ls), cast(Any, fake_document))

    assert len(published) == 1
    assert published[0].diagnostics
    assert "Expected one of:" in published[0].diagnostics[0].message


def test_publish_diagnostics_reports_root_program_hint_when_snapshot_bundle_is_missing(monkeypatch, tmp_path):
    source = source_with_unused_variable("LocalVar")
    published = []
    fake_ls = SimpleNamespace(
        settings=SimpleNamespace(enable_variable_diagnostics=True),
        document_states={},
        local_parser=FullDocumentParserAdapter(),
        text_document_publish_diagnostics=lambda params: published.append(params),
    )
    fake_document = SimpleNamespace(uri="file:///Program/Main.s", source=source)

    monkeypatch.setattr(
        "sattlint_lsp._server_document._document_path", lambda document: tmp_path / "Program" / "Main.s"
    )
    monkeypatch.setattr("sattlint_lsp._server_document._load_snapshot_bundle_compat", lambda *_args, **_kwargs: None)

    _publish_diagnostics(cast(Any, fake_ls), cast(Any, fake_document))

    assert len(published) == 1
    assert len(published[0].diagnostics) == 1
    assert published[0].diagnostics[0].message.startswith("Could not determine the root program for this file.")
