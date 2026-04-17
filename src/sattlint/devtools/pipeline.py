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
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.path_sanitizer import sanitize_command_for_report, sanitize_path_for_report
from sattlint.reporting.variables_report import IssueKind, VariablesReport
from sattlint.tracing import trace_source_file_analysis

REPO_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "analysis"
DEFAULT_TRACE_TARGET = REPO_ROOT / "tests" / "fixtures" / "sample_sattline_files" / "LinterTestProgram.s"


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
        IssueKind.NEVER_READ.value: isinstance(getattr(VariablesReport, "never_read", None), property),
        IssueKind.STRING_MAPPING_MISMATCH.value: isinstance(getattr(VariablesReport, "string_mapping_mismatch", None), property),
        IssueKind.DATATYPE_DUPLICATION.value: isinstance(getattr(VariablesReport, "datatype_duplication", None), property),
        IssueKind.MIN_MAX_MAPPING_MISMATCH.value: isinstance(getattr(VariablesReport, "min_max_mapping_mismatch", None), property),
        IssueKind.MAGIC_NUMBER.value: isinstance(getattr(VariablesReport, "magic_numbers", None), property),
        IssueKind.NAME_COLLISION.value: isinstance(getattr(VariablesReport, "name_collisions", None), property),
        IssueKind.SHADOWING.value: isinstance(getattr(VariablesReport, "shadowing", None), property),
        IssueKind.RESET_CONTAMINATION.value: isinstance(getattr(VariablesReport, "reset_contamination", None), property),
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


def _run_pipeline(output_dir: Path, *, trace_target: Path | None, include_vulture: bool, include_bandit: bool) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    python_cmd = [_resolve_python_executable()]

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
        python_cmd + ["-m", "pytest", "-q", f"--junitxml={junit_path}"],
    )
    pytest_parsed = _parse_pytest_junit(junit_path)
    pytest_report = _command_payload(pytest_result, **pytest_parsed)
    _write_json(output_dir / "pytest.json", pytest_report)

    if include_vulture:
        vulture_result = _run_command(
            "vulture",
            python_cmd + ["-m", "vulture", "src", "--min-confidence", "80"],
        )
        vulture_findings = _parse_vulture_output(vulture_result.stdout)
        vulture_report = _command_payload(vulture_result, finding_count=len(vulture_findings), findings=vulture_findings)
        _write_json(output_dir / "vulture.json", vulture_report)
    else:
        vulture_report = {"tool": "vulture", "skipped": True}

    if include_bandit:
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

    architecture_report = _collect_architecture_report()
    _write_json(output_dir / "architecture.json", architecture_report)

    trace_report: dict[str, Any] | None = None
    if trace_target is not None and trace_target.exists():
        trace_output_path = output_dir / "trace.json"
        trace_report = trace_source_file_analysis(trace_target, output_path=trace_output_path)

    summary = {
        "output_dir": sanitize_path_for_report(output_dir, repo_root=REPO_ROOT),
        "reports": {
            "environment": "environment.json",
            "ruff": "ruff.json",
            "mypy": "mypy.json",
            "pytest": "pytest.json",
            "architecture": "architecture.json",
            "vulture": None if not include_vulture else "vulture.json",
            "bandit": None if not include_bandit else "bandit.json",
            "trace": None if trace_report is None else "trace.json",
        },
        "status": {
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
        include_vulture=not args.skip_vulture,
        include_bandit=not args.skip_bandit,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
