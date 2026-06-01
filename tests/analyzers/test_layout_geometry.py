from typing import Any, cast

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import (
    BasePicture,
    GraphObject,
    InteractObject,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    SingleModule,
)
from sattlint.analyzers import layout_geometry as layout_geometry_module
from sattlint.analyzers.layout_geometry import collect_layout_overlap_issues
from sattlint.reporting.variables_report import IssueKind


def _hdr(
    name: str,
    *,
    layer_info: str | None = None,
    invoke_coord: tuple[float, float, float, float, float] = (0.0, 0.0, 0.0, 0.1, 0.1),
) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=invoke_coord, layer_info=layer_info)


def test_layout_overlap_detects_overlapping_module_invocations() -> None:
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 1
    ModuleDef
        ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
SUBMODULES
    ChildA Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : ChildType;
    ChildB Invocation ( 0.5 , 0.5 , 0.0 , 1.0 , 1.0 ) : ChildType;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    issues = collect_layout_overlap_issues(bp)

    assert len(issues) == 1
    assert issues[0].kind is IssueKind.LAYOUT_OVERLAP
    assert issues[0].role == "module 'ChildA' overlaps module 'ChildB'"


def test_layout_overlap_ignores_modules_on_different_layers() -> None:
    child_moduledef = ModuleDef(clipping_bounds=((-1.0, -1.0), (1.0, 1.0)))
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Layer1", layer_info="1"),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("Layer2", layer_info="2", invoke_coord=(0.02, 0.02, 0.0, 0.1, 0.1)),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    assert collect_layout_overlap_issues(bp) == []


def test_layout_overlap_uses_module_clipping_bounds_for_visible_overlap() -> None:
    child_moduledef = ModuleDef(clipping_bounds=((-1.0, -1.0), (1.0, 1.0)))
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("ChildA"),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("ChildB", invoke_coord=(0.1, 0.1, 0.0, 0.1, 0.1)),
                moduledef=child_moduledef,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    issues = collect_layout_overlap_issues(bp)

    assert len(issues) == 1
    assert issues[0].role == "module 'ChildA' overlaps module 'ChildB'"


def test_layout_overlap_detects_overlapping_graph_and_interact_objects() -> None:
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=ModuleDef(
            graph_objects=[GraphObject(type="TextObject", properties={"coords": ((0.0, 0.0), (1.0, 1.0))})],
            interact_objects=[InteractObject(type="ComBut_", properties={"coords": [((0.5, 0.5), (1.25, 1.25))]})],
        ),
    )

    issues = collect_layout_overlap_issues(bp)

    assert len(issues) == 1
    assert issues[0].role == "graph object TextObject #1 overlaps interact object ComBut_ #1"


def test_layout_overlap_ignores_objects_on_different_layers() -> None:
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=ModuleDef(
            graph_objects=[GraphObject(type="TextObject", properties={"coords": ((0.0, 0.0), (1.0, 1.0)), "layer": 1})],
            interact_objects=[
                InteractObject(type="ComBut_", properties={"coords": [((0.5, 0.5), (1.25, 1.25))], "layer": 2})
            ],
        ),
    )

    assert collect_layout_overlap_issues(bp) == []


