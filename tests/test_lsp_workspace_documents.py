# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false
"""Workspace document and workspace-diagnostics focused LSP tests."""

from __future__ import annotations

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
from sattlint.reporting.variables_report import IssueKind, VariableIssue
from sattlint_lsp import _server_helpers as lsp_helpers
from sattlint_lsp import _server_scan_helpers as scan_helpers
from sattlint_lsp.server import (
    LspSettings,
    SattLineLanguageServer,
    SnapshotBundle,
    _publish_closed_document_diagnostics,
    _publish_workspace_diagnostics_for_paths,
    _semantic_diagnostics_for_path,
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


def test_publish_closed_document_diagnostics_drops_stale_cache_when_snapshot_load_fails(monkeypatch, tmp_path):
    path = (tmp_path / "Program" / "Main.s").resolve()
    stale_diagnostic = cast(
        Any,
        SimpleNamespace(
            range=Range(start=Position(line=0, character=0), end=Position(line=0, character=1)),
            message="Stale",
            severity=1,
            source="sattlint",
        ),
    )
    published = []

    ls = SattLineLanguageServer()
    ls.settings = LspSettings(enable_variable_diagnostics=True, workspace_diagnostics_mode="background")
    ls.text_document_publish_diagnostics = lambda params: published.append(params)
    ls.published_workspace_diagnostics = {path: (stale_diagnostic,)}

    monkeypatch.setattr(
        "sattlint_lsp._server_document._load_snapshot_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("workspace unavailable")),
    )

    _publish_closed_document_diagnostics(ls, path)

    assert len(published) == 1
    assert published[0].uri.casefold() == path.as_uri().casefold()
    assert published[0].diagnostics == []
    assert path not in ls.published_workspace_diagnostics


def test_collect_entry_workspace_diagnostics_converts_recoverable_snapshot_failures(tmp_path):
    entry = (tmp_path / "Program" / "Main.s").resolve()
    snapshot_store = SimpleNamespace(
        get_bundle_for_entry=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("workspace unavailable"))
    )
    ls = SimpleNamespace(snapshot_store=snapshot_store)

    key, diagnostics_by_path = scan_helpers.collect_entry_workspace_diagnostics(ls, entry)

    assert key == entry.as_posix().casefold()
    assert diagnostics_by_path[entry][0].message.startswith("Workspace snapshot failed")


def test_collect_entry_workspace_diagnostics_propagates_fatal_snapshot_failures(tmp_path):
    entry = (tmp_path / "Program" / "Main.s").resolve()
    snapshot_store = SimpleNamespace(
        get_bundle_for_entry=lambda *_args, **_kwargs: (_ for _ in ()).throw(MemoryError("fatal snapshot"))
    )
    ls = SimpleNamespace(snapshot_store=snapshot_store)

    with pytest.raises(MemoryError, match="fatal snapshot"):
        scan_helpers.collect_entry_workspace_diagnostics(ls, entry)


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
        cast(Any, SimpleNamespace(kind=IssueKind.UNKNOWN_PARAMETER_TARGET, role="moduleparameter"))
    ).startswith("Unknown parameter mapping target: moduleparameter")
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
        source_file=cast(Any, "/tmp/Main.s"),
        source_library=cast(Any, "MainLib"),
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
                source_file=cast(Any, "/tmp/Main.s"),
                source_library=cast(Any, "MainLib"),
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
                source_file=cast(Any, "/tmp/Main.s"),
                source_library=cast(Any, "MainLib"),
                line=12,
                column=4,
                length=len("RecordVar"),
                message=core_diagnostics._format_semantic_diagnostic_message(issue),
                analyzer_key="variables",
            ),
        )
    }
