from __future__ import annotations

import types

import pytest

import sattlint.devtools as devtools
from sattlint.devtools import ai, audit, sandbox
from sattlint.devtools.ai import ai_work_map
from sattlint.devtools.audit import repo_audit
from sattlint.devtools.sandbox import fuzzer


def test_ai_package_exports_use_explicit_module_reexports() -> None:
    assert ai.ai_work_map is ai_work_map
    assert ai.build_ai_work_map is ai_work_map.build_ai_work_map
    assert ai.render_ai_work_map is ai_work_map.render_ai_work_map
    assert "build_ai_work_map" in ai.__all__


def test_audit_package_exports_use_explicit_module_reexports() -> None:
    assert audit.repo_audit is repo_audit
    assert audit.audit_repository is repo_audit.audit_repository
    assert audit.run_check_my_changes is repo_audit.run_check_my_changes
    assert "audit_repository" in audit.__all__


def test_sandbox_package_exports_use_explicit_module_reexports() -> None:
    assert sandbox.fuzzer is fuzzer
    assert sandbox.run_parser_fuzzer is fuzzer.run_parser_fuzzer
    assert sandbox.write_fuzzer_report is fuzzer.write_fuzzer_report
    assert "run_parser_fuzzer" in sandbox.__all__


@pytest.mark.parametrize(
    ("name", "expected_module"),
    [
        ("_ai_chat_grounding", "sattlint.devtools._ai_chat_grounding"),
        ("_ai_chat_transcripts", "sattlint.devtools._ai_chat_transcripts"),
        ("_portable_command_text", "sattlint.devtools._portable_command_text"),
        ("_repo_audit_full_run", "sattlint.devtools.audit._repo_audit_full_run"),
        ("_semble_adapter", "sattlint.devtools._semble_adapter"),
        ("_structural_budget_inventory", "sattlint.devtools.structural._structural_budget_inventory"),
        ("fuzzer", "sattlint.devtools.sandbox.fuzzer"),
        ("impact_analyzer", "sattlint.devtools.structural.impact_analyzer"),
        ("pipeline", "sattlint.devtools.pipeline"),
        ("pipeline_artifacts", "sattlint.devtools.shared.pipeline_artifacts"),
        ("pipeline_checks", "sattlint.devtools.shared.pipeline_checks"),
        ("repo_audit_runs", "sattlint.devtools.audit.repo_audit_runs"),
    ],
)
def test_devtools_module_exports_resolve_to_explicit_owner_packages(name: str, expected_module: str) -> None:
    exported = getattr(devtools, name)

    assert isinstance(exported, types.ModuleType)
    assert exported.__name__ == expected_module


@pytest.mark.parametrize(
    ("name", "expected_module", "expected_attribute"),
    [
        ("ArtifactDefinition", "sattlint.devtools.artifact_registry", "ArtifactDefinition"),
        ("run_property_tests", "sattlint.devtools.property_tests", "run_property_tests"),
        ("run_scan", "sattlint.devtools.doc_gardener", "run_scan"),
    ],
)
def test_devtools_attribute_exports_resolve_from_explicit_provider_modules(
    name: str,
    expected_module: str,
    expected_attribute: str,
) -> None:
    exported = getattr(devtools, name)
    owner_module = __import__(expected_module, fromlist=[expected_attribute])

    assert exported is getattr(owner_module, expected_attribute)


def test_devtools_fuzzer_timeout_export_uses_fuzzer_owner_constant() -> None:
    assert devtools.FUZZER_DEFAULT_TIMEOUT_SECONDS == devtools.fuzzer.DEFAULT_TIMEOUT_SECONDS
    assert "FUZZER_DEFAULT_TIMEOUT_SECONDS" in dir(devtools)
