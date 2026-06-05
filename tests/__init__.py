"""Test package for shared helper imports and fixtures."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType


def _aggregate_test_module(module_name: str, part_names: tuple[str, ...]) -> ModuleType:
    aggregated = ModuleType(module_name)
    aggregated.__file__ = __file__
    aggregated.__package__ = __name__

    for part_name in part_names:
        part_module = import_module(f"{__name__}.{part_name}")
        for name, value in vars(part_module).items():
            if name.startswith("_"):
                continue
            setattr(aggregated, name, value)

    return aggregated


test_pipeline_collection = _aggregate_test_module(
    "test_pipeline_collection",
    (
        "test_pipeline_collection_part1",
        "test_pipeline_collection_part2",
        "test_pipeline_collection_part3",
        "test_pipeline_collection_part4",
        "test_pipeline_collection_part5",
        "test_pipeline_collection_part6",
    ),
)

test_repo_audit = _aggregate_test_module(
    "test_repo_audit",
    (
        "test_repo_audit_part1",
        "test_repo_audit_part2",
        "test_repo_audit_part3",
        "test_repo_audit_part4",
        "test_repo_audit_part5",
        "test_repo_audit_part6",
        "test_repo_audit_part7",
        "test_repo_audit_part8",
    ),
)

__all__ = ["test_pipeline_collection", "test_repo_audit"]
