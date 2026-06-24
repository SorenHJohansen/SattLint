"""Compatibility wrapper for the split module transformer mixins."""

from __future__ import annotations

from . import _module_shared as _module_shared
from ._module_assembly_mixin import ModuleAssemblyMixin
from ._module_header_mixin import ModuleHeaderMixin
from ._module_layout_mixin import ModuleLayoutMixin

ModuleInvocation = _module_shared.ModuleInvocation
TransformerItem = _module_shared.TransformerItem
TransformerTree = _module_shared.TransformerTree
coord_pair = _module_shared.coord_pair
flatten_items = _module_shared.flatten_items
float_tuple = _module_shared.float_tuple
groupconn_value = _module_shared.groupconn_value
meta_span = _module_shared.meta_span
submodule_children = _module_shared.submodule_children
tree_children = _module_shared.tree_children
v_args = _module_shared.v_args


class _ModulesMixin(ModuleHeaderMixin, ModuleAssemblyMixin, ModuleLayoutMixin):
    """Backward-compatible composition of module-related transformer mixins."""


ModulesMixin = _ModulesMixin
