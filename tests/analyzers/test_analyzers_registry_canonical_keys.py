"""Tests for canonical analyzer key handling (Phase 8)."""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from sattlint.analyzers import dispatch as dispatch_module
from sattlint.analyzers import registry as registry_module


def test_canonicalize_analyzer_key_folds_case() -> None:
    assert registry_module.canonicalize_analyzer_key("VARIABLES") == "variables"
    assert registry_module.canonicalize_analyzer_key("variables") == "variables"


def test_canonicalize_analyzer_keys_strips_and_canonicalizes() -> None:
    assert registry_module.canonicalize_analyzer_keys([" variables ", " DATATYPE-FIELDS "]) == (
        "variables",
        "datatype-fields",
    )


def test_importing_the_registry_does_not_import_analyzers_or_the_loader() -> None:
    script = textwrap.dedent(
        """
        import sys
        import sattlint.analyzers.registry

        loaded = {"variables" if "sattlint.analyzers.variables" in sys.modules else "",
                  "project" if "sattlint.project.loading" in sys.modules else ""}
        print(",".join(sorted(name for name in loaded if name)))
        """
    )

    result = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)

    assert result.stdout.strip() == ""


def test_selectable_analyzers_are_keyed_by_canonical_keys() -> None:
    analyzers = registry_module.get_selectable_analyzers()
    canonical_keys = {registry_module.canonicalize_analyzer_key(spec.key) for spec in analyzers}

    assert {spec.key for spec in analyzers} == canonical_keys
    assert all(registry_module.canonicalize_analyzer_key(spec.key) == spec.key for spec in analyzers)


def test_registry_analyzer_spec_lookup_unknown_key_raises() -> None:
    with pytest.raises(KeyError, match="no-such-analyzer"):
        dispatch_module.get_registry_analyzer_spec("no-such-analyzer")


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

    with pytest.raises(ValueError, match="No analyzers selected"):
        dispatch_module.resolve_selected_analyzers(
            selected_keys=None,
            get_enabled_analyzers_fn=lambda: enabled,
        )


def test_icf_analyzer_is_declared_per_run_scope() -> None:
    icf_spec = dispatch_module.get_registry_analyzer_spec("icf")

    assert icf_spec.scope == "per-run"


def test_all_other_selectable_analyzers_are_per_target_scope() -> None:
    for spec in registry_module.get_selectable_analyzers():
        if spec.key == "icf":
            assert spec.scope == "per-run"
        else:
            assert spec.scope == "per-target"
