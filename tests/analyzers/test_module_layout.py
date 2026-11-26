"""Focused tests for the module-layout graphics analyzer."""

from __future__ import annotations

from math import inf, nan
from pathlib import Path

from sattline_parser import parse_source_file, parse_source_text
from sattline_parser.ast import (
    BasePicture,
    ClippingClause,
    FrameModule,
    GraphObject,
    InteractObject,
    LitStringTail,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    SourceSpan,
    Tail,
    VarRef,
    VarTail,
)

from sattlint.analyzers.module_layout import analyze_module_layout
from sattlint.config.analysis import (
    DEFAULT_MODULE_GRID,
    DEFAULT_MODULE_GRID_TOLERANCE,
    module_grid,
    module_grid_tolerance,
)
from sattlint.graphics.module_geometry import (
    Rect,
    diagnose_module_layout,
)

CENTERED = ((-1.0, -1.0), (1.0, 1.0))
BOTTOM_LEFT = ((0.0, 0.0), (1.0, 1.0))


def _header(
    name: str,
    coords: tuple[float, float, float, float, float] = (0.0, 0.0, 0.0, 1.0, 1.0),
    *,
    tails: tuple[Tail, ...] = (),
    line: int | None = None,
) -> ModuleHeader:
    span = None if line is None else SourceSpan(start=0, end=1, line=line, column=1)
    return ModuleHeader(name=name, invoke_coord=coords, invoke_coord_tails=list(tails), declaration_span=span)


def _module_def(
    clip: tuple[tuple[float, float], tuple[float, float]] = CENTERED,
    *,
    grid: float | None = None,
    tails: tuple[Tail, ...] = (),
    line: int | None = None,
    graph_objects: list[GraphObject] | None = None,
    interact_objects: list[InteractObject] | None = None,
) -> ModuleDef:
    span = None if line is None else SourceSpan(start=0, end=1, line=line, column=1)
    return ModuleDef(
        clipping=ClippingClause(bounds=clip, tails=tails, span=span),
        grid=grid,
        graph_objects=[] if graph_objects is None else graph_objects,
        interact_objects=[] if interact_objects is None else interact_objects,
    )


def _child(
    name: str,
    coords: tuple[float, float, float, float, float],
    module_def: ModuleDef | None = None,
) -> SingleModule:
    return SingleModule(header=_header(name, coords), moduledef=module_def or _module_def())


def _picture(
    *,
    clip: tuple[tuple[float, float], tuple[float, float]] = CENTERED,
    grid: float | None = None,
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] | None = None,
    moduletype_defs: list[ModuleTypeDef] | None = None,
    graph_objects: list[GraphObject] | None = None,
    interact_objects: list[InteractObject] | None = None,
    origin_file: str | None = None,
    origin_lib: str | None = None,
) -> BasePicture:
    return BasePicture(
        header=_header("Root"),
        name="Root",
        moduletype_defs=[] if moduletype_defs is None else moduletype_defs,
        submodules=[] if submodules is None else submodules,
        moduledef=_module_def(
            clip,
            grid=grid,
            graph_objects=graph_objects,
            interact_objects=interact_objects,
        ),
        origin_file=origin_file,
        origin_lib=origin_lib,
    )


def _kinds(picture: BasePicture) -> list[str]:
    return [finding.kind for finding in diagnose_module_layout(picture)]


def test_centered_clipping_has_no_origin_finding() -> None:
    assert "module_layout.origo_not_centered_or_corner" not in _kinds(_picture(clip=CENTERED))


def test_bottom_left_clipping_has_no_origin_finding() -> None:
    assert "module_layout.origo_not_centered_or_corner" not in _kinds(_picture(clip=BOTTOM_LEFT))


def test_origin_somewhere_else_is_reported() -> None:
    picture = _picture(clip=((-1.0, -1.0), (1.0, 1.66)))

    findings = diagnose_module_layout(picture)

    assert [finding.kind for finding in findings] == ["module_layout.origo_not_centered_or_corner"]
    assert findings[0].module_path == ("Root",)
    assert "neither at the clipping center nor at the bottom-left corner" in findings[0].message


