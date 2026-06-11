from __future__ import annotations

import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint.analyzers.variables import IssueKind
from sattlint.analyzers.variables import _variables_execution as variables_execution_module


def test_variables_execution_filters_noisy_unresolved_debug_names(
    caplog: pytest.LogCaptureFixture,
) -> None:
    helper: Any

    def _trace(*_args: object, **_kwargs: object) -> None:
        return None

    def _update_status(*_args: object, **_kwargs: object) -> None:
        return None

    def _record_phase_timing(phase: str, _started_at: object, _ended_at: object | None = None) -> None:
        helper._phase_timings.append({"phase": phase, "duration_ms": 1.0})

    def _run_timed_phase(_phase: str, callback: Callable[[], object]) -> object:
        return callback()

    def _analyze_root_scope() -> None:
        helper._unresolved_variable_lookup_counts.update({"ToggleWindow": 12, "Bool_Value": 4, "MissingVar": 2})
        helper._unresolved_variable_lookup_examples.update(
            {
                "ToggleWindow": (80, "BasePicture -> TypeDef:Example"),
                "Bool_Value": (14, "BasePicture -> TypeDef:Example -> Info"),
                "MissingVar": (3, "BasePicture -> Unit -> Logic"),
            }
        )
        helper._unresolved_variable_lookup_total = 18

    def _collect_basepicture_issues(_path: list[str]) -> None:
        helper._issues.extend([SimpleNamespace(kind=IssueKind.UNUSED), SimpleNamespace(kind=IssueKind.UNUSED)])

    helper: Any = SimpleNamespace(
        _issues=[],
        _param_mapping_issue_indexes={},
        context_builder=SimpleNamespace(issues=[]),
        _limit_to_module_path=None,
        _phase_timings=[],
        _alias_links=[],
        _analysis_warnings=[],
        _selected_issue_kinds=frozenset({IssueKind.UNUSED}),
        _analyzed_target_is_library=False,
        _include_dependency_moduletype_usage=False,
        bp=SimpleNamespace(header=SimpleNamespace(name="Root"), localvariables=[], submodules=[], moduletype_defs=[]),
        debug=True,
        _trace=_trace,
        _update_status=_update_status,
        _record_phase_timing=_record_phase_timing,
        _run_timed_phase=_run_timed_phase,
        _analyze_root_scope=_analyze_root_scope,
        _analyze_library_dependency_typedef_usage=lambda: None,
        _apply_alias_back_propagation=lambda: None,
        _propagate_procedure_status_bindings=lambda: None,
        _run_post_traversal_analyses=lambda: None,
        _collect_basepicture_issues=_collect_basepicture_issues,
        _collect_typedef_issues=lambda: None,
        _add_naming_role_mismatch_issues=lambda: None,
        _add_global_scope_minimization_issues=lambda: None,
        _add_hidden_global_coupling_issues=lambda: None,
        _add_high_fan_in_out_issues=lambda: None,
        _add_unused_datatype_field_issues=lambda: None,
    )

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        variables_execution_module.run(helper)

    messages = list(caplog.messages)
    assert "Variables unresolved lookups: total=2 unique=1 suppressed_noise=16" in messages
    assert any("unresolved MissingVar x2" in message for message in messages)
    assert not any("unresolved ToggleWindow" in message for message in messages)
    assert not any("unresolved Bool_Value" in message for message in messages)
