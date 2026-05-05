"""Repository audit core checks for portability, security, wiring, and public-readiness."""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess  # nosec B404 - audit intentionally executes trusted local developer tools
import tempfile
import time
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from defusedxml import ElementTree  # type: ignore[import-untyped]

from sattlint import app as app_module
from sattlint import config as config_module
from sattlint.contracts import FindingCollection, FindingLocation, FindingRecord
from sattlint.devtools import ai_gc as _ai_gc_module
from sattlint.devtools import ai_work_map as _ai_work_map_module
from sattlint.devtools import coverage_reports as _coverage_reports_module
from sattlint.devtools import doc_gardener as _doc_gardener_module
from sattlint.devtools import pipeline as pipeline_module
from sattlint.devtools import repo_audit_entrypoints as _repo_audit_entrypoints
from sattlint.devtools import structural_reports as structural_reports_module
from sattlint.devtools.artifact_registry import AUDIT_ARTIFACTS, artifact_reports_map
from sattlint.devtools.pipeline_artifacts import write_json_artifact
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.devtools.repo_audit_cli import main
from sattlint.path_sanitizer import sanitize_path_for_report

REPO_AUDIT_FINDING_CHECK_IDS = _repo_audit_entrypoints.REPO_AUDIT_FINDING_CHECK_IDS
REPO_AUDIT_INDIVIDUAL_CHECK_IDS = _repo_audit_entrypoints.REPO_AUDIT_INDIVIDUAL_CHECK_IDS
REPO_AUDIT_SPECIAL_CHECK_IDS = _repo_audit_entrypoints.REPO_AUDIT_SPECIAL_CHECK_IDS
_blocking_finding_count = _repo_audit_entrypoints._blocking_finding_count
_category_counts = _repo_audit_entrypoints._category_counts
_default_corpus_manifest_dir = _repo_audit_entrypoints._default_corpus_manifest_dir
_max_severity = _repo_audit_entrypoints._max_severity
_print_cli_summary = _repo_audit_entrypoints._print_cli_summary
_repo_audit_finding_check_definitions = _repo_audit_entrypoints._repo_audit_finding_check_definitions
_recommended_command = _repo_audit_entrypoints._recommended_command
_run_repo_audit_cli_consistency_check = _repo_audit_entrypoints._run_repo_audit_cli_consistency_check
_run_repo_audit_findings_checks = _repo_audit_entrypoints._run_repo_audit_findings_checks
_severity_counts = _repo_audit_entrypoints._severity_counts
_should_fail = _repo_audit_entrypoints._should_fail
build_repo_audit_check_catalog = _repo_audit_entrypoints.build_repo_audit_check_catalog
build_repo_audit_check_recommendations = _repo_audit_entrypoints.build_repo_audit_check_recommendations
collect_custom_findings = _repo_audit_entrypoints.collect_custom_findings
run_check_my_changes = _repo_audit_entrypoints.run_check_my_changes
run_recommended_repo_audit_finish_gate = _repo_audit_entrypoints.run_recommended_repo_audit_finish_gate
run_recommended_repo_audit_slice = _repo_audit_entrypoints.run_recommended_repo_audit_slice

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "audit"
PIPELINE_OUTPUT_DIRNAME = "pipeline"
AUDIT_RUN_HISTORY_FILENAME = "run_history.json"
AUDIT_RUN_HISTORY_DIRNAME = "history"
AUDIT_RUN_HISTORY_LIMIT = 10
AUDIT_RUN_HISTORY_SCHEMA_KIND = "sattlint.audit_run_history"
AUDIT_RUN_HISTORY_SCHEMA_VERSION = 1
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".gitignore",
    ".ini",
    ".js",
    ".json",
    ".l",
    ".md",
    ".p",
    ".ps1",
    ".py",
    ".s",
    ".toml",
    ".txt",
    ".x",
    ".xml",
    ".yaml",
    ".yml",
    ".z",
}
SKIP_CONTENT_SCAN_PREFIXES = (
    "artifacts/",
    "build/",
    "coverage.xml",
    "htmlcov/",
    "Libs/",
    "src/sattlint.egg-info/",
    "tests/fixtures/",
)
GENERATED_PATH_PREFIXES = (
    "artifacts/",
    "build/",
    "dist/",
    "coverage.xml",
    "htmlcov/",
)
TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST = frozenset(
    {
        ".ai",
        ".editorconfig",
        ".gitattributes",
        ".github",
        ".gitignore",
        ".markdownlint-cli2.jsonc",
        ".markdownlint.json",
        ".markdownlintignore",
        ".pre-commit-config.yaml",
        ".vscode",
        "AGENTS.md",
        "ARCHITECTURE.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "README.md",
        "SECURITY.md",
        "custom.toml",
        "docs",
        "metrics",
        "pyproject.toml",
        "scripts",
        "src",
        "tests",
        "vscode",
    }
)
IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PREFIXES = ("src/sattlint/devtools/",)
IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PATHS = {
    "scripts/check_ratchet_policy.py",
    "scripts/repo_health.py",
    "tests/test_artifact_contracts.py",
    "tests/test_devtools_review_observability.py",
    "tests/test_pipeline_collection.py",
    "tests/test_pipeline_run.py",
    "tests/test_context_health.py",
    "tests/test_repo_audit.py",
    "tests/test_repo_audit_entrypoints_helpers.py",
    "tests/test_run_markdownlint.py",
    "tests/test_ratchet_policy.py",
    "tests/test_repo_health.py",
    "tests/test_recommendation_routing.py",
    "tests/test_structural_reports.py",
}
IGNORED_REPO_PATH_REFERENCE_PREFIXES = (
    "Libs/",
    "artifacts/",
    "build/",
    "dist/",
    "htmlcov/",
)
IGNORED_REPO_PATH_REFERENCE_EXACT = {
    ".coverage",
    "coverage.xml",
}
SKIP_SELF_SCAN_PATHS = {
    "AGENTS.md",
    "src/sattlint/devtools/repo_audit.py",
    "tests/test_repo_audit.py",
}
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "htmlcov",
}
LEAK_RELEVANT_CATEGORIES = {"portability", "secrets-pii"}
LEAK_RELEVANT_FINDING_IDS = {"tracked-generated-artifacts"}
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
AUDIT_PROFILE_CHOICES = ("quick", "full")
PLACEHOLDER_VALUES = {
    "<repo-url>",
    "<repository-url>",
    "<token>",
    "<secret>",
    "changeme",
    "example",
    "example-token",
    "example-secret",
    "placeholder",
}
ALLOWED_PRINT_MODULES = {
    "src/sattlint/app.py",
    "src/sattlint/config.py",
    "src/sattlint/console.py",
    "src/sattlint/docgenerator/configgen.py",
    "src/sattlint/engine.py",
    "src/sattlint/tracing.py",
    "src/sattlint/devtools/corpus.py",
    "src/sattlint/devtools/pipeline.py",
    "src/sattlint/devtools/progress_reporting.py",
    "src/sattlint/devtools/repo_audit.py",
}
ALLOWED_PRINT_PREFIXES = ("src/sattlint/devtools/",)
WINDOWS_PATH_RE = re.compile(r"(?<![\w/])(?:[A-Za-z]:[\\/][^\s'\">|]+)")
_DOCUMENTED_COMMAND_RE = re.compile(r"\b(sattlint(?:-[a-z0-9-]+)?)(?:\s+([a-z][a-z0-9-]*))?", re.IGNORECASE)
UNIX_PATH_RE = re.compile(r"(?<![\w.])/(?:home|Users|mnt/c|mnt/[A-Za-z]/Users)/[^\s'\">]+")
LOCAL_ENDPOINT_RE = re.compile(r"\b(?:localhost|127(?:\.\d{1,3}){3}|[a-z0-9-]+\.local)(?::\d{2,5})?\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(?:['\"]?(?:[a-z0-9_-]*?(?:api[_-]?key|token|secret|password|passwd|connection[_-]?string))['\"]?)\s*[:=]\s*['\"]([^'\"]+)['\"]"
)
PRINT_CALL_RE = re.compile(r"\bprint\s*\(")
OVERSIZED_MODULE_LINE_LIMIT = 2000
STRUCTURAL_DEBT_FINDING_IDS = {
    "structural-source-file-budget",
    "structural-test-file-budget",
    "structural-function-budget",
    "structural-class-budget",
}
HARNESS_FRESHNESS_DOC_SCANNERS = (
    "scan_agents_md",
    "scan_dead_links",
    "scan_completed_exec_plans_still_active",
    "scan_stale_docs",
)
IGNORED_NORMALIZED_PIPELINE_FINDINGS = {
    ("bandit-b101", "src/sattlint/devtools/parser_properties.py"),
    ("bandit-b110", "src/sattlint/devtools/doc_gardener.py"),
    ("bandit-b110", "src/sattlint/devtools/layer_linter.py"),
    ("bandit-b112", "src/sattlint/devtools/mutation_engine.py"),
    ("bandit-b311", "src/sattline_parser/fuzz_harness.py"),
    ("bandit-b311", "src/sattlint/devtools/parser_properties.py"),
    ("bandit-b404", "src/sattlint/devtools/doc_gardener.py"),
    ("bandit-b404", "src/sattlint/devtools/review_tool.py"),
    ("bandit-b603", "src/sattlint/devtools/doc_gardener.py"),
    ("bandit-b603", "src/sattlint/devtools/review_tool.py"),
    ("bandit-b607", "src/sattlint/devtools/doc_gardener.py"),
    ("bandit-b607", "src/sattlint/devtools/pipeline.py"),
}
LOCAL_CI_PARITY_LINE_FINDING_IDS = {
    "hardcoded-windows-path",
    "hardcoded-unix-path",
    "local-endpoint",
}
LOCAL_DEPENDENCY_MARKERS = (
    ".venv/",
    ".tox/",
    ".nox/",
    "site-packages",
    "__pypackages__/",
)
PATH_INJECTION_CALL_PATHS = {
    ("site", "addsitedir"),
    ("sys", "path", "append"),
    ("sys", "path", "extend"),
    ("sys", "path", "insert"),
}
HOST_SIGNAL_ATTR_PATHS = {
    ("os", "name"),
    ("sys", "platform"),
}
HOST_SIGNAL_CALL_PATHS = {
    ("platform", "machine"),
    ("platform", "platform"),
    ("platform", "system"),
}


