# pyright: reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false

"""Workspace document and workspace-diagnostics focused LSP tests."""

from __future__ import annotations

import runpy
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from lsprotocol.types import Position, Range

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleDef,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint.analyzers.framework import Issue
from sattlint.core import diagnostics as core_diagnostics
from sattlint.core.semantic import WorkspaceSourceDiscovery
from sattlint.reporting.variables_report import IssueKind, VariableIssue
from sattlint_lsp import _server_helpers as lsp_helpers
from sattlint_lsp import workspace_store as lsp_workspace_store
from sattlint_lsp.document_state import DocumentState
from sattlint_lsp.server import (
    LspSettings,
    SattLineLanguageServer,
    SnapshotBundle,
    _clear_workspace_entries,
    _invalidate_cached_entries_for_path,
    _publish_closed_document_diagnostics,
    _publish_workspace_diagnostics_for_paths,
    _semantic_diagnostics_for_path,
    cli,
    on_completion,
    on_definition,
    on_did_change,
    on_did_change_configuration,
    on_did_close,
    on_did_open,
    on_did_save,
    on_hover,
    on_initialize,
    on_references,
    on_rename,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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

    monkeypatch.setattr(
        "sattlint_lsp._server_document._load_snapshot_bundle", lambda server, document_path: fake_bundle
    )
    monkeypatch.setattr(
        "sattlint_lsp._server_helpers.collect_semantic_diagnostics", lambda bundle, document_path: [diagnostic]
    )

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

    monkeypatch.setattr("sattlint_lsp._server_helpers.collect_semantic_diagnostics", fake_collect)

    first = _semantic_diagnostics_for_path(bundle, path)
    second = _semantic_diagnostics_for_path(bundle, path)

    assert len(first) == 1
    assert first is second
    assert first[0].message == "Unused variable"
    assert calls == 1


def test_server_helper_validation_and_workspace_message_edges_cover_none_branches():
    assert lsp_helpers._root_workspace_failure_message("Root cause\n\nResolved targets (1)\n- Lib\n") == "Root cause"
    assert lsp_helpers._validated_text_document_position(SimpleNamespace()) is None
    assert lsp_helpers._validated_open_request(SimpleNamespace()) is None
    assert lsp_helpers._validated_change_request(SimpleNamespace()) is None
    assert (
        lsp_helpers._validated_change_request(
            SimpleNamespace(
                text_document=SimpleNamespace(uri="file:///Main.s", version="bad"),
                content_changes=[],
            )
        )
        is None
    )


def test_server_helpers_resolve_entry_file_document_path_and_module_scope_edges(monkeypatch, tmp_path):
    library = tmp_path / "Libs" / "Support.l"
    program = tmp_path / "Program" / "Main.s"
    other_program = tmp_path / "Program" / "Aux.s"
    _write_text(library, "Support\n")
    _write_text(program, '"x"\n"y"\n"z"\n')
    _write_text(other_program, '"x"\n"y"\n"z"\n')

    monkeypatch.setattr(
        "sattlint_lsp._server_helpers.discover_workspace_sources",
        lambda _root: SimpleNamespace(program_files=(program,)),
    )

    assert lsp_helpers.resolve_entry_file(library, workspace_root=tmp_path) == program.resolve()

    monkeypatch.setattr(
        "sattlint_lsp._server_helpers.discover_workspace_sources",
        lambda _root: SimpleNamespace(program_files=(program, other_program)),
    )

    assert lsp_helpers.resolve_entry_file(library, workspace_root=tmp_path) is None
    assert lsp_helpers._document_path(cast(Any, SimpleNamespace(uri=None))) == Path().resolve()

    source = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "TYPEDEFINITIONS",
            "    Child = MODULEDEFINITION DateCode_ 2",
            "    ModuleDef",
            "    ENDDEF (*Child*);",
            "ENDDEF (*BasePicture*);",
        ]
    )

    assert lsp_helpers.infer_module_path_from_source(source, 6) == "BasePicture.Child"
    assert lsp_helpers.infer_module_path_from_source(source, 8) is None


def test_semantic_diagnostics_for_path_uses_cache_filled_during_collection(monkeypatch, tmp_path):
    path = (tmp_path / "Program" / "Main.s").resolve()
    cached_diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Cached",
            severity=1,
            source="sattlint",
        ),
    )
    computed_diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=1, character=0), end=Position(line=1, character=1)),
            message="Computed",
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

    def fake_collect(current_bundle, document_path):
        current_bundle.semantic_diagnostics_by_path[document_path.resolve()] = (cached_diagnostic,)
        return [computed_diagnostic]

    monkeypatch.setattr("sattlint_lsp._server_helpers.collect_semantic_diagnostics", fake_collect)

    result = _semantic_diagnostics_for_path(bundle, path)

    assert result == (cached_diagnostic,)


def test_core_diagnostics_helper_projection_edges_cover_missing_path_and_factory() -> None:
    left = core_diagnostics._diagnostics_by_file_factory()
    right = core_diagnostics._diagnostics_by_file_factory()

    assert left == {}
    assert right == {}
    assert left is not right
    assert core_diagnostics._cf("MiXeD") == "mixed"
    assert core_diagnostics._format_semantic_diagnostic_message(
        cast(Any, SimpleNamespace(kind="custom", role=None))
    ) == ("SattLint issue")

    missing_path_issue = cast(Any, SimpleNamespace(module_path=None, message="missing path"))
    result = core_diagnostics.project_report_issues((missing_path_issue,), {}, analyzer_key="spec-compliance")

    assert result.diagnostics_by_file == {}
    assert result.dropped_issues == (
        core_diagnostics.DroppedDiagnosticIssue(
            analyzer_key="spec-compliance",
            reason="missing-module-path",
            message="missing path",
        ),
    )


