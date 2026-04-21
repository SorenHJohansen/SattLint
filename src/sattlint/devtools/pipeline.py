"""Repeatable static-analysis pipeline that emits machine-readable JSON reports."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess  # nosec B404 - pipeline intentionally executes trusted local developer tools
import sys
import time
import tomllib
from typing import Any

from defusedxml import ElementTree as ET  # type: ignore[import-untyped]

from sattlint.app import VARIABLE_ANALYSES
from sattlint.analyzers.registry import (
    get_default_analyzer_catalog,
    get_default_analyzers,
)
from sattlint.core.semantic import discover_workspace_sources, load_workspace_snapshot
from sattlint.path_sanitizer import sanitize_command_for_report, sanitize_path_for_report
from sattlint.reporting.variables_report import IssueKind, VariablesReport
from sattlint.tracing import trace_source_file_analysis

REPO_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "analysis"
DEFAULT_TRACE_TARGET = REPO_ROOT / "tests" / "fixtures" / "sample_sattline_files" / "LinterTestProgram.s"
PIPELINE_PROFILE_CHOICES = ("quick", "full")
DEFAULT_PIPELINE_PROFILE = "full"


@dataclass(slots=True)
class CommandResult:
    name: str
    command: list[str]
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str


def _read_pyproject() -> dict[str, Any]:
    raw = PYPROJECT_PATH.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return tomllib.loads(raw.decode(encoding))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            continue
    return tomllib.loads(raw.decode("utf-8", errors="replace"))


def _tool_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def _resolve_python_executable() -> str:
    candidates: list[Path] = []

    override = os.environ.get("SATTLINT_PYTHON")
    if override:
        candidates.append(Path(override))

    if sys.executable:
        candidates.append(Path(sys.executable))

    base_executable = getattr(sys, "_base_executable", "")
    if base_executable:
        candidates.append(Path(base_executable))

    prefix = Path(sys.prefix)
    if os.name == "nt":
        candidates.append(prefix / "Scripts" / "python.exe")
    else:
        candidates.append(prefix / "bin" / "python")

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())

    fallback = shutil.which("python")
    if fallback:
        return fallback

    return sys.executable


def _run_command(name: str, command: list[str], *, cwd: Path = REPO_ROOT) -> CommandResult:
    start = time.perf_counter()
    completed = subprocess.run(  # nosec B603 - command list is constructed internally
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    duration = time.perf_counter() - start
    return CommandResult(
        name=name,
        command=command,
        exit_code=completed.returncode,
        duration_seconds=round(duration, 3),
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _profile_settings(profile: str) -> dict[str, Any]:
    if profile == "quick":
        return {
            "include_vulture": False,
            "include_bandit": False,
            "include_structural_reports": False,
            "include_trace": False,
            "pytest_addopts_override": "--strict-markers --strict-config",
        }
    if profile == "full":
        return {
            "include_vulture": True,
            "include_bandit": True,
            "include_structural_reports": True,
            "include_trace": True,
            "pytest_addopts_override": None,
        }
    raise ValueError(f"Unsupported pipeline profile: {profile}")


def _build_pytest_command(python_cmd: list[str], junit_path: Path, *, profile: str) -> list[str]:
    settings = _profile_settings(profile)
    command = [*python_cmd, "-m", "pytest", "-q"]
    addopts_override = settings.get("pytest_addopts_override")
    if addopts_override:
        command.extend(["-o", f"addopts={addopts_override}"])
    command.append(f"--junitxml={junit_path}")
    return command


def _make_tool_status(
    *,
    status: str,
    report: str | None,
    raw_exit_code: int | None,
    normalized_exit_code: int | None,
    finding_count: int = 0,
    note_count: int = 0,
    detail: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "report": report,
        "raw_exit_code": raw_exit_code,
        "normalized_exit_code": normalized_exit_code,
        "finding_count": finding_count,
    }
    if note_count:
        payload["note_count"] = note_count
    if detail:
        payload["detail"] = detail
    return payload


def _overall_status(tool_statuses: dict[str, dict[str, Any]]) -> str:
    statuses = [payload["status"] for payload in tool_statuses.values()]
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "pass_with_notes" for status in statuses):
        return "pass_with_notes"
    return "pass"


def _print_cli_summary(status_report: dict[str, Any]) -> None:
    print(f"Pipeline profile: {status_report['profile']}")
    print(f"Overall status: {status_report['overall_status']}")
    for tool_name in ("ruff", "mypy", "pytest", "vulture", "bandit"):
        tool_status = status_report["tool_statuses"].get(tool_name)
        if tool_status is None:
            continue
        detail = tool_status.get("detail")
        line = f"- {tool_name}: {tool_status['status']}"
        if detail:
            line = f"{line} ({detail})"
        print(line)
    print(f"Status report: {status_report['status_report']}")
    print(f"Summary report: {status_report['summary_report']}")


def _command_payload(result: CommandResult, **extra: Any) -> dict[str, Any]:
    payload = {
        "tool": result.name,
        "command": sanitize_command_for_report(result.command, repo_root=REPO_ROOT),
        "exit_code": result.exit_code,
        "duration_seconds": result.duration_seconds,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    payload.update(extra)
    return payload


def _parse_json_lines(raw_output: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        records.append(json.loads(stripped))
    return records


def _parse_vulture_output(raw_output: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"^(?P<file>.*?):(?P<line>\d+): (?P<message>.*) \((?P<confidence>\d+)% confidence\)$"
    )
    findings: list[dict[str, Any]] = []
    for line in raw_output.splitlines():
        match = pattern.match(line.strip())
        if match is None:
            continue
        findings.append(
            {
                "file": match.group("file"),
                "line": int(match.group("line")),
                "message": match.group("message"),
                "confidence": int(match.group("confidence")),
            }
        )
    return findings


def _parse_pytest_junit(xml_path: Path) -> dict[str, Any]:
    root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    testcases: list[dict[str, Any]] = []
    summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        summary["tests"] += int(suite.attrib.get("tests", 0))
        summary["failures"] += int(suite.attrib.get("failures", 0))
        summary["errors"] += int(suite.attrib.get("errors", 0))
        summary["skipped"] += int(suite.attrib.get("skipped", 0))
        for testcase in suite.findall("testcase"):
            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped = testcase.find("skipped")
            if failure is not None:
                outcome = "failed"
                detail = failure.attrib.get("message") or (failure.text or "")
            elif error is not None:
                outcome = "error"
                detail = error.attrib.get("message") or (error.text or "")
            elif skipped is not None:
                outcome = "skipped"
                detail = skipped.attrib.get("message") or (skipped.text or "")
            else:
                outcome = "passed"
                detail = ""
            testcases.append(
                {
                    "classname": testcase.attrib.get("classname", ""),
                    "name": testcase.attrib.get("name", ""),
                    "time": testcase.attrib.get("time", "0"),
                    "outcome": outcome,
                    "detail": detail.strip(),
                }
            )
    return {"summary": summary, "testcases": testcases}


def _collect_environment_report() -> dict[str, Any]:
    pyproject = _read_pyproject()
    project = pyproject.get("project", {})
    optional_deps = project.get("optional-dependencies", {})
    python_executable = _resolve_python_executable()
    return {
        "project_name": project.get("name"),
        "project_version": project.get("version"),
        "requires_python": project.get("requires-python"),
        "platform": platform.platform(),
        "python": {
            "executable": sanitize_path_for_report(python_executable, repo_root=REPO_ROOT),
            "version": platform.python_version(),
        },
        "dependencies": {
            "runtime": project.get("dependencies", []),
            "optional": optional_deps,
        },
        "installed_tool_versions": {
            name: _tool_version(name)
            for name in ("ruff", "mypy", "pytest", "bandit", "vulture", "types-openpyxl")
        },
    }


def _collect_architecture_report() -> dict[str, Any]:
    cli_filter_kinds = sorted(
        {
            issue_kind.value
            for _label, kinds in VARIABLE_ANALYSES.values()
            if kinds is not None
            for issue_kind in kinds
        }
    )
    summary_supported = {
        IssueKind.UNUSED.value: isinstance(getattr(VariablesReport, "unused", None), property),
        IssueKind.UNUSED_DATATYPE_FIELD.value: isinstance(getattr(VariablesReport, "unused_datatype_fields", None), property),
        IssueKind.READ_ONLY_NON_CONST.value: isinstance(getattr(VariablesReport, "read_only_non_const", None), property),
        IssueKind.UI_ONLY.value: isinstance(getattr(VariablesReport, "ui_only", None), property),
        IssueKind.NEVER_READ.value: isinstance(getattr(VariablesReport, "never_read", None), property),
        IssueKind.GLOBAL_SCOPE_MINIMIZATION.value: isinstance(getattr(VariablesReport, "global_scope_minimization", None), property),
        IssueKind.HIGH_FAN_IN_OUT.value: isinstance(getattr(VariablesReport, "high_fan_in_out", None), property),
        IssueKind.STRING_MAPPING_MISMATCH.value: isinstance(getattr(VariablesReport, "string_mapping_mismatch", None), property),
        IssueKind.HIDDEN_GLOBAL_COUPLING.value: isinstance(getattr(VariablesReport, "hidden_global_coupling", None), property),
        IssueKind.DATATYPE_DUPLICATION.value: isinstance(getattr(VariablesReport, "datatype_duplication", None), property),
        IssueKind.MIN_MAX_MAPPING_MISMATCH.value: isinstance(getattr(VariablesReport, "min_max_mapping_mismatch", None), property),
        IssueKind.MAGIC_NUMBER.value: isinstance(getattr(VariablesReport, "magic_numbers", None), property),
        IssueKind.NAME_COLLISION.value: isinstance(getattr(VariablesReport, "name_collisions", None), property),
        IssueKind.SHADOWING.value: isinstance(getattr(VariablesReport, "shadowing", None), property),
        IssueKind.RESET_CONTAMINATION.value: isinstance(getattr(VariablesReport, "reset_contamination", None), property),
        IssueKind.IMPLICIT_LATCH.value: isinstance(getattr(VariablesReport, "implicit_latches", None), property),
    }

    analyzer_specs = get_default_analyzers()
    registry_keys = [spec.key for spec in analyzer_specs]
    live_diagnostic_analyzers = [spec.key for spec in analyzer_specs if spec.supports_live_diagnostics]
    server_source = (REPO_ROOT / "src" / "sattlint_lsp" / "server.py").read_text(encoding="utf-8")

    findings: list[dict[str, Any]] = []
    missing_cli_filters = sorted(kind for kind, supported in summary_supported.items() if supported and kind not in cli_filter_kinds)
    if missing_cli_filters:
        findings.append(
            {
                "id": "cli-variable-filter-gap",
                "severity": "medium",
                "message": "Some variable issue kinds are rendered in reports but not exposed as CLI quick filters.",
                "missing_issue_kinds": missing_cli_filters,
            }
        )

    semantic_source = (REPO_ROOT / "src" / "sattlint" / "core" / "semantic.py").read_text(encoding="utf-8")
    unresolved_live_diagnostics = [key for key in live_diagnostic_analyzers if key != "variables"]
    if unresolved_live_diagnostics and "collect_project_variable_diagnostics" in semantic_source and "enable_variable_diagnostics" in server_source:
        findings.append(
            {
                "id": "lsp-variable-only-diagnostics",
                "severity": "medium",
                "message": "The semantic snapshot layer only projects variable diagnostics; some analyzers marked as live-diagnostic capable are not surfaced in the editor.",
                "registered_analyzers_not_in_lsp": unresolved_live_diagnostics,
            }
        )

    return {
        "registered_analyzers": registry_keys,
        "live_diagnostic_analyzers": live_diagnostic_analyzers,
        "cli_variable_filter_issue_kinds": cli_filter_kinds,
        "variables_report_summary_support": summary_supported,
        "findings": findings,
    }


def _collect_analyzer_registry_report() -> dict[str, Any]:
    catalog = get_default_analyzer_catalog()
    return catalog.to_report(generated_by="sattlint.devtools.pipeline")


def _collect_workspace_graph_inputs(
    workspace_root: Path = REPO_ROOT,
) -> tuple[Any, list[Any], list[dict[str, Any]]]:
    discovery = discover_workspace_sources(workspace_root)
    snapshots: list[Any] = []
    failures: list[dict[str, Any]] = []

    for entry_file in discovery.program_files:
        try:
            snapshot = load_workspace_snapshot(
                entry_file,
                workspace_root=workspace_root,
                collect_variable_diagnostics=False,
            )
        except Exception as exc:
            failures.append(
                {
                    "entry_file": sanitize_path_for_report(entry_file, repo_root=workspace_root),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            continue
        snapshots.append(snapshot)

    return discovery, snapshots, failures


def _collect_dependency_graph_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    discovery, snapshots, failures = (
        graph_inputs if graph_inputs is not None else _collect_workspace_graph_inputs(workspace_root)
    )

    node_index: dict[str, dict[str, Any]] = {}
    edge_index: dict[tuple[str, str], dict[str, Any]] = {}

    for snapshot in snapshots:
        entry_file = sanitize_path_for_report(snapshot.entry_file, repo_root=workspace_root)
        for source, targets in sorted(snapshot.project_graph.library_dependencies.items()):
            node_index.setdefault(source, {"id": source, "kind": "library"})
            for target in sorted(targets):
                node_index.setdefault(target, {"id": target, "kind": "library"})
                key = (source.casefold(), target.casefold())
                edge = edge_index.setdefault(
                    key,
                    {
                        "source": source,
                        "target": target,
                        "kind": "depends_on",
                        "entries": set(),
                    },
                )
                edge["entries"].add(entry_file)

    edges = [
        {
            "source": edge["source"],
            "target": edge["target"],
            "kind": edge["kind"],
            "entries": sorted(edge["entries"]),
        }
        for edge in sorted(
            edge_index.values(),
            key=lambda item: (item["source"].casefold(), item["target"].casefold()),
        )
    ]

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "workspace_root": sanitize_path_for_report(workspace_root, repo_root=workspace_root),
        "source_files": {
            "program_files": [
                sanitize_path_for_report(path, repo_root=workspace_root)
                for path in discovery.program_files
            ],
            "dependency_files": [
                sanitize_path_for_report(path, repo_root=workspace_root)
                for path in discovery.dependency_files
            ],
        },
        "nodes": sorted(node_index.values(), key=lambda item: item["id"].casefold()),
        "edges": edges,
        "snapshot_count": len(snapshots),
        "snapshot_failures": failures,
    }


def _collect_call_graph_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    _discovery, snapshots, failures = (
        graph_inputs if graph_inputs is not None else _collect_workspace_graph_inputs(workspace_root)
    )

    node_index: dict[str, dict[str, Any]] = {}
    edge_index: dict[tuple[str, str], dict[str, Any]] = {}

    for snapshot in snapshots:
        entry_file = sanitize_path_for_report(snapshot.entry_file, repo_root=workspace_root)
        root_module = getattr(snapshot.base_picture, "name", snapshot.entry_file.stem)
        for definition in snapshot.definitions:
            if definition.field_path is not None:
                continue

            target_path = definition.declaration_module_path or (root_module,)
            target_module = ".".join(target_path)
            node_index.setdefault(target_module.casefold(), {"id": target_module, "kind": "module"})

            for access in snapshot.find_accesses_to(definition):
                source_path = access.use_module_path or (root_module,)
                source_module = ".".join(source_path)
                node_index.setdefault(source_module.casefold(), {"id": source_module, "kind": "module"})

                key = (source_module.casefold(), target_module.casefold())
                edge = edge_index.setdefault(
                    key,
                    {
                        "source": source_module,
                        "target": target_module,
                        "kind": "module-access",
                        "reads": 0,
                        "writes": 0,
                        "symbols": set(),
                        "entries": set(),
                    },
                )
                if access.kind == "read":
                    edge["reads"] += 1
                elif access.kind == "write":
                    edge["writes"] += 1
                edge["symbols"].add(definition.canonical_path)
                edge["entries"].add(entry_file)

    edges = [
        {
            "source": edge["source"],
            "target": edge["target"],
            "kind": edge["kind"],
            "reads": edge["reads"],
            "writes": edge["writes"],
            "access_count": edge["reads"] + edge["writes"],
            "symbol_count": len(edge["symbols"]),
            "symbols": sorted(edge["symbols"]),
            "entries": sorted(edge["entries"]),
        }
        for edge in sorted(
            edge_index.values(),
            key=lambda item: (item["source"].casefold(), item["target"].casefold()),
        )
    ]

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "workspace_root": sanitize_path_for_report(workspace_root, repo_root=workspace_root),
        "graph_kind": "module-access",
        "nodes": sorted(node_index.values(), key=lambda item: item["id"].casefold()),
        "edges": edges,
        "snapshot_count": len(snapshots),
        "snapshot_failures": failures,
    }


def _dedupe_snapshot_failures(*failure_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    failures: list[dict[str, Any]] = []
    for items in failure_lists:
        for item in items:
            marker = json.dumps(item, sort_keys=True)
            if marker in seen:
                continue
            seen.add(marker)
            failures.append(item)
    return failures


def _collect_reverse_impact(
    node_id: str,
    incoming_edges: dict[str, list[dict[str, Any]]],
    *,
    list_fields: tuple[str, ...] = (),
    count_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    direct_dependents: set[str] = set()
    direct_entry_files: set[str] = set()
    direct_list_values: dict[str, set[str]] = {field: set() for field in list_fields}
    direct_count_values = {field: 0 for field in count_fields}

    for edge in incoming_edges.get(node_id, []):
        direct_dependents.add(edge["source"])
        direct_entry_files.update(edge.get("entries", []))
        for field in list_fields:
            direct_list_values[field].update(edge.get(field, []))
        for field in count_fields:
            direct_count_values[field] += int(edge.get(field, 0))

    transitive_dependents: set[str] = set()
    transitive_entry_files: set[str] = set()
    transitive_list_values: dict[str, set[str]] = {field: set() for field in list_fields}
    transitive_count_values = {field: 0 for field in count_fields}
    pending = [node_id]
    visited_targets: set[str] = set()

    while pending:
        target = pending.pop()
        target_key = target.casefold()
        if target_key in visited_targets:
            continue
        visited_targets.add(target_key)
        for edge in incoming_edges.get(target, []):
            source = edge["source"]
            transitive_dependents.add(source)
            transitive_entry_files.update(edge.get("entries", []))
            for field in list_fields:
                transitive_list_values[field].update(edge.get(field, []))
            for field in count_fields:
                transitive_count_values[field] += int(edge.get(field, 0))
            pending.append(source)

    impact = {
        "direct_dependents": sorted(direct_dependents, key=str.casefold),
        "transitive_dependents": sorted(transitive_dependents, key=str.casefold),
        "direct_entry_files": sorted(direct_entry_files, key=str.casefold),
        "transitive_entry_files": sorted(transitive_entry_files, key=str.casefold),
        "direct_dependent_count": len(direct_dependents),
        "transitive_dependent_count": len(transitive_dependents),
    }
    for field in list_fields:
        direct_values = sorted(direct_list_values[field], key=str.casefold)
        transitive_values = sorted(transitive_list_values[field], key=str.casefold)
        impact[f"direct_{field}"] = direct_values
        impact[f"transitive_{field}"] = transitive_values
        impact[f"direct_{field[:-1]}_count"] = len(direct_values)
        impact[f"transitive_{field[:-1]}_count"] = len(transitive_values)
    for field in count_fields:
        impact[f"direct_{field}"] = direct_count_values[field]
        impact[f"transitive_{field}"] = transitive_count_values[field]
    return impact


def _collect_impact_analysis_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
    dependency_graph_report: dict[str, Any] | None = None,
    call_graph_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_dependency_graph = dependency_graph_report or _collect_dependency_graph_report(
        workspace_root,
        graph_inputs=graph_inputs,
    )
    resolved_call_graph = call_graph_report or _collect_call_graph_report(
        workspace_root,
        graph_inputs=graph_inputs,
    )

    dependency_incoming: dict[str, list[dict[str, Any]]] = {}
    for edge in resolved_dependency_graph.get("edges", []):
        dependency_incoming.setdefault(edge["target"], []).append(edge)

    module_incoming: dict[str, list[dict[str, Any]]] = {}
    for edge in resolved_call_graph.get("edges", []):
        if edge["source"].casefold() == edge["target"].casefold():
            continue
        module_incoming.setdefault(edge["target"], []).append(edge)

    library_impacts = []
    for node in resolved_dependency_graph.get("nodes", []):
        impact = _collect_reverse_impact(node["id"], dependency_incoming)
        library_impacts.append(
            {
                "id": node["id"],
                "kind": node.get("kind", "library"),
                **impact,
            }
        )

    module_impacts = []
    for node in resolved_call_graph.get("nodes", []):
        impact = _collect_reverse_impact(
            node["id"],
            module_incoming,
            list_fields=("symbols",),
            count_fields=("reads", "writes", "access_count"),
        )
        module_impacts.append(
            {
                "id": node["id"],
                "kind": node.get("kind", "module"),
                **impact,
            }
        )

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "report_kind": "impact-analysis",
        "workspace_root": sanitize_path_for_report(workspace_root, repo_root=workspace_root),
        "library_impacts": library_impacts,
        "module_impacts": module_impacts,
        "snapshot_failures": _dedupe_snapshot_failures(
            resolved_dependency_graph.get("snapshot_failures", []),
            resolved_call_graph.get("snapshot_failures", []),
        ),
    }


def _run_pipeline(
    output_dir: Path,
    *,
    trace_target: Path | None,
    profile: str = DEFAULT_PIPELINE_PROFILE,
    include_vulture: bool | None = None,
    include_bandit: bool | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    python_cmd = [_resolve_python_executable()]
    settings = _profile_settings(profile)
    run_vulture = settings["include_vulture"] if include_vulture is None else include_vulture
    run_bandit = settings["include_bandit"] if include_bandit is None else include_bandit
    run_structural_reports = settings["include_structural_reports"]
    run_trace = settings["include_trace"] and trace_target is not None and trace_target.exists()
    sanitized_output_dir = sanitize_path_for_report(output_dir, repo_root=REPO_ROOT) or output_dir.as_posix()

    environment_report = _collect_environment_report()
    _write_json(output_dir / "environment.json", environment_report)

    ruff_result = _run_command(
        "ruff",
        python_cmd + ["-m", "ruff", "check", "src", "tests", "--output-format", "json"],
    )
    ruff_findings = json.loads(ruff_result.stdout or "[]")
    ruff_report = _command_payload(ruff_result, finding_count=len(ruff_findings), findings=ruff_findings)
    _write_json(output_dir / "ruff.json", ruff_report)

    mypy_result = _run_command(
        "mypy",
        python_cmd
        + [
            "-m",
            "mypy",
            "src",
            "tests",
            "--show-error-codes",
            "--hide-error-context",
            "--show-column-numbers",
            "--output",
            "json",
        ],
    )
    mypy_findings = _parse_json_lines(mypy_result.stdout)
    mypy_error_count = sum(1 for finding in mypy_findings if finding.get("severity") == "error")
    mypy_note_count = sum(1 for finding in mypy_findings if finding.get("severity") == "note")
    mypy_report = _command_payload(
        mypy_result,
        finding_count=len(mypy_findings),
        error_count=mypy_error_count,
        note_count=mypy_note_count,
        effective_exit_code=0 if mypy_error_count == 0 else mypy_result.exit_code,
        findings=mypy_findings,
    )
    _write_json(output_dir / "mypy.json", mypy_report)

    junit_path = output_dir / "pytest.junit.xml"
    pytest_result = _run_command(
        "pytest",
        _build_pytest_command(python_cmd, junit_path, profile=profile),
    )
    pytest_parsed = _parse_pytest_junit(junit_path)
    pytest_report = _command_payload(pytest_result, **pytest_parsed)
    _write_json(output_dir / "pytest.json", pytest_report)

    if run_vulture:
        vulture_result = _run_command(
            "vulture",
            python_cmd + ["-m", "vulture", "src", "--min-confidence", "80"],
        )
        vulture_findings = _parse_vulture_output(vulture_result.stdout)
        vulture_report = _command_payload(vulture_result, finding_count=len(vulture_findings), findings=vulture_findings)
        _write_json(output_dir / "vulture.json", vulture_report)
    else:
        vulture_report = {"tool": "vulture", "skipped": True}

    if run_bandit:
        bandit_result = _run_command(
            "bandit",
            python_cmd + ["-m", "bandit", "-r", "src", "-f", "json", "-q"],
        )
        bandit_findings = json.loads(bandit_result.stdout or "{}")
        bandit_report = _command_payload(
            bandit_result,
            metrics=bandit_findings.get("metrics", {}),
            findings=bandit_findings.get("results", []),
            errors=bandit_findings.get("errors", []),
        )
        _write_json(output_dir / "bandit.json", bandit_report)
    else:
        bandit_report = {"tool": "bandit", "skipped": True}

    architecture_report: dict[str, Any] = {"findings": [], "skipped": not run_structural_reports}
    analyzer_registry_report: dict[str, Any] = {"rules": [], "skipped": not run_structural_reports}
    dependency_graph_report: dict[str, Any] = {"edges": [], "skipped": not run_structural_reports}
    call_graph_report: dict[str, Any] = {"edges": [], "skipped": not run_structural_reports}
    impact_analysis_report: dict[str, Any] = {
        "library_impacts": [],
        "module_impacts": [],
        "skipped": not run_structural_reports,
    }
    workspace_graph_inputs: tuple[Any, Any, list[dict[str, Any]]] | None = None
    if run_structural_reports:
        architecture_report = _collect_architecture_report()
        _write_json(output_dir / "architecture.json", architecture_report)

        analyzer_registry_report = _collect_analyzer_registry_report()
        _write_json(output_dir / "analyzer_registry.json", analyzer_registry_report)

        workspace_graph_inputs = _collect_workspace_graph_inputs()

        dependency_graph_report = _collect_dependency_graph_report(graph_inputs=workspace_graph_inputs)
        _write_json(output_dir / "dependency_graph.json", dependency_graph_report)

        call_graph_report = _collect_call_graph_report(graph_inputs=workspace_graph_inputs)
        _write_json(output_dir / "call_graph.json", call_graph_report)

        impact_analysis_report = _collect_impact_analysis_report(
            graph_inputs=workspace_graph_inputs,
            dependency_graph_report=dependency_graph_report,
            call_graph_report=call_graph_report,
        )
        _write_json(output_dir / "impact_analysis.json", impact_analysis_report)

    trace_report: dict[str, Any] | None = None
    if run_trace:
        trace_output_path = output_dir / "trace.json"
        assert trace_target is not None
        trace_report = trace_source_file_analysis(trace_target, output_path=trace_output_path)

    tool_statuses = {
        "ruff": _make_tool_status(
            status="fail" if ruff_report["exit_code"] != 0 else "pass",
            report="ruff.json",
            raw_exit_code=ruff_report["exit_code"],
            normalized_exit_code=ruff_report["exit_code"],
            finding_count=ruff_report.get("finding_count", 0),
            detail=f"{ruff_report.get('finding_count', 0)} findings",
        ),
        "mypy": _make_tool_status(
            status=(
                "fail"
                if mypy_report.get("error_count", 0) > 0
                else "pass_with_notes"
                if mypy_report.get("note_count", 0) > 0
                else "pass"
            ),
            report="mypy.json",
            raw_exit_code=mypy_report["exit_code"],
            normalized_exit_code=mypy_report["effective_exit_code"],
            finding_count=mypy_report.get("error_count", 0),
            note_count=mypy_report.get("note_count", 0),
            detail=(
                f"{mypy_report.get('error_count', 0)} errors, {mypy_report.get('note_count', 0)} notes"
            ),
        ),
        "pytest": _make_tool_status(
            status=(
                "fail"
                if pytest_report["summary"]["failures"] or pytest_report["summary"]["errors"]
                else "pass"
            ),
            report="pytest.json",
            raw_exit_code=pytest_report["exit_code"],
            normalized_exit_code=pytest_report["exit_code"],
            finding_count=pytest_report["summary"]["failures"] + pytest_report["summary"]["errors"],
            detail=(
                f"{pytest_report['summary']['tests']} tests, "
                f"{pytest_report['summary']['failures']} failures, "
                f"{pytest_report['summary']['errors']} errors"
            ),
        ),
        "vulture": _make_tool_status(
            status=(
                "skipped"
                if vulture_report.get("skipped")
                else "fail"
                if vulture_report.get("finding_count", 0) or vulture_report.get("exit_code", 0) != 0
                else "pass"
            ),
            report=None if vulture_report.get("skipped") else "vulture.json",
            raw_exit_code=vulture_report.get("exit_code"),
            normalized_exit_code=(0 if vulture_report.get("skipped") else vulture_report.get("exit_code")),
            finding_count=vulture_report.get("finding_count", 0),
            detail=("skipped by profile" if vulture_report.get("skipped") else f"{vulture_report.get('finding_count', 0)} findings"),
        ),
        "bandit": _make_tool_status(
            status=(
                "skipped"
                if bandit_report.get("skipped")
                else "fail"
                if bandit_report.get("findings") or bandit_report.get("errors") or bandit_report.get("exit_code", 0) != 0
                else "pass"
            ),
            report=None if bandit_report.get("skipped") else "bandit.json",
            raw_exit_code=bandit_report.get("exit_code"),
            normalized_exit_code=(0 if bandit_report.get("skipped") else bandit_report.get("exit_code")),
            finding_count=len(bandit_report.get("findings", [])),
            detail=("skipped by profile" if bandit_report.get("skipped") else f"{len(bandit_report.get('findings', []))} findings"),
        ),
    }
    overall_status = _overall_status(tool_statuses)
    failing_tools = [name for name, payload in tool_statuses.items() if payload["status"] == "fail"]
    non_blocking_tools = [
        name for name, payload in tool_statuses.items() if payload["status"] == "pass_with_notes"
    ]

    reports = {
        "status": "status.json",
        "summary": "summary.json",
        "environment": "environment.json",
        "ruff": "ruff.json",
        "mypy": "mypy.json",
        "pytest": "pytest.json",
        "architecture": None if not run_structural_reports else "architecture.json",
        "analyzer_registry": None if not run_structural_reports else "analyzer_registry.json",
        "dependency_graph": None if not run_structural_reports else "dependency_graph.json",
        "call_graph": None if not run_structural_reports else "call_graph.json",
        "impact_analysis": None if not run_structural_reports else "impact_analysis.json",
        "vulture": None if not run_vulture else "vulture.json",
        "bandit": None if not run_bandit else "bandit.json",
        "trace": None if trace_report is None else "trace.json",
    }

    status_report = {
        "kind": "sattlint.pipeline.status",
        "profile": profile,
        "overall_status": overall_status,
        "canonical_command": f"sattlint-analysis-pipeline --profile {profile} --output-dir {sanitized_output_dir}",
        "status_report": f"{sanitized_output_dir}/status.json",
        "summary_report": f"{sanitized_output_dir}/summary.json",
        "tool_statuses": tool_statuses,
        "failing_tools": failing_tools,
        "non_blocking_tools": non_blocking_tools,
    }
    _write_json(output_dir / "status.json", status_report)

    summary = {
        "output_dir": sanitized_output_dir,
        "profile": profile,
        "entry_report": "status.json",
        "canonical_command": f"sattlint-analysis-pipeline --profile {profile} --output-dir {sanitized_output_dir}",
        "reports": reports,
        "status": {
            "overall_status": overall_status,
            "tool_statuses": tool_statuses,
            "failing_tools": failing_tools,
            "non_blocking_tools": non_blocking_tools,
            "ruff_exit_code": ruff_report["exit_code"],
            "mypy_exit_code": mypy_report["effective_exit_code"],
            "pytest_exit_code": pytest_report["exit_code"],
            "vulture_exit_code": vulture_report.get("exit_code"),
            "bandit_exit_code": bandit_report.get("exit_code"),
        },
        "counts": {
            "ruff_findings": ruff_report.get("finding_count", 0),
            "mypy_errors": mypy_report.get("error_count", 0),
            "mypy_notes": mypy_report.get("note_count", 0),
            "pytest_failures": pytest_report["summary"]["failures"],
            "pytest_errors": pytest_report["summary"]["errors"],
            "vulture_findings": vulture_report.get("finding_count", 0),
            "bandit_findings": len(bandit_report.get("findings", [])),
            "architecture_findings": len(architecture_report["findings"]),
            "semantic_rule_count": len(analyzer_registry_report["rules"]),
            "dependency_graph_edges": len(dependency_graph_report["edges"]),
            "call_graph_edges": len(call_graph_report["edges"]),
            "impact_analysis_library_nodes": len(impact_analysis_report["library_impacts"]),
            "impact_analysis_module_nodes": len(impact_analysis_report["module_impacts"]),
            "workspace_graph_snapshot_failures": 0 if workspace_graph_inputs is None else len(workspace_graph_inputs[2]),
            "trace_dataflow_issues": 0 if trace_report is None else trace_report.get("dataflow_analysis", {}).get("issue_count", 0),
            "trace_unreachable_logic": 0 if trace_report is None else len(trace_report.get("heuristics", {}).get("unreachable_logic", [])),
            "trace_transform_violations": 0 if trace_report is None else len(trace_report.get("heuristics", {}).get("transform_invariant_violations", [])),
        },
    }
    _write_json(output_dir / "summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the SattLint analysis pipeline and emit JSON reports.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where JSON reports will be written",
    )
    parser.add_argument(
        "--profile",
        choices=PIPELINE_PROFILE_CHOICES,
        default=DEFAULT_PIPELINE_PROFILE,
        help="Run the fast quick profile or the complete full profile",
    )
    parser.add_argument(
        "--trace-target",
        default=str(DEFAULT_TRACE_TARGET) if DEFAULT_TRACE_TARGET.exists() else "",
        help="Optional SattLine source fixture to trace into trace.json",
    )
    parser.add_argument("--skip-vulture", action="store_true", help="Skip the Vulture dead-code scan")
    parser.add_argument("--skip-bandit", action="store_true", help="Skip the Bandit security scan")
    args = parser.parse_args(argv)

    trace_target = Path(args.trace_target).resolve() if args.trace_target else None
    summary = _run_pipeline(
        Path(args.output_dir).resolve(),
        trace_target=trace_target,
        profile=args.profile,
        include_vulture=False if args.skip_vulture else None,
        include_bandit=False if args.skip_bandit else None,
    )
    _print_cli_summary(
        {
            "profile": summary["profile"],
            "overall_status": summary["status"]["overall_status"],
            "tool_statuses": summary["status"]["tool_statuses"],
            "status_report": f"{summary['output_dir']}/status.json",
            "summary_report": f"{summary['output_dir']}/summary.json",
        }
    )
    return 1 if summary["status"]["overall_status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
