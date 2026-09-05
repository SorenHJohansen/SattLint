# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Tests for canonical analyzer key handling (Phase 8)."""

from __future__ import annotations

import pytest

from sattlint.analyzers import dispatch as dispatch_module
from sattlint.analyzers import registry as registry_module


def test_canonicalize_analyzer_key_maps_legacy_aliases() -> None:
    assert registry_module.canonicalize_analyzer_key("config_drift") == "config-drift"
    assert registry_module.canonicalize_analyzer_key("data_dependency") == "data-dependency"
    assert registry_module.canonicalize_analyzer_key("CONFIG_DRIFT") == "config-drift"
    assert registry_module.canonicalize_analyzer_key("variables") == "variables"


def test_default_cli_analyzers_are_keyed_by_canonical_keys() -> None:
    analyzers = registry_module.get_default_cli_analyzers()
    canonical_keys = {registry_module.canonicalize_analyzer_key(spec.key) for spec in analyzers}

    assert {spec.key for spec in analyzers} == canonical_keys
    assert all(registry_module.canonicalize_analyzer_key(spec.key) == spec.key for spec in analyzers)


def test_registry_analyzer_spec_lookup_accepts_legacy_aliases() -> None:
    spec = dispatch_module.get_registry_analyzer_spec("config_drift")

    assert spec.key == "config-drift"


def test_registry_analyzer_spec_lookup_accepts_uppercase_alias() -> None:
    spec = dispatch_module.get_registry_analyzer_spec("CONFIG_DRIFT")

    assert spec.key == "config-drift"


def test_registry_analyzer_spec_lookup_unknown_key_raises() -> None:
    with pytest.raises(KeyError, match="no-such-analyzer"):
        dispatch_module.get_registry_analyzer_spec("no-such-analyzer")


def test_cli_dispatch_selection_canonicalizes_legacy_alias_keys() -> None:
    analyzers = dispatch_module.get_cli_dispatch_analyzers(
        selected_keys=("config_drift",),
        get_enabled_analyzers_fn=registry_module.get_enabled_analyzers,
    )

    assert [spec.key for spec in analyzers] == ["config-drift"]


def test_internal_requirement_maps_use_canonical_keys() -> None:
    specs = tuple(registry_module.get_default_analyzers())
    for spec in specs:
        for required_key in spec.requires:
            assert registry_module.canonicalize_analyzer_key(required_key) == required_key
