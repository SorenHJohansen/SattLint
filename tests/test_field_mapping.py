#!/usr/bin/env python3
"""Sanity checks for field path mapping logic.

Verifies that only the last component of a dotted path is used as the prefix.
"""


def _last_component(path: str) -> str:
    return path.split(".")[-1] if "." in path else ""


def _reconstruct(prefix: str, field_path: str) -> str:
    if prefix and field_path:
        return f"{prefix}.{field_path}"
    return prefix or field_path


def test_mapping_uses_last_component_as_prefix():
    source_path = "Dv.I.WT001"
    last_component = _last_component(source_path)
    assert last_component == "WT001"

    full_field_path = _reconstruct(last_component, "Value")
    assert full_field_path == "WT001.Value"


def test_mapping_handles_deeper_nesting():
    source_path = "Dv.A.B.C.D.WT002"
    last_component = _last_component(source_path)
    assert last_component == "WT002"

    reconstructed = _reconstruct(last_component, "Status.Code")
    assert reconstructed == "WT002.Status.Code"