def test_core_diagnostics_projection_wrappers_cover_module_site_and_missing_definition_site() -> None:
    issue = Issue(kind="spec.issue", message="projected issue", module_path=["BasePicture"])
    site = core_diagnostics._DiagnosticSite(
        source_file="/tmp/Main.s",
        source_library="MainLib",
        line=7,
        column=3,
        length=5,
    )

    projected = core_diagnostics.project_report_issues_by_file(
        (issue,),
        {("basepicture",): site},
        analyzer_key="spec-compliance",
    )

    assert projected == {
        "/tmp/main.s": (
            core_diagnostics.SemanticDiagnostic(
                source_file="/tmp/Main.s",
                source_library="MainLib",
                line=7,
                column=3,
                length=5,
                message="projected issue",
                analyzer_key="spec-compliance",
            ),
        )
    }

    variable_issue = VariableIssue(
        kind=IssueKind.UNUSED,
        module_path=["BasePicture"],
        variable=Variable(name="MissingSite", datatype=Simple_DataType.INTEGER),
    )
    definition = SimpleNamespace(
        source_file=None,
        source_library="MainLib",
        declaration_span=SourceSpan(4, 2),
        canonical_path="BasePicture.MissingSite",
        field_path=None,
    )

    variable_projection = core_diagnostics.project_variable_issues(
        (variable_issue,), {("basepicture", "missingsite"): definition}
    )

    assert variable_projection.diagnostics_by_file == {}
    assert variable_projection.dropped_issues == (
        core_diagnostics.DroppedDiagnosticIssue(
            analyzer_key="variables",
            reason="missing-definition-site",
            module_path=("BasePicture",),
            variable_name="MissingSite",
            field_path=None,
            message=str(variable_issue),
        ),
    )
    assert (
        core_diagnostics.project_variable_issues_by_file(
            (variable_issue,),
            {("basepicture", "missingsite"): definition},
        )
        == {}
    )


def test_core_diagnostics_site_builder_covers_register_skip_and_nested_walk() -> None:
    sites: dict[tuple[str, ...], core_diagnostics._DiagnosticSite] = {}
    core_diagnostics._register_site(
        sites,
        ["BasePicture"],
        source_file=None,
        source_library="MainLib",
        line=1,
        column=1,
        label="BasePicture",
    )

    grandchild = SingleModule(
        header=ModuleHeader(
            name="Grandchild", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0), declaration_span=SourceSpan(8, 3)
        ),
        moduledef=ModuleDef(),
    )
    child = SingleModule(
        header=ModuleHeader(name="Child", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0), declaration_span=SourceSpan(6, 2)),
        moduledef=ModuleDef(),
        submodules=[grandchild],
    )
    base_picture = BasePicture(
        header=ModuleHeader(
            name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0), declaration_span=SourceSpan(4, 1)
        ),
        name="BasePicture",
        position=(0.0, 0.0, 0.0, 1.0, 1.0),
        moduledef=ModuleDef(),
        submodules=[child],
        origin_file="Main.s",
        origin_lib="MainLib",
    )

    built_sites = core_diagnostics.build_module_diagnostic_sites(base_picture)

    assert sites == {}
    assert ("basepicture", "child", "grandchild") in built_sites
    assert built_sites[("basepicture", "child", "grandchild")].line == 8


def test_core_diagnostics_variable_projection_falls_back_to_variable_site_when_field_path_is_missing() -> None:
    issue = VariableIssue(
        kind=IssueKind.UNUSED_DATATYPE_FIELD,
        module_path=["BasePicture"],
        variable=Variable(name="RecordVar", datatype=Simple_DataType.INTEGER),
        field_path="Nested.Leaf",
    )
    definition = SimpleNamespace(
        source_file="/tmp/Main.s",
        source_library="MainLib",
        declaration_span=SourceSpan(12, 4),
        canonical_path="BasePicture.RecordVar",
        field_path=None,
    )

    result = core_diagnostics.project_variable_issues(
        (issue,),
        {("basepicture", "recordvar"): definition},
    )

    assert result.dropped_issues == ()
    assert result.diagnostics_by_file == {
        "/tmp/main.s": (
            core_diagnostics.SemanticDiagnostic(
                source_file="/tmp/Main.s",
                source_library="MainLib",
                line=12,
                column=4,
                length=len("RecordVar"),
                message=core_diagnostics._format_semantic_diagnostic_message(issue),
                analyzer_key="variables",
            ),
        )
    }


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


def test_on_did_close_restores_active_diagnostics_among_same_name_dependencies(tmp_path):
    active_path = (tmp_path / "Program" / "Main.s").resolve()
    support_path = (tmp_path / "Libs" / "Support" / "Main.s").resolve()
    backup_path = (tmp_path / "Libs" / "Backup" / "Main.s").resolve()
    uri = active_path.as_uri()
    published = []
    active_diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=1, character=0), end=Position(line=1, character=3)),
            message="Active document warning",
            severity=1,
            source="sattlint",
        ),
    )
    support_diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=2, character=0), end=Position(line=2, character=3)),
            message="Support library warning",
            severity=1,
            source="sattlint",
        ),
    )

    ls = SattLineLanguageServer()
    ls.text_document_publish_diagnostics = lambda params: published.append(params)
    ls.document_states[uri] = DocumentState(
        uri=uri,
        path=active_path,
        version=2,
        text="Renamed = Renamed;\n",
        is_dirty=True,
    )
    ls.entry_diagnostics = {
        "entry": {
            active_path: (active_diagnostic,),
            support_path: (support_diagnostic,),
            backup_path: (support_diagnostic,),
        }
    }

    on_did_close(ls, cast(Any, SimpleNamespace(text_document=SimpleNamespace(uri=uri))))

    assert published[-1].uri.casefold() == uri.casefold()
    assert [item.message for item in published[-1].diagnostics] == ["Active document warning"]
    assert ls.published_workspace_diagnostics[active_path][0].message == "Active document warning"
    assert support_path not in ls.published_workspace_diagnostics


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