def test_empty_clipping_is_reported_and_skips_the_rest() -> None:
    picture = _picture(
        clip=((0.5, 0.5), (0.5, 0.5)),
        graph_objects=[GraphObject(type="TextObject", properties={"coords": ((9.0, 9.0), (10.0, 10.0))})],
    )

    findings = diagnose_module_layout(picture)

    assert [finding.kind for finding in findings] == ["module_layout.invalid_clipping"]


def test_clipping_with_tails_is_not_judged_from_its_literal_values() -> None:
    picture = BasePicture(
        header=_header("Root"),
        name="Root",
        moduledef=_module_def(
            ((9.0, 9.0), (10.0, 10.0)),
            tails=(VarTail(direction="in", value="ClipVar"),),
            graph_objects=[GraphObject(type="TextObject", properties={"coords": ((0.0, 0.0), (0.1, 0.1))})],
        ),
    )

    assert diagnose_module_layout(picture) == ()


def test_clipping_size_off_grid_is_reported() -> None:
    picture = _picture(clip=((0.0, 0.0), (0.27, 1.0)))

    findings = diagnose_module_layout(picture)

    assert [finding.kind for finding in findings] == ["module_layout.size_off_grid"]
    assert "width 0.27" in findings[0].message


def test_clipping_size_uses_the_modules_own_grid() -> None:
    assert diagnose_module_layout(_picture(clip=((0.0, 0.0), (0.03, 0.1)), grid=0.01)) == ()
    assert "module_layout.size_off_grid" in _kinds(_picture(clip=((0.0, 0.0), (0.03, 0.1))))


def test_invocation_position_off_grid_is_reported() -> None:
    picture = _picture(submodules=[_child("Child", (0.05, 0.0, 0.0, 0.4, 0.4))])

    findings = [finding for finding in diagnose_module_layout(picture) if finding.kind.endswith("position_off_grid")]

    assert len(findings) == 1
    assert findings[0].module_path == ("Root", "Child")
    assert "x = 0.05" in findings[0].message
    assert findings[0].details["grid"] == DEFAULT_MODULE_GRID


def test_invocation_size_off_grid_is_reported() -> None:
    picture = _picture(submodules=[_child("Child", (0.0, 0.0, 0.0, 0.27, 0.4))])

    findings = [finding for finding in diagnose_module_layout(picture) if finding.kind == "module_layout.size_off_grid"]

    assert len(findings) == 1
    assert "width 0.27" in findings[0].message


def test_invocation_uses_the_parent_grid() -> None:
    picture = _picture(grid=0.01, submodules=[_child("Child", (0.03, 0.0, 0.0, 0.03, 0.03))])

    assert diagnose_module_layout(picture) == ()


def test_invocation_with_tails_is_not_judged_from_its_literal_values() -> None:
    child = SingleModule(
        header=_header(
            "Child",
            (0.05, 0.0, 0.0, 0.27, 0.4),
            tails=(VarTail(direction="in", value="PosVar"),),
        ),
        moduledef=_module_def(),
    )

    assert diagnose_module_layout(_picture(submodules=[child])) == ()


def test_expression_tail_is_treated_as_variable_driven() -> None:
    child = SingleModule(
        header=_header("Child", (0.05, 0.0, 0.0, 0.27, 0.4), tails=(VarRef(name="PosVar"),)),
        moduledef=_module_def(),
    )

    assert diagnose_module_layout(_picture(submodules=[child])) == ()


def test_outvar_tail_leaves_the_written_position_static() -> None:
    child = SingleModule(
        header=_header("Child", (0.05, 0.0, 0.0, 0.4, 0.4), tails=(VarTail(direction="out", value="PosOut"),)),
        moduledef=_module_def(),
    )

    assert [finding.kind for finding in diagnose_module_layout(_picture(submodules=[child]))] == [
        "module_layout.position_off_grid"
    ]


def test_invar_literal_tail_leaves_the_written_position_static() -> None:
    child = SingleModule(
        header=_header("Child", (0.05, 0.0, 0.0, 0.4, 0.4), tails=(VarTail(direction="in", value=5),)),
        moduledef=_module_def(),
    )

    assert [finding.kind for finding in diagnose_module_layout(_picture(submodules=[child]))] == [
        "module_layout.position_off_grid"
    ]