@dataclass(slots=True)
class Finding:
    id: str
    category: str
    severity: str
    confidence: str
    message: str
    path: str | None = None
    line: int | None = None
    detail: str | None = None
    suggestion: str | None = None
    source: str = "custom"
    history_cleanup_recommended: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_record(self, *, artifact: str = "findings") -> FindingRecord:
        return FindingRecord(
            id=self.id,
            rule_id=self.id,
            category=self.category,
            severity=self.severity,
            confidence=self.confidence,
            message=self.message,
            source=self.source,
            analyzer="repo-audit",
            artifact=artifact,
            location=FindingLocation(path=self.path, line=self.line),
            detail=self.detail,
            suggestion=self.suggestion,
            data={
                "history_cleanup_recommended": self.history_cleanup_recommended,
            },
        )


@dataclass(frozen=True, slots=True)
class DocumentedCommand:
    command: str
    subcommand: str | None
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class PythonSourceScanContext:
    source_root: Path
    texts: dict[Path, str]
    asts: dict[Path, ast.AST]


@dataclass(frozen=True, slots=True)
class RepoAuditScanContext:
    root: Path
    include_generated: bool
    tracked_only: bool
    tracked_paths: tuple[str, ...] | None
    suspicious_identifiers: frozenset[str]
    source_context: PythonSourceScanContext
    test_context: PythonSourceScanContext
    scripts_context: PythonSourceScanContext
    scripts: frozenset[str]
    subcommands: frozenset[str]
    documented_commands: tuple[DocumentedCommand, ...]
    line_findings: tuple[Finding, ...] | None = None


def _leading_string_args(args: Sequence[ast.expr]) -> tuple[str, ...]:
    parts: list[str] = []
    for arg in args:
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            break
        value = arg.value.strip().replace("\\", "/").strip("/")
        if not value:
            continue
        parts.append(value)
    return tuple(parts)


def _attribute_path(node: ast.AST) -> tuple[str, ...] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return tuple(reversed(parts))


def _repo_relative_path_from_expr(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name) and node.id == "REPO_ROOT":
        return ()
    if isinstance(node, ast.Attribute) and node.attr == "REPO_ROOT":
        return ()
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_repo_path":
        parts = _leading_string_args(node.args)
        return parts or None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _repo_relative_path_from_expr(node.left)
        if left is None:
            return None
        if not isinstance(node.right, ast.Constant) or not isinstance(node.right.value, str):
            return None
        right = node.right.value.strip().replace("\\", "/").strip("/")
        if not right:
            return left
        return (*left, right)
    return None


def _normalize_repo_relative_literal(value: str) -> str | None:
    normalized = value.strip().replace("\\", "/")
    if not normalized or "://" in normalized or normalized.startswith(("/", "../", "./", "<")):
        return None
    return normalized.rstrip("/")


def _is_ignored_repo_path_reference(candidate: str, tracked_paths: tuple[str, ...] | None) -> bool:
    normalized = candidate.rstrip("/")
    prefix = f"{normalized}/"
    if tracked_paths is not None and any(path == normalized or path.startswith(prefix) for path in tracked_paths):
        return False
    if normalized in IGNORED_REPO_PATH_REFERENCE_EXACT:
        return True
    if normalized.startswith(".coverage"):
        return True
    return normalized.startswith(IGNORED_REPO_PATH_REFERENCE_PREFIXES)


def _source_segment_summary(text: str, node: ast.AST, *, max_length: int = 160) -> str | None:
    segment = ast.get_source_segment(text, node)
    if not segment:
        return None
    normalized = " ".join(segment.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3] + "..."


def _contains_host_signal(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and _attribute_path(child) in HOST_SIGNAL_ATTR_PATHS:
            return True
        if isinstance(child, ast.Call) and _attribute_path(child.func) in HOST_SIGNAL_CALL_PATHS:
            return True
    return False


def _is_pythonpath_target(node: ast.AST) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    if _attribute_path(node.value) != ("os", "environ"):
        return False
    slice_node = node.slice
    return isinstance(slice_node, ast.Constant) and slice_node.value == "PYTHONPATH"


def _find_marker_in_segment(segment: str) -> str | None:
    normalized = segment.replace("\\", "/").casefold()
    for marker in LOCAL_DEPENDENCY_MARKERS:
        if marker in normalized:
            return marker
    return None


def _find_ignored_repo_path_references(
    context: PythonSourceScanContext,
    *,
    root: Path = REPO_ROOT,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()
    for path, tree in context.asts.items():
        rel_path = _relative_path(path, root)
        if rel_path in SKIP_SELF_SCAN_PATHS:
            continue
        if rel_path in IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PATHS:
            continue
        if any(rel_path.startswith(prefix) for prefix in IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PREFIXES):
            continue

        for node in ast.walk(tree):
            candidates: list[str] = []
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                normalized = _normalize_repo_relative_literal(node.value)
                if normalized is not None:
                    candidates.append(normalized)
            else:
                repo_relative = _repo_relative_path_from_expr(node)
                if repo_relative:
                    candidates.append("/".join(repo_relative))

            for candidate in candidates:
                if not _is_ignored_repo_path_reference(candidate, tracked_paths):
                    continue
                line_number = getattr(node, "lineno", None)
                if line_number is None:
                    continue
                key = (rel_path, line_number, candidate)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    Finding(
                        id="gitignored-repo-path-reference",
                        category="public-readiness",
                        severity=_severity_for_path(rel_path, "high"),
                        confidence="high",
                        message="Tracked Python file depends on a repo-local path that is ignored by git.",
                        path=rel_path,
                        line=line_number,
                        detail=f"Matched ignored path {candidate}",
                        suggestion="Use a tracked fixture, explicit config input, or an allowlisted generated-output seam instead.",
                    )
                )
    return findings


def _find_hidden_local_dependency_findings(
    context: PythonSourceScanContext,
    *,
    root: Path = REPO_ROOT,
) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()
    for path, tree in context.asts.items():
        rel_path = _relative_path(path, root)
        if rel_path in SKIP_SELF_SCAN_PATHS:
            continue
        text = context.texts.get(path, "")
        for node in ast.walk(tree):
            marker: str | None = None
            if (
                (isinstance(node, ast.Call) and _attribute_path(node.func) in PATH_INJECTION_CALL_PATHS)
                or (isinstance(node, ast.Assign) and any(_is_pythonpath_target(target) for target in node.targets))
                or (isinstance(node, ast.AugAssign) and _is_pythonpath_target(node.target))
            ):
                marker = _find_marker_in_segment(ast.get_source_segment(text, node) or "")
            if marker is None:
                continue
            line_number = getattr(node, "lineno", None)
            if line_number is None:
                continue
            key = (rel_path, line_number, marker)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    id="hidden-local-dependency-root",
                    category="portability",
                    severity=_severity_for_path(rel_path, "high"),
                    confidence="high",
                    message="Python path setup relies on a local environment directory that CI will not have.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched local dependency marker {marker}",
                    suggestion="Declare the dependency in pyproject or use tracked in-repo fixtures instead of injecting local environment paths.",
                )
            )
    return findings


def _find_host_specific_test_assumptions(
    context: PythonSourceScanContext,
    *,
    root: Path = REPO_ROOT,
) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[str, int]] = set()
    for path, tree in context.asts.items():
        rel_path = _relative_path(path, root)
        if rel_path in SKIP_SELF_SCAN_PATHS:
            continue
        text = context.texts.get(path, "")
        for node in ast.walk(tree):
            signal_node: ast.AST | None = None
            if isinstance(node, ast.Call) and _attribute_path(node.func) == ("pytest", "mark", "skipif") and node.args:
                if _contains_host_signal(node.args[0]):
                    signal_node = node
            elif isinstance(node, (ast.If, ast.IfExp, ast.Assert)) and _contains_host_signal(node.test):
                signal_node = node.test
            if signal_node is None:
                continue
            line_number = getattr(node, "lineno", None)
            if line_number is None:
                continue
            key = (rel_path, line_number)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    id="host-specific-test-assumption",
                    category="portability",
                    severity="medium",
                    confidence="high",
                    message="Test behavior depends on the local host OS or platform.",
                    path=rel_path,
                    line=line_number,
                    detail=_source_segment_summary(text, node),
                    suggestion="Prefer host-agnostic assertions, or isolate platform-specific behavior behind an explicit portability seam.",
                )
            )
    return findings


def _run_local_ci_parity_check(context: RepoAuditScanContext) -> list[Finding]:
    findings = [
        finding for finding in _shared_text_line_findings(context) if finding.id in LOCAL_CI_PARITY_LINE_FINDING_IDS
    ]
    findings.extend(_find_hidden_local_dependency_findings(context.source_context, root=context.root))
    findings.extend(_find_hidden_local_dependency_findings(context.test_context, root=context.root))
    findings.extend(_find_hidden_local_dependency_findings(context.scripts_context, root=context.root))
    findings.extend(_find_host_specific_test_assumptions(context.test_context, root=context.root))
    return findings


