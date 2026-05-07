from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)
from sattlint.devtools import structural_reports


def test_access_iteration_and_graphics_helpers_cover_iterator_and_optional_fields(tmp_path):
    definition = SimpleNamespace(canonical_path="Target.value", field_path=None)
    iterator_snapshot = SimpleNamespace(
        iter_access_events_by_definition=lambda *, roots_only: [(definition, ["access"])],
    )
    fallback_snapshot = SimpleNamespace(
        definitions=[definition, SimpleNamespace(field_path=("child",))],
        find_accesses_to=lambda current: [current.canonical_path],
    )
    header = ModuleHeader(
        name="Module",
        invoke_coord=(1, 2, 3, 4, 5),
        invocation_arguments=("A",),
        layer_info="L1",
        zoom_limits=(0.5, 2.0),
        zoomable=True,
    )
    moduledef = ModuleDef(
        clipping_bounds=((1, 2), (3, 4)),
        zoom_limits=(0.25, 1.5),
        grid=0.5,
        zoomable=True,
    )
    resolved_moduletype = ModuleTypeDef(name="MT", origin_file="lib/file.s", origin_lib="Lib")

    entry = structural_reports._graphics_layout_entry(
        workspace_root=tmp_path,
        entry_file=tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "entry.s",
        module_path=("Root", "Child"),
        module_kind="moduletype-instance",
        header=header,
        moduledef=moduledef,
        definition_scope="module",
        moduledef_origin_kind="moduletype-definition",
        moduletype_name="MT",
        resolved_moduletype=resolved_moduletype,
        resolution_error="warn",
    )
    drift_payload = structural_reports._graphics_layout_group_payload(
        module_kind="module",
        module_name="Child",
        members=[
            entry,
            {
                **entry,
                "module_path": "Root.Other",
                "moduledef": {**entry["moduledef"], "grid": 0.75},
            },
        ],
    )
    consistent_payload = structural_reports._graphics_layout_group_payload(
        module_kind="module",
        module_name="Child",
        members=[entry],
    )

    assert list(structural_reports._iter_snapshot_accesses_by_definition(iterator_snapshot)) == [
        (definition, ["access"])
    ]
    assert list(structural_reports._iter_snapshot_accesses_by_definition(fallback_snapshot)) == [
        (definition, ["Target.value"])
    ]
    assert structural_reports._serialize_invoke_coord(header) == {
        "coords": [1.0, 2.0, 3.0, 4.0, 5.0],
        "arguments": ["A"],
        "layer": "L1",
        "zoom_limits": [0.5, 2.0],
        "zoomable": True,
    }
    assert structural_reports._serialize_moduledef(moduledef) == {
        "clipping_origin": [1.0, 2.0],
        "clipping_size": [3.0, 4.0],
        "zoom_limits": [0.25, 1.5],
        "grid": 0.5,
        "zoomable": True,
    }
    assert structural_reports._stable_json_marker({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert structural_reports._graphics_field_value(entry, "moduledef.grid") == 0.5
    assert structural_reports._graphics_field_value(entry, "moduledef.grid.value") is None
    assert drift_payload["status"] == "drift"
    assert drift_payload["differing_fields"]
    assert drift_payload["field_variants"]
    assert consistent_payload["status"] == "consistent"
    assert entry["relative_module_path"] == "Child"
    assert entry["moduletype_name"] == "MT"
    assert entry["resolved_moduletype"] == {
        "name": "MT",
        "origin_file": "lib/file.s",
        "origin_lib": "Lib",
    }
    assert entry["resolution_error"] == "warn"


def test_walk_graphics_layout_children_covers_recursive_moduletype_and_resolution_failure(monkeypatch, tmp_path):
    recursive_type = ModuleTypeDef(
        name="ResolvedType",
        moduledef=ModuleDef(grid=0.25),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="NestedLeaf", invoke_coord=(0, 0, 0, 0, 0)),
                moduledef=ModuleDef(grid=0.5),
            ),
            ModuleTypeInstance(
                header=ModuleHeader(name="NestedSelf", invoke_coord=(0, 0, 0, 0, 0)),
                moduletype_name="ResolvedType",
            ),
        ],
        origin_lib="Lib",
        origin_file="Lib/ResolvedType.s",
    )

    def fake_resolve(_bp, moduletype_name, *, current_library=None, unavailable_libraries=None):
        assert unavailable_libraries == {"Ghost"}
        if moduletype_name == "MissingType":
            raise LookupError("missing moduletype")
        return recursive_type

    monkeypatch.setattr(structural_reports, "resolve_moduletype_def_strict", fake_resolve)

    entries: list[dict[str, object]] = []
    active_moduletype_keys: set[tuple[str, str]] = set()
    children = [
        SingleModule(
            header=ModuleHeader(name="Local", invoke_coord=(0, 0, 0, 0, 0)),
            moduledef=ModuleDef(grid=1.0),
        ),
        FrameModule(
            header=ModuleHeader(name="Frame", invoke_coord=(0, 0, 0, 0, 0)),
            submodules=[
                SingleModule(
                    header=ModuleHeader(name="FrameLeaf", invoke_coord=(0, 0, 0, 0, 0)),
                    moduledef=ModuleDef(grid=2.0),
                )
            ],
            moduledef=ModuleDef(grid=1.5),
        ),
        ModuleTypeInstance(
            header=ModuleHeader(name="Resolved", invoke_coord=(0, 0, 0, 0, 0)),
            moduletype_name="ResolvedType",
        ),
        ModuleTypeInstance(
            header=ModuleHeader(name="Broken", invoke_coord=(0, 0, 0, 0, 0)),
            moduletype_name="MissingType",
        ),
    ]

    structural_reports._walk_graphics_layout_children(
        bp=cast(Any, SimpleNamespace(name="BasePicture")),
        children=children,
        entry_file=tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "entry.s",
        workspace_root=tmp_path,
        snapshot=SimpleNamespace(project_graph=SimpleNamespace(unavailable_libraries={"Ghost"})),
        entries=entries,
        parent_path=("BasePicture",),
        current_library=None,
        definition_scope="module",
        active_moduletype_keys=active_moduletype_keys,
    )

    entry_names = [entry["module_path"] for entry in entries]

    assert entry_names == [
        "BasePicture.Local",
        "BasePicture.Frame",
        "BasePicture.Frame.FrameLeaf",
        "BasePicture.Resolved",
        "BasePicture.Resolved.NestedLeaf",
        "BasePicture.Resolved.NestedSelf",
        "BasePicture.Broken",
    ]
    assert entries[3]["moduledef_origin_kind"] == "moduletype-definition"
    assert entries[5]["moduledef_origin_kind"] == "moduletype-definition"
    assert entries[6]["moduledef_origin_kind"] == "unresolved-moduletype"
    assert entries[6]["resolution_error"] == "missing moduletype"
    assert active_moduletype_keys == set()


