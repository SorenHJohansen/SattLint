"""Coverage guards for the shared nested-module walk."""

from __future__ import annotations

import dataclasses
from typing import get_args

import sattline_parser.ast as ast

from sattlint.analyzers.shared._walk_utils import NestedModule, iter_nested_modules, walk_nested_modules_with_state


def _header(name: str) -> ast.ModuleHeader:
    return ast.ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def test_every_parser_module_container_with_submodules_is_known() -> None:
    containers = {
        cls.__name__
        for cls in vars(ast).values()
        if isinstance(cls, type)
        and dataclasses.is_dataclass(cls)
        and any(field.name == "submodules" for field in dataclasses.fields(cls))
    }

    # BasePicture and ModuleTypeDef pass their ``submodules`` into the walk;
    # SingleModule and FrameModule are recursed by the walk itself.
    assert containers == {"BasePicture", "SingleModule", "FrameModule", "ModuleTypeDef"}

    nested_union = NestedModule.__value__  # pyright: ignore[reportAttributeAccessIssue]
    assert set(get_args(nested_union)) == {ast.SingleModule, ast.FrameModule, ast.ModuleTypeInstance}


def test_iter_nested_modules_visits_every_container_kind() -> None:
    leaf = ast.SingleModule(header=_header("Leaf"))
    frame = ast.FrameModule(header=_header("Frame"), submodules=[leaf])
    typedef_child = ast.SingleModule(header=_header("TypedefChild"))
    instance = ast.ModuleTypeInstance(header=_header("Instance"), moduletype_name="Typedef")
    typedef = ast.ModuleTypeDef(name="Typedef", submodules=[typedef_child])
    base_picture = ast.BasePicture(header=_header("Root"), submodules=[frame, instance])

    def resolve_instance(
        module: ast.ModuleTypeInstance,
    ) -> list[ast.SingleModule | ast.FrameModule | ast.ModuleTypeInstance]:
        assert module is instance
        return typedef.submodules

    visited = [
        module.header.name
        for module, _path in iter_nested_modules(
            base_picture.submodules,
            parent_path=[base_picture.header.name],
            resolve_instance_submodules=resolve_instance,
        )
    ]
    typedef_visited = [
        module.header.name for module, _path in iter_nested_modules(typedef.submodules, parent_path=["Typedef"])
    ]

    assert visited == ["Frame", "Leaf", "Instance", "TypedefChild"]
    assert typedef_visited == ["TypedefChild"]


def test_walk_nested_modules_with_state_visits_single_frame_and_instance() -> None:
    single = ast.SingleModule(header=_header("Single"))
    frame = ast.FrameModule(header=_header("Frame"), submodules=[single])
    instance = ast.ModuleTypeInstance(header=_header("Instance"), moduletype_name="Typedef")
    visited: list[tuple[str, str, int]] = []

    walk_nested_modules_with_state(
        [frame, instance],
        parent_path=["Root"],
        state=0,
        build_single_state=lambda module, path, state: state + 1,
        build_frame_state=lambda module, path, state: state,
        visit_single=lambda module, path, state: visited.append(("single", module.header.name, state)),
        visit_frame=lambda module, path, state: visited.append(("frame", module.header.name, state)),
        visit_instance=lambda module, path, state: visited.append(("instance", module.header.name, state)),
    )

    assert visited == [("frame", "Frame", 0), ("single", "Single", 1), ("instance", "Instance", 0)]
