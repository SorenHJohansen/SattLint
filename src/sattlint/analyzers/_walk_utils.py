"""Shared read-only nested-module traversal helpers for analyzers."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence

from sattline_parser.models.ast_model import FrameModule, ModuleTypeInstance, SingleModule

type NestedModule = SingleModule | FrameModule | ModuleTypeInstance
type InstanceSubmoduleResolver = Callable[[ModuleTypeInstance], Sequence[NestedModule] | None]


def iter_nested_modules(
    modules: Sequence[NestedModule] | None,
    *,
    parent_path: Sequence[str],
    resolve_instance_submodules: InstanceSubmoduleResolver | None = None,
) -> Iterator[tuple[NestedModule, list[str]]]:
    for module in modules or ():
        child_path = [*parent_path, module.header.name]
        yield module, child_path

        if isinstance(module, ModuleTypeInstance):
            if resolve_instance_submodules is None:
                continue
            try:
                nested_modules = resolve_instance_submodules(module)
            except ValueError:
                continue
            yield from iter_nested_modules(
                nested_modules,
                parent_path=child_path,
                resolve_instance_submodules=resolve_instance_submodules,
            )
            continue

        yield from iter_nested_modules(
            module.submodules,
            parent_path=child_path,
            resolve_instance_submodules=resolve_instance_submodules,
        )


def walk_nested_modules_with_state[StateT](
    modules: Sequence[NestedModule] | None,
    *,
    parent_path: Sequence[str],
    state: StateT,
    build_single_state: Callable[[SingleModule, list[str], StateT], StateT],
    build_frame_state: Callable[[FrameModule, list[str], StateT], StateT] | None = None,
    visit_single: Callable[[SingleModule, list[str], StateT], None] | None = None,
    visit_frame: Callable[[FrameModule, list[str], StateT], None] | None = None,
    visit_instance: Callable[[ModuleTypeInstance, list[str], StateT], None] | None = None,
) -> None:
    for module in modules or ():
        child_path = [*parent_path, module.header.name]

        if isinstance(module, SingleModule):
            child_state = build_single_state(module, child_path, state)
            if visit_single is not None:
                visit_single(module, child_path, child_state)
            walk_nested_modules_with_state(
                module.submodules,
                parent_path=child_path,
                state=child_state,
                build_single_state=build_single_state,
                build_frame_state=build_frame_state,
                visit_single=visit_single,
                visit_frame=visit_frame,
                visit_instance=visit_instance,
            )
            continue

        if isinstance(module, FrameModule):
            child_state = state if build_frame_state is None else build_frame_state(module, child_path, state)
            if visit_frame is not None:
                visit_frame(module, child_path, child_state)
            walk_nested_modules_with_state(
                module.submodules,
                parent_path=child_path,
                state=child_state,
                build_single_state=build_single_state,
                build_frame_state=build_frame_state,
                visit_single=visit_single,
                visit_frame=visit_frame,
                visit_instance=visit_instance,
            )
            continue

        if visit_instance is not None:
            visit_instance(module, child_path, state)


__all__ = ["iter_nested_modules", "walk_nested_modules_with_state"]