def test_on_initialize_resets_server_state_and_prefers_root_uri(monkeypatch, tmp_path):
    ls = SattLineLanguageServer()
    ls.document_states["file:///old.s"] = DocumentState(
        uri="file:///old.s",
        path=tmp_path / "old.s",
        version=1,
        text="x",
    )
    ls.document_paths[(tmp_path / "old.s").resolve()] = "file:///old.s"
    ls.entry_diagnostics["entry"] = {}
    ls.published_workspace_diagnostics[(tmp_path / "old.s").resolve()] = ()
    ls.entry_scan_generation["entry"] = 1
    calls: list[str] = []

    monkeypatch.setattr(
        "sattlint_lsp.server._ensure_snapshot_store_configured", lambda current_ls: calls.append("configured") or True
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan", lambda current_ls, entry_files=None: calls.append("scan")
    )

    params = SimpleNamespace(
        initialization_options={"workspaceDiagnosticsMode": "background"},
        root_uri=tmp_path.resolve().as_uri(),
        root_path=str(tmp_path / "ignored"),
    )

    on_initialize(ls, cast(Any, params))

    assert ls.workspace_root == tmp_path.resolve()
    assert ls.settings.workspace_diagnostics_mode == "background"
    assert ls.document_states == {}
    assert ls.document_paths == {}
    assert ls.entry_diagnostics == {}
    assert ls.published_workspace_diagnostics == {}
    assert ls.entry_scan_generation == {}
    assert calls == ["configured", "scan"]


def test_on_did_change_configuration_reconfigures_workspace_and_schedules_scan(monkeypatch, tmp_path):
    stale_path = (tmp_path / "Programs" / "Main.s").resolve()
    publish_calls: list[set[Path]] = []
    calls: list[str] = []

    ls = SimpleNamespace(
        settings=LspSettings(entry_file="Programs/Old.s", workspace_diagnostics_mode="background"),
        workspace_root=tmp_path,
        entry_diagnostics={"entry": {stale_path: ()}},
        published_workspace_diagnostics={stale_path: ()},
        entry_scan_generation={"entry": 1},
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending={stale_path},
    )

    monkeypatch.setattr(
        "sattlint_lsp.server._publish_workspace_diagnostics_for_paths",
        lambda current_ls, paths: publish_calls.append(set(paths)),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._ensure_snapshot_store_configured", lambda current_ls: calls.append("configured") or True
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan", lambda current_ls, entry_files=None: calls.append("scan")
    )

    params = SimpleNamespace(
        settings={
            "entryFile": "Programs/New.s",
            "mode": "official",
            "workspaceDiagnosticsMode": "background",
        }
    )

    on_did_change_configuration(cast(Any, ls), cast(Any, params))

    assert ls.settings.entry_file == "Programs/New.s"
    assert ls.settings.mode == "official"
    assert ls.entry_diagnostics == {}
    assert ls.entry_scan_generation == {}
    assert ls.workspace_scan_pending == set()
    assert publish_calls == [{stale_path}]
    assert calls == ["configured", "scan"]


def test_on_did_change_configuration_reconfigures_when_cache_cap_changes(monkeypatch, tmp_path):
    calls: list[str] = []

    ls = SimpleNamespace(
        settings=LspSettings(max_cached_entry_snapshots=2),
        workspace_root=tmp_path,
        entry_diagnostics={},
        published_workspace_diagnostics={},
        entry_scan_generation={},
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending=set(),
    )

    monkeypatch.setattr(
        "sattlint_lsp.server._publish_workspace_diagnostics_for_paths",
        lambda current_ls, paths: None,
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._ensure_snapshot_store_configured", lambda current_ls: calls.append("configured") or True
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan", lambda current_ls, entry_files=None: calls.append("scan")
    )

    params = SimpleNamespace(settings={"maxCachedEntrySnapshots": 1})

    on_did_change_configuration(cast(Any, ls), cast(Any, params))

    assert ls.settings.max_cached_entry_snapshots == 1
    assert calls == ["configured", "scan"]


def test_on_did_open_and_change_ignore_non_diagnostic_documents(monkeypatch, tmp_path):
    path = (tmp_path / "notes.txt").resolve()
    uri = path.as_uri()
    published = []

    ls = SimpleNamespace(
        workspace=SimpleNamespace(
            get_text_document=lambda requested_uri: SimpleNamespace(uri=requested_uri, source="text", version=2)
        ),
        text_document_publish_diagnostics=lambda params: published.append(params),
        document_states={uri: DocumentState(uri=uri, path=path, version=1, text="old")},
        document_paths={path: uri},
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: path)

    open_params = SimpleNamespace(text_document=SimpleNamespace(uri=uri, version=2, text="text"))
    on_did_open(cast(Any, ls), cast(Any, open_params))

    assert uri not in ls.document_states
    assert path not in ls.document_paths
    assert published[-1].uri == uri
    assert published[-1].diagnostics == []

    ls.document_states[uri] = DocumentState(uri=uri, path=path, version=2, text="old")
    ls.document_paths[path] = uri
    change_params = SimpleNamespace(
        text_document=SimpleNamespace(uri=uri, version=3),
        content_changes=[SimpleNamespace(text="new")],
    )
    on_did_change(cast(Any, ls), cast(Any, change_params))

    assert uri not in ls.document_states
    assert path not in ls.document_paths
    assert published[-1].uri == uri
    assert published[-1].diagnostics == []


