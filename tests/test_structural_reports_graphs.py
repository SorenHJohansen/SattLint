# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint.devtools.structural import structural_reports
from tests import test_pipeline_collection as pipeline_collection_tests


def test_collect_graphics_layout_report_resolves_moduletype_moduledefs(tmp_path):
    pipeline_collection_tests.test_collect_graphics_layout_report_resolves_moduletype_moduledefs(tmp_path)


def test_collect_graphics_layout_report_flags_repeated_module_name_drift(tmp_path):
    pipeline_collection_tests.test_collect_graphics_layout_report_flags_repeated_module_name_drift(tmp_path)


def test_collect_workspace_graph_inputs_collects_snapshots_and_failures(monkeypatch, tmp_path):
    entry_ok = tmp_path / "ok.s"
    entry_fail = tmp_path / "fail.s"
    discovery = SimpleNamespace(program_files=[entry_ok, entry_fail])

    monkeypatch.setattr(structural_reports, "discover_workspace_sources", lambda _root: discovery)

    def fake_load_workspace_snapshot(entry_file, **_kwargs):
        if entry_file == entry_fail:
            raise RuntimeError("boom")
        return SimpleNamespace(entry_file=entry_file)

    monkeypatch.setattr(structural_reports, "load_workspace_snapshot", fake_load_workspace_snapshot)

    report = structural_reports.collect_workspace_graph_inputs(tmp_path)

    assert report.discovery is discovery
    assert report.snapshots == [SimpleNamespace(entry_file=entry_ok)]
    assert report.snapshot_failures == [
        {
            "entry_file": "fail.s",
            "error": "boom",
            "error_type": "RuntimeError",
        }
    ]


def test_collect_workspace_graph_inputs_scopes_entries_but_uses_full_discovery(monkeypatch, tmp_path):
    scoped_entry = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "ok.s"
    skipped_entry = tmp_path / "src" / "pkg" / "skip.s"
    full_discovery = SimpleNamespace(
        program_files=[scoped_entry, skipped_entry],
        dependency_files=[],
        referenced_program_names=frozenset({"ok"}),
    )
    filtered_discovery = SimpleNamespace(
        program_files=[scoped_entry],
        dependency_files=[],
        referenced_program_names=frozenset({"ok"}),
    )
    seen: list[tuple[Path, Any]] = []

    monkeypatch.setattr(structural_reports, "discover_workspace_sources", lambda _root: full_discovery)
    monkeypatch.setattr(
        structural_reports,
        "structural_report_discovery",
        lambda _root, _discovery: filtered_discovery,
    )

    def fake_load_workspace_snapshot(entry_file, **kwargs):
        seen.append((entry_file, kwargs.get("discovery")))
        return SimpleNamespace(entry_file=entry_file)

    monkeypatch.setattr(structural_reports, "load_workspace_snapshot", fake_load_workspace_snapshot)

    report = structural_reports.collect_workspace_graph_inputs(tmp_path)

    assert report.discovery is filtered_discovery
    assert report.snapshots == [SimpleNamespace(entry_file=scoped_entry)]
    assert seen == [(scoped_entry, full_discovery)]


@pytest.mark.parametrize(
    ("index", "total", "expected"),
    [
        (1, 3, True),
        (1, 20, True),
        (10, 20, True),
        (11, 20, False),
        (20, 20, True),
    ],
)
def test_should_emit_snapshot_progress_uses_small_first_last_and_tenth_markers(index, total, expected):
    assert structural_reports._should_emit_snapshot_progress(index, total) is expected


def test_registry_and_discovery_helpers_cover_structural_entry_scoping(monkeypatch, tmp_path):
    monkeypatch.setattr(
        structural_reports,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(to_report=lambda *, generated_by: {"generated_by": generated_by}),
    )

    scoped_entry = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "entry.s"
    other_entry = tmp_path / "src" / "pkg" / "other.s"
    discovery = SimpleNamespace(
        workspace_root=tmp_path,
        source_dirs=(tmp_path / "src",),
        program_files=[scoped_entry, other_entry],
        dependency_files=[tmp_path / "Libs" / "dep.s"],
        abb_lib_dir=tmp_path / "Libs",
        program_files_by_stem={"entry": scoped_entry},
        dependency_files_by_stem={"dep": tmp_path / "Libs" / "dep.s"},
        referenced_program_names=frozenset({"entry"}),
    )

    assert structural_reports.collect_analyzer_registry_report() == {"generated_by": "sattlint.devtools.pipeline"}
    assert structural_reports._structural_entry_files(tmp_path, (scoped_entry, other_entry)) == (scoped_entry,)

    scoped_discovery = structural_reports._structural_report_discovery(tmp_path, discovery)
    passthrough_discovery = structural_reports._structural_report_discovery(
        tmp_path,
        SimpleNamespace(**{**discovery.__dict__, "program_files": [other_entry]}),
    )

    assert scoped_discovery.program_files == (scoped_entry,)
    assert scoped_discovery.referenced_program_names == frozenset({"entry"})
    assert passthrough_discovery.program_files == [other_entry]


