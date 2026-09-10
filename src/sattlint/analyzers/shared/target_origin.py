"""Target-origin scoping helpers for analyzers.

A merged BasePicture carries moduletype definitions and code from the analyzed
target plus every dependency program/library. Analyzers that walk the whole
picture must gate their traversal with a target-origin filter so findings stay
scoped to the code the user actually asked to analyze.
"""

from __future__ import annotations

from collections.abc import Callable

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef

from .variable_utils import matches_root_origin

OriginNode = BasePicture | ModuleTypeDef
TargetOriginFilter = Callable[[OriginNode], bool]


def build_target_origin_filter(
    root_origin_file: str | None,
    *,
    root_origin_lib: str | None = None,
    analyzed_target_is_library: bool = False,
) -> TargetOriginFilter:
    """Return a predicate that keeps only nodes defined by the analyzed target."""

    def _is_root_origin(node: OriginNode) -> bool:
        return matches_root_origin(
            getattr(node, "origin_file", None),
            root_origin_file,
            analyzed_target_is_library=analyzed_target_is_library,
            origin_lib=getattr(node, "origin_lib", None),
            root_origin_lib=root_origin_lib,
        )

    return _is_root_origin


def build_target_origin_filter_for_basepicture(
    base_picture: BasePicture,
    *,
    analyzed_target_is_library: bool = False,
) -> TargetOriginFilter:
    return build_target_origin_filter(
        getattr(base_picture, "origin_file", None),
        root_origin_lib=getattr(base_picture, "origin_lib", None),
        analyzed_target_is_library=analyzed_target_is_library,
    )


__all__ = [
    "OriginNode",
    "TargetOriginFilter",
    "build_target_origin_filter",
    "build_target_origin_filter_for_basepicture",
]