def test_on_did_save_ignores_non_diagnostic_documents(monkeypatch, tmp_path):
    path = (tmp_path / "notes.txt").resolve()
    uri = path.as_uri()
    published = []

    ls = SimpleNamespace(
        workspace=SimpleNamespace(
            get_text_document=lambda requested_uri: SimpleNamespace(uri=requested_uri, source="saved", version=4)
        ),
        text_document_publish_diagnostics=lambda params: published.append(params),
        document_states={uri: DocumentState(uri=uri, path=path, version=3, text="old")},
        document_paths={path: uri},
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: path)

    save_params = SimpleNamespace(text_document=SimpleNamespace(uri=uri))
    on_did_save(cast(Any, ls), cast(Any, save_params))

    assert uri not in ls.document_states
    assert path not in ls.document_paths
    assert published[-1].uri == uri
    assert published[-1].diagnostics == []


@pytest.mark.parametrize("suffix", [".l", ".z"])
def test_on_did_save_rescans_workspace_dependency_lists(monkeypatch, tmp_path, suffix):
    path = (tmp_path / "Libs" / f"Support{suffix}").resolve()
    uri = path.as_uri()
    stale_path = (tmp_path / "Programs" / "Main.s").resolve()
    new_path = (tmp_path / "Programs" / "Other.s").resolve()
    unaffected_path = (tmp_path / "Programs" / "Keep.s").resolve()
    published = []
    publish_calls: list[set[Path]] = []
    invalidate_calls: list[Path] = []
    scan_calls: list[tuple[Path, ...] | None] = []

    ls = SimpleNamespace(
        workspace=SimpleNamespace(
            get_text_document=lambda requested_uri: SimpleNamespace(uri=requested_uri, source="Support\n", version=4)
        ),
        text_document_publish_diagnostics=lambda params: published.append(params),
        document_states={uri: DocumentState(uri=uri, path=path, version=3, text="old")},
        document_paths={path: uri},
        workspace_root=tmp_path,
        entry_diagnostics={"entry": {stale_path: ()}, "keep": {unaffected_path: ()}},
        published_workspace_diagnostics={stale_path: (), unaffected_path: ()},
        entry_scan_generation={"entry": 1, "keep": 2},
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending={stale_path},
        snapshot_store=SimpleNamespace(
            refresh_workspace=lambda: lsp_workspace_store.WorkspaceRefreshResult(
                entry_files=(stale_path, unaffected_path, new_path),
                affected_entries=(new_path,),
                removed_entries=(),
            )
        ),
    )

    monkeypatch.setattr("sattlint_lsp.server._document_path", lambda document: path)
    monkeypatch.setattr(
        "sattlint_lsp.server._publish_workspace_diagnostics_for_paths",
        lambda current_ls, paths: publish_calls.append(set(paths)),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan",
        lambda current_ls, entry_files=None: scan_calls.append(entry_files),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._record_document_open",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("dependency lists should not open diagnostics state")
        ),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._clear_workspace_diagnostics",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("dependency list saves should not clear unrelated workspace diagnostics")
        ),
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._invalidate_cached_entries_for_path",
        lambda _ls, dependency_path: invalidate_calls.append(dependency_path) or (stale_path,),
    )

    save_params = SimpleNamespace(text_document=SimpleNamespace(uri=uri))
    on_did_save(cast(Any, ls), cast(Any, save_params))

    assert uri not in ls.document_states
    assert path not in ls.document_paths
    assert published[-1].uri == uri
    assert published[-1].diagnostics == []
    assert invalidate_calls == [path]
    assert ls.entry_diagnostics == {"entry": {stale_path: ()}, "keep": {unaffected_path: ()}}
    assert ls.entry_scan_generation == {"entry": 1, "keep": 2}
    assert ls.workspace_scan_pending == {stale_path}
    assert publish_calls == []
    assert scan_calls == [tuple(sorted((new_path, stale_path), key=lambda item: item.as_posix().casefold()))]