def test_graph_snapshot_helpers_build_and_collect_reports(tmp_path):
    entry_file = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "entry.s"
    discovery = SimpleNamespace(
        program_files=[entry_file],
        dependency_files=[tmp_path / "Libs" / "dep.s"],
    )
    definition = SimpleNamespace(
        declaration_module_path=("Target",),
        canonical_path="Target.value",
        field_path=None,
    )
    ignored_definition = SimpleNamespace(
        declaration_module_path=("Target",),
        canonical_path="Target.ignored",
        field_path=("child",),
    )
    read_access = SimpleNamespace(use_module_path=("Source",), kind=SimpleNamespace(value="read"))
    write_access = SimpleNamespace(use_module_path=None, kind=SimpleNamespace(value="write"))
    snapshot = SimpleNamespace(
        entry_file=entry_file,
        project_graph=SimpleNamespace(library_dependencies={"LibA": {"LibB"}}),
        base_picture=SimpleNamespace(name="Root"),
        definitions=[definition, ignored_definition],
        find_accesses_to=lambda current: [read_access, write_access] if current is definition else [],
    )

    dependency_nodes: dict[str, dict[str, object]] = {}
    dependency_edges: dict[tuple[str, str], dict[str, object]] = {}
    call_nodes: dict[str, dict[str, object]] = {}
    call_edges: dict[tuple[str, str], dict[str, object]] = {}

    structural_reports._accumulate_dependency_graph_snapshot(
        snapshot,
        workspace_root=tmp_path,
        node_index=dependency_nodes,
        edge_index=dependency_edges,
    )
    structural_reports._accumulate_call_graph_snapshot(
        snapshot,
        workspace_root=tmp_path,
        node_index=call_nodes,
        edge_index=call_edges,
    )

    dependency_report = structural_reports._build_dependency_graph_report(
        workspace_root=tmp_path,
        discovery=discovery,
        node_index=dependency_nodes,
        edge_index=dependency_edges,
        snapshot_count=1,
        snapshot_failures=[{"entry_file": "broken.s", "error": "boom", "error_type": "RuntimeError"}],
    )
    call_report = structural_reports._build_call_graph_report(
        workspace_root=tmp_path,
        node_index=call_nodes,
        edge_index=call_edges,
        snapshot_count=1,
        snapshot_failures=[],
    )
    collected_dependency_report = structural_reports.collect_dependency_graph_report(
        tmp_path,
        graph_inputs=(
            discovery,
            [snapshot],
            [{"entry_file": "broken.s", "error": "boom", "error_type": "RuntimeError"}],
        ),
    )
    collected_call_report = structural_reports.collect_call_graph_report(
        tmp_path,
        graph_inputs=(discovery, [snapshot], []),
    )

    assert dependency_nodes == {
        "LibA": {"id": "LibA", "kind": "library"},
        "LibB": {"id": "LibB", "kind": "library"},
    }
    assert dependency_report["edges"] == [
        {
            "source": "LibA",
            "target": "LibB",
            "kind": "depends_on",
            "entries": ["tests/fixtures/sample_sattline_files/entry.s"],
        }
    ]
    assert dependency_report["snapshot_count"] == 1
    assert dependency_report["snapshot_failures"][0]["entry_file"] == "broken.s"

    assert call_nodes == {
        "target": {"id": "Target", "kind": "module"},
        "source": {"id": "Source", "kind": "module"},
        "root": {"id": "Root", "kind": "module"},
    }
    assert call_report["edges"] == [
        {
            "source": "Root",
            "target": "Target",
            "kind": "module-access",
            "reads": 0,
            "writes": 1,
            "access_count": 1,
            "symbol_count": 1,
            "symbols": ["Target.value"],
            "entries": ["tests/fixtures/sample_sattline_files/entry.s"],
        },
        {
            "source": "Source",
            "target": "Target",
            "kind": "module-access",
            "reads": 1,
            "writes": 0,
            "access_count": 1,
            "symbol_count": 1,
            "symbols": ["Target.value"],
            "entries": ["tests/fixtures/sample_sattline_files/entry.s"],
        },
    ]
    assert collected_dependency_report["edges"] == dependency_report["edges"]
    assert collected_call_report["edges"] == call_report["edges"]


