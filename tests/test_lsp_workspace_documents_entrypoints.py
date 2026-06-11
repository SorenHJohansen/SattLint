"""Entrypoint and dispatch focused LSP workspace tests."""

from __future__ import annotations

import runpy
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattlint.core.semantic import WorkspaceSourceDiscovery
from sattlint_lsp import workspace_store as lsp_workspace_store
from sattlint_lsp.document_state import DocumentState
from sattlint_lsp.server import (
    LspSettings,
    cli,
    on_completion,
    on_definition,
    on_did_change,
    on_did_change_configuration,
    on_did_close,
    on_did_open,
    on_did_save,
    on_hover,
    on_references,
    on_rename,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_server_configuration_document_dispatch_and_passthrough_edges(monkeypatch, tmp_path):  # noqa: PLR0915
    configuration_calls: list[str] = []
    ls = SimpleNamespace(
        settings=LspSettings(entry_file="Programs/Old.s", workspace_diagnostics_mode="background"),
        workspace_root=tmp_path,
        entry_diagnostics={},
        published_workspace_diagnostics={},
        entry_scan_generation={},
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending=set(),
    )

    monkeypatch.setattr(
        "sattlint_lsp.server._clear_workspace_diagnostics",
        lambda current_ls: configuration_calls.append("clear"),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._ensure_snapshot_store_configured",
        lambda current_ls: configuration_calls.append("configured") or False,
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan",
        lambda current_ls, entry_files=None: configuration_calls.append("scan"),
    )

    on_did_change_configuration(
        cast(Any, ls),
        cast(Any, SimpleNamespace(settings={"entryFile": "Programs/Old.s", "workspaceDiagnosticsMode": "background"})),
    )
    on_did_change_configuration(
        cast(Any, ls),
        cast(Any, SimpleNamespace(settings={"entryFile": "Programs/New.s", "workspaceDiagnosticsMode": "background"})),
    )

    assert configuration_calls == ["clear", "configured"]

    program_path = (tmp_path / "Programs" / "Main.s").resolve()
    graphics_path = (tmp_path / "Graphics" / "Panel.g").resolve()
    library_path = (tmp_path / "Libs" / "Support.l").resolve()
    notes_path = (tmp_path / "notes.txt").resolve()
    program_uri = program_path.as_uri()
    graphics_uri = graphics_path.as_uri()
    library_uri = library_path.as_uri()
    notes_uri = notes_path.as_uri()
    published = []
    open_calls: list[tuple[Path, int, str]] = []
    change_calls: list[tuple[Path, int, int, str]] = []
    diagnostic_calls: list[tuple[str, bool, bool]] = []
    scan_calls: list[tuple[Path, ...] | None] = []
    definition_calls: list[tuple[Any, Any]] = []
    hover_calls: list[tuple[Any, Any]] = []
    rename_calls: list[tuple[Any, Any, dict[str, object]]] = []
    completion_calls: list[tuple[Any, Any, dict[str, object]]] = []
    reference_calls: list[tuple[Any, Any]] = []
    documents = {
        program_uri: SimpleNamespace(uri=program_uri, source="program", version=7),
        graphics_uri: SimpleNamespace(uri=graphics_uri, source="graphics", version=6),
        library_uri: SimpleNamespace(uri=library_uri, source="support", version=5),
        notes_uri: SimpleNamespace(uri=notes_uri, source="notes", version=3),
    }
    server_ls = SimpleNamespace(
        workspace=SimpleNamespace(get_text_document=lambda requested_uri: documents[requested_uri]),
        text_document_publish_diagnostics=lambda params: published.append(params),
        document_states={
            graphics_uri: DocumentState(uri=graphics_uri, path=graphics_path, version=5, text="old"),
            library_uri: DocumentState(uri=library_uri, path=library_path, version=4, text="old"),
            notes_uri: DocumentState(uri=notes_uri, path=notes_path, version=2, text="old"),
        },
        document_paths={graphics_path: graphics_uri, library_path: library_uri, notes_path: notes_uri},
        workspace_root=tmp_path,
    )

    monkeypatch.setattr(
        "sattlint_lsp.server._document_path", lambda document: Path(document.uri.removeprefix("file://"))
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._record_document_open",
        lambda current_ls, document_path, *, uri, version, text: open_calls.append((document_path, version, text)),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._record_document_change",
        lambda current_ls, document_path, *, uri, version, content_changes, fallback_text: change_calls.append(
            (document_path, version, len(content_changes), fallback_text)
        ),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._publish_diagnostics",
        lambda current_ls, document, include_semantic=True, include_comment_validation=True: diagnostic_calls.append(
            (document.uri, include_semantic, include_comment_validation)
        ),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._invalidate_cached_entries_for_path",
        lambda current_ls, document_path: (program_path,),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan",
        lambda current_ls, entry_files=None: scan_calls.append(entry_files),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._handle_definition",
        lambda current_ls, params: definition_calls.append((current_ls, params)) or ["definition"],
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._handle_hover",
        lambda current_ls, params: hover_calls.append((current_ls, params)) or "hover",
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._handle_rename",
        lambda current_ls, params, **kwargs: rename_calls.append((current_ls, params, kwargs)) or "renamed",
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._handle_completion",
        lambda current_ls, params, **kwargs: (
            completion_calls.append((current_ls, params, kwargs))
            or cast(Any, SimpleNamespace(items=[], is_incomplete=False))
        ),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._handle_references",
        lambda current_ls, params: reference_calls.append((current_ls, params)) or ["reference"],
    )

    on_did_open(cast(Any, server_ls), cast(Any, SimpleNamespace()))
    on_did_change(cast(Any, server_ls), cast(Any, SimpleNamespace()))
    on_did_save(cast(Any, server_ls), cast(Any, SimpleNamespace()))
    on_did_close(cast(Any, server_ls), cast(Any, SimpleNamespace()))

    on_did_open(
        cast(Any, server_ls),
        cast(Any, SimpleNamespace(text_document=SimpleNamespace(uri=program_uri, version=7, text="program"))),
    )
    on_did_change(
        cast(Any, server_ls),
        cast(
            Any,
            SimpleNamespace(
                text_document=SimpleNamespace(uri=program_uri, version=8),
                content_changes=[SimpleNamespace(text="next")],
            ),
        ),
    )
    on_did_save(cast(Any, server_ls), cast(Any, SimpleNamespace(text_document=SimpleNamespace(uri=program_uri))))
    on_did_close(cast(Any, server_ls), cast(Any, SimpleNamespace(text_document=SimpleNamespace(uri=notes_uri))))
    on_did_close(cast(Any, server_ls), cast(Any, SimpleNamespace(text_document=SimpleNamespace(uri=graphics_uri))))
    on_did_close(cast(Any, server_ls), cast(Any, SimpleNamespace(text_document=SimpleNamespace(uri=library_uri))))

    assert open_calls == [(program_path, 7, "program"), (program_path, 7, "program")]
    assert change_calls == [(program_path, 8, 1, "program")]
    assert diagnostic_calls == [
        (program_uri, True, True),
        (program_uri, False, False),
        (program_uri, True, True),
    ]
    assert scan_calls == [(program_path,)]
    assert notes_uri not in server_ls.document_states
    assert notes_path not in server_ls.document_paths
    assert graphics_uri not in server_ls.document_states
    assert graphics_path not in server_ls.document_paths
    assert library_uri not in server_ls.document_states
    assert library_path not in server_ls.document_paths
    assert published[-3].uri == notes_uri
    assert published[-3].diagnostics == []
    assert published[-2].uri == graphics_uri
    assert published[-2].diagnostics == []
    assert published[-1].uri == library_uri
    assert published[-1].diagnostics == []

    assert on_definition(cast(Any, server_ls), cast(Any, SimpleNamespace())) == ["definition"]
    assert on_hover(cast(Any, server_ls), cast(Any, SimpleNamespace())) == "hover"
    assert on_rename(cast(Any, server_ls), cast(Any, SimpleNamespace(new_name="Renamed"))) == "renamed"
    assert on_references(cast(Any, server_ls), cast(Any, SimpleNamespace())) == ["reference"]
    completion_result = on_completion(
        cast(Any, server_ls),
        cast(
            Any,
            SimpleNamespace(
                text_document=SimpleNamespace(uri=program_uri), position=SimpleNamespace(line=0, character=0)
            ),
        ),
    )
    assert completion_result.items == []
    assert definition_calls == [(server_ls, cast(Any, SimpleNamespace()))] or len(definition_calls) == 1
    assert hover_calls == [(server_ls, cast(Any, SimpleNamespace()))] or len(hover_calls) == 1
    assert rename_calls[0][2]["validated_rename_request"] is not None
    assert completion_calls[0][2]["validated_text_document_position"] is not None
    assert reference_calls == [(server_ls, cast(Any, SimpleNamespace()))] or len(reference_calls) == 1


def test_server_cli_and_module_entrypoint_start_io(monkeypatch):
    start_calls: list[str] = []

    monkeypatch.setattr("sattlint_lsp.server.server.start_io", lambda: start_calls.append("cli"))
    cli()

    monkeypatch.setattr("pygls.lsp.server.LanguageServer.start_io", lambda self: start_calls.append("module"))
    runpy.run_module("sattlint_lsp.server", run_name="__main__")

    assert start_calls == ["cli", "module"]


def test_workspace_entry_files_prefers_unreferenced_programs(tmp_path):
    prog_a = tmp_path / "Programs" / "A.s"
    prog_b = tmp_path / "Programs" / "B.s"
    dep = tmp_path / "Programs" / "Main.l"
    _write_text(prog_a, '"x"\n"y"\n"z"\n')
    _write_text(prog_b, '"x"\n"y"\n"z"\n')
    _write_text(dep, "A\n")

    discovery = WorkspaceSourceDiscovery(
        workspace_root=tmp_path,
        source_dirs=(prog_a.parent.resolve(),),
        program_files=(prog_a.resolve(), prog_b.resolve()),
        dependency_files=(dep.resolve(),),
        program_files_by_stem={
            "a": (prog_a.resolve(),),
            "b": (prog_b.resolve(),),
        },
        dependency_files_by_stem={"main": (dep.resolve(),)},
        referenced_program_names=frozenset({"a"}),
    )

    assert lsp_workspace_store._workspace_entry_files(discovery) == (prog_b.resolve(),)


def test_workspace_entry_files_falls_back_when_all_programs_are_referenced(tmp_path):
    prog_a = tmp_path / "Programs" / "A.s"
    prog_b = tmp_path / "Programs" / "B.s"
    dep = tmp_path / "Programs" / "Main.l"
    _write_text(prog_a, '"x"\n"y"\n"z"\n')
    _write_text(prog_b, '"x"\n"y"\n"z"\n')
    _write_text(dep, "A\nB\n")

    discovery = WorkspaceSourceDiscovery(
        workspace_root=tmp_path,
        source_dirs=(prog_a.parent.resolve(),),
        program_files=(prog_a.resolve(), prog_b.resolve()),
        dependency_files=(dep.resolve(),),
        program_files_by_stem={
            "a": (prog_a.resolve(),),
            "b": (prog_b.resolve(),),
        },
        dependency_files_by_stem={"main": (dep.resolve(),)},
        referenced_program_names=frozenset({"a", "b"}),
    )

    assert lsp_workspace_store._workspace_entry_files(discovery) == tuple(
        sorted((prog_a.resolve(), prog_b.resolve()), key=lambda p: p.as_posix().casefold())
    )


def test_workspace_entry_files_uses_cached_dependency_references_without_reread(tmp_path, monkeypatch):
    prog_a = tmp_path / "Programs" / "A.s"
    prog_b = tmp_path / "Programs" / "B.s"
    dep = tmp_path / "Programs" / "Main.l"
    _write_text(prog_a, '"x"\n"y"\n"z"\n')
    _write_text(prog_b, '"x"\n"y"\n"z"\n')
    _write_text(dep, "A\n")

    discovery = WorkspaceSourceDiscovery(
        workspace_root=tmp_path,
        source_dirs=(prog_a.parent.resolve(),),
        program_files=(prog_a.resolve(), prog_b.resolve()),
        dependency_files=(dep.resolve(),),
        program_files_by_stem={
            "a": (prog_a.resolve(),),
            "b": (prog_b.resolve(),),
        },
        dependency_files_by_stem={"main": (dep.resolve(),)},
        referenced_program_names=frozenset({"a"}),
    )

    monkeypatch.setattr(
        lsp_workspace_store,
        "_read_dependency_names",
        lambda _path: (_ for _ in ()).throw(AssertionError("dependency files should not be reread")),
        raising=False,
    )

    assert lsp_workspace_store._workspace_entry_files(discovery) == (prog_b.resolve(),)


def test_workspace_snapshot_store_resolve_entry_file_edges(tmp_path):
    store = lsp_workspace_store.WorkspaceSnapshotStore()
    workspace_root = tmp_path.resolve()
    program = tmp_path / "Programs" / "Main.s"
    other_program = tmp_path / "Programs" / "Other.s"
    library = tmp_path / "Libs" / "Support.l"

    _write_text(program, '"x"\n"y"\n"z"\n')
    _write_text(other_program, '"x"\n"y"\n"z"\n')
    _write_text(library, "Support\n")

    assert store.resolve_entry_file(library) is None

    discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(program.parent.resolve(), library.parent.resolve()),
        program_files=(program.resolve(),),
        dependency_files=(library.resolve(),),
        program_files_by_stem={"main": (program.resolve(),)},
        dependency_files_by_stem={"support": (library.resolve(),)},
    )
    store._workspace_root = workspace_root
    store._discovery = discovery
    store._settings = SimpleNamespace(entry_file="Programs/missing.txt")
    store._entry_files = (program.resolve(),)

    assert store.resolve_entry_file(library) == program.resolve()

    store._settings = SimpleNamespace(entry_file="Programs/Main.s")
    store._entry_files = (program.resolve(), other_program.resolve())
    assert store.resolve_entry_file(library) == program.resolve()

    store._settings = SimpleNamespace(entry_file="Programs/missing.txt")
    assert store.resolve_entry_file(library) is None
