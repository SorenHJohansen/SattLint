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


__all__ = ["iter_nested_modules"]
