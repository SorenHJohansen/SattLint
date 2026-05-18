"""Debug helpers for module comparison and version drift output."""

import logging
from typing import Any

from sattline_parser.models.ast_model import BasePicture, FrameModule, ModuleTypeInstance, SingleModule

log = logging.getLogger("SattLint")

_DEFAULT_DEBUG_MAX_DEPTH = 10


def debug_module_structure(base_picture: BasePicture, max_depth: int = _DEFAULT_DEBUG_MAX_DEPTH) -> None:
    """Detailed debugging: show everything about the structure."""
    log.debug("=== DEBUGGING MODULE STRUCTURE ===")
    log.debug("BasePicture type: %s", type(base_picture))
    log.debug("BasePicture name: %r", base_picture.header.name)
    log.debug("BasePicture has %d submodules", len(base_picture.submodules))
    log.debug("BasePicture has %d moduletype_defs", len(base_picture.moduletype_defs))

    log.debug("--- ModuleTypeDefs ---")
    for moduletype in base_picture.moduletype_defs:
        log.debug("  ModuleTypeDef: %r", moduletype.name)
        log.debug("    - has %d submodules", len(moduletype.submodules))
        for index, submodule in enumerate(moduletype.submodules):
            log.debug(
                "    - submodule[%d]: %s - %r",
                index,
                type(submodule).__name__,
                submodule.header.name,
            )

    def _walk(node: Any, depth: int = 0, parent_name: str = "") -> None:
        if depth > max_depth:
            log.debug("%s[MAX DEPTH REACHED]", "  " * depth)
            return

        indent = "  " * depth
        node_type = type(node).__name__

        if isinstance(node, SingleModule):
            name = node.header.name
            log.debug("%sSingleModule: name=%r, datecode=%s, parent=%r", indent, name, node.datecode, parent_name)
            log.debug("%s  - has %d submodules", indent, len(node.submodules))
            for index, submodule in enumerate(node.submodules):
                log.debug("%s  - submodule[%d] type: %s", indent, index, type(submodule).__name__)
                _walk(submodule, depth + 1, name)
            return

        if isinstance(node, FrameModule):
            name = node.header.name
            log.debug("%sFrameModule: name=%r, datecode=%s, parent=%r", indent, name, node.datecode, parent_name)
            log.debug("%s  - has %d submodules", indent, len(node.submodules))
            for index, submodule in enumerate(node.submodules):
                log.debug("%s  - submodule[%d] type: %s", indent, index, type(submodule).__name__)
                _walk(submodule, depth + 1, name)
            return

        if isinstance(node, ModuleTypeInstance):
            name = node.header.name
            log.debug(
                "%sModuleTypeInstance: name=%r, type=%r, parent=%r", indent, name, node.moduletype_name, parent_name
            )
            return

        if isinstance(node, BasePicture):
            log.debug("%sBasePicture: name=%r", indent, node.name)
            log.debug("%s  - has %d submodules", indent, len(node.submodules))
            for index, submodule in enumerate(node.submodules):
                log.debug("%s  - submodule[%d] type: %s", indent, index, type(submodule).__name__)
                _walk(submodule, depth + 1, node.name)
            return

        log.debug("%sUnknown type: %s", indent, node_type)

    log.debug("--- Submodules Tree ---")
    _walk(base_picture)
    log.debug("=== END DEBUGGING ===")
