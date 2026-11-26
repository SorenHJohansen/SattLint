"""Origin matching used to keep dependency internals out of root-only analysis."""

from __future__ import annotations

from pathlib import Path

from ..utils.casefolding import unit_equal


def is_root_origin(
    origin_file: str | None,
    origin_lib: str | None,
    *,
    root_origin_file: str | None,
    root_origin_library: str | None,
) -> bool:
    """Return True when an entity's origin belongs to the analyzed root.

    A different library disqualifies the entity. Within the same library the
    file name decides, so a root module type and its instances match even when
    one side reports a relative and the other an absolute path. The full name
    is compared, not the stem, because the draft and official bodies of one
    program share a stem but are different artifacts. Missing origin data is
    treated as root-owned.
    """
    if root_origin_library and origin_lib and not unit_equal(origin_lib, root_origin_library):
        return False
    if origin_file and root_origin_file:
        return unit_equal(Path(origin_file).name, Path(root_origin_file).name)
    return True


__all__ = ["is_root_origin"]