def test_server_workspace_entry_and_initialization_edge_paths(monkeypatch, tmp_path):
    stale_path = (tmp_path / "Programs" / "Main.s").resolve()
    keep_path = (tmp_path / "Programs" / "Keep.s").resolve()
    publish_calls: list[set[Path]] = []

    ls = SimpleNamespace(
        entry_diagnostics={
            stale_path.as_posix().casefold(): {stale_path: ()},
            keep_path.as_posix().casefold(): {keep_path: ()},
        },
        entry_scan_generation={
            stale_path.as_posix().casefold(): 1,
            keep_path.as_posix().casefold(): 2,
        },
        workspace_scan_condition=threading.Condition(),
        workspace_scan_pending={stale_path, keep_path},
    )

    monkeypatch.setattr(
        "sattlint_lsp.server._publish_workspace_diagnostics_for_paths",
        lambda current_ls, paths: publish_calls.append(set(paths)),
    )

    _clear_workspace_entries(cast(Any, ls), ())
    _clear_workspace_entries(cast(Any, ls), (stale_path,))

    assert set(ls.entry_diagnostics) == {keep_path.as_posix().casefold()}
    assert ls.entry_scan_generation == {keep_path.as_posix().casefold(): 2}
    assert ls.workspace_scan_pending == {keep_path}
    assert publish_calls == [{stale_path}]

    calls: list[str] = []
    server_ls = SattLineLanguageServer()
    server_ls.document_states["file:///stale"] = cast(Any, object())
    server_ls.document_paths[stale_path] = "file:///stale"
    server_ls.entry_diagnostics = {"stale": {stale_path: ()}}
    server_ls.published_workspace_diagnostics = {stale_path: ()}
    server_ls.entry_scan_generation = {"stale": 1}
    with server_ls.workspace_scan_condition:
        server_ls.workspace_scan_pending.add(stale_path)
        server_ls.workspace_scan_thread = cast(Any, object())
        server_ls.workspace_scan_generation = 9

    monkeypatch.setattr(
        "sattlint_lsp.server._ensure_snapshot_store_configured",
        lambda current_ls: calls.append("configured") or True,
    )
    monkeypatch.setattr(
        "sattlint_lsp.server._schedule_workspace_scan",
        lambda current_ls, entry_files=None: calls.append("scan"),
    )

    on_initialize(
        server_ls,
        cast(
            Any,
            SimpleNamespace(initialization_options={}, root_uri=object(), root_path=str(tmp_path)),
        ),
    )
    assert server_ls.workspace_root == tmp_path.resolve()
    assert server_ls.document_states == {}
    assert server_ls.document_paths == {}
    assert server_ls.entry_diagnostics == {}
    assert server_ls.published_workspace_diagnostics == {}
    assert server_ls.entry_scan_generation == {}

    on_initialize(
        server_ls,
        cast(
            Any,
            SimpleNamespace(initialization_options={}, root_uri=None, root_path=object()),
        ),
    )

    assert server_ls.workspace_root is None
    assert calls == ["configured", "scan", "configured", "scan"]


def test_server_configuration_document_dispatch_and_passthrough_edges(monkeypatch, tmp_path):
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


def test_workspace_snapshot_store_cache_prefetch_and_invalidation_edges(tmp_path, monkeypatch):
    from concurrent.futures import Future

    store = lsp_workspace_store.WorkspaceSnapshotStore()
    workspace_root = tmp_path.resolve()
    entry = (tmp_path / "Programs" / "Main.s").resolve()
    sibling = (tmp_path / "Programs" / "Other.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()

    for path in (entry, sibling, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    store._workspace_root = workspace_root
    store._settings = SimpleNamespace(entry_file="", max_cached_entry_snapshots=1)
    store._discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry.parent,),
        program_files=(entry, sibling),
        dependency_files=(dependency,),
        program_files_by_stem={
            "main": (entry,),
            "other": (sibling,),
        },
        dependency_files_by_stem={"support": (dependency,)},
    )
    store._entry_files = (entry, sibling)

    state_entry = store._state_for_entry_locked(entry)
    state_sibling = store._state_for_entry_locked(sibling)
    bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=state_entry.cache_key,
        source_files=(entry,),
    )
    state_entry.bundle = bundle
    state_entry.stale = False
    state_entry.last_access = 1.0
    state_entry.last_error = RuntimeError("old error")
    state_sibling.stale = True

    sibling_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=sibling,
        cache_key=state_sibling.cache_key,
        source_files=(sibling,),
    )

    refresh_future = Future()
    refresh_future.set_result(sibling_bundle)
    state_sibling.future = refresh_future
    store._source_file_to_entry_keys = {
        entry: {state_entry.cache_key},
    }
    store._finalize_future(state_sibling.cache_key, refresh_future)

    assert state_entry.bundle is None
    assert state_sibling.bundle is sibling_bundle
    assert entry not in store._source_file_to_entry_keys
    assert store._source_file_to_entry_keys[sibling] == {state_sibling.cache_key}

    submitted: list[Path] = []

    def _submit_refresh(state):
        submitted.append(state.entry_file)
        future = Future()
        future.set_result(bundle)
        state.future = future
        return future

    monkeypatch.setattr(store, "_submit_refresh_locked", _submit_refresh)

    assert store.prefetch_entries() == (entry,)
    assert submitted == [entry]
    assert state_entry.future is not None
    store._finalize_future(state_entry.cache_key, state_entry.future)
    assert store.get_cached_bundle(entry) is bundle
    state_entry.stale = True
    assert store.get_cached_bundle(entry, allow_stale=False) is None
    assert store.get_cached_bundle(entry, allow_stale=True) is bundle
    assert store.last_error_for_entry(entry) is state_entry.last_error
    assert store.last_error_for_entry(tmp_path / "missing.s") is None

    store._source_file_to_entry_keys[dependency] = {state_entry.cache_key, "missing"}
    affected = store.invalidate_path(dependency)
    assert affected == (entry,)
    assert state_entry.stale is True
    assert state_entry.generation == 1
    assert state_entry.last_error is None

    assert store.get_affected_entry_keys(entry) == (state_entry.cache_key,)


