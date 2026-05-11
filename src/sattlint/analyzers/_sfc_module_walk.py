"""Shared module-code traversal helpers for SFC analyzers."""

from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Sequence as SequenceABC

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    SingleModule,
)


def iter_sfc_modulecodes(base_picture: BasePicture) -> Iterator[tuple[list[str], ModuleCode | None]]:
    """Yield (module_path, modulecode) for root, nested modules, and moduletype defs."""

    root_path = [base_picture.header.name]
    yield root_path, base_picture.modulecode

    yield from _iter_nested_modulecodes(base_picture.submodules, root_path)

    for moduletype in base_picture.moduletype_defs or ():
        yield [base_picture.header.name, f"TypeDef:{moduletype.name}"], moduletype.modulecode


def _iter_nested_modulecodes(
    modules: SequenceABC[object] | None,
    module_path: list[str],
) -> Iterator[tuple[list[str], ModuleCode | None]]:
    for module in modules or ():
        if isinstance(module, SingleModule):
            child_path = [*module_path, module.header.name]
            yield child_path, module.modulecode
            yield from _iter_nested_modulecodes(module.submodules, child_path)
        elif isinstance(module, FrameModule):
            child_path = [*module_path, module.header.name]
            yield child_path, getattr(module, "modulecode", None)
            yield from _iter_nested_modulecodes(module.submodules, child_path)