def test_collect_structural_reports_uses_provided_graph_inputs_branch(monkeypatch, tmp_path):
    discovery = SimpleNamespace(program_files=[], dependency_files=[])
    tuple_graph_inputs = (discovery, [SimpleNamespace(entry_file=tmp_path / "entry.s")], [{"entry_file": "entry.s"}])
    collector_calls: list[tuple[str, object]] = []

    monkeypatch.setattr(structural_reports, "collect_architecture_report", lambda: {"name": "architecture"})
    monkeypatch.setattr(structural_reports, "collect_analyzer_registry_report", lambda: {"name": "registry"})
    monkeypatch.setattr(
        structural_reports,
        "collect_dependency_graph_report",
        lambda _root, *, graph_inputs: collector_calls.append(("dependency", graph_inputs)) or {"name": "dependency"},
    )
    monkeypatch.setattr(
        structural_reports,
        "collect_call_graph_report",
        lambda _root, *, graph_inputs: collector_calls.append(("call", graph_inputs)) or {"name": "call"},
    )
    monkeypatch.setattr(structural_reports, "collect_graphics_layout_report", lambda *_a, **_k: {"name": "graphics"})
    monkeypatch.setattr(structural_reports, "collect_impact_analysis_report", lambda *_a, **_k: {"name": "impact"})

    bundle = structural_reports.collect_structural_reports(tmp_path, graph_inputs=tuple_graph_inputs)

    assert isinstance(bundle.graph_inputs, structural_reports.WorkspaceGraphInputs)
    assert bundle.graph_inputs.discovery is discovery
    assert [name for name, _inputs in collector_calls] == ["dependency", "call"]
    assert collector_calls[0][1] is bundle.graph_inputs
    assert collector_calls[1][1] is bundle.graph_inputs
    assert bundle.dependency_graph_report == {"name": "dependency"}
    assert bundle.call_graph_report == {"name": "call"}
