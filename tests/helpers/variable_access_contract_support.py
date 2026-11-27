# pyright: reportPrivateUsage=false
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sattlint.analyzers import _dependency_usage_scope_support as dependency_scope_module
from sattlint.analyzers.dataflow import DataflowAnalyzer
from sattlint.analyzers.variables import _variables_access as variables_access_module
from sattlint.analyzers.variables import _variables_contracts as variables_contracts_module
from sattlint.resolution.type_graph import TypeGraph

variables_access_impl = variables_access_module
variables_contracts_impl = variables_contracts_module
# The mixin has no single owner type: its helpers take a state protocol that the
# duck-typed access state below satisfies structurally, so keep this seam dynamic.
dependency_scope_mixin_impl: Any = dependency_scope_module.DependencyUsageScopeSupportMixin
DataflowAnalyzerType = DataflowAnalyzer

__all__ = [
    "DataflowAnalyzerType",
    "dependency_scope_mixin_impl",
    "make_strict_access_helper",
    "variables_access_impl",
    "variables_contracts_impl",
]


def make_strict_access_helper(
    *,
    fail_loudly: bool = False,
    unavailable_libraries: set[str] | None = None,
    opaque_builtin_types: set[str] | None = None,
    type_graph: TypeGraph | None = None,
    warnings: list[str] | None = None,
) -> Any:
    """Build the duck-typed access state the module-level helpers expect."""
    return SimpleNamespace(
        fail_loudly=fail_loudly,
        unavailable_libraries=set() if unavailable_libraries is None else unavailable_libraries,
        opaque_builtin_types=opaque_builtin_types or {"opaque"},
        type_graph=type_graph or TypeGraph.from_datatypes([]),
        site_stack=["site"],
        warn=(warnings if warnings is not None else []).append,
    )