def test_litstring_tail_leaves_the_written_position_static() -> None:
    symbol = LitStringTail(keyword="LitString", text="SymbolName")
    child = SingleModule(
        header=_header("Child", (0.05, 0.0, 0.0, 0.4, 0.4), tails=(VarTail(direction="in", value=symbol),)),
        moduledef=_module_def(),
    )

    assert [finding.kind for finding in diagnose_module_layout(_picture(submodules=[child]))] == [
        "module_layout.position_off_grid"
    ]


def test_object_fully_outside_clipping_is_reported() -> None:
    picture = _picture(
        graph_objects=[GraphObject(type="TextObject", properties={"coords": ((2.0, 2.0), (3.0, 3.0))})],
    )

    findings = diagnose_module_layout(picture)

    assert [finding.kind for finding in findings] == ["module_layout.object_outside_clipping"]
    assert "TextObject lies entirely outside" in findings[0].message
    assert findings[0].details["object_class"] == "graph"


def test_object_touching_the_clipping_edge_is_not_reported() -> None:
    picture = _picture(
        graph_objects=[GraphObject(type="TextObject", properties={"coords": ((1.0, 0.0), (2.0, 1.0))})],
    )

    assert diagnose_module_layout(picture) == ()


def test_object_partly_outside_clipping_is_not_reported() -> None:
    picture = _picture(
        graph_objects=[GraphObject(type="TextObject", properties={"coords": ((0.5, 0.0), (2.0, 1.0))})],
    )

    assert diagnose_module_layout(picture) == ()


def test_interactor_bounding_box_is_the_union_of_its_boxes() -> None:
    picture = _picture(
        interact_objects=[
            InteractObject(
                type="TextBox_",
                properties={"coords": [((0.0, 0.0), (0.4, 0.4)), ((0.8, 0.8), (1.0, 1.0))]},
            )
        ],
    )

    assert diagnose_module_layout(picture) == ()


def test_object_with_coordinate_tails_is_skipped() -> None:
    object_with_tail = GraphObject(
        type="TextObject",
        properties={
            "coords": ((2.0, 2.0), (3.0, 3.0)),
            "coord_tails": ((), (VarTail(direction="in", value="PosVar"),), (), ()),
        },
    )

    assert diagnose_module_layout(_picture(graph_objects=[object_with_tail])) == ()


def test_module_type_definition_is_checked() -> None:
    module_type = ModuleTypeDef(
        name="Panel",
        moduledef=_module_def(((0.0, 0.0), (0.27, 1.0))),
    )

    findings = diagnose_module_layout(_picture(moduletype_defs=[module_type]))

    assert [finding.kind for finding in findings] == ["module_layout.size_off_grid"]
    assert findings[0].module_path == ("Root", "TypeDef:Panel")


def test_module_types_from_dependencies_are_not_reported() -> None:
    local_panel = ModuleTypeDef(
        name="LocalPanel",
        moduledef=_module_def(((0.0, 0.0), (0.27, 1.0))),
        origin_file="Local.s",
        origin_lib="LocalLib",
    )
    dependency_panel = ModuleTypeDef(
        name="DependencyPanel",
        moduledef=_module_def(((0.0, 0.0), (0.29, 1.0))),
        origin_file="Dependency.s",
        origin_lib="DependencyLib",
    )
    picture = _picture(
        moduletype_defs=[local_panel, dependency_panel],
        origin_file="Local.s",
        origin_lib="LocalLib",
    )

    report = analyze_module_layout(picture)

    assert [tuple(issue.module_path or ()) for issue in report.issues] == [("Root", "TypeDef:LocalPanel")]


def test_module_type_instance_placement_is_checked_but_its_body_is_not_descended_into() -> None:
    instance = ModuleTypeInstance(
        header=_header("Panel1", (0.05, 0.0, 0.0, 0.4, 0.4)),
        moduletype_name="Panel",
    )

    findings = diagnose_module_layout(_picture(submodules=[instance]))

    assert [finding.kind for finding in findings] == ["module_layout.position_off_grid"]
    assert findings[0].module_path == ("Root", "Panel1")


