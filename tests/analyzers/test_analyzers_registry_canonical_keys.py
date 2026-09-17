# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Tests for canonical analyzer key handling (Phase 8)."""

from __future__ import annotations

import pytest

from sattlint.analyzers import dispatch as dispatch_module
from sattlint.analyzers import registry as registry_module


def test_canonicalize_analyzer_key_maps_legacy_aliases() -> None:
    assert registry_module.canonicalize_analyzer_key("same_cycle") == "same-cycle"
    assert registry_module.canonicalize_analyzer_key("SAME_CYCLE") == "same-cycle"
    assert registry_module.canonicalize_analyzer_key("variables") == "variables"


def test_default_cli_analyzers_are_keyed_by_canonical_keys() -> None:
    analyzers = registry_module.get_default_cli_analyzers()
    canonical_keys = {registry_module.canonicalize_analyzer_key(spec.key) for spec in analyzers}

    assert {spec.key for spec in analyzers} == canonical_keys
    assert all(registry_module.canonicalize_analyzer_key(spec.key) == spec.key for spec in analyzers)


def test_registry_analyzer_spec_lookup_accepts_legacy_aliases() -> None:
    spec = dispatch_module.get_registry_analyzer_spec("same_cycle")

    assert spec.key == "same-cycle"


def test_registry_analyzer_spec_lookup_accepts_uppercase_alias() -> None:
    spec = dispatch_module.get_registry_analyzer_spec("SAME_CYCLE")

    assert spec.key == "same-cycle"


def test_registry_analyzer_spec_lookup_unknown_key_raises() -> None:
    with pytest.raises(KeyError, match="no-such-analyzer"):
        dispatch_module.get_registry_analyzer_spec("no-such-analyzer")


def test_cli_dispatch_selection_canonicalizes_legacy_alias_keys() -> None:
    analyzers = dispatch_module.get_cli_dispatch_analyzers(
        selected_keys=("same_cycle",),
        get_enabled_analyzers_fn=registry_module.get_enabled_analyzers,
    )

    assert [spec.key for spec in analyzers] == ["same-cycle"]


def test_internal_requirement_maps_use_canonical_keys() -> None:
    specs = tuple(registry_module.get_default_analyzers())
    for spec in specs:
        assert registry_module.canonicalize_analyzer_key(spec.key) == spec.key


def test_resolve_selected_analyzers_is_exact_and_preserves_order() -> None:
    variables_spec = dispatch_module.get_registry_analyzer_spec("variables")
    dataflow_spec = dispatch_module.get_registry_analyzer_spec("dataflow")
    enabled = [dataflow_spec, variables_spec]

    selected = dispatch_module.resolve_selected_analyzers(
        selected_keys=["variables", "dataflow"],
        get_enabled_analyzers_fn=lambda: enabled,
    )

    assert [spec.key for spec in selected] == ["dataflow", "variables"]

    unselected = dispatch_module.resolve_selected_analyzers(
        selected_keys=["sfc"],
        get_enabled_analyzers_fn=lambda: enabled,
    )
    assert unselected == ()

    default = dispatch_module.resolve_selected_analyzers(
        selected_keys=None,
        get_enabled_analyzers_fn=lambda: enabled,
    )
    assert [spec.key for spec in default] == ["dataflow", "variables"]


def test_icf_analyzer_is_declared_per_run_scope() -> None:
    icf_spec = dispatch_module.get_registry_analyzer_spec("icf")

    assert icf_spec.scope == "per-run"


def test_all_other_default_analyzers_are_per_target_scope() -> None:
    for spec in registry_module.get_default_cli_analyzers():
        if spec.key == "icf":
            assert spec.scope == "per-run"
        else:
            assert spec.scope == "per-target"