def test_layout_geometry_helpers_cover_normalization_and_fallbacks() -> None:
    helpers: Any = layout_geometry_module

    assert helpers._path_key(["Root", "Child"]) == ("root", "child")
    assert helpers._path_relation(["Root"], None) == "within"
    assert helpers._path_relation(["Root"], ["ROOT", "Child"]) == "ancestor"
    assert helpers._path_relation(["Root", "Child"], ["Elsewhere"]) == "unrelated"

    assert helpers._point_pair_to_rect((1.0, 1.0), (1.0, 2.0)) is None
    assert helpers._is_point([0.0, 1.0]) is False
    assert helpers._is_point((0.0, "bad")) is False
    assert helpers._is_point_pair([(0.0, 0.0), (1.0, 1.0)]) is False
    assert helpers._is_point_pair(((0.0, 0.0), (1.0, "bad"))) is False
    assert helpers._normalize_rect([(0.0, 0.0), (1.0, 1.0)]) == (0.0, 0.0, 1.0, 1.0)
    assert helpers._normalize_rect([((0.0, 0.0), (1.0, 1.0))]) == (0.0, 0.0, 1.0, 1.0)
    assert helpers._normalize_rect([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]) is None
    assert helpers._normalize_layer(None) is None
    assert helpers._normalize_layer("   ") is None

    degenerate_child = SingleModule(
        header=_hdr("Flat", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    fallback_child = SingleModule(
        header=_hdr("Fallback", layer_info=" LayerA ", invoke_coord=(1.0, 2.0, 0.0, 2.0, 3.0)),
        moduledef=ModuleDef(clipping_bounds=cast(Any, [(0.0, 0.0), ("bad", 1.0)])),
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    assert helpers._clip_rect(degenerate_child) is None
    assert helpers._module_rect(degenerate_child) is None
    assert helpers._clip_rect(fallback_child) is None

    fallback_rect = helpers._module_rect(fallback_child)

    assert fallback_rect is not None
    assert fallback_rect.rect == (1.0, 2.0, 3.0, 5.0)
    assert fallback_rect.layer == "LayerA"

    object_rects = helpers._collect_object_rects(
        [
            GraphObject(type="Skipped", properties={}),
            type("AnonymousGraphic", (), {"properties": {"coords": [((0.0, 0.0), (1.0, 1.0))]}})(),
        ],
        category="graph object",
    )

    assert len(object_rects) == 1
    assert object_rects[0].label == "graph object graph object #2"


def test_layout_overlap_limit_path_can_target_typedefs() -> None:
    child_moduledef = ModuleDef(clipping_bounds=((-1.0, -1.0), (1.0, 1.0)))
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[
            ModuleTypeDef(
                name="ChildType",
                moduleparameters=[],
                localvariables=[],
                submodules=[
                    SingleModule(
                        header=_hdr("ChildA"),
                        moduledef=child_moduledef,
                        moduleparameters=[],
                        localvariables=[],
                        submodules=[],
                        modulecode=None,
                        parametermappings=[],
                    ),
                    SingleModule(
                        header=_hdr("ChildB", invoke_coord=(0.1, 0.1, 0.0, 0.1, 0.1)),
                        moduledef=child_moduledef,
                        moduleparameters=[],
                        localvariables=[],
                        submodules=[],
                        modulecode=None,
                        parametermappings=[],
                    ),
                ],
                moduledef=None,
                modulecode=None,
                parametermappings=[],
            )
        ],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    issues = collect_layout_overlap_issues(bp, limit_to_module_path=["Program", "TypeDef:ChildType"])

    assert len(issues) == 1
    assert issues[0].module_path == ["Program", "TypeDef:ChildType"]
    assert collect_layout_overlap_issues(bp, limit_to_module_path=["Program", "Elsewhere"]) == []


def test_layout_overlap_skips_same_layer_rects_when_they_do_not_intersect() -> None:
    issues = collect_layout_overlap_issues(
        BasePicture(
            header=_hdr("Program"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[],
            submodules=[
                SingleModule(
                    header=_hdr("Left", layer_info="1", invoke_coord=(0.0, 0.0, 0.0, 0.1, 0.1)),
                    moduledef=None,
                    moduleparameters=[],
                    localvariables=[],
                    submodules=[],
                    modulecode=None,
                    parametermappings=[],
                ),
                SingleModule(
                    header=_hdr("Right", layer_info="1", invoke_coord=(0.5, 0.5, 0.0, 0.1, 0.1)),
                    moduledef=None,
                    moduleparameters=[],
                    localvariables=[],
                    submodules=[],
                    modulecode=None,
                    parametermappings=[],
                ),
            ],
            modulecode=None,
            moduledef=None,
        )
    )

    assert issues == []
