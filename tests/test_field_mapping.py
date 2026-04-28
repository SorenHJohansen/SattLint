#!/usr/bin/env python3
"""Sanity checks for field path mapping logic.

Verifies that only the last component of a dotted path is used as the prefix.
"""

import pytest


def _last_component(path: str) -> str:
    return path.split(".")[-1] if "." in path else ""


def _reconstruct(prefix: str, field_path: str) -> str:
    if prefix and field_path:
        return f"{prefix}.{field_path}"
    return prefix or field_path


@pytest.mark.parametrize(
    ("source_path", "field_path", "expected_prefix", "expected_reconstructed"),
    [
        ("Dv.I.WT001", "Value", "WT001", "WT001.Value"),
        ("Dv.A.B.C.D.WT002", "Status.Code", "WT002", "WT002.Status.Code"),
    ],
)
def test_mapping_uses_last_component_as_prefix(
    source_path: str,
    field_path: str,
    expected_prefix: str,
    expected_reconstructed: str,
) -> None:
    last_component = _last_component(source_path)
    assert last_component == expected_prefix

    full_field_path = _reconstruct(last_component, field_path)
    assert full_field_path == expected_reconstructed