def test_line_numbers_come_from_the_clipping_and_header_spans() -> None:
    child = SingleModule(
        header=_header("Child", (0.05, 0.0, 0.0, 0.4, 0.4), line=12),
        moduledef=_module_def(((0.0, 0.0), (0.27, 1.0)), line=20),
    )

    findings = {finding.kind: finding for finding in diagnose_module_layout(_picture(submodules=[child]))}

    assert findings["module_layout.position_off_grid"].line == 12
    assert findings["module_layout.size_off_grid"].line == 20


def test_analyzer_exposes_findings_with_line_metadata() -> None:
    picture = _picture(submodules=[_child("Child", (0.05, 0.0, 0.0, 0.4, 0.4))])

    report = analyze_module_layout(picture)

    assert report.name == "Root"
    issue = next(issue for issue in report.issues if issue.kind == "module_layout.position_off_grid")
    assert issue.module_path == ["Root", "Child"]
    assert issue.data is not None
    assert issue.data["position"] == [0.05, 0.0]


def test_grid_configuration_defaults_and_overrides() -> None:
    assert module_grid(None) == DEFAULT_MODULE_GRID
    assert module_grid_tolerance(None) == DEFAULT_MODULE_GRID_TOLERANCE
    assert module_grid({"analysis": {"module_grid": 0.01}}) == 0.01
    assert module_grid({"analysis": {"module_grid": 0}}) == DEFAULT_MODULE_GRID
    assert module_grid({"analysis": {"module_grid": inf}}) == DEFAULT_MODULE_GRID
    assert module_grid({"analysis": {"module_grid": nan}}) == DEFAULT_MODULE_GRID
    assert module_grid_tolerance({"analysis": {"module_grid_tolerance": 0.001}}) == 0.001


def test_analyzer_reads_the_grid_from_config() -> None:
    picture = _picture(submodules=[_child("Child", (0.05, 0.0, 0.0, 0.4, 0.4))])

    off_grid = analyze_module_layout(picture)
    configured = analyze_module_layout(picture, config={"analysis": {"module_grid": 0.01}})

    assert [issue.kind for issue in off_grid.issues] == ["module_layout.position_off_grid"]
    assert configured.issues == []


def test_finding_kinds_have_human_labels() -> None:
    from sattlint.application.findings import kind_human_label  # noqa: PLC0415

    assert kind_human_label("module_layout.invalid_clipping") == "Invalid clipping bounds"
    assert kind_human_label("module_layout.size_off_grid") == "Module size off grid"
    assert kind_human_label("module_layout.position_off_grid") == "Module placement off grid"
    assert kind_human_label("module_layout.object_outside_clipping") == "Object outside clipping bounds"
    assert (
        kind_human_label("module_layout.origo_not_centered_or_corner")
        == "Module origin not centered or at the bottom-left"
    )


def test_analyzer_is_selectable_with_the_expected_metadata() -> None:
    from sattlint.analyzers.registry import get_selectable_analyzers  # noqa: PLC0415

    spec = next(spec for spec in get_selectable_analyzers() if spec.key == "module-layout")

    assert spec.name == "Module layout"
    assert spec.category == "heuristic"
    assert spec.scope == "per-target"


def test_rect_normalizes_reversed_corners() -> None:
    rect = Rect.from_corners((1.0, 2.0), (-1.0, 0.5))

    assert (rect.x_min, rect.y_min, rect.x_max, rect.y_max) == (-1.0, 0.5, 1.0, 2.0)


def _parse_layout_source(body: str) -> BasePicture:
    return parse_source_text(
        '"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"\n'
        '"Original file date: ---"\n'
        '"Program date: 2026-04-23-12:00:00.000, name: Layout"\n'
        "\n"
        "BasePicture Invocation\n"
        "   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION\n"
        "\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        f"{body}\n"
        "ENDDEF (*BasePicture*);\n"
    )


def test_parsed_polygon_outside_clipping_is_reported() -> None:
    picture = _parse_layout_source(
        "GraphObjects :\n   PolygonObject ( 2.0 , 2.0 ) ( 3.0 , 3.0 )\n      ( 2.5 , 2.5 )\n"
    )

    findings = diagnose_module_layout(picture)

    assert [finding.kind for finding in findings] == ["module_layout.object_outside_clipping"]
    assert findings[0].line == 11