def test_workspace_snapshot_store_refresh_workspace_preserves_unchanged_bundles(tmp_path, monkeypatch):
    store = lsp_workspace_store.WorkspaceSnapshotStore()
    workspace_root = tmp_path.resolve()
    entry = (tmp_path / "Programs" / "Main.s").resolve()
    removed = (tmp_path / "Programs" / "Old.s").resolve()
    added = (tmp_path / "Programs" / "New.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()

    for path in (entry, removed, added, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    store._workspace_root = workspace_root
    store._settings = SimpleNamespace(entry_file="", max_cached_entry_snapshots=2)
    store._discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry.parent, dependency.parent),
        program_files=(entry, removed),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (entry,), "old": (removed,)},
        dependency_files_by_stem={"support": (dependency,)},
    )
    store._entry_files = (entry, removed)

    entry_state = store._state_for_entry_locked(entry)
    removed_state = store._state_for_entry_locked(removed)
    preserved_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=entry_state.cache_key,
        source_files=(entry, dependency),
    )
    removed_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=removed,
        cache_key=removed_state.cache_key,
        source_files=(removed, dependency),
    )
    entry_state.bundle = preserved_bundle
    removed_state.bundle = removed_bundle
    store._source_file_to_entry_keys = {
        entry: {entry_state.cache_key},
        removed: {removed_state.cache_key},
        dependency: {entry_state.cache_key, removed_state.cache_key},
    }

    refreshed_discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry.parent, dependency.parent),
        program_files=(entry, added),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (entry,), "new": (added,)},
        dependency_files_by_stem={"support": (dependency,)},
    )
    monkeypatch.setattr(lsp_workspace_store, "discover_workspace_sources", lambda _root: refreshed_discovery)

    result = store.refresh_workspace()

    assert result.entry_files == (entry, added)
    assert result.affected_entries == (added,)
    assert result.removed_entries == (removed,)
    assert store.get_cached_bundle(entry) is preserved_bundle
    assert store.get_cached_bundle(removed) is None
    assert removed not in store._source_file_to_entry_keys
    assert store._source_file_to_entry_keys[dependency] == {entry_state.cache_key}


def test_workspace_snapshot_store_index_and_configuration_edges(tmp_path, monkeypatch):
    workspace_root = tmp_path.resolve()
    main_a = (tmp_path / "Programs" / "Main.s").resolve()
    aux = (tmp_path / "Programs" / "Aux.s").resolve()
    main_b = (tmp_path / "OtherPrograms" / "Main.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()

    for path in (main_a, aux, main_b, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    by_name, by_key = lsp_workspace_store._build_source_path_index((main_b, main_a, aux))
    assert by_name["main.s"] == tuple(sorted((main_a, main_b), key=lambda path: path.as_posix().casefold()))
    assert by_key[("main.s", "programs")] == main_a
    assert by_key[("main.s", "otherprograms")] == main_b

    candidate_discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(main_a.parent, main_b.parent),
        program_files=(main_a, aux),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (main_a,), "aux": (aux,)},
        dependency_files_by_stem={"support": (dependency,)},
        referenced_program_names=frozenset({"main"}),
    )
    assert lsp_workspace_store._workspace_entry_files(candidate_discovery) == (aux,)

    all_referenced_discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(main_a.parent, main_b.parent),
        program_files=(main_a, main_b),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (main_a, main_b)},
        dependency_files_by_stem={"support": (dependency,)},
        referenced_program_names=frozenset({"main"}),
    )
    assert lsp_workspace_store._workspace_entry_files(all_referenced_discovery) == tuple(
        sorted((main_a, main_b), key=lambda path: path.as_posix().casefold())
    )

    store = lsp_workspace_store.WorkspaceSnapshotStore()
    store._entry_files = (main_a,)
    assert store.list_entry_files() == (main_a,)
    assert store.resolve_entry_file(main_a) == main_a

    result = store.refresh_workspace()
    assert result == lsp_workspace_store.WorkspaceRefreshResult((), (), (main_a,))

    assert store.ensure_configured(None, SimpleNamespace()) is False

    monkeypatch.setattr(lsp_workspace_store, "discover_workspace_sources", lambda _root: candidate_discovery)
    settings = SimpleNamespace(entry_file="")
    assert store.ensure_configured(workspace_root, settings) is True
    assert store.ensure_configured(workspace_root, settings) is True

    stale_state = store._state_for_entry_locked(aux)
    stale_state.stale = True
    refreshed = store.refresh_workspace()
    assert refreshed.affected_entries == (aux,)

    missing_program = (tmp_path / "Programs" / "Missing.s").resolve()
    _write_text(missing_program, '"x"\n"y"\n"z"\n')
    assert store.invalidate_path(missing_program) == ()
    assert store.get_affected_entry_keys(missing_program) == (missing_program.as_posix().casefold(),)

    store._drop_entry_state_locked("missing")


