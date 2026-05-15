"""Shared constants, data models, and pure helpers for repo audit."""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sattlint.contracts import FindingLocation, FindingRecord

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
    "build/",
    "dist/",
    "coverage.xml",
    "htmlcov/",
)
TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST = frozenset(
    {
        ".codegraph",
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
        "artifacts",
        "custom.toml",
        "docs",
        "metrics",
        "opencode.json",
        "pyproject.toml",
        "scripts",
        "src",
        "tests",
        "uv.lock",
        "vscode",
    }
)
IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PREFIXES = ("src/sattlint/devtools/",)
IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PATHS = {
    "scripts/check_ratchet_policy.py",
    "scripts/repo_health.py",
    "tests/test_artifact_contracts.py",
    "tests/devtools/test_devtools_review_observability.py",
    "tests/test_pipeline_collection.py",
    "tests/test_pipeline_run.py",
    "tests/test_repo_audit_reporting_helpers.py",
    "tests/devtools/test_context_health.py",
    "tests/test_repo_audit.py",
    "tests/test_repo_audit_entrypoints_helpers.py",
    "tests/devtools/test_run_markdownlint.py",
    "tests/test_ratchet_policy.py",
    "tests/devtools/test_repo_health.py",
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
    "src/sattlint/devtools/leak_detection.py",
    "src/sattlint/devtools/repo_audit.py",
    "src/sattlint/devtools/repo_audit_shared.py",
    "tests/test_repo_audit.py",
}
SKIP_SELF_SCAN_PREFIXES = (
    "tests/_pipeline_collection_part",
    "tests/_repo_audit_part",
)
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
DOCUMENTED_COMMAND_RE = re.compile(r"\b(sattlint(?:-[a-z0-9-]+)?)(?:\s+([a-z][a-z0-9-]*))?", re.IGNORECASE)
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


def leading_string_args(args: Sequence[ast.expr]) -> tuple[str, ...]:
    parts: list[str] = []
    for arg in args:
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            break
        value = arg.value.strip().replace("\\", "/").strip("/")
        if not value:
            continue
        parts.append(value)
    return tuple(parts)


def attribute_path(node: ast.AST) -> tuple[str, ...] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return tuple(reversed(parts))


def repo_relative_path_from_expr(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name) and node.id == "REPO_ROOT":
        return ()
    if isinstance(node, ast.Attribute) and node.attr == "REPO_ROOT":
        return ()
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_repo_path":
        parts = leading_string_args(node.args)
        return parts or None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = repo_relative_path_from_expr(node.left)
        if left is None:
            return None
        if not isinstance(node.right, ast.Constant) or not isinstance(node.right.value, str):
            return None
        right = node.right.value.strip().replace("\\", "/").strip("/")
        if not right:
            return left
        return (*left, right)
    return None


def normalize_repo_relative_literal(value: str) -> str | None:
    normalized = value.strip().replace("\\", "/")
    if not normalized or "://" in normalized or normalized.startswith(("/", "../", "./", "<")):
        return None
    return normalized.rstrip("/")


def is_ignored_repo_path_reference(candidate: str, tracked_paths: tuple[str, ...] | None) -> bool:
    normalized = candidate.rstrip("/")
    prefix = f"{normalized}/"
    if tracked_paths is not None and any(path == normalized or path.startswith(prefix) for path in tracked_paths):
        return False
    if normalized in IGNORED_REPO_PATH_REFERENCE_EXACT:
        return True
    if normalized.startswith(".coverage"):
        return True
    return normalized.startswith(IGNORED_REPO_PATH_REFERENCE_PREFIXES)