def test_stream_and_bundle_helpers_cover_progress_failures_and_normalization(monkeypatch, tmp_path):
    entry_ok = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "ok.s"
    entry_fail = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "fail.s"
    full_discovery = SimpleNamespace(program_files=[entry_ok, entry_fail], dependency_files=[])
    filtered_discovery = SimpleNamespace(program_files=[entry_ok, entry_fail], dependency_files=[])
    ok_snapshot = SimpleNamespace(entry_file=entry_ok)
    progress_messages: list[str] = []
    streamed_graph_inputs = structural_reports.WorkspaceGraphInputs(
        discovery=filtered_discovery,
        snapshots=[],
        snapshot_failures=[
            {
                "entry_file": "tests/fixtures/sample_sattline_files/fail.s",
                "error": "boom",
                "error_type": "ValueError",
            }
        ],
    )

    monkeypatch.setattr(structural_reports, "discover_workspace_sources", lambda _root: full_discovery)
    monkeypatch.setattr(structural_reports, "_structural_report_discovery", lambda _root, _disc: filtered_discovery)

    def fake_load_workspace_snapshot(entry_file, **_kwargs):
        if entry_file == entry_fail:
            raise ValueError("boom")
        return ok_snapshot

    monkeypatch.setattr(structural_reports, "load_workspace_snapshot", fake_load_workspace_snapshot)
    monkeypatch.setattr(
        structural_reports,
        "_accumulate_dependency_graph_snapshot",
        lambda snapshot, **kwargs: kwargs["node_index"].setdefault(
            "dep", {"id": snapshot.entry_file.stem, "kind": "library"}
        ),
    )
    monkeypatch.setattr(
        structural_reports,
        "_accumulate_call_graph_snapshot",
        lambda snapshot, **kwargs: kwargs["node_index"].setdefault(
            "call", {"id": snapshot.entry_file.stem, "kind": "module"}
        ),
    )
    monkeypatch.setattr(
        structural_reports,
        "accumulate_graphics_layout_snapshot",
        lambda snapshot, **kwargs: kwargs["entries"].append(
            {
                "entry_file": snapshot.entry_file.name,
                "module_path": snapshot.entry_file.stem,
                "module_kind": "basepicture",
                "module_name": snapshot.entry_file.stem,
            }
        ),
    )
    monkeypatch.setattr(
        structural_reports,
        "build_graphics_layout_report",
        lambda **kwargs: {
            "name": "graphics",
            "snapshot_count": kwargs["snapshot_count"],
            "entries": kwargs["entries"],
        },
    )

    graph_inputs, dependency_report, call_report, graphics_report = structural_reports._stream_workspace_graph_reports(
        tmp_path,
        progress_callback=progress_messages.append,
    )

    assert graph_inputs.snapshots == []
    assert graph_inputs.snapshot_failures == streamed_graph_inputs.snapshot_failures
    assert dependency_report["snapshot_count"] == 1
    assert call_report["snapshot_count"] == 1
    assert graphics_report["snapshot_count"] == 1
    assert graphics_report["entries"] == [
        {"entry_file": "ok.s", "module_path": "ok", "module_kind": "basepicture", "module_name": "ok"}
    ]
    assert progress_messages == [
        "Structural: loading 1/2 tests/fixtures/sample_sattline_files/ok.s",
        "Structural: loading 2/2 tests/fixtures/sample_sattline_files/fail.s",
        "Structural: failed 2/2 tests/fixtures/sample_sattline_files/fail.s (ValueError)",
    ]

    normalized_none = structural_reports._normalize_graph_inputs(None, workspace_root=tmp_path)
    normalized_tuple = structural_reports._normalize_graph_inputs(
        (filtered_discovery, [ok_snapshot], [{"entry_file": "fail.s"}]),
        workspace_root=tmp_path,
    )

    monkeypatch.setattr(structural_reports, "collect_workspace_graph_inputs", lambda _root: streamed_graph_inputs)
    normalized_none = structural_reports._normalize_graph_inputs(None, workspace_root=tmp_path)

    monkeypatch.setattr(structural_reports, "collect_architecture_report", lambda: {"name": "architecture"})
    monkeypatch.setattr(structural_reports, "collect_analyzer_registry_report", lambda: {"name": "registry"})
    monkeypatch.setattr(
        structural_reports,
        "_stream_workspace_graph_reports",
        lambda _root, progress_callback=None: (
            streamed_graph_inputs,
            {"name": "dependency"},
            {"name": "call"},
            {"name": "graphics-streamed"},
        ),
    )
    monkeypatch.setattr(
        structural_reports,
        "collect_graphics_layout_report",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("streamed bundle should reuse graphics report")),
    )
    monkeypatch.setattr(structural_reports, "collect_impact_analysis_report", lambda *_a, **_k: {"name": "impact"})

    bundle = structural_reports.collect_structural_reports(tmp_path)

    assert normalized_none is streamed_graph_inputs
    assert normalized_tuple.discovery is filtered_discovery
    assert normalized_tuple.snapshots == [ok_snapshot]
    assert normalized_tuple.snapshot_failures == [{"entry_file": "fail.s"}]
    assert bundle.architecture_report == {"name": "architecture"}
    assert bundle.analyzer_registry_report == {"name": "registry"}
    assert bundle.graph_inputs is streamed_graph_inputs
    assert bundle.dependency_graph_report == {"name": "dependency"}
    assert bundle.call_graph_report == {"name": "call"}
    assert bundle.graphics_layout_report == {"name": "graphics-streamed"}
    assert bundle.impact_analysis_report == {"name": "impact"}