def _relative_path(path: Path, root: Path = REPO_ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _write_text_artifact(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: PermissionError | None = None
    for _ in range(5):
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(content)
                temp_path = handle.name
            os.replace(temp_path, path)
            return
        except PermissionError as exc:
            last_error = exc
            if temp_path is not None:
                Path(temp_path).unlink(missing_ok=True)
            time.sleep(0.1)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to write {path}")


def _write_markdown(path: Path, findings: list[Finding], summary: dict[str, Any]) -> None:
    lines = ["# Repository Audit", "", "## Summary", ""]
    for severity in ("critical", "high", "medium", "low"):
        lines.append(f"- {severity.title()}: {summary['severity_counts'].get(severity, 0)}")
    lines.extend(["", "## Findings", ""])
    if not findings:
        lines.append("- No findings.")
    else:
        for finding in findings:
            location = finding.path or "<repo>"
            if finding.line is not None:
                location = f"{location}:{finding.line}"
            lines.append(f"- [{finding.severity.upper()}] {finding.category}: {finding.message} ({location})")
            if finding.detail:
                lines.append(f"  Detail: {finding.detail}")
    _write_text_artifact(path, "\n".join(lines) + "\n")


def _mirror_latest_reports(source_dir: Path, latest_output_dir: Path | None) -> None:
    if latest_output_dir is None:
        return
    if source_dir.resolve() == latest_output_dir.resolve():
        return
    latest_output_dir.mkdir(parents=True, exist_ok=True)
    for source_path in source_dir.rglob("*"):
        relative_path = source_path.relative_to(source_dir)
        target_path = latest_output_dir / relative_path
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def _sanitize_report_path(path: Path) -> str:
    return sanitize_path_for_report(path.resolve(), repo_root=REPO_ROOT) or path.resolve().as_posix()


def _load_audit_run_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(_read_text(path))
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    runs = payload.get("runs")
    if not isinstance(runs, list):
        return []
    return [entry for entry in runs if isinstance(entry, dict) and isinstance(entry.get("run_id"), str)]


def _build_audit_run_id() -> str:
    epoch_seconds = time.time()
    millis = int((epoch_seconds % 1) * 1000)
    return f"{time.strftime('%Y%m%dT%H%M%S', time.gmtime(epoch_seconds))}-{millis:03d}Z"


def _collect_audit_git_state(root: Path = REPO_ROOT) -> dict[str, Any]:
    git_executable = shutil.which("git")
    if git_executable is None:
        return {"head": None, "dirty": None}

    try:
        head_completed = subprocess.run(  # nosec B603 - fixed git executable with controlled arguments
            [git_executable, "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        dirty_completed = subprocess.run(  # nosec B603 - fixed git executable with controlled arguments
            [git_executable, "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return {"head": None, "dirty": None}

    head = None
    if head_completed.returncode == 0:
        candidate = head_completed.stdout.strip()
        head = candidate or None

    dirty = None
    if dirty_completed.returncode == 0:
        dirty = bool(dirty_completed.stdout.strip())

    return {"head": head, "dirty": dirty}


def _copy_audit_snapshot(source_dir: Path, snapshot_dir: Path) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for source_path in source_dir.rglob("*"):
        relative_path = source_path.relative_to(source_dir)
        if relative_path.parts and relative_path.parts[0] == AUDIT_RUN_HISTORY_DIRNAME:
            continue
        if relative_path.name == AUDIT_RUN_HISTORY_FILENAME:
            continue
        target_path = snapshot_dir / relative_path
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source_path, target_path)
        except FileNotFoundError:
            continue


def _history_stale_reasons(entry: dict[str, Any], *, latest: bool) -> list[str]:
    reasons = [str(reason) for reason in entry.get("base_stale_reasons", []) if str(reason)]
    if not latest and "superseded-by-newer-run" not in reasons:
        reasons.append("superseded-by-newer-run")
    return reasons


def _failure_signature(entry: dict[str, Any]) -> str | None:
    if entry.get("overall_status") == "pass":
        return None
    components: list[str] = [str(entry.get("report_kind", "audit"))]
    selected_surface = entry.get("selected_surface")
    if isinstance(selected_surface, str) and selected_surface:
        components.append(selected_surface)
    finish_gate_status = entry.get("finish_gate_status")
    if isinstance(finish_gate_status, str) and finish_gate_status:
        components.append(f"finish:{finish_gate_status}")
    top_failure_ids = entry.get("top_failure_ids")
    if isinstance(top_failure_ids, list) and top_failure_ids:
        components.extend(str(item) for item in top_failure_ids[:5] if str(item))
    else:
        selected_checks = entry.get("selected_checks")
        if isinstance(selected_checks, list) and selected_checks:
            components.extend(str(item) for item in selected_checks[:5] if str(item))
    if len(components) == 1:
        return None
    return "|".join(components)


def _build_failure_patterns(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in runs:
        signature = _failure_signature(entry)
        if signature is None:
            continue
        group = grouped.get(signature)
        if group is None:
            group = {
                "signature": signature,
                "occurrence_count": 0,
                "latest_run_id": entry["run_id"],
                "latest_captured_at": entry["captured_at"],
                "report_kind": entry.get("report_kind"),
                "selected_surface": entry.get("selected_surface"),
                "finish_gate_status": entry.get("finish_gate_status"),
                "top_failure_ids": list(entry.get("top_failure_ids", [])),
                "top_failure_messages": list(entry.get("top_failure_messages", []))[:3],
                "run_ids": [],
            }
            grouped[signature] = group
        group["occurrence_count"] += 1
        group["run_ids"].append(entry["run_id"])
    return sorted(
        grouped.values(),
        key=lambda item: (-int(item["occurrence_count"]), str(item["latest_captured_at"])),
    )


def _build_audit_run_entry(
    *,
    run_id: str,
    captured_at: str,
    snapshot_dir: Path,
    history_base: Path,
    source_dir: Path,
    report_kind: str,
    primary_payload: dict[str, Any],
    status_payload: dict[str, Any] | None,
    summary_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    git_state = _collect_audit_git_state()
    top_findings: list[dict[str, Any]] = []
    if isinstance(status_payload, dict) and isinstance(status_payload.get("top_findings"), list):
        top_findings = list(status_payload["top_findings"])
    if not top_findings and isinstance(primary_payload.get("top_findings"), list):
        top_findings = list(primary_payload["top_findings"])

    selected_checks: list[str] = []
    if isinstance(summary_payload, dict) and isinstance(summary_payload.get("selected_checks"), list):
        selected_checks = [str(item) for item in summary_payload["selected_checks"] if str(item)]
    elif isinstance(primary_payload.get("selected_checks"), list):
        selected_checks = [str(item) for item in primary_payload["selected_checks"] if str(item)]
    elif isinstance(primary_payload.get("recommendation"), dict):
        recommended = primary_payload["recommendation"].get("recommended_check_ids")
        if isinstance(recommended, list):
            selected_checks = [str(item) for item in recommended if str(item)]

    changed_files: list[str] = []
    if isinstance(primary_payload.get("changed_files"), list):
        changed_files = [str(item) for item in primary_payload["changed_files"] if str(item)]

    base_stale_reasons: list[str] = []
    if git_state["dirty"] is True:
        base_stale_reasons.append("workspace-dirty-at-run-time")
    if git_state["head"] is None:
        base_stale_reasons.append("git-head-unavailable")

    profile = None
    if isinstance(primary_payload.get("profile"), str):
        profile = primary_payload["profile"]
    elif isinstance(status_payload, dict) and isinstance(status_payload.get("profile"), str):
        profile = status_payload["profile"]
    elif isinstance(summary_payload, dict) and isinstance(summary_payload.get("profile"), str):
        profile = summary_payload["profile"]

    fail_on = None
    if isinstance(primary_payload.get("fail_on"), str):
        fail_on = primary_payload["fail_on"]
    elif isinstance(status_payload, dict) and isinstance(status_payload.get("fail_on"), str):
        fail_on = status_payload["fail_on"]

    overall_status = None
    if isinstance(primary_payload.get("overall_status"), str):
        overall_status = primary_payload["overall_status"]
    elif isinstance(status_payload, dict) and isinstance(status_payload.get("overall_status"), str):
        overall_status = status_payload["overall_status"]

    canonical_command = None
    if isinstance(primary_payload.get("selected_command"), str):
        canonical_command = primary_payload["selected_command"]
    elif isinstance(summary_payload, dict) and isinstance(summary_payload.get("canonical_command"), str):
        canonical_command = summary_payload["canonical_command"]
    elif isinstance(status_payload, dict) and isinstance(status_payload.get("canonical_command"), str):
        canonical_command = status_payload["canonical_command"]

    return {
        "run_id": run_id,
        "captured_at": captured_at,
        "report_kind": report_kind,
        "profile": profile,
        "fail_on": fail_on,
        "overall_status": overall_status,
        "finish_gate_status": primary_payload.get("finish_gate_status")
        if isinstance(primary_payload.get("finish_gate_status"), str)
        else None,
        "canonical_command": canonical_command,
        "selected_surface": primary_payload.get("selected_surface")
        if isinstance(primary_payload.get("selected_surface"), str)
        else None,
        "selected_checks": selected_checks,
        "changed_files": changed_files,
        "finding_count": (
            status_payload.get("finding_count")
            if isinstance(status_payload, dict) and isinstance(status_payload.get("finding_count"), int)
            else summary_payload.get("finding_count")
            if isinstance(summary_payload, dict) and isinstance(summary_payload.get("finding_count"), int)
            else None
        ),
        "blocking_finding_count": (
            status_payload.get("blocking_finding_count")
            if isinstance(status_payload, dict) and isinstance(status_payload.get("blocking_finding_count"), int)
            else None
        ),
        "max_severity": (
            status_payload.get("max_severity")
            if isinstance(status_payload, dict) and isinstance(status_payload.get("max_severity"), str)
            else summary_payload.get("max_severity")
            if isinstance(summary_payload, dict) and isinstance(summary_payload.get("max_severity"), str)
            else None
        ),
        "top_failure_ids": [
            str(item.get("id")) for item in top_findings if isinstance(item, dict) and isinstance(item.get("id"), str)
        ][:5],
        "top_failure_messages": [
            str(item.get("message"))
            for item in top_findings
            if isinstance(item, dict) and isinstance(item.get("message"), str)
        ][:5],
        "reports": dict(primary_payload.get("reports", {})) if isinstance(primary_payload.get("reports"), dict) else {},
        "output_dir": _sanitize_report_path(source_dir),
        "history_base": _sanitize_report_path(history_base),
        "history_path": _sanitize_report_path(snapshot_dir),
        "snapshot_dir_name": snapshot_dir.name,
        "git_head": git_state["head"],
        "git_dirty": git_state["dirty"],
        "base_stale_reasons": base_stale_reasons,
    }


def _write_audit_run_history(
    source_dir: Path,
    *,
    latest_output_dir: Path | None,
    report_kind: str,
    primary_payload: dict[str, Any],
    status_payload: dict[str, Any] | None = None,
    summary_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    history_base = source_dir.resolve() if latest_output_dir is None else latest_output_dir.resolve()
    history_base.mkdir(parents=True, exist_ok=True)
    history_dir = history_base / AUDIT_RUN_HISTORY_DIRNAME
    history_dir.mkdir(parents=True, exist_ok=True)

    run_id = _build_audit_run_id()
    snapshot_dir = history_dir / run_id
    _copy_audit_snapshot(source_dir, snapshot_dir)

    history_index_path = history_base / AUDIT_RUN_HISTORY_FILENAME
    existing_runs = _load_audit_run_history(history_index_path)
    captured_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    current_entry = _build_audit_run_entry(
        run_id=run_id,
        captured_at=captured_at,
        snapshot_dir=snapshot_dir,
        history_base=history_base,
        source_dir=source_dir,
        report_kind=report_kind,
        primary_payload=primary_payload,
        status_payload=status_payload,
        summary_payload=summary_payload,
    )

    runs = [current_entry, *existing_runs]
    removed_runs = runs[AUDIT_RUN_HISTORY_LIMIT:]
    runs = runs[:AUDIT_RUN_HISTORY_LIMIT]

    for removed_entry in removed_runs:
        snapshot_dir_name = removed_entry.get("snapshot_dir_name")
        if isinstance(snapshot_dir_name, str) and snapshot_dir_name:
            snapshot_path = history_dir / snapshot_dir_name
        else:
            history_path_text = removed_entry.get("history_path")
            if not isinstance(history_path_text, str) or not history_path_text:
                continue
            snapshot_path = Path(history_path_text)
            if not snapshot_path.is_absolute():
                snapshot_path = REPO_ROOT / snapshot_path
        if snapshot_path.exists():
            shutil.rmtree(snapshot_path, ignore_errors=True)

    for index, entry in enumerate(runs):
        latest = index == 0
        stale_reasons = _history_stale_reasons(entry, latest=latest)
        entry["latest"] = latest
        entry["likely_stale"] = bool(stale_reasons)
        entry["likely_stale_reasons"] = stale_reasons
        entry.pop("base_stale_reasons", None)

    payload = {
        "kind": AUDIT_RUN_HISTORY_SCHEMA_KIND,
        "schema_version": AUDIT_RUN_HISTORY_SCHEMA_VERSION,
        "generated_at": captured_at,
        "latest_output_dir": _sanitize_report_path(history_base),
        "latest_run_id": runs[0]["run_id"],
        "retained_run_limit": AUDIT_RUN_HISTORY_LIMIT,
        "run_count": len(runs),
        "reuse_guidance": {
            "prefer_latest_run_id": runs[0]["run_id"],
            "safe_to_reuse_when": [
                "the entry is latest",
                "likely_stale is false",
                "git_head still matches the current workspace HEAD",
                "the command and changed_files still match the question being answered",
            ],
        },
        "failure_patterns": _build_failure_patterns(runs),
        "runs": runs,
    }
    write_json_artifact(history_base / AUDIT_RUN_HISTORY_FILENAME, payload)
    write_json_artifact(source_dir / AUDIT_RUN_HISTORY_FILENAME, payload)
    return payload


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("binary")
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _should_skip_dir(dirname: str) -> bool:
    if dirname in SKIP_DIRS:
        return True
    return dirname.startswith(".venv")


def _list_tracked_repo_paths(root: Path) -> tuple[str, ...] | None:
    git_executable = shutil.which("git")
    if git_executable is None:
        return None

    try:
        completed = subprocess.run(  # nosec B603 - fixed git command with controlled arguments
            [git_executable, "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None

    return tuple(
        sorted(
            raw_rel_path.strip()
            for raw_rel_path in completed.stdout.decode("utf-8", errors="replace").split("\x00")
            if raw_rel_path.strip()
        )
    )


def _iter_repo_file_candidates(root: Path, *, include_generated: bool) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root, topdown=True):
        current_path = Path(current_root)
        rel_dir = _relative_path(current_path, root)
        if rel_dir == ".":
            rel_dir = ""
        filtered_dirs: list[str] = []
        for dirname in dirs:
            if _should_skip_dir(dirname):
                if include_generated and dirname in {"artifacts", "build", "htmlcov"}:
                    filtered_dirs.append(dirname)
                    continue
                continue
            filtered_dirs.append(dirname)
        dirs[:] = filtered_dirs

        for filename in files:
            path = current_path / filename
            rel_path = _relative_path(path, root)
            if not include_generated and rel_path.startswith("artifacts/"):
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES and filename not in {"README", "LICENSE"}:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            yield path


def _iter_tracked_repo_file_candidates(root: Path, *, include_generated: bool) -> Iterable[Path]:
    tracked_paths = _list_tracked_repo_paths(root)
    if tracked_paths is None:
        yield from _iter_repo_file_candidates(root, include_generated=include_generated)
        return

    for rel_path in tracked_paths:
        if not include_generated and rel_path.startswith("artifacts/"):
            continue

        path = root / Path(rel_path)
        if not path.exists() or path.is_dir():
            continue
        if any(
            _should_skip_dir(part) and not (include_generated and part in {"artifacts", "build", "htmlcov"})
            for part in path.parts
        ):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"README", "LICENSE"}:
            continue
        if path.stat().st_size > 2_000_000:
            continue
        yield path


def _iter_repo_text_files(root: Path, *, include_generated: bool) -> Iterable[Path]:
    for path in _iter_repo_file_candidates(root, include_generated=include_generated):
        try:
            _read_text(path)
        except ValueError:
            continue
        yield path


def _iter_tracked_repo_text_files(root: Path, *, include_generated: bool) -> Iterable[Path]:
    for path in _iter_tracked_repo_file_candidates(root, include_generated=include_generated):
        try:
            _read_text(path)
        except ValueError:
            continue
        yield path


def _iter_repo_text_entries(
    root: Path,
    *,
    include_generated: bool,
    tracked_only: bool,
) -> Iterable[tuple[Path, str]]:
    candidates = (
        _iter_tracked_repo_file_candidates(root, include_generated=include_generated)
        if tracked_only
        else _iter_repo_file_candidates(root, include_generated=include_generated)
    )
    for path in candidates:
        try:
            text = _read_text(path)
        except ValueError:
            continue
        yield path, text


def _redact_value(value: str) -> str:
    if len(value) <= 6:
        return "<redacted>"
    return f"{value[:2]}...{value[-2:]}"


def _redact_email(value: str) -> str:
    local, _, domain = value.partition("@")
    if not local:
        return "<redacted-email>"
    return f"{local[:1]}***@{domain}"


def _severity_for_path(rel_path: str, default: str) -> str:
    if rel_path.startswith(("README", "CONTRIBUTING", "src/", "scripts/", "vscode/")):
        return default
    if rel_path.startswith(("tests/", "Libs/")) and default == "high":
        return "medium"
    return default


def _line_findings(
    path: Path,
    text: str,
    suspicious_identifiers: set[str],
    *,
    root: Path = REPO_ROOT,
) -> list[Finding]:
    findings: list[Finding] = []
    rel_path = _relative_path(path, root)
    if (
        rel_path == "coverage.xml"
        or rel_path.startswith(SKIP_CONTENT_SCAN_PREFIXES)
        or rel_path in SKIP_SELF_SCAN_PATHS
    ):
        return findings
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue

        for match in WINDOWS_PATH_RE.finditer(line):
            value = match.group(0)
            if "%USERPROFILE%" in value or "C:\\Users\\MyUser" in value:
                continue
            if rel_path == "README.md" and ("C:\\Tools\\SattLint" in value or "C:\\Path\\To\\Program.s" in value):
                continue
            findings.append(
                Finding(
                    id="hardcoded-windows-path",
                    category="portability",
                    severity=_severity_for_path(rel_path, "high"),
                    confidence="high",
                    message="Absolute Windows path committed to the repository.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched path {_redact_value(value)}",
                    suggestion="Use a CLI argument, config value, or repo-relative path instead.",
                )
            )

        for match in UNIX_PATH_RE.finditer(line):
            value = match.group(0)
            findings.append(
                Finding(
                    id="hardcoded-unix-path",
                    category="portability",
                    severity=_severity_for_path(rel_path, "high"),
                    confidence="high",
                    message="Absolute Unix-style path committed to the repository.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched path {_redact_value(value)}",
                    suggestion="Replace workstation-specific paths with portable examples or runtime config.",
                )
            )

        for match in LOCAL_ENDPOINT_RE.finditer(line):
            value = match.group(0)
            findings.append(
                Finding(
                    id="local-endpoint",
                    category="portability",
                    severity=_severity_for_path(rel_path, "medium"),
                    confidence="medium",
                    message="Localhost or local-domain assumption found.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched endpoint {_redact_value(value)}",
                    suggestion="Make local endpoints configurable or mark them as placeholder examples.",
                )
            )

        for identifier in suspicious_identifiers:
            if not identifier:
                continue
            if re.search(rf"\b{re.escape(identifier)}\b", line, re.IGNORECASE):
                findings.append(
                    Finding(
                        id="suspicious-identifier",
                        category="secrets-pii",
                        severity=_severity_for_path(rel_path, "medium"),
                        confidence="medium",
                        message="Developer-specific identifier found in repository text.",
                        path=rel_path,
                        line=line_number,
                        detail="Matched a configured suspicious identifier.",
                        suggestion="Replace personal identifiers with placeholders or role-based labels.",
                    )
                )

        for match in EMAIL_RE.finditer(line):
            value = match.group(0)
            findings.append(
                Finding(
                    id="email-address",
                    category="secrets-pii",
                    severity=_severity_for_path(rel_path, "low"),
                    confidence="medium",
                    message="Email address committed to the repository.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched email {_redact_email(value)}",
                    suggestion="Use a role-based address if you do not want personal contact details published.",
                )
            )

        if PRIVATE_KEY_RE.search(line):
            findings.append(
                Finding(
                    id="private-key",
                    category="secrets-pii",
                    severity="critical",
                    confidence="high",
                    message="Private key material detected.",
                    path=rel_path,
                    line=line_number,
                    detail="Matched a private-key header.",
                    suggestion="Remove the key immediately and rotate any associated credentials.",
                    history_cleanup_recommended=True,
                )
            )

        for match in SECRET_ASSIGNMENT_RE.finditer(line):
            value = match.group(1).strip()
            if value.casefold() in PLACEHOLDER_VALUES or value.startswith("<"):
                continue
            findings.append(
                Finding(
                    id="secret-assignment",
                    category="secrets-pii",
                    severity=_severity_for_path(rel_path, "high"),
                    confidence="medium",
                    message="Potential hardcoded secret-like value found.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched {_redact_value(value)}",
                    suggestion="Move secret material to runtime configuration or secure secret storage.",
                    history_cleanup_recommended=True,
                )
            )
    return findings


def _load_pyproject(root: Path) -> dict[str, Any]:
    raw = (root / "pyproject.toml").read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return tomllib.loads(raw.decode(encoding))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            continue
    return tomllib.loads(raw.decode("utf-8", errors="replace"))


def _extract_documented_commands(paths: Iterable[Path], *, root: Path = REPO_ROOT) -> list[DocumentedCommand]:
    commands: list[DocumentedCommand] = []
    for path in paths:
        text = _read_text(path)
        rel_path = _relative_path(path, root)
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in _DOCUMENTED_COMMAND_RE.finditer(line):
                command = match.group(1)
                subcommand = match.group(2)
                if command == "sattlint" and subcommand in {"and", "is", "supports"}:
                    continue
                commands.append(
                    DocumentedCommand(
                        command=command,
                        subcommand=subcommand,
                        path=rel_path,
                        line=line_number,
                    )
                )
    return commands


def _collect_cli_metadata() -> tuple[set[str], set[str]]:
    pyproject = _load_pyproject(REPO_ROOT)
    scripts = set(pyproject.get("project", {}).get("scripts", {}).keys())
    parser = app_module.build_cli_parser()
    subcommands: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if choices:
            subcommands.update(choices.keys())
    return scripts, subcommands


def _find_documentation_command_gaps(
    documented_commands: Iterable[DocumentedCommand],
    scripts: set[str],
    subcommands: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    for item in documented_commands:
        if item.command == "sattlint" and item.subcommand and item.subcommand not in subcommands:
            findings.append(
                Finding(
                    id="documented-missing-subcommand",
                    category="feature-wiring",
                    severity="medium",
                    confidence="high",
                    message=f"Documented CLI subcommand '{item.subcommand}' is not implemented.",
                    path=item.path,
                    line=item.line,
                    detail="The docs mention a `sattlint` subcommand that the parser does not expose.",
                    suggestion="Update the docs or add the missing subcommand.",
                )
            )
        if item.command.startswith("sattlint-") and item.command not in scripts:
            findings.append(
                Finding(
                    id="documented-missing-script",
                    category="feature-wiring",
                    severity="medium",
                    confidence="high",
                    message=f"Documented console script '{item.command}' is not declared in pyproject.",
                    path=item.path,
                    line=item.line,
                    suggestion="Keep project.scripts and docs in sync.",
                )
            )
    return findings


def _find_unused_config_keys(
    source_root: Path,
    default_keys: Iterable[str],
    *,
    content_by_file: dict[Path, str] | None = None,
) -> list[Finding]:
    if content_by_file is None:
        content_by_file = {}
        for path in source_root.rglob("*.py"):
            if path.name == "repo_audit.py":
                continue
            content_by_file[path] = _read_text(path)

    findings: list[Finding] = []
    for key in default_keys:
        pattern = re.compile(rf"['\"]{re.escape(key)}['\"]")
        count = 0
        for path, text in content_by_file.items():
            if path.name == "config.py":
                count += max(0, len(pattern.findall(text)) - 1)
            else:
                count += len(pattern.findall(text))
        if count == 0:
            findings.append(
                Finding(
                    id="unused-config-key",
                    category="configuration-hygiene",
                    severity="medium",
                    confidence="medium",
                    message=f"Config key '{key}' appears to be declared but unused.",
                    path="src/sattlint/config.py",
                    suggestion="Remove the key, document it, or wire it into runtime behavior.",
                )
            )
    return findings


def _module_name_from_path(path: Path, root: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def _resolve_import(module_name: str, imported: str | None, level: int) -> str | None:
    parts = module_name.split(".")
    if level == 0:
        return imported
    if level > len(parts):
        return imported
    prefix = parts[:-level]
    if imported:
        prefix.extend(imported.split("."))
    return ".".join(part for part in prefix if part)


def _build_local_import_graph(
    source_root: Path,
    *,
    content_by_file: dict[Path, str] | None = None,
    ast_by_file: dict[Path, ast.AST] | None = None,
) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    known_modules: dict[str, Path] = {}
    module_paths = list((content_by_file or {}).keys()) or list(source_root.rglob("*.py"))
    for path in module_paths:
        module_name = _module_name_from_path(path, source_root)
        known_modules[module_name] = path

    for module_name, path in known_modules.items():
        if ast_by_file is not None and path in ast_by_file:
            tree = ast_by_file[path]
        else:
            tree = ast.parse((content_by_file or {}).get(path) or _read_text(path), filename=str(path))
        imports: set[str] = set()
        type_checking_lines: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                for guarded_node in node.body:
                    start = getattr(guarded_node, "lineno", None)
                    end = getattr(guarded_node, "end_lineno", start)
                    if start is None or end is None:
                        continue
                    type_checking_lines.update(range(start, end + 1))
        for node in ast.walk(tree):
            if getattr(node, "lineno", None) in type_checking_lines:
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in known_modules:
                        imports.add(alias.name)
                    else:
                        for candidate in known_modules:
                            if candidate.startswith(alias.name + "."):
                                imports.add(alias.name)
                                break
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve_import(module_name, node.module, node.level)
                if not resolved:
                    continue
                if resolved in known_modules:
                    imports.add(resolved)
                else:
                    for candidate in known_modules:
                        if candidate.startswith(resolved + "."):
                            imports.add(resolved)
                            break
        graph[module_name] = imports
    return graph


def _find_import_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            if node in stack:
                start = stack.index(node)
                cycles.append([*stack[start:], node])
            return
        visiting.add(node)
        stack.append(node)
        for neighbor in graph.get(node, set()):
            if neighbor in graph:
                visit(neighbor)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return cycles


def _find_architecture_findings(
    source_root: Path,
    *,
    content_by_file: dict[Path, str] | None = None,
    ast_by_file: dict[Path, ast.AST] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    graph = _build_local_import_graph(
        source_root,
        content_by_file=content_by_file,
        ast_by_file=ast_by_file,
    )
    cycles = _find_import_cycles(graph)
    for cycle in cycles:
        cycle_str = " -> ".join(cycle)
        if "sattline_semantics" in cycle and "rule_profiles" in cycle:
            severity = "info"
            message = "Known aggregator cycle (rule metadata requires aggregator)."
        elif len(cycle) > 4:
            severity = "info"
            message = "Long import cycle through multiple analyzers."
        else:
            severity = "high"
            message = "Circular import detected."
        findings.append(
            Finding(
                id="import-cycle",
                category="architecture",
                severity=severity,
                confidence="high",
                message=message,
                detail=cycle_str,
                suggestion="Break the cycle with a lower-level shared module or dependency inversion.",
            )
        )

    file_iterable = list((content_by_file or {}).items()) or [
        (path, _read_text(path)) for path in source_root.rglob("*.py")
    ]
    for path, text in file_iterable:
        rel_path = _relative_path(path)
        lines = text.splitlines()
        non_empty_lines = [line for line in lines if line.strip() and not line.strip().startswith("#")]
        if len(non_empty_lines) >= OVERSIZED_MODULE_LINE_LIMIT and not rel_path.endswith("_builtins.py"):
            findings.append(
                Finding(
                    id="oversized-module",
                    category="architecture",
                    severity="medium",
                    confidence="high",
                    message="Large module with high maintenance cost.",
                    path=rel_path,
                    detail=f"{len(non_empty_lines)} non-empty lines",
                    suggestion="Split unrelated responsibilities into smaller modules.",
                )
            )

    semantic_path = source_root / "sattlint" / "core" / "semantic.py"
    if semantic_path.exists():
        semantic_text = (content_by_file or {}).get(semantic_path) or _read_text(semantic_path)
        if (
            "from ..analyzers.variables import VariablesAnalyzer" in semantic_text
            or "from sattlint.analyzers.variables import VariablesAnalyzer" in semantic_text
        ):
            findings.append(
                Finding(
                    id="core-analyzer-coupling",
                    category="architecture",
                    severity="medium",
                    confidence="high",
                    message="Core semantic layer depends directly on analyzer code.",
                    path=_relative_path(semantic_path),
                    suggestion="Keep `sattlint.core` analysis-agnostic or move shared logic into a lower-level package.",
                )
            )
    return findings


def _find_cli_findings() -> list[Finding]:
    parser = app_module.build_cli_parser()
    findings: list[Finding] = []
    if not parser.description:
        findings.append(
            Finding(
                id="cli-missing-description",
                category="cli-ux",
                severity="low",
                confidence="high",
                message="Top-level CLI parser is missing a description.",
                path="src/sattlint/app.py",
                suggestion="Add a short parser description so `--help` is self-explanatory.",
            )
        )
    for action in parser._actions:
        choices = getattr(action, "choices", None) or {}
        for subparser in choices.values():
            if not subparser.description:
                findings.append(
                    Finding(
                        id="cli-missing-subcommand-description",
                        category="cli-ux",
                        severity="low",
                        confidence="high",
                        message="CLI subcommand is missing a description.",
                        path="src/sattlint/app.py",
                        suggestion="Give each subcommand a description for consistent help output.",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Coverage summary public API (delegates to coverage_reports module to avoid
# introducing a circular import with pipeline.py)
# ---------------------------------------------------------------------------


def build_coverage_summary_report(root: Path) -> dict[str, Any]:
    """Build a coverage-summary report for the repository at *root*.

    Delegates to :mod:`sattlint.devtools.coverage_reports` so that this module
    does not import ``pipeline`` and avoids a circular dependency.
    """
    return _coverage_reports_module.build_coverage_summary_report(root)


def build_ai_gc_report(
    root: Path = REPO_ROOT,
    *,
    tracked_paths: Iterable[str] | None = None,
    stale_after_days: int = _ai_gc_module.DEFAULT_STALE_AFTER_DAYS,
    now_ts: float | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    return _ai_gc_module.build_ai_gc_report(
        root,
        tracked_paths=tracked_paths,
        stale_after_days=stale_after_days,
        now_ts=now_ts,
        apply=apply,
    )


def apply_ai_gc(
    root: Path = REPO_ROOT,
    *,
    output_dir: Path | None = None,
    tracked_paths: Iterable[str] | None = None,
    stale_after_days: int = _ai_gc_module.DEFAULT_STALE_AFTER_DAYS,
    now_ts: float | None = None,
) -> dict[str, Any]:
    report = build_ai_gc_report(
        root,
        tracked_paths=tracked_paths,
        stale_after_days=stale_after_days,
        now_ts=now_ts,
        apply=True,
    )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json_artifact(output_dir / _ai_gc_module.AI_GC_REPORT_FILENAME, report)
    return report


def _ai_gc_report_findings(report: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for candidate in report.get("candidates", []):
        if candidate.get("applied"):
            continue
        candidate_id = str(candidate.get("candidate_id") or "ai-gc")
        path = candidate.get("path")
        age_days = candidate.get("age_days")
        severity = (
            "medium"
            if candidate_id == "stale-generated-output-manifest" or (isinstance(age_days, int) and age_days >= 30)
            else "low"
        )
        if candidate_id == "stale-generated-output-manifest":
            message = "Generated output drifted from its source-digest manifest."
            detail = str(candidate.get("reason") or "")
        else:
            message = "Stale AI-generated artifact can be collected."
            detail = (
                f"age_days={age_days} size_bytes={candidate.get('size_bytes', 0)}"
                if age_days is not None
                else str(candidate.get("reason") or "")
            )
        findings.append(
            Finding(
                id=candidate_id,
                category="maintenance",
                severity=severity,
                confidence="high",
                message=message,
                path=path,
                detail=detail,
                suggestion="Run sattlint-repo-audit --apply-ai-gc to delete safe stale artifacts.",
                source="ai-gc",
            )
        )
    return findings


def _is_active_output_ai_gc_path(path: str | None, *, output_dir_path: str | None) -> bool:
    if not path or not output_dir_path:
        return False
    return path.rstrip("/") == output_dir_path.rstrip("/")


def _filter_ai_gc_report_for_output_dir(report: dict[str, Any], *, output_dir_path: str | None) -> dict[str, Any]:
    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        return report
    filtered_candidates = [
        candidate
        for candidate in candidates
        if not (
            isinstance(candidate, dict)
            and str(candidate.get("candidate_id") or "") == "stale-generated-output-manifest"
            and _is_active_output_ai_gc_path(candidate.get("path"), output_dir_path=output_dir_path)
        )
    ]
    if len(filtered_candidates) == len(candidates):
        return report
    filtered_report = dict(report)
    filtered_report["candidates"] = filtered_candidates
    filtered_summary = dict(report.get("summary", {}))
    filtered_summary["candidate_count"] = len(filtered_candidates)
    filtered_summary["artifact_candidate_count"] = sum(
        1
        for candidate in filtered_candidates
        if candidate.get("candidate_id") in {"stale-ai-artifact", "stale-generated-output-manifest"}
    )
    filtered_summary["manifest_drift_candidate_count"] = sum(
        1 for candidate in filtered_candidates if candidate.get("candidate_id") == "stale-generated-output-manifest"
    )
    filtered_report["summary"] = filtered_summary
    failures = filtered_report.get("failures")
    filtered_report["status"] = (
        "fail"
        if isinstance(failures, list) and failures
        else "needs-attention"
        if filtered_candidates and filtered_report.get("mode") != "apply"
        else "pass"
    )
    return filtered_report


def _filter_ai_gc_findings_for_output_dir(findings: list[Finding], *, output_dir_path: str | None) -> list[Finding]:
    return [
        finding
        for finding in findings
        if not (
            finding.source == "ai-gc"
            and finding.id == "stale-generated-output-manifest"
            and _is_active_output_ai_gc_path(finding.path, output_dir_path=output_dir_path)
        )
    ]


CLI_CONSISTENCY_SCHEMA_KIND = "sattlint.cli_consistency"
CLI_CONSISTENCY_SCHEMA_VERSION = 1
CLI_CONSISTENCY_DOC_PATHS = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/references/cli-commands.md",
    "docs/references/ai-agent-reference.md",
)


def _cli_consistency_doc_paths(root: Path) -> list[Path]:
    doc_paths: list[Path] = []
    for rel_path in CLI_CONSISTENCY_DOC_PATHS:
        path = root / rel_path
        if path.exists():
            doc_paths.append(path)
    return doc_paths


def build_cli_consistency_report(*, root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build a machine-readable CLI/TUI consistency report.

    Collects declared scripts and subcommands from pyproject.toml and the
    CLI parser, then compares them against documented commands found in docs
    and markdown files.  Emits a consolidated ``cli_consistency.json``
    artifact with gaps, undocumented commands, and undeclared documented
    references.
    """
    scripts, subcommands = _collect_cli_metadata()
    doc_paths = _cli_consistency_doc_paths(root)
    documented_commands = _extract_documented_commands(doc_paths, root=root)

    # Build gap lists
    undeclared_subcommands: list[dict[str, Any]] = []
    undeclared_scripts: list[dict[str, Any]] = []
    for item in documented_commands:
        if item.command == "sattlint" and item.subcommand and item.subcommand not in subcommands:
            undeclared_subcommands.append(
                {
                    "subcommand": item.subcommand,
                    "referenced_in": item.path,
                    "line": item.line,
                }
            )
        if item.command.startswith("sattlint-") and item.command not in scripts:
            undeclared_scripts.append(
                {
                    "script": item.command,
                    "referenced_in": item.path,
                    "line": item.line,
                }
            )

    # Documented subcommands that are implemented (for completeness)
    documented_subcommand_names = {
        item.subcommand for item in documented_commands if item.command == "sattlint" and item.subcommand
    }
    undocumented_subcommands = sorted(subcommands - documented_subcommand_names)

    documented_script_names = {item.command for item in documented_commands if item.command.startswith("sattlint-")}
    undocumented_scripts = sorted(scripts - documented_script_names)

    gap_count = len(undeclared_subcommands) + len(undeclared_scripts)
    return {
        "kind": CLI_CONSISTENCY_SCHEMA_KIND,
        "schema_version": CLI_CONSISTENCY_SCHEMA_VERSION,
        "generated_by": "sattlint.devtools.repo_audit",
        "declared": {
            "scripts": sorted(scripts),
            "subcommands": sorted(subcommands),
        },
        "gaps": {
            "undeclared_subcommands": undeclared_subcommands,
            "undeclared_scripts": undeclared_scripts,
            "undocumented_subcommands": undocumented_subcommands,
            "undocumented_scripts": undocumented_scripts,
        },
        "summary": {
            "declared_script_count": len(scripts),
            "declared_subcommand_count": len(subcommands),
            "undeclared_subcommand_count": len(undeclared_subcommands),
            "undeclared_script_count": len(undeclared_scripts),
            "undocumented_subcommand_count": len(undocumented_subcommands),
            "undocumented_script_count": len(undocumented_scripts),
            "gap_count": gap_count,
        },
        "status": "fail" if gap_count > 0 else "pass",
    }


def _find_logging_findings(
    source_root: Path,
    *,
    content_by_file: dict[Path, str] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    file_iterable = list((content_by_file or {}).items()) or [
        (path, _read_text(path)) for path in source_root.rglob("*.py")
    ]
    for path, text in file_iterable:
        rel_path = _relative_path(path)
        allows_console_output = rel_path in ALLOWED_PRINT_MODULES or any(
            rel_path.startswith(prefix) for prefix in ALLOWED_PRINT_PREFIXES
        )
        if PRINT_CALL_RE.search(text) and not allows_console_output:
            findings.append(
                Finding(
                    id="unexpected-print",
                    category="logging-observability",
                    severity="medium",
                    confidence="medium",
                    message="Library module uses print() instead of structured logging or return values.",
                    path=rel_path,
                    suggestion="Keep prints in CLI entry points; use logging or reports in library code.",
                )
            )
    return findings


def _should_ignore_normalized_pipeline_finding(finding_id: str, path: str | None) -> bool:
    if path is None:
        return False
    return (finding_id, path) in IGNORED_NORMALIZED_PIPELINE_FINDINGS


def _build_python_source_scan_context(
    source_root: Path,
    *,
    root: Path = REPO_ROOT,
    tracked_paths: tuple[str, ...] | None = None,
) -> PythonSourceScanContext:
    texts: dict[Path, str] = {}
    asts: dict[Path, ast.AST] = {}
    if tracked_paths is None:
        paths = sorted(source_root.rglob("*.py"))
    else:
        source_prefix = _relative_path(source_root, root).rstrip("/")
        paths = [
            root / rel_path
            for rel_path in tracked_paths
            if rel_path.endswith(".py") and (rel_path == source_prefix or rel_path.startswith(f"{source_prefix}/"))
        ]
    for path in paths:
        if not path.exists():
            continue
        text = _read_text(path)
        texts[path] = text
        try:
            asts[path] = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
    return PythonSourceScanContext(source_root=source_root, texts=texts, asts=asts)


def _parse_coverage_findings(
    root: Path,
    *,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Finding]:
    coverage_path = root / "coverage.xml"
    if tracked_paths is not None and "coverage.xml" not in tracked_paths:
        return []
    if not coverage_path.exists():
        return []

    findings: list[Finding] = []
    root_xml = ElementTree.fromstring(coverage_path.read_text(encoding="utf-8"))
    for class_node in root_xml.findall(".//class"):
        filename = class_node.attrib.get("filename", "")
        line_rate = float(class_node.attrib.get("line-rate", "0"))
        if not filename.startswith("src/"):
            continue
        severity = None
        if line_rate < 0.10:
            severity = "high"
        elif line_rate < 0.40:
            severity = "medium"
        elif line_rate < 0.60:
            severity = "low"
        if severity is None:
            continue
        findings.append(
            Finding(
                id="low-test-coverage",
                category="test-coverage",
                severity=severity,
                confidence="high",
                message="Source module has low test coverage.",
                path=filename,
                detail=f"line-rate={line_rate:.0%}",
                suggestion="Add targeted tests for this module or reduce dead code within it.",
                source="coverage.xml",
            )
        )
    return findings


def _find_public_readiness_findings(
    root: Path,
    *,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    tracked_path_set = None if tracked_paths is None else set(tracked_paths)
    required_files = ["README.md", "LICENSE", "CONTRIBUTING.md", ".gitignore"]
    for filename in required_files:
        exists = (root / filename).exists() if tracked_path_set is None else filename in tracked_path_set
        if not exists:
            findings.append(
                Finding(
                    id="missing-public-file",
                    category="public-readiness",
                    severity="high",
                    confidence="high",
                    message=f"Expected public-facing file '{filename}' is missing.",
                    suggestion="Add the missing file before publishing the repository.",
                )
            )

    pyproject = _load_pyproject(root)
    urls = pyproject.get("project", {}).get("urls", {})
    if not urls:
        findings.append(
            Finding(
                id="missing-project-urls",
                category="public-readiness",
                severity="low",
                confidence="high",
                message="pyproject metadata does not declare project URLs.",
                path="pyproject.toml",
                suggestion="Add homepage, repository, and issue tracker URLs.",
            )
        )

    if tracked_path_set is None:
        workflow_dir = root / ".github" / "workflows"
        has_workflow = workflow_dir.exists() and any(workflow_dir.glob("*.y*ml"))
    else:
        has_workflow = any(
            rel_path.startswith(".github/workflows/") and rel_path.endswith((".yml", ".yaml"))
            for rel_path in tracked_path_set
        )
    if not has_workflow:
        findings.append(
            Finding(
                id="missing-ci-workflow",
                category="public-readiness",
                severity="medium",
                confidence="high",
                message="Repository does not define a CI workflow.",
                suggestion="Add an audit or test workflow so external contributors get immediate feedback.",
            )
        )

    tracked = list(tracked_paths or ())
    if not tracked and tracked_path_set is None:
        git_executable = shutil.which("git")
        completed = None
        if git_executable is not None:
            try:
                completed = subprocess.run(  # nosec B603 - fixed git command with controlled arguments
                    [git_executable, "ls-files", "artifacts", "build", "htmlcov", "coverage.xml"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                completed = None
        if completed and completed.returncode == 0:
            tracked = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    if tracked:
        generated = [
            line
            for line in tracked
            if any(line == prefix or line.startswith(prefix) for prefix in GENERATED_PATH_PREFIXES)
        ]
        if generated:
            findings.append(
                Finding(
                    id="tracked-generated-artifacts",
                    category="public-readiness",
                    severity="high",
                    confidence="high",
                    message="Generated artifacts are tracked in git and may embed workstation-specific data.",
                    detail=", ".join(generated[:5]) + (" ..." if len(generated) > 5 else ""),
                    suggestion="Remove generated outputs from version control and consider history cleanup for already-published leaks.",
                    history_cleanup_recommended=True,
                )
            )

    tracked_top_level_entries = sorted(
        {
            rel_path.split("/", 1)[0]
            for rel_path in (tracked_paths if tracked_paths is not None else (_list_tracked_repo_paths(root) or ()))
            if rel_path
        }
    )
    unexpected_root_entries = [
        entry for entry in tracked_top_level_entries if entry not in TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST
    ]
    if unexpected_root_entries:
        findings.append(
            Finding(
                id="unexpected-tracked-root-entry",
                category="public-readiness",
                severity="medium",
                confidence="high",
                message="Repository root contains tracked helper or scratch entries outside the approved top-level layout.",
                detail=", ".join(unexpected_root_entries[:5]) + (" ..." if len(unexpected_root_entries) > 5 else ""),
                suggestion="Move reusable tooling under scripts/ or another owner directory, and delete one-off scratch files from the repo root.",
            )
        )
    return findings


def _find_pipeline_findings(output_dir: Path) -> list[Finding]:
    findings_path = output_dir / "findings.json"
    if findings_path.exists():
        payload = json.loads(findings_path.read_text(encoding="utf-8"))
        normalized_findings: list[Finding] = []
        for entry in payload.get("findings", []):
            finding_id = str(entry.get("id") or entry.get("rule_id") or "pipeline-finding")
            if finding_id in STRUCTURAL_DEBT_FINDING_IDS:
                continue
            location = entry.get("location") or {}
            path = location.get("path")
            if _should_ignore_normalized_pipeline_finding(finding_id, path):
                continue
            normalized_findings.append(
                Finding(
                    id=finding_id,
                    category=str(entry.get("category") or "unknown"),
                    severity=str(entry.get("severity") or "medium"),
                    confidence=str(entry.get("confidence") or "medium"),
                    message=str(entry.get("message") or "Pipeline reported a finding."),
                    path=path,
                    line=location.get("line"),
                    detail=entry.get("detail"),
                    suggestion=entry.get("suggestion"),
                    source=str(entry.get("source") or "pipeline"),
                )
            )
        return normalized_findings

    findings: list[Finding] = []
    vulture_path = output_dir / "vulture.json"
    if vulture_path.exists():
        payload = json.loads(vulture_path.read_text(encoding="utf-8"))
        for entry in payload.get("findings", []):
            findings.append(
                Finding(
                    id="vulture-dead-code",
                    category="dead-code",
                    severity="medium",
                    confidence="medium",
                    message=entry.get("message", "Potential dead code found."),
                    path=entry.get("file"),
                    line=entry.get("line"),
                    source="vulture",
                )
            )

    bandit_path = output_dir / "bandit.json"
    if bandit_path.exists():
        payload = json.loads(bandit_path.read_text(encoding="utf-8"))
        for entry in payload.get("findings", []):
            issue_severity = str(entry.get("issue_severity", "medium")).lower()
            filename = str(entry.get("filename", ""))
            issue_text = str(entry.get("issue_text", ""))
            if filename.replace("\\", "/").endswith("src/sattlint/cache.py") and "pickle" in issue_text.lower():
                issue_severity = "low"
            findings.append(
                Finding(
                    id="bandit-finding",
                    category="secrets-pii",
                    severity=issue_severity if issue_severity in SEVERITY_RANK else "medium",
                    confidence=str(entry.get("issue_confidence", "medium")).lower(),
                    message=issue_text or "Bandit reported a security issue.",
                    path=filename,
                    line=entry.get("line_number"),
                    source="bandit",
                )
            )

    pytest_path = output_dir / "pytest.json"
    if pytest_path.exists():
        payload = json.loads(pytest_path.read_text(encoding="utf-8"))
        summary = payload.get("summary", {})
        failures = int(summary.get("failures", 0))
        errors = int(summary.get("errors", 0))
        if failures or errors:
            findings.append(
                Finding(
                    id="pytest-failures",
                    category="correctness",
                    severity="high",
                    confidence="high",
                    message="Pytest reported failing or erroring tests.",
                    detail=f"failures={failures}, errors={errors}",
                    source="pytest",
                )
            )
    return findings


def _dedupe_findings(findings: Iterable[Finding]) -> list[Finding]:
    seen: set[tuple[str, str | None, int | None, str]] = set()
    deduped: list[Finding] = []
    for finding in findings:
        key = (finding.id, finding.path, finding.line, finding.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def _is_leak_finding(finding: Finding) -> bool:
    return finding.category in LEAK_RELEVANT_CATEGORIES or finding.id in LEAK_RELEVANT_FINDING_IDS


def _structural_report_location_detail(finding: dict[str, Any]) -> tuple[str | None, str | None]:
    finding_id = finding["id"]
    if finding_id in {"structural-source-file-budget", "structural-test-file-budget"}:
        entries = finding.get("over_budget_files", [])
        if entries:
            first_entry = entries[0]
            return first_entry.get("path"), f"{first_entry.get('line_count')} lines"
    if finding_id == "structural-function-budget":
        entries = finding.get("over_budget_functions", [])
        if entries:
            first_entry = entries[0]
            return first_entry.get("path"), f"{first_entry.get('qualname')} spans {first_entry.get('line_span')} lines"
    if finding_id == "structural-class-budget":
        entries = finding.get("over_budget_classes", [])
        if entries:
            first_entry = entries[0]
            return first_entry.get(
                "path"
            ), f"{first_entry.get('qualname')} defines {first_entry.get('method_count')} methods"
    if finding_id == "structural-private-helper-duplication":
        entries = finding.get("repeated_private_names", [])
        if entries:
            first_entry = entries[0]
            first_path = next(iter(first_entry.get("paths", [])), None)
            return first_path, f"{first_entry.get('name')} repeats across {first_entry.get('file_count')} files"
    if finding_id == "structural-facade-private-boundary":
        entries = finding.get("private_entrypoints", [])
        if entries:
            first_entry = entries[0]
            return first_entry.get("path"), f"calls {first_entry.get('target')} at line {first_entry.get('line')}"
    if finding_id == "structural-budget-ratchet-regression":
        regressions = finding.get("regressions", [])
        if regressions:
            first_regression = regressions[0]
            return None, (
                f"{first_regression.get('metric')}: {first_regression.get('actual')} > "
                f"{first_regression.get('expected_max')}"
            )
    return None, None


def _find_structural_report_findings(root: Path = REPO_ROOT) -> list[Finding]:
    architecture_report = structural_reports_module.collect_architecture_report(root)
    structural_findings: list[Finding] = []
    for finding in architecture_report.get("findings", []):
        finding_id = finding.get("id")
        if not isinstance(finding_id, str) or not finding_id.startswith("structural-"):
            continue
        if finding_id in STRUCTURAL_DEBT_FINDING_IDS:
            continue
        path, detail = _structural_report_location_detail(finding)
        structural_findings.append(
            Finding(
                id=finding_id,
                category="architecture",
                severity=str(finding.get("severity", "medium")),
                confidence="high",
                message=str(finding.get("message", "Structural report finding.")),
                path=path,
                detail=detail,
                source="structural-reports",
            )
        )
    return structural_findings


def _build_repo_audit_scan_context(
    root: Path = REPO_ROOT,
    *,
    include_generated: bool = False,
    tracked_only: bool = False,
    suspicious_identifiers: Iterable[str] = (),
) -> RepoAuditScanContext:
    suspicious_set = frozenset(identifier.strip() for identifier in suspicious_identifiers if identifier.strip())
    tracked_paths = _list_tracked_repo_paths(root) if tracked_only else None
    docs_to_scan = [root / "README.md", root / "CONTRIBUTING.md", root / "vscode" / "sattline-vscode" / "README.md"]
    source_context = _build_python_source_scan_context(
        root / "src",
        root=root,
        tracked_paths=tracked_paths,
    )
    test_context = _build_python_source_scan_context(
        root / "tests",
        root=root,
        tracked_paths=tracked_paths,
    )
    scripts_context = _build_python_source_scan_context(
        root / "scripts",
        root=root,
        tracked_paths=tracked_paths,
    )
    scripts, subcommands = _collect_cli_metadata()
    documented_commands = tuple(
        _extract_documented_commands((path for path in docs_to_scan if path.exists()), root=root)
    )
    return RepoAuditScanContext(
        root=root,
        include_generated=include_generated,
        tracked_only=tracked_only,
        tracked_paths=tracked_paths,
        suspicious_identifiers=suspicious_set,
        source_context=source_context,
        test_context=test_context,
        scripts_context=scripts_context,
        scripts=frozenset(scripts),
        subcommands=frozenset(subcommands),
        documented_commands=documented_commands,
    )


def _shared_text_line_findings(context: RepoAuditScanContext) -> tuple[Finding, ...]:
    if context.line_findings is not None:
        return context.line_findings

    findings: list[Finding] = []
    suspicious_identifiers = set(context.suspicious_identifiers)
    for path, text in _iter_repo_text_entries(
        context.root,
        include_generated=context.include_generated,
        tracked_only=context.tracked_only,
    ):
        findings.extend(_line_findings(path, text, suspicious_identifiers, root=context.root))
    return tuple(findings)


def _with_shared_text_line_findings(context: RepoAuditScanContext) -> RepoAuditScanContext:
    if context.line_findings is not None:
        return context
    return replace(context, line_findings=_shared_text_line_findings(context))


def _run_text_scan_check(context: RepoAuditScanContext) -> list[Finding]:
    return [
        finding for finding in _shared_text_line_findings(context) if finding.id not in LOCAL_CI_PARITY_LINE_FINDING_IDS
    ]


def _run_documented_commands_check(context: RepoAuditScanContext) -> list[Finding]:
    return _find_documentation_command_gaps(context.documented_commands, set(context.scripts), set(context.subcommands))


def _run_unused_config_keys_check(context: RepoAuditScanContext) -> list[Finding]:
    return _find_unused_config_keys(
        context.root / "src" / "sattlint",
        config_module.DEFAULT_CONFIG.keys(),
        content_by_file={
            path: text
            for path, text in context.source_context.texts.items()
            if path.is_relative_to(context.root / "src" / "sattlint") and path.name != "repo_audit.py"
        },
    )


def _run_architecture_check(context: RepoAuditScanContext) -> list[Finding]:
    return _find_architecture_findings(
        context.root / "src",
        content_by_file=context.source_context.texts,
        ast_by_file=context.source_context.asts,
    )


def _run_structural_report_check(context: RepoAuditScanContext) -> list[Finding]:
    return _find_structural_report_findings(context.root)


def _run_cli_check(_context: RepoAuditScanContext) -> list[Finding]:
    return _find_cli_findings()


def _run_logging_check(context: RepoAuditScanContext) -> list[Finding]:
    return _find_logging_findings(context.root / "src", content_by_file=context.source_context.texts)


def _run_ai_gc_check(context: RepoAuditScanContext) -> list[Finding]:
    report = build_ai_gc_report(
        context.root,
        tracked_paths=context.tracked_paths,
    )
    return _ai_gc_report_findings(report)


def _run_ignored_repo_paths_check(context: RepoAuditScanContext) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(
        _find_ignored_repo_path_references(
            context.source_context,
            root=context.root,
            tracked_paths=context.tracked_paths,
        )
    )
    findings.extend(
        _find_ignored_repo_path_references(
            context.test_context,
            root=context.root,
            tracked_paths=context.tracked_paths,
        )
    )
    findings.extend(
        _find_ignored_repo_path_references(
            context.scripts_context,
            root=context.root,
            tracked_paths=context.tracked_paths,
        )
    )
    return findings


def _run_coverage_check(context: RepoAuditScanContext) -> list[Finding]:
    return _parse_coverage_findings(context.root, tracked_paths=context.tracked_paths)


def _patch_doc_gardener_paths(root: Path):
    return patch.multiple(
        _doc_gardener_module,
        REPO_ROOT=root,
        DOCS_DIR=root / "docs",
        AGENTS_MD=root / "AGENTS.md",
        QUALITY_SCORE=root / "docs" / "quality-score.md",
        TECH_DEBT=root / "docs" / "exec-plans" / "tech-debt-tracker.md",
        CURRENT_WORK=root / ".github" / "coordination" / "current_work_lock.json",
        CURRENT_WORK_TEMPLATE=root / ".github" / "coordination" / "current-work.template.md",
        AI_FIRST_PLAN=root / "docs" / "exec-plans" / "active" / "ai-first-repo-hardening.md",
        AI_FIRST_DEBT=root / "docs" / "exec-plans" / "tech-debt-tracker.md",
    )


def _doc_gardener_finding_to_repo_audit(finding: Any) -> Finding:
    return Finding(
        id=f"harness-{str(finding.category).replace('_', '-')}",
        category="harness-freshness",
        severity=str(finding.severity).casefold(),
        confidence="high",
        message=str(finding.message),
        path=str(finding.file) or None,
        line=None if int(getattr(finding, "line", 0)) <= 0 else int(finding.line),
        source="harness-freshness",
    )


def _ai_harness_issue_to_finding(issue: dict[str, Any]) -> Finding:
    issue_id = str(issue.get("issue_id", "ai-harness-issue")).strip() or "ai-harness-issue"
    return Finding(
        id=f"harness-{issue_id}",
        category="harness-freshness",
        severity=str(issue.get("severity", "high")).casefold(),
        confidence="high",
        message=str(issue.get("message", "AI harness freshness issue.")),
        path=str(issue.get("path", "")).strip() or None,
        detail=json.dumps(issue, sort_keys=True),
        source="harness-freshness",
    )


def _run_harness_freshness_check(context: RepoAuditScanContext) -> list[Finding]:
    findings = [
        _ai_harness_issue_to_finding(issue)
        for issue in _ai_work_map_module.verify_ai_harness_freshness(
            repo_root=context.root,
            output_path=context.root / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json",
            session_output_path=context.root
            / ".github"
            / "skills"
            / "validation-routing"
            / "references"
            / "ai-session-context-map.json",
        )["issues"]
    ]
    with _patch_doc_gardener_paths(context.root):
        for scanner_name in HARNESS_FRESHNESS_DOC_SCANNERS:
            findings.extend(
                _doc_gardener_finding_to_repo_audit(finding)
                for finding in getattr(_doc_gardener_module, scanner_name)()
            )
    return findings


def _run_public_readiness_check(context: RepoAuditScanContext) -> list[Finding]:
    return _find_public_readiness_findings(context.root, tracked_paths=context.tracked_paths)


def audit_repository(
    output_dir: Path,
    *,
    profile: str,
    fail_on: str,
    include_generated: bool,
    leaks_only: bool,
    suspicious_identifiers: Iterable[str],
    skip_pipeline: bool,
    skip_vulture: bool,
    skip_bandit: bool,
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ai_gc_report: dict[str, Any] | None = None
    pipeline_summary: dict[str, Any] | None = None
    pipeline_findings: list[Finding] = []
    audit_profile = "leaks" if leaks_only else profile
    sanitized_output_dir = sanitize_path_for_report(output_dir, repo_root=REPO_ROOT) or output_dir.as_posix()
    sanitized_latest_output_dir = (
        None
        if latest_output_dir is None
        else sanitize_path_for_report(latest_output_dir, repo_root=REPO_ROOT) or latest_output_dir.as_posix()
    )
    progress = ProgressReporter(
        kind="sattlint.repo_audit.progress",
        title="Repository audit",
        output_dir=output_dir,
        write_json=write_json_artifact,
        stages=[
            ("pipeline", "Run shared pipeline"),
            ("custom_scan", "Run repository-specific checks"),
            ("merge_findings", "Merge and normalize findings"),
            ("write_reports", "Write audit reports"),
        ],
        canonical_command=_recommended_command(
            output_dir=sanitized_output_dir,
            profile=profile,
            fail_on=fail_on,
            leaks_only=leaks_only,
        ),
    )
    if not skip_pipeline and not leaks_only:
        pipeline_output_dir = output_dir / PIPELINE_OUTPUT_DIRNAME
        corpus_manifest_dir = _default_corpus_manifest_dir()
        progress.start_stage("pipeline")
        pipeline_summary = pipeline_module._run_pipeline(
            pipeline_output_dir,
            trace_target=pipeline_module.DEFAULT_TRACE_TARGET
            if pipeline_module.DEFAULT_TRACE_TARGET.exists()
            else None,
            profile=profile,
            include_vulture=False if skip_vulture else None,
            include_bandit=False if skip_bandit else None,
            corpus_manifest_dir=corpus_manifest_dir,
        )
        pipeline_findings = _find_pipeline_findings(pipeline_output_dir)
        progress.complete_stage(
            "pipeline",
            detail=f"{len(pipeline_findings)} pipeline findings",
        )
    else:
        progress.skip_stage(
            "pipeline",
            detail="skipped by flags" if skip_pipeline or leaks_only else None,
        )

    progress.start_stage("custom_scan")
    custom_findings = collect_custom_findings(
        REPO_ROOT,
        include_generated=(include_generated or leaks_only),
        tracked_only=True,
        suspicious_identifiers=suspicious_identifiers,
    )
    custom_findings = _filter_ai_gc_findings_for_output_dir(custom_findings, output_dir_path=sanitized_output_dir)
    if not leaks_only:
        ai_gc_report = _filter_ai_gc_report_for_output_dir(
            build_ai_gc_report(REPO_ROOT),
            output_dir_path=sanitized_output_dir,
        )
    progress.complete_stage("custom_scan", detail=f"{len(custom_findings)} custom findings")
    progress.start_stage("merge_findings")
    findings = _dedupe_findings([*pipeline_findings, *custom_findings])
    if leaks_only:
        findings = [finding for finding in findings if _is_leak_finding(finding)]
    findings = sorted(
        findings,
        key=lambda item: (-SEVERITY_RANK[item.severity], item.category, item.path or "", item.line or 0, item.id),
    )
    blocking_count = _blocking_finding_count(findings, fail_on)
    enabled_audit_artifact_ids = {"progress", "status", "summary", "findings", "summary_markdown", "run_history"}
    if audit_profile == "full":
        enabled_audit_artifact_ids.add("cli_consistency")
    if ai_gc_report is not None:
        enabled_audit_artifact_ids.add("ai_gc")
    reports = artifact_reports_map(
        AUDIT_ARTIFACTS,
        profile=audit_profile,
        enabled_artifact_ids=enabled_audit_artifact_ids,
    )
    progress.complete_stage("merge_findings", detail=f"{len(findings)} total findings")
    reports["pipeline_status"] = None if pipeline_summary is None else f"{PIPELINE_OUTPUT_DIRNAME}/status.json"
    reports["pipeline_summary"] = None if pipeline_summary is None else f"{PIPELINE_OUTPUT_DIRNAME}/summary.json"
    finding_collection = FindingCollection(tuple(finding.to_record() for finding in findings))
    overall_status_value = "fail" if blocking_count else "pass"
    summary = {
        "generated_by": "sattlint.devtools.repo_audit",
        "output_dir": sanitized_output_dir,
        "profile": audit_profile,
        "entry_report": "status.json",
        "canonical_command": _recommended_command(
            output_dir=sanitized_output_dir,
            profile=profile,
            fail_on=fail_on,
            leaks_only=leaks_only,
        ),
        "pipeline_ran": (not skip_pipeline and not leaks_only),
        "pipeline_summary": pipeline_summary,
        "reports": reports,
        "finding_count": len(findings),
        "severity_counts": _severity_counts(findings),
        "category_counts": _category_counts(findings),
        "max_severity": _max_severity(findings),
        "findings_schema": finding_collection.schema_metadata,
        "history_cleanup_findings": [finding.to_dict() for finding in findings if finding.history_cleanup_recommended],
        "findings": [finding.to_dict() for finding in findings],
    }
    status_report = {
        "kind": "sattlint.repo_audit.status",
        "generated_by": "sattlint.devtools.repo_audit",
        "profile": audit_profile,
        "fail_on": fail_on,
        "overall_status": overall_status_value,
        "canonical_command": summary["canonical_command"],
        "status_report": f"{sanitized_output_dir}/status.json",
        "summary_report": f"{sanitized_output_dir}/summary.json",
        "progress_report": f"{sanitized_output_dir}/progress.json",
        "finding_count": summary["finding_count"],
        "blocking_finding_count": blocking_count,
        "max_severity": summary["max_severity"],
        "severity_counts": summary["severity_counts"],
        "category_counts": summary["category_counts"],
        "findings_schema": summary["findings_schema"],
        "pipeline_status_report": None
        if pipeline_summary is None
        else f"{sanitized_output_dir}/{PIPELINE_OUTPUT_DIRNAME}/status.json",
        "latest_status_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/status.json",
        "latest_summary_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/summary.json",
        "top_findings": [
            {
                "id": finding.id,
                "severity": finding.severity,
                "path": finding.path,
                "line": finding.line,
                "message": finding.message,
            }
            for finding in findings[:5]
        ],
    }
    progress.start_stage("write_reports")
    write_json_artifact(output_dir / "status.json", status_report)
    write_json_artifact(output_dir / "summary.json", summary)
    write_json_artifact(output_dir / "findings.json", finding_collection.to_dict())
    if ai_gc_report is not None:
        write_json_artifact(output_dir / _ai_gc_module.AI_GC_REPORT_FILENAME, ai_gc_report)
    _write_markdown(output_dir / "summary.md", findings, summary)
    if audit_profile == "full":
        cli_consistency_report = build_cli_consistency_report(root=REPO_ROOT)
        write_json_artifact(output_dir / "cli_consistency.json", cli_consistency_report)
    _write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="repo_audit",
        primary_payload=summary,
        status_payload=status_report,
        summary_payload=summary,
    )
    _mirror_latest_reports(output_dir, latest_output_dir)
    progress.complete_stage("write_reports")
    progress.finalize(overall_status=overall_status_value)
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