def test_parsed_variable_driven_polygon_point_is_skipped() -> None:
    picture = _parse_layout_source(
        'GraphObjects :\n   PolygonObject ( 2.0 , 2.0 ) ( 3.0 , 3.0 )\n      ( 2.5 : InVar_ "X" , 2.5 )\n'
    )

    assert diagnose_module_layout(picture) == ()


def test_real_fixture_reports_its_off_grid_child() -> None:
    picture = parse_source_file(Path(__file__).resolve().parents[1] / "fixtures/sample_sattline_files/EnableExpr.s")

    findings = diagnose_module_layout(picture)

    assert [finding.kind for finding in findings] == ["module_layout.position_off_grid"]
    assert findings[0].module_path == ("BasePicture", "Child")


def test_analyzer_omits_line_metadata_when_the_source_has_none() -> None:
    report = analyze_module_layout(_picture(clip=((-1.0, -1.0), (1.0, 1.66))))

    assert report.issues[0].data is not None
    assert "line" not in report.issues[0].data


def test_analyzer_includes_line_metadata_when_the_source_has_it() -> None:
    picture = _parse_layout_source(
        'GraphObjects :\n   TextObject ( 2.0 , 2.0 ) ( 3.0 , 3.0 )\n      "Label"\n      OutlineColour : Colour0 = -3\n'
    )

    report = analyze_module_layout(picture)

    assert report.issues[0].data is not None
    assert report.issues[0].data["line"] == 11


def test_segment_point_extends_the_object_bounds() -> None:
    picture = _picture(
        graph_objects=[
            GraphObject(
                type="SegmentObject",
                properties={"coords": ((2.0, 2.0), (2.2, 2.2)), "segment_point": (9.0, 9.0)},
            )
        ],
    )

    assert [finding.kind for finding in diagnose_module_layout(picture)] == ["module_layout.object_outside_clipping"]


def test_point_coordinate_is_treated_as_a_zero_area_box() -> None:
    picture = _picture(graph_objects=[GraphObject(type="ConnectionNode", properties={"coords": (9.0, 9.0)})])

    assert [finding.kind for finding in diagnose_module_layout(picture)] == ["module_layout.object_outside_clipping"]


def test_object_without_geometry_is_skipped() -> None:
    assert diagnose_module_layout(_picture(graph_objects=[GraphObject(type="CompositeObject")])) == ()


def test_interactor_outside_clipping_is_reported() -> None:
    picture = _picture(
        interact_objects=[InteractObject(type="TextBox_", properties={"coords": [((2.0, 2.0), (3.0, 3.0))]})],
    )

    findings = diagnose_module_layout(picture)

    assert [finding.kind for finding in findings] == ["module_layout.object_outside_clipping"]
    assert findings[0].details["object_class"] == "interactor"


def test_interactor_with_coordinate_tails_is_skipped() -> None:
    interact_object = InteractObject(
        type="TextBox_",
        properties={
            "coords": [((2.0, 2.0), (3.0, 3.0))],
            "coord_tails": ((), (), (VarTail(direction="in", value="PosVar"),), ()),
        },
    )

    assert diagnose_module_layout(_picture(interact_objects=[interact_object])) == ()


def test_interactor_without_coordinates_is_skipped() -> None:
    assert diagnose_module_layout(_picture(interact_objects=[InteractObject(type="TextBox_")])) == ()


def test_module_without_a_layout_block_is_skipped() -> None:
    picture = BasePicture(header=_header("Root"), name="Root", moduledef=None)

    assert diagnose_module_layout(picture) == ()


def test_clipping_height_off_grid_is_reported() -> None:
    findings = diagnose_module_layout(_picture(clip=((0.0, 0.0), (1.0, 0.27))))

    assert [finding.kind for finding in findings] == ["module_layout.size_off_grid"]
    assert "height 0.27" in findings[0].message


def test_zero_grid_disables_alignment_findings() -> None:
    picture = _picture(clip=((0.0, 0.0), (0.27, 0.27)), submodules=[_child("Child", (0.05, 0.0, 0.0, 0.4, 0.4))])

    assert diagnose_module_layout(picture, grid=0) == ()
