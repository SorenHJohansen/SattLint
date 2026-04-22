"""Repository audit runner for portability, security, wiring, and public-readiness checks."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess  # nosec B404 - audit intentionally executes trusted local developer tools
import tomllib
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as ET  # type: ignore[import-untyped]

from sattlint import app as app_module
from sattlint import config as config_module
from sattlint.contracts import FindingCollection, FindingLocation, FindingRecord
from sattlint.devtools.artifact_registry import AUDIT_ARTIFACTS, artifact_reports_map
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.path_sanitizer import sanitize_path_for_report

from . import pipeline as pipeline_module

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "audit"
PIPELINE_OUTPUT_DIRNAME = "pipeline"
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
    "coverage.xml",
    "htmlcov/",
)
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
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}
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
    "src/sattlint/docgenerator/configgen.py",
    "src/sattlint/engine.py",
    "src/sattlint/tracing.py",
    "src/sattlint/devtools/corpus.py",
    "src/sattlint/devtools/pipeline.py",
    "src/sattlint/devtools/progress_reporting.py",
    "src/sattlint/devtools/repo_audit.py",
}
WINDOWS_PATH_RE = re.compile(r"(?<![\w/])(?:[A-Za-z]:[\\/][^\s'\">|]+)")
UNIX_PATH_RE = re.compile(r"(?<![\w.])/(?:home|Users|mnt/c|mnt/[A-Za-z]/Users)/[^\s'\">]+")
LOCAL_ENDPOINT_RE = re.compile(r"\b(?:localhost|127(?:\.\d{1,3}){3}|[a-z0-9-]+\.local)(?::\d{2,5})?\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:[a-z0-9_-]*?(?:api[_-]?key|token|secret|password|passwd|connection[_-]?string))\b.{0,24}?[:=]\s*['\"]([^'\"]+)['\"]"
)
PRINT_CALL_RE = re.compile(r"\bprint\s*\(")
OVERSIZED_MODULE_LINE_LIMIT = 2000


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


def _relative_path(path: Path, root: Path = REPO_ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


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
            lines.append(
                f"- [{finding.severity.upper()}] {finding.category}: {finding.message} ({location})"
            )
            if finding.detail:
                lines.append(f"  Detail: {finding.detail}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    git_executable = shutil.which("git")
    if git_executable is None:
        yield from _iter_repo_file_candidates(root, include_generated=include_generated)
        return

    try:
        completed = subprocess.run(  # nosec B603 - fixed git command with controlled arguments
            [git_executable, "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError:
        yield from _iter_repo_file_candidates(root, include_generated=include_generated)
        return

    if completed.returncode != 0:
        yield from _iter_repo_file_candidates(root, include_generated=include_generated)
        return

    for raw_rel_path in completed.stdout.decode("utf-8", errors="replace").split("\x00"):
        rel_path = raw_rel_path.strip()
        if not rel_path:
            continue
        if not include_generated and rel_path.startswith("artifacts/"):
            continue

        path = root / Path(rel_path)
        if not path.exists() or path.is_dir():
            continue
        if any(
            _should_skip_dir(part)
            and not (include_generated and part in {"artifacts", "build", "htmlcov"})
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
    if rel_path == "coverage.xml" or rel_path.startswith(SKIP_CONTENT_SCAN_PREFIXES) or rel_path in SKIP_SELF_SCAN_PATHS:
        return findings
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue

        for match in WINDOWS_PATH_RE.finditer(line):
            value = match.group(0)
            if "%USERPROFILE%" in value or "C:\\Users\\MyUser" in value:
                continue
            if (
                rel_path == "README.md"
                and ("C:\\Tools\\SattLint" in value or "C:\\Path\\To\\Program.s" in value)
            ):
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
    pattern = re.compile(r"\b(sattlint(?:-[a-z0-9-]+)?)(?:\s+([a-z][a-z0-9-]*))?", re.IGNORECASE)
    commands: list[DocumentedCommand] = []
    for path in paths:
        text = _read_text(path)
        rel_path = _relative_path(path, root)
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in pattern.finditer(line):
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
        findings.append(
            Finding(
                id="import-cycle",
                category="architecture",
                severity="high",
                confidence="high",
                message="Circular import detected.",
                detail=" -> ".join(cycle),
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
        if PRINT_CALL_RE.search(text) and rel_path not in ALLOWED_PRINT_MODULES:
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


def _build_python_source_scan_context(source_root: Path) -> PythonSourceScanContext:
    texts: dict[Path, str] = {}
    asts: dict[Path, ast.AST] = {}
    for path in source_root.rglob("*.py"):
        text = _read_text(path)
        texts[path] = text
        try:
            asts[path] = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
    return PythonSourceScanContext(source_root=source_root, texts=texts, asts=asts)


def _parse_coverage_findings(root: Path) -> list[Finding]:
    coverage_path = root / "coverage.xml"
    if not coverage_path.exists():
        return []

    findings: list[Finding] = []
    root_xml = ET.fromstring(coverage_path.read_text(encoding="utf-8"))
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


def _find_public_readiness_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    required_files = ["README.md", "LICENSE", "CONTRIBUTING.md", ".gitignore"]
    for filename in required_files:
        if not (root / filename).exists():
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

    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists() or not any(workflow_dir.glob("*.y*ml")):
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
        generated = [
            line
            for line in tracked
            if any(
                line == prefix or line.startswith(prefix)
                for prefix in GENERATED_PATH_PREFIXES
            )
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
    return findings


def _find_pipeline_findings(output_dir: Path) -> list[Finding]:
    findings_path = output_dir / "findings.json"
    if findings_path.exists():
        payload = json.loads(findings_path.read_text(encoding="utf-8"))
        normalized_findings: list[Finding] = []
        for entry in payload.get("findings", []):
            location = entry.get("location") or {}
            normalized_findings.append(
                Finding(
                    id=str(entry.get("id") or entry.get("rule_id") or "pipeline-finding"),
                    category=str(entry.get("category") or "unknown"),
                    severity=str(entry.get("severity") or "medium"),
                    confidence=str(entry.get("confidence") or "medium"),
                    message=str(entry.get("message") or "Pipeline reported a finding."),
                    path=location.get("path"),
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
    return (
        finding.category in LEAK_RELEVANT_CATEGORIES
        or finding.id in LEAK_RELEVANT_FINDING_IDS
    )


def collect_custom_findings(
    root: Path = REPO_ROOT,
    *,
    include_generated: bool = False,
    tracked_only: bool = False,
    suspicious_identifiers: Iterable[str] = ("SQHJ",),
) -> list[Finding]:
    findings: list[Finding] = []
    suspicious_set = {identifier.strip() for identifier in suspicious_identifiers if identifier.strip()}
    docs_to_scan = [root / "README.md", root / "CONTRIBUTING.md", root / "vscode" / "sattline-vscode" / "README.md"]
    for path, text in _iter_repo_text_entries(
        root,
        include_generated=include_generated,
        tracked_only=tracked_only,
    ):
        findings.extend(_line_findings(path, text, suspicious_set, root=root))

    source_context = _build_python_source_scan_context(root / "src")

    scripts, subcommands = _collect_cli_metadata()
    documented_commands = _extract_documented_commands(
        (path for path in docs_to_scan if path.exists()),
        root=root,
    )
    findings.extend(_find_documentation_command_gaps(documented_commands, scripts, subcommands))
    findings.extend(
        _find_unused_config_keys(
            root / "src" / "sattlint",
            config_module.DEFAULT_CONFIG.keys(),
            content_by_file={
                path: text
                for path, text in source_context.texts.items()
                if path.is_relative_to(root / "src" / "sattlint") and path.name != "repo_audit.py"
            },
        )
    )
    findings.extend(
        _find_architecture_findings(
            root / "src",
            content_by_file=source_context.texts,
            ast_by_file=source_context.asts,
        )
    )
    findings.extend(_find_cli_findings())
    findings.extend(_find_logging_findings(root / "src", content_by_file=source_context.texts))
    findings.extend(_parse_coverage_findings(root))
    findings.extend(_find_public_readiness_findings(root))
    return _dedupe_findings(findings)


def _severity_counts(findings: Iterable[Finding]) -> dict[str, int]:
    counts = Counter(finding.severity for finding in findings)
    return {severity: counts.get(severity, 0) for severity in ("critical", "high", "medium", "low")}


def _category_counts(findings: Iterable[Finding]) -> dict[str, int]:
    counts = Counter(finding.category for finding in findings)
    return dict(sorted(counts.items()))


def _max_severity(findings: Iterable[Finding]) -> str | None:
    max_finding = max(findings, key=lambda item: SEVERITY_RANK[item.severity], default=None)
    return None if max_finding is None else max_finding.severity


def _should_fail(findings: Iterable[Finding], threshold: str) -> bool:
    minimum_rank = SEVERITY_RANK[threshold]
    return any(SEVERITY_RANK[finding.severity] >= minimum_rank for finding in findings)


def _blocking_finding_count(findings: Iterable[Finding], threshold: str) -> int:
    minimum_rank = SEVERITY_RANK[threshold]
    return sum(1 for finding in findings if SEVERITY_RANK[finding.severity] >= minimum_rank)


def _recommended_command(*, output_dir: str, profile: str, fail_on: str, leaks_only: bool) -> str:
    parts = ["sattlint-repo-audit"]
    if leaks_only:
        parts.append("--leaks-only")
    else:
        parts.extend(["--profile", profile])
    parts.extend(["--fail-on", fail_on, "--output-dir", output_dir])
    return " ".join(parts)


def _print_cli_summary(status_report: dict[str, Any]) -> None:
    print(f"Audit profile: {status_report['profile']}")
    print(f"Overall status: {status_report['overall_status']}")
    findings_schema = status_report.get("findings_schema")
    if findings_schema:
        print(
            "Findings schema: "
            f"{findings_schema.get('kind', 'unknown')} "
            f"v{findings_schema.get('schema_version', '?')}"
        )
    print(
        "Findings: "
        f"{status_report['finding_count']} total, "
        f"{status_report['blocking_finding_count']} blocking at fail-on {status_report['fail_on']}"
    )
    print(f"Status report: {status_report['status_report']}")
    print(f"Summary report: {status_report['summary_report']}")
    latest_status_report = status_report.get("latest_status_report")
    latest_summary_report = status_report.get("latest_summary_report")
    if latest_status_report and latest_summary_report:
        print(f"Latest status report: {latest_status_report}")
        print(f"Latest summary report: {latest_summary_report}")


def _default_corpus_manifest_dir() -> Path | None:
    manifest_dir = pipeline_module.DEFAULT_CORPUS_MANIFEST_DIR.resolve()
    if not manifest_dir.exists():
        return None
    if not any(manifest_dir.rglob("*.json")):
        return None
    return manifest_dir


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
        write_json=_write_json,
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
            trace_target=pipeline_module.DEFAULT_TRACE_TARGET if pipeline_module.DEFAULT_TRACE_TARGET.exists() else None,
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
        tracked_only=leaks_only,
        suspicious_identifiers=suspicious_identifiers,
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
    reports = artifact_reports_map(
        AUDIT_ARTIFACTS,
        profile=audit_profile,
        enabled_artifact_ids={"progress", "status", "summary", "findings", "summary_markdown"},
    )
    progress.complete_stage("merge_findings", detail=f"{len(findings)} total findings")
    reports["pipeline_status"] = None if pipeline_summary is None else f"{PIPELINE_OUTPUT_DIRNAME}/status.json"
    reports["pipeline_summary"] = None if pipeline_summary is None else f"{PIPELINE_OUTPUT_DIRNAME}/summary.json"
    finding_collection = FindingCollection(tuple(finding.to_record() for finding in findings))
    overall_status_value = "fail" if blocking_count else "pass"
    summary = {
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
        "history_cleanup_findings": [
            finding.to_dict() for finding in findings if finding.history_cleanup_recommended
        ],
        "findings": [finding.to_dict() for finding in findings],
    }
    status_report = {
        "kind": "sattlint.repo_audit.status",
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
        "pipeline_status_report": None if pipeline_summary is None else f"{sanitized_output_dir}/{PIPELINE_OUTPUT_DIRNAME}/status.json",
        "latest_status_report": None if sanitized_latest_output_dir is None else f"{sanitized_latest_output_dir}/status.json",
        "latest_summary_report": None if sanitized_latest_output_dir is None else f"{sanitized_latest_output_dir}/summary.json",
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
    _write_json(output_dir / "status.json", status_report)
    _write_json(output_dir / "summary.json", summary)
    _write_json(output_dir / "findings.json", finding_collection.to_dict())
    _write_markdown(output_dir / "summary.md", findings, summary)
    _mirror_latest_reports(output_dir, latest_output_dir)
    progress.complete_stage("write_reports")
    progress.finalize(overall_status=overall_status_value)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run repository audit checks for portability, security, wiring, architecture, and public-readiness."
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where audit reports will be written",
    )
    parser.add_argument(
        "--profile",
        choices=AUDIT_PROFILE_CHOICES,
        default="full",
        help="Run the fast quick profile or the complete full profile",
    )
    parser.add_argument(
        "--fail-on",
        choices=("critical", "high", "medium", "low"),
        default=None,
        help="Exit non-zero when findings at or above this severity exist",
    )
    parser.add_argument(
        "--leaks-only",
        action="store_true",
        help="Only report repository leak findings such as hardcoded paths, identifiers, emails, and tracked generated artifacts",
    )
    parser.add_argument(
        "--suspicious-identifier",
        action="append",
        default=[],
        help="Additional username, hostname, or developer-specific token to flag",
    )
    parser.add_argument(
        "--include-generated",
        action="store_true",
        help="Include generated artifacts such as artifacts/analysis in custom scans",
    )
    parser.add_argument("--skip-pipeline", action="store_true", help="Skip the existing lint/type/test/security pipeline")
    parser.add_argument("--skip-vulture", action="store_true", help="Skip Vulture inside the shared pipeline")
    parser.add_argument("--skip-bandit", action="store_true", help="Skip Bandit inside the shared pipeline")
    args = parser.parse_args(argv)

    suspicious_identifiers = ["SQHJ", *args.suspicious_identifier]
    fail_on = args.fail_on or ("medium" if args.leaks_only else "high")
    summary = audit_repository(
        Path(args.output_dir).resolve(),
        profile=args.profile,
        fail_on=fail_on,
        include_generated=args.include_generated,
        leaks_only=args.leaks_only,
        suspicious_identifiers=suspicious_identifiers,
        skip_pipeline=args.skip_pipeline,
        skip_vulture=args.skip_vulture,
        skip_bandit=args.skip_bandit,
        latest_output_dir=DEFAULT_OUTPUT_DIR.resolve(),
    )
    _print_cli_summary(
        {
            "profile": summary["profile"],
            "overall_status": "fail" if _should_fail((Finding(**finding) for finding in summary["findings"]), fail_on) else "pass",
            "findings_schema": summary.get("findings_schema"),
            "finding_count": summary["finding_count"],
            "blocking_finding_count": _blocking_finding_count((Finding(**finding) for finding in summary["findings"]), fail_on),
            "fail_on": fail_on,
            "status_report": f"{summary['output_dir']}/status.json",
            "summary_report": f"{summary['output_dir']}/summary.json",
            "latest_status_report": None if Path(args.output_dir).resolve() == DEFAULT_OUTPUT_DIR.resolve() else f"{(sanitize_path_for_report(DEFAULT_OUTPUT_DIR.resolve(), repo_root=REPO_ROOT) or DEFAULT_OUTPUT_DIR.resolve().as_posix())}/status.json",
            "latest_summary_report": None if Path(args.output_dir).resolve() == DEFAULT_OUTPUT_DIR.resolve() else f"{(sanitize_path_for_report(DEFAULT_OUTPUT_DIR.resolve(), repo_root=REPO_ROOT) or DEFAULT_OUTPUT_DIR.resolve().as_posix())}/summary.json",
        }
    )
    return 1 if _should_fail((Finding(**finding) for finding in summary["findings"]), fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
