from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
)

from sattlint.graphics.picture_display_runtime import (
    build_runtime_tree,
    collect_concrete_composite_placeholders,
)


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _recursive_dependency_picture() -> BasePicture:
    """A dependency module type whose body instantiates itself once more."""
    recursive = ModuleTypeDef(
        name="Rec",
        moduleparameters=[],
        localvariables=[],
        submodules=[ModuleTypeInstance(header=_header("Inner"), moduletype_name="Rec", parametermappings=[])],
        moduledef=ModuleDef(),
        modulecode=None,
    )
    recursive.origin_file = "Dep.s"
    base_picture = BasePicture(
        header=_header("Root"),
        datatype_defs=[],
        moduletype_defs=[recursive],
        localvariables=[],
        submodules=[ModuleTypeInstance(header=_header("Outer"), moduletype_name="Rec", parametermappings=[])],
        modulecode=None,
        moduledef=ModuleDef(),
    )
    base_picture.origin_file = "Root.s"
    return base_picture


def test_runtime_tree_stops_at_a_recursive_dependency_moduletype() -> None:
    base_picture = _recursive_dependency_picture()

    tree = build_runtime_tree(base_picture, graph=None)

    outer = tree.root.children[0]
    assert outer.name == "Outer"
    assert [child.name for child in outer.children] == ["Inner"]
    assert outer.children[0].children == ()


def test_placeholder_walk_stops_at_a_recursive_dependency_moduletype() -> None:
    base_picture = _recursive_dependency_picture()

    assert collect_concrete_composite_placeholders(base_picture, graph=None) == ()