def test_workspace_snapshot_store_bundle_resolution_edges(tmp_path, monkeypatch):
    from concurrent.futures import TimeoutError

    entry = (tmp_path / "Programs" / "Main.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()
    for path in (entry, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=entry.as_posix().casefold(),
        source_files=(entry,),
    )

    store = lsp_workspace_store.WorkspaceSnapshotStore()
    state = store._state_for_entry_locked(entry)
    state.bundle = bundle
    state.stale = False
    assert store.get_bundle_for_entry(entry) is bundle

    monkeypatch.setattr(store, "resolve_entry_file", lambda document_path: None)
    assert store.get_bundle_for_document(dependency) is None

    forwarded = []
    monkeypatch.setattr(store, "resolve_entry_file", lambda document_path: entry)
    monkeypatch.setattr(
        store,
        "get_bundle_for_entry",
        lambda entry_file, **kwargs: forwarded.append((entry_file, kwargs)) or bundle,
    )
    assert store.get_bundle_for_document(dependency, wait_budget=1.5, allow_stale=False, raise_on_error=True) is bundle
    assert forwarded == [
        (
            entry,
            {"wait_budget": 1.5, "allow_stale": False, "raise_on_error": True},
        )
    ]

    submit_store = lsp_workspace_store.WorkspaceSnapshotStore()

    class ReadyFuture:
        def result(self, timeout=None):
            return bundle

    ready_future = ReadyFuture()

    def _submit_ready(current_state):
        current_state.bundle = bundle
        current_state.future = ready_future
        return ready_future

    monkeypatch.setattr(submit_store, "_submit_refresh_locked", _submit_ready)
    assert submit_store.get_bundle_for_entry(entry) is bundle

    timeout_store = lsp_workspace_store.WorkspaceSnapshotStore()
    timeout_state = timeout_store._state_for_entry_locked(entry)
    finalized: list[tuple[str, object]] = []

    class TimeoutFuture:
        def result(self, timeout=None):
            raise TimeoutError()

    timeout_future = TimeoutFuture()

    monkeypatch.setattr(
        timeout_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", timeout_future) or timeout_future,
    )
    monkeypatch.setattr(
        timeout_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: finalized.append((entry_key, future)),
    )
    assert timeout_store.get_bundle_for_entry(entry, wait_budget=1.0) is None
    assert finalized == [(entry.as_posix().casefold(), timeout_future)]
    assert timeout_state.last_access > 0.0

    error_store = lsp_workspace_store.WorkspaceSnapshotStore()
    error_state = error_store._state_for_entry_locked(entry)

    class ErrorFuture:
        def result(self, timeout=None):
            raise RuntimeError("boom")

    error_future = ErrorFuture()
    monkeypatch.setattr(
        error_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", error_future) or error_future,
    )
    monkeypatch.setattr(error_store, "_finalize_future", lambda entry_key, future, **kwargs: None)
    with pytest.raises(RuntimeError, match="boom"):
        error_store.get_bundle_for_entry(entry, wait_budget=1.0, raise_on_error=True)
    assert error_state.last_access > 0.0

    missing_store = lsp_workspace_store.WorkspaceSnapshotStore()
    missing_store._state_for_entry_locked(entry)
    monkeypatch.setattr(
        missing_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", timeout_future) or timeout_future,
    )
    monkeypatch.setattr(
        missing_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: missing_store._states.pop(entry_key, None),
    )
    assert missing_store.get_bundle_for_entry(entry, wait_budget=1.0) is None

    final_bundle_store = lsp_workspace_store.WorkspaceSnapshotStore()
    final_bundle_state = final_bundle_store._state_for_entry_locked(entry)
    monkeypatch.setattr(
        final_bundle_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", timeout_future) or timeout_future,
    )
    monkeypatch.setattr(
        final_bundle_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: setattr(final_bundle_store._states[entry_key], "bundle", bundle),
    )
    assert final_bundle_store.get_bundle_for_entry(entry, wait_budget=1.0) is bundle
    assert final_bundle_state.bundle is bundle

    final_error_store = lsp_workspace_store.WorkspaceSnapshotStore()
    final_error_state = final_error_store._state_for_entry_locked(entry)
    monkeypatch.setattr(
        final_error_store,
        "_submit_refresh_locked",
        lambda current_state: setattr(current_state, "future", timeout_future) or timeout_future,
    )
    monkeypatch.setattr(
        final_error_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: setattr(
            final_error_store._states[entry_key], "last_error", ValueError("final")
        ),
    )
    with pytest.raises(ValueError, match="final"):
        final_error_store.get_bundle_for_entry(entry, wait_budget=1.0, raise_on_error=True)
    assert final_error_state.last_error is not None

    captured_error_store = lsp_workspace_store.WorkspaceSnapshotStore()
    captured_state = captured_error_store._state_for_entry_locked(entry)
    captured_state.last_error = ValueError("captured")
    captured_state.future = timeout_future
    monkeypatch.setattr(
        captured_error_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: setattr(captured_error_store._states[entry_key], "last_error", None),
    )
    with pytest.raises(ValueError, match="captured"):
        captured_error_store.get_bundle_for_entry(entry, wait_budget=1.0, raise_on_error=True)


def test_workspace_snapshot_store_cache_submit_build_and_finalize_edges(tmp_path, monkeypatch):
    from concurrent.futures import Future

    workspace_root = tmp_path.resolve()
    entry = (tmp_path / "Programs" / "Main.s").resolve()
    old_source = (tmp_path / "Programs" / "Old.s").resolve()
    dependency = (tmp_path / "Libs" / "Support.l").resolve()
    for path in (entry, old_source, dependency):
        _write_text(path, '"x"\n"y"\n"z"\n')

    discovery = WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry.parent, dependency.parent),
        program_files=(entry,),
        dependency_files=(dependency,),
        program_files_by_stem={"main": (entry,)},
        dependency_files_by_stem={"support": (dependency,)},
    )

    bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=entry.as_posix().casefold(),
        source_files=(entry,),
    )
    old_bundle = SnapshotBundle(
        snapshot=cast(Any, object()),
        source_paths_by_name={},
        source_paths_by_key={},
        entry_file=entry,
        cache_key=entry.as_posix().casefold(),
        source_files=(old_source,),
    )

    store = lsp_workspace_store.WorkspaceSnapshotStore()
    state = store._state_for_entry_locked(entry)
    assert store._bundle_from_state(state, allow_stale=True) is None

    store._settings = SimpleNamespace(max_cached_entry_snapshots="bad")
    assert store._max_cached_entry_snapshots_locked() == 2

    store._remove_bundle_sources_locked(state.cache_key, bundle)

    store._evict_bundle_locked(state)
    state.bundle = bundle
    state.stale = True
    store._source_file_to_entry_keys = {entry: {state.cache_key}}
    store._evict_bundle_locked(state)
    assert state.bundle is None
    assert state.stale is False
    assert entry not in store._source_file_to_entry_keys

    state.bundle = bundle
    state.last_access = 1.0
    store._states = {state.cache_key: state}
    store._settings = SimpleNamespace(max_cached_entry_snapshots=5)
    store._enforce_bundle_cap_locked()
    assert state.bundle is bundle

    uninitialized_store = lsp_workspace_store.WorkspaceSnapshotStore()
    with pytest.raises(RuntimeError, match="not initialized"):
        uninitialized_store._submit_refresh_locked(uninitialized_store._state_for_entry_locked(entry))

    submit_store = lsp_workspace_store.WorkspaceSnapshotStore()
    submit_store._workspace_root = workspace_root
    submit_store._settings = SimpleNamespace(mode="official", scan_root_only=True, enable_variable_diagnostics=False)
    submit_store._discovery = discovery
    submit_store._config_version = 3
    submit_state = submit_store._state_for_entry_locked(entry)
    submit_state.generation = 4
    submit_calls: list[tuple[str, int | None, int | None]] = []

    class ImmediateExecutor:
        def submit(self, fn, *args):
            future = Future()
            future.set_result(bundle)
            return future

    monkeypatch.setattr(submit_store, "_executor", ImmediateExecutor())
    monkeypatch.setattr(
        submit_store,
        "_finalize_future",
        lambda entry_key, future, **kwargs: submit_calls.append(
            (entry_key, kwargs.get("expected_config_version"), kwargs.get("expected_generation"))
        ),
    )
    returned_future = submit_store._submit_refresh_locked(submit_state)
    assert submit_state.future is returned_future
    assert submit_calls == [(submit_state.cache_key, 3, 4)]

    build_store = lsp_workspace_store.WorkspaceSnapshotStore()
    snapshot = SimpleNamespace(project_graph=SimpleNamespace(source_files=(dependency, entry)))
    load_calls: list[tuple[Path, Path, str, bool, bool, object]] = []
    monkeypatch.setattr(
        lsp_workspace_store,
        "load_workspace_snapshot",
        lambda entry_file, *, workspace_root, mode, scan_root_only, collect_variable_diagnostics, discovery, _analysis_provider: (
            load_calls.append(
                (entry_file, workspace_root, mode, scan_root_only, collect_variable_diagnostics, _analysis_provider)
            )
            or snapshot
        ),
    )
    built_bundle = build_store._build_bundle(
        entry,
        workspace_root,
        SimpleNamespace(mode="official", scan_root_only=True, enable_variable_diagnostics=False),
        discovery,
    )
    assert built_bundle.entry_file == entry
    assert built_bundle.source_files == tuple(sorted((dependency, entry), key=lambda path: path.as_posix().casefold()))
    assert built_bundle.source_paths_by_key[("main.s", "programs")] == entry
    assert load_calls == [
        (entry, workspace_root, "official", True, False, lsp_workspace_store.build_variable_semantic_artifacts)
    ]

    config_store = lsp_workspace_store.WorkspaceSnapshotStore()
    config_state = config_store._state_for_entry_locked(entry)
    config_future = Future()
    config_future.set_result(bundle)
    config_state.future = config_future
    config_store._config_version = 2
    config_store._finalize_future(config_state.cache_key, config_future, expected_config_version=1)
    assert config_state.future is config_future

    missing_state_store = lsp_workspace_store.WorkspaceSnapshotStore()
    missing_future = Future()
    missing_future.set_result(bundle)
    missing_state_store._finalize_future(entry.as_posix().casefold(), missing_future)

    generation_store = lsp_workspace_store.WorkspaceSnapshotStore()
    generation_state = generation_store._state_for_entry_locked(entry)
    generation_future = Future()
    generation_future.set_result(bundle)
    generation_state.future = generation_future
    generation_state.generation = 2
    generation_store._finalize_future(generation_state.cache_key, generation_future, expected_generation=1)
    assert generation_state.future is None

    mismatch_store = lsp_workspace_store.WorkspaceSnapshotStore()
    mismatch_state = mismatch_store._state_for_entry_locked(entry)
    mismatch_future = Future()
    mismatch_future.set_result(bundle)
    mismatch_state.future = Future()
    mismatch_store._finalize_future(mismatch_state.cache_key, mismatch_future)
    assert mismatch_state.future is not mismatch_future

    error_store = lsp_workspace_store.WorkspaceSnapshotStore()
    error_state = error_store._state_for_entry_locked(entry)
    error_future = Future()
    error_future.set_exception(RuntimeError("broken"))
    error_state.future = error_future
    error_store._finalize_future(error_state.cache_key, error_future)
    assert isinstance(error_state.last_error, RuntimeError)

    none_store = lsp_workspace_store.WorkspaceSnapshotStore()
    none_state = none_store._state_for_entry_locked(entry)
    none_future = Future()
    none_future.set_result(cast(Any, None))
    none_state.future = none_future
    none_store._finalize_future(none_state.cache_key, none_future)
    assert isinstance(none_state.last_error, RuntimeError)

    previous_store = lsp_workspace_store.WorkspaceSnapshotStore()
    previous_state = previous_store._state_for_entry_locked(entry)
    previous_state.bundle = old_bundle
    previous_future = Future()
    previous_future.set_result(bundle)
    previous_state.future = previous_future
    previous_store._source_file_to_entry_keys = {old_source: {previous_state.cache_key}}
    previous_store._finalize_future(previous_state.cache_key, previous_future)
    assert previous_state.bundle is bundle
    assert old_source not in previous_store._source_file_to_entry_keys
