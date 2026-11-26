"""Shared traversal of every module code block in a base picture."""

from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Sequence as SequenceABC
from typing import cast

from sattlint.parser_api import (
    BasePicture,
    FrameModule,
    ModuleCode,
    SingleModule,
)

from ._walk_utils import iter_nested_modules
from .target_origin import TargetOriginFilter


def iter_modulecodes(
    base_picture: BasePicture,
    *,
    moduletype_filter: TargetOriginFilter | None = None,
) -> Iterator[tuple[list[str], ModuleCode | None]]:
    """Yield (module_path, modulecode) for the root, nested modules, and target-origin moduletype defs."""

    root_path = [base_picture.header.name]
    yield root_path, base_picture.modulecode

    yield from _iter_nested_modulecodes(base_picture.submodules, root_path)

    for moduletype in base_picture.moduletype_defs or ():
        if moduletype_filter is not None and not moduletype_filter(moduletype):
            continue
        path = [base_picture.header.name, f"TypeDef:{moduletype.name}"]
        yield path, moduletype.modulecode
        yield from _iter_nested_modulecodes(moduletype.submodules, path)


def _iter_nested_modulecodes(
    modules: SequenceABC[object] | None,
    module_path: list[str],
) -> Iterator[tuple[list[str], ModuleCode | None]]:
    for module, child_path in iter_nested_modules(
        cast(SequenceABC[SingleModule | FrameModule], modules), parent_path=module_path
    ):
        if isinstance(module, SingleModule):
            yield child_path, module.modulecode
        elif isinstance(module, FrameModule):
            yield child_path, getattr(module, "modulecode", None)


__all__ = ["iter_modulecodes"]
