"""Compatibility wrapper for the split module transformer mixins."""

from __future__ import annotations

from . import _module_shared as _module_shared
from ._module_assembly_mixin import _ModuleAssemblyMixin
from ._module_header_mixin import _ModuleHeaderMixin
from ._module_layout_mixin import _ModuleLayoutMixin

ModuleInvocation = _module_shared.ModuleInvocation
TransformerItem = _module_shared.TransformerItem
TransformerTree = _module_shared.TransformerTree
_coord_pair = _module_shared._coord_pair
_flatten_items = _module_shared._flatten_items
_float_tuple = _module_shared._float_tuple
_groupconn_value = _module_shared._groupconn_value
_meta_span = _module_shared._meta_span
_submodule_children = _module_shared._submodule_children
_tree_children = _module_shared._tree_children
_v_args = _module_shared._v_args


class _ModulesMixin(_ModuleHeaderMixin, _ModuleAssemblyMixin, _ModuleLayoutMixin):
    """Backward-compatible composition of module-related transformer mixins."""


ModulesMixin = _ModulesMixin
