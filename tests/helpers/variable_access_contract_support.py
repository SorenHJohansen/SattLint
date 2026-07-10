# pyright: reportPrivateUsage=false, reportUnusedImport=false
from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from sattlint.analyzers import _dependency_usage_scope_support as dependency_scope_module
from sattlint.analyzers.dataflow import DataflowAnalyzer
from sattlint.analyzers.variables import _variables_access as variables_access_module
from sattlint.analyzers.variables import _variables_contracts as variables_contracts_module
from tests.helpers.variable_test_support import ns as _ns

RecordResolver = Callable[[str], object | None]

variables_access_impl: Any = variables_access_module
variables_contracts_impl: Any = variables_contracts_module
dependency_scope_mixin_impl: Any = dependency_scope_module.DependencyUsageScopeSupportMixin
DataflowAnalyzerType: Any = DataflowAnalyzer

__all__ = [
    "DataflowAnalyzerType",
    "RecordResolver",
    "dependency_scope_mixin_impl",
    "make_strict_access_helper",
    "variables_access_impl",
    "variables_contracts_impl",
]


def _resolve_no_record(_name: str) -> None:
    return None


def make_strict_access_helper(
    *,
    fail_loudly: bool = False,
    unavailable_libraries: set[str] | None = None,
    opaque_builtin_types: set[str] | None = None,
    record_resolver: RecordResolver | None = None,
    warnings: list[str] | None = None,
) -> Any:
    return SimpleNamespace(
        fail_loudly=fail_loudly,
        unavailable_libraries=unavailable_libraries or {"Lib"},
        opaque_builtin_types=opaque_builtin_types or {"opaque"},
        type_graph=_ns(record=record_resolver or _resolve_no_record),
        site_stack=["site"],
        warn=(warnings if warnings is not None else []).append,
    )
