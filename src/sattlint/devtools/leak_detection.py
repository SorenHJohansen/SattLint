"""Helpers for repo text scanning, leak detection, and scan contexts."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

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
WINDOWS_PATH_RE = re.compile(r"(?<![\w/])(?:[A-Za-z]:[\\/][^\s'\">|]+)")
UNIX_PATH_RE = re.compile(r"(?<![\w.])/(?:home|Users|mnt/c|mnt/[A-Za-z]/Users)/[^\s'\">]+")
LOCAL_ENDPOINT_RE = re.compile(r"\b(?:localhost|127(?:\.\d{1,3}){3}|[a-z0-9-]+\.local)(?::\d{2,5})?\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(?:['\"]?(?:[a-z0-9_-]*?(?:api[_-]?key|token|secret|password|passwd|connection[_-]?string))['\"]?)\s*[:=]\s*['\"]([^'\"]+)['\"]"
)
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
WINDOWS_USER_PLACEHOLDER = "C:" + "\\" + "\\".join(("Users", "MyUser"))
README_WINDOWS_TOOL_PATH = "C:" + "\\" + "\\".join(("Tools", "SattLint"))
README_WINDOWS_PROGRAM_PATH = "C:" + "\\" + "\\".join(("Path", "To", "Program.s"))


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("binary")
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def should_skip_dir(dirname: str) -> bool:
    if dirname in SKIP_DIRS:
        return True
    return dirname.startswith(".venv")


def list_tracked_repo_paths(
    root: Path,
    *,
    git_which: Callable[[str], str | None] = shutil.which,
    run_command: Callable[..., Any] = subprocess.run,
) -> tuple[str, ...] | None:
    git_executable = git_which("git")
    if git_executable is None:
        return None

    try:
        completed = run_command(  # nosec B603 - fixed git command with controlled arguments
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


def iter_repo_file_candidates(
    root: Path,
    *,
    include_generated: bool,
    relative_path: Callable[[Path, Path], str],
    should_skip_dir_fn: Callable[[str], bool] = should_skip_dir,
    text_suffixes: set[str] = TEXT_SUFFIXES,
) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root, topdown=True):
        current_path = Path(current_root)
        rel_dir = relative_path(current_path, root)
        if rel_dir == ".":
            rel_dir = ""
        filtered_dirs: list[str] = []
        for dirname in dirs:
            if should_skip_dir_fn(dirname):
                if include_generated and dirname in {"artifacts", "build", "htmlcov"}:
                    filtered_dirs.append(dirname)
                    continue
                continue
            filtered_dirs.append(dirname)
        dirs[:] = filtered_dirs

        for filename in files:
            path = current_path / filename
            rel_path = relative_path(path, root)
            if not include_generated and rel_path.startswith("artifacts/"):
                continue
            if path.suffix.lower() not in text_suffixes and filename not in {"README", "LICENSE"}:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            yield path


def iter_tracked_repo_file_candidates(
    root: Path,
    *,
    include_generated: bool,
    list_tracked_repo_paths_fn: Callable[[Path], tuple[str, ...] | None],
    should_skip_dir_fn: Callable[[str], bool] = should_skip_dir,
    text_suffixes: set[str] = TEXT_SUFFIXES,
) -> Iterable[Path]:
    tracked_paths = list_tracked_repo_paths_fn(root)
    if tracked_paths is None:
        yield from iter_repo_file_candidates(
            root,
            include_generated=include_generated,
            relative_path=lambda path, base: path.relative_to(base).as_posix(),
            should_skip_dir_fn=should_skip_dir_fn,
            text_suffixes=text_suffixes,
        )
        return

    for rel_path in tracked_paths:
        if not include_generated and rel_path.startswith("artifacts/"):
            continue

        path = root / Path(rel_path)
        if not path.exists() or path.is_dir():
            continue
        if any(
            should_skip_dir_fn(part) and not (include_generated and part in {"artifacts", "build", "htmlcov"})
            for part in path.parts
        ):
            continue
        if path.suffix.lower() not in text_suffixes and path.name not in {"README", "LICENSE"}:
            continue
        if path.stat().st_size > 2_000_000:
            continue
        yield path


def iter_repo_text_files(
    root: Path,
    *,
    include_generated: bool,
    iter_repo_file_candidates_fn: Callable[[Path, bool], Iterable[Path]],
    read_text_fn: Callable[[Path], str],
) -> Iterable[Path]:
    for path in iter_repo_file_candidates_fn(root, include_generated):
        try:
            read_text_fn(path)
        except ValueError:
            continue
        yield path


def iter_tracked_repo_text_files(
    root: Path,
    *,
    include_generated: bool,
    iter_tracked_repo_file_candidates_fn: Callable[[Path, bool], Iterable[Path]],
    read_text_fn: Callable[[Path], str],
) -> Iterable[Path]:
    for path in iter_tracked_repo_file_candidates_fn(root, include_generated):
        try:
            read_text_fn(path)
        except ValueError:
            continue
        yield path


def iter_repo_text_entries(
    root: Path,
    *,
    include_generated: bool,
    tracked_only: bool,
    iter_repo_file_candidates_fn: Callable[[Path, bool], Iterable[Path]],
    iter_tracked_repo_file_candidates_fn: Callable[[Path, bool], Iterable[Path]],
    read_text_fn: Callable[[Path], str],
) -> Iterable[tuple[Path, str]]:
    candidates = (
        iter_tracked_repo_file_candidates_fn(root, include_generated)
        if tracked_only
        else iter_repo_file_candidates_fn(root, include_generated)
    )
    for path in candidates:
        try:
            text = read_text_fn(path)
        except ValueError:
            continue
        yield path, text


def redact_value(value: str) -> str:
    if len(value) <= 6:
        return "<redacted>"
    return f"{value[:2]}...{value[-2:]}"


def redact_email(value: str) -> str:
    local, _, domain = value.partition("@")
    if not local:
        return "<redacted-email>"
    return f"{local[:1]}***@{domain}"


def severity_for_path(rel_path: str, default: str) -> str:
    if rel_path.startswith(("README", "CONTRIBUTING", "src/", "scripts/", "vscode/")):
        return default
    if rel_path.startswith(("tests/", "Libs/")) and default == "high":
        return "medium"
    return default


def _should_skip_self_scan_path(rel_path: str) -> bool:
    return rel_path in SKIP_SELF_SCAN_PATHS or rel_path.startswith(SKIP_SELF_SCAN_PREFIXES)


def line_findings(
    path: Path,
    text: str,
    suspicious_identifiers: set[str],
    *,
    root: Path,
    relative_path: Callable[[Path, Path], str],
    finding_factory: Callable[..., Any],
) -> list[Any]:
    findings: list[Any] = []
    rel_path = relative_path(path, root)
    if (
        rel_path == "coverage.xml"
        or rel_path.startswith(SKIP_CONTENT_SCAN_PREFIXES)
        or _should_skip_self_scan_path(rel_path)
    ):
        return findings
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue

        for match in WINDOWS_PATH_RE.finditer(line):
            value = match.group(0)
            if "%USERPROFILE%" in value or WINDOWS_USER_PLACEHOLDER in value:
                continue
            if rel_path == "README.md" and (README_WINDOWS_TOOL_PATH in value or README_WINDOWS_PROGRAM_PATH in value):
                continue
            findings.append(
                finding_factory(
                    id="hardcoded-windows-path",
                    category="portability",
                    severity=severity_for_path(rel_path, "high"),
                    confidence="high",
                    message="Absolute Windows path committed to the repository.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched path {redact_value(value)}",
                    suggestion="Use a CLI argument, config value, or repo-relative path instead.",
                )
            )

        for match in UNIX_PATH_RE.finditer(line):
            value = match.group(0)
            findings.append(
                finding_factory(
                    id="hardcoded-unix-path",
                    category="portability",
                    severity=severity_for_path(rel_path, "high"),
                    confidence="high",
                    message="Absolute Unix-style path committed to the repository.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched path {redact_value(value)}",
                    suggestion="Replace workstation-specific paths with portable examples or runtime config.",
                )
            )

        for match in LOCAL_ENDPOINT_RE.finditer(line):
            value = match.group(0)
            findings.append(
                finding_factory(
                    id="local-endpoint",
                    category="portability",
                    severity=severity_for_path(rel_path, "medium"),
                    confidence="medium",
                    message="Localhost or local-domain assumption found.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched endpoint {redact_value(value)}",
                    suggestion="Make local endpoints configurable or mark them as placeholder examples.",
                )
            )

        for identifier in suspicious_identifiers:
            if not identifier:
                continue
            if re.search(rf"\b{re.escape(identifier)}\b", line, re.IGNORECASE):
                findings.append(
                    finding_factory(
                        id="suspicious-identifier",
                        category="secrets-pii",
                        severity=severity_for_path(rel_path, "medium"),
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
                finding_factory(
                    id="email-address",
                    category="secrets-pii",
                    severity=severity_for_path(rel_path, "low"),
                    confidence="medium",
                    message="Email address committed to the repository.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched email {redact_email(value)}",
                    suggestion="Use a role-based address if you do not want personal contact details published.",
                )
            )

        if PRIVATE_KEY_RE.search(line):
            findings.append(
                finding_factory(
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
                finding_factory(
                    id="secret-assignment",
                    category="secrets-pii",
                    severity=severity_for_path(rel_path, "high"),
                    confidence="medium",
                    message="Potential hardcoded secret-like value found.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched {redact_value(value)}",
                    suggestion="Move secret material to runtime configuration or secure secret storage.",
                    history_cleanup_recommended=True,
                )
            )
    return findings


def source_segment_summary(text: str, node: ast.AST, *, max_length: int = 160) -> str | None:
    segment = ast.get_source_segment(text, node)
    if not segment:
        return None
    normalized = " ".join(segment.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3] + "..."


def contains_host_signal(node: ast.AST, *, attribute_path: Callable[[ast.AST], tuple[str, ...] | None]) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and attribute_path(child) in HOST_SIGNAL_ATTR_PATHS:
            return True
        if isinstance(child, ast.Call) and attribute_path(child.func) in HOST_SIGNAL_CALL_PATHS:
            return True
    return False


def is_pythonpath_target(
    node: ast.AST,
    *,
    attribute_path: Callable[[ast.AST], tuple[str, ...] | None],
) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    if attribute_path(node.value) != ("os", "environ"):
        return False
    slice_node = node.slice
    return isinstance(slice_node, ast.Constant) and slice_node.value == "PYTHONPATH"


def find_marker_in_segment(segment: str) -> str | None:
    normalized = segment.replace("\\", "/").casefold()
    for marker in LOCAL_DEPENDENCY_MARKERS:
        if marker in normalized:
            return marker
    return None


def find_ignored_repo_path_references(
    context: Any,
    *,
    root: Path,
    tracked_paths: tuple[str, ...] | None,
    relative_path: Callable[[Path, Path], str],
    normalize_repo_relative_literal: Callable[[str], str | None],
    repo_relative_path_from_expr: Callable[[ast.AST], tuple[str, ...] | None],
    is_ignored_repo_path_reference: Callable[[str, tuple[str, ...] | None], bool],
    finding_factory: Callable[..., Any],
    skip_self_scan_paths: set[str],
    allowlist_paths: set[str],
    allowlist_prefixes: tuple[str, ...],
) -> list[Any]:
    findings: list[Any] = []
    seen: set[tuple[str, int, str]] = set()
    for path, tree in context.asts.items():
        rel_path = relative_path(path, root)
        if rel_path in skip_self_scan_paths or rel_path.startswith(SKIP_SELF_SCAN_PREFIXES):
            continue
        if rel_path in allowlist_paths:
            continue
        if any(rel_path.startswith(prefix) for prefix in allowlist_prefixes):
            continue

        for node in ast.walk(tree):
            candidates: list[str] = []
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                normalized = normalize_repo_relative_literal(node.value)
                if normalized is not None:
                    candidates.append(normalized)
            else:
                repo_relative = repo_relative_path_from_expr(node)
                if repo_relative:
                    candidates.append("/".join(repo_relative))

            for candidate in candidates:
                if not is_ignored_repo_path_reference(candidate, tracked_paths):
                    continue
                line_number = getattr(node, "lineno", None)
                if line_number is None:
                    continue
                key = (rel_path, line_number, candidate)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    finding_factory(
                        id="gitignored-repo-path-reference",
                        category="public-readiness",
                        severity=severity_for_path(rel_path, "high"),
                        confidence="high",
                        message="Tracked Python file depends on a repo-local path that is ignored by git.",
                        path=rel_path,
                        line=line_number,
                        detail=f"Matched ignored path {candidate}",
                        suggestion="Use a tracked fixture, explicit config input, or an allowlisted generated-output seam instead.",
                    )
                )
    return findings


def find_hidden_local_dependency_findings(
    context: Any,
    *,
    root: Path,
    relative_path: Callable[[Path, Path], str],
    attribute_path: Callable[[ast.AST], tuple[str, ...] | None],
    is_pythonpath_target_fn: Callable[[ast.AST], bool],
    find_marker_in_segment_fn: Callable[[str], str | None],
    finding_factory: Callable[..., Any],
    skip_self_scan_paths: set[str],
    path_injection_call_paths: set[tuple[str, ...]],
) -> list[Any]:
    findings: list[Any] = []
    seen: set[tuple[str, int, str]] = set()
    for path, tree in context.asts.items():
        rel_path = relative_path(path, root)
        if rel_path in skip_self_scan_paths or rel_path.startswith(SKIP_SELF_SCAN_PREFIXES):
            continue
        text = context.texts.get(path, "")
        for node in ast.walk(tree):
            marker: str | None = None
            if (
                (isinstance(node, ast.Call) and attribute_path(node.func) in path_injection_call_paths)
                or (isinstance(node, ast.Assign) and any(is_pythonpath_target_fn(target) for target in node.targets))
                or (isinstance(node, ast.AugAssign) and is_pythonpath_target_fn(node.target))
            ):
                marker = find_marker_in_segment_fn(ast.get_source_segment(text, node) or "")
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
                finding_factory(
                    id="hidden-local-dependency-root",
                    category="portability",
                    severity=severity_for_path(rel_path, "high"),
                    confidence="high",
                    message="Python path setup relies on a local environment directory that CI will not have.",
                    path=rel_path,
                    line=line_number,
                    detail=f"Matched local dependency marker {marker}",
                    suggestion="Declare the dependency in pyproject or use tracked in-repo fixtures instead of injecting local environment paths.",
                )
            )
    return findings


def find_host_specific_test_assumptions(
    context: Any,
    *,
    root: Path,
    relative_path: Callable[[Path, Path], str],
    contains_host_signal_fn: Callable[[ast.AST], bool],
    source_segment_summary_fn: Callable[[str, ast.AST], str | None],
    finding_factory: Callable[..., Any],
    skip_self_scan_paths: set[str],
) -> list[Any]:
    findings: list[Any] = []
    seen: set[tuple[str, int]] = set()
    for path, tree in context.asts.items():
        rel_path = relative_path(path, root)
        if rel_path in skip_self_scan_paths or rel_path.startswith(SKIP_SELF_SCAN_PREFIXES):
            continue
        text = context.texts.get(path, "")
        for node in ast.walk(tree):
            signal_node: ast.AST | None = None
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "skipif" and node.args:
                if contains_host_signal_fn(node.args[0]):
                    signal_node = node
            elif isinstance(node, (ast.If, ast.IfExp, ast.Assert)) and contains_host_signal_fn(node.test):
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
                finding_factory(
                    id="host-specific-test-assumption",
                    category="portability",
                    severity="medium",
                    confidence="high",
                    message="Test behavior depends on the local host OS or platform.",
                    path=rel_path,
                    line=line_number,
                    detail=source_segment_summary_fn(text, node),
                    suggestion="Prefer host-agnostic assertions, or isolate platform-specific behavior behind an explicit portability seam.",
                )
            )
    return findings


def build_python_source_scan_context(
    source_root: Path,
    *,
    root: Path,
    tracked_paths: tuple[str, ...] | None,
    relative_path: Callable[[Path, Path], str],
    read_text_fn: Callable[[Path], str],
    context_factory: Callable[..., Any],
) -> Any:
    texts: dict[Path, str] = {}
    asts: dict[Path, ast.AST] = {}
    if tracked_paths is None:
        paths = sorted(source_root.rglob("*.py"))
    else:
        source_prefix = relative_path(source_root, root).rstrip("/")
        paths = [
            root / rel_path
            for rel_path in tracked_paths
            if rel_path.endswith(".py") and (rel_path == source_prefix or rel_path.startswith(f"{source_prefix}/"))
        ]
    for path in paths:
        if not path.exists():
            continue
        text = read_text_fn(path)
        texts[path] = text
        try:
            asts[path] = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
    return context_factory(source_root=source_root, texts=texts, asts=asts)
