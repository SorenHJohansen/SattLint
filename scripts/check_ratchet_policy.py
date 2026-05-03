from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from defusedxml import ElementTree  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]
STRUCTURAL_RATCHET_PATH = "artifacts/analysis/structural_budget_ratchet.json"
COVERAGE_RATCHET_PATH = "artifacts/analysis/coverage_ratchet.json"
PYPROJECT_PATH = "pyproject.toml"
PROTECTED_PATHS = frozenset({STRUCTURAL_RATCHET_PATH, COVERAGE_RATCHET_PATH, PYPROJECT_PATH})
APPROVAL_RECORD_PREFIX = ".github/approvals/ratchet-rebaseline"
APPROVAL_RECORD_HINT = ".github/approvals/ratchet-rebaseline-<date>.md"
APPROVAL_BY_RE = re.compile(r"^Approved-by:\s+.+$", re.MULTILINE)
APPROVAL_REASON_RE = re.compile(r"^Reason:\s+.+$", re.MULTILINE)
NEW_PYTHON_FILE_LINE_LIMIT = 500
NEW_MARKDOWN_FILE_LINE_LIMIT = 500
NEW_SOURCE_FILE_COVERAGE_BASIS_POINTS = 10000
COVERAGE_FLOOR_BUFFER_BASIS_POINTS = 100


@dataclass(frozen=True, slots=True)
class ChangeContext:
    changed_files: tuple[str, ...]
    added_files: tuple[str, ...]
    base_ref: str | None
    source: str


@dataclass(frozen=True, slots=True)
class TypingRatchetState:
    strict_paths: tuple[str, ...]
    strict_roots: tuple[str, ...]
    debt_allowlist: tuple[str, ...]


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 - fixed git executable and controlled arguments
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _normalize_changed_files(raw: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in raw.splitlines() if line.strip())


def _normalize_added_files(raw: str) -> tuple[str, ...]:
    added: list[str] = []
    for line in raw.splitlines():
        parts = line.strip().split("\t", 1)
        if len(parts) != 2 or parts[0] != "A":
            continue
        path = parts[1].strip()
        if path:
            added.append(path)
    return tuple(added)


def _normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/").strip().strip("/")


def _detect_change_context(repo_root: Path, env: Mapping[str, str] | None = None) -> ChangeContext:
    effective_env = os.environ if env is None else env
    base_ref_name = effective_env.get("SATTLINT_RATCHET_BASE_REF")
    if not base_ref_name and effective_env.get("GITHUB_BASE_REF"):
        base_ref_name = f"origin/{effective_env['GITHUB_BASE_REF']}"
    if base_ref_name:
        diff = _git(repo_root, "diff", "--name-only", "--diff-filter=ACMR", f"{base_ref_name}...HEAD")
        added = _git(repo_root, "diff", "--name-status", "--diff-filter=A", f"{base_ref_name}...HEAD")
        if diff.returncode != 0:
            raise RuntimeError(diff.stderr.strip() or f"Failed to diff against {base_ref_name}.")
        if added.returncode != 0:
            raise RuntimeError(added.stderr.strip() or f"Failed to inspect added files against {base_ref_name}.")
        return ChangeContext(
            _normalize_changed_files(diff.stdout),
            _normalize_added_files(added.stdout),
            base_ref_name,
            "base-ref",
        )

    staged = _git(repo_root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    staged_added = _git(repo_root, "diff", "--cached", "--name-status", "--diff-filter=A")
    if staged.returncode != 0:
        raise RuntimeError(staged.stderr.strip() or "Failed to inspect staged files.")
    if staged_added.returncode != 0:
        raise RuntimeError(staged_added.stderr.strip() or "Failed to inspect staged added files.")
    staged_files = _normalize_changed_files(staged.stdout)
    if staged_files:
        return ChangeContext(staged_files, _normalize_added_files(staged_added.stdout), "HEAD", "staged")

    worktree = _git(repo_root, "diff", "--name-only", "--diff-filter=ACMR", "HEAD")
    worktree_added = _git(repo_root, "diff", "--name-status", "--diff-filter=A", "HEAD")
    if worktree.returncode == 0 and worktree_added.returncode == 0:
        worktree_files = _normalize_changed_files(worktree.stdout)
        if worktree_files:
            return ChangeContext(worktree_files, _normalize_added_files(worktree_added.stdout), "HEAD", "worktree")

    parent = _git(repo_root, "rev-parse", "--verify", "HEAD^")
    if parent.returncode == 0:
        diff = _git(repo_root, "diff", "--name-only", "--diff-filter=ACMR", "HEAD^..HEAD")
        added = _git(repo_root, "diff", "--name-status", "--diff-filter=A", "HEAD^..HEAD")
        if diff.returncode != 0:
            raise RuntimeError(diff.stderr.strip() or "Failed to diff HEAD^..HEAD.")
        if added.returncode != 0:
            raise RuntimeError(added.stderr.strip() or "Failed to inspect added files in HEAD^..HEAD.")
        return ChangeContext(
            _normalize_changed_files(diff.stdout),
            _normalize_added_files(added.stdout),
            "HEAD^",
            "head-parent",
        )

    return ChangeContext((), (), None, "none")


def _is_approval_record_path(path: str) -> bool:
    return path.startswith(APPROVAL_RECORD_PREFIX) and path.endswith(".md")


def _load_current_texts(repo_root: Path, rel_paths: Sequence[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for rel_path in rel_paths:
        path = repo_root / rel_path
        if not path.exists():
            continue
        texts[rel_path] = path.read_text(encoding="utf-8")
    return texts


def _load_base_texts(repo_root: Path, base_ref: str | None, rel_paths: Sequence[str]) -> dict[str, str | None]:
    texts: dict[str, str | None] = dict.fromkeys(rel_paths)
    if base_ref is None:
        return texts
    for rel_path in rel_paths:
        completed = _git(repo_root, "show", f"{base_ref}:{rel_path}")
        if completed.returncode == 0:
            texts[rel_path] = completed.stdout
    return texts


def _parse_json_payload(text: str, label: str) -> dict[str, Any]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return payload


def _normalized_string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list.")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} entries must be non-empty strings.")
        rel_path = _normalize_rel_path(item)
        if rel_path in seen:
            raise ValueError(f"{label} contains duplicate path {rel_path!r}.")
        seen.add(rel_path)
        normalized.append(rel_path)
    return tuple(normalized)


def _pyproject_payload(text: str, label: str) -> dict[str, Any]:
    payload = tomllib.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must parse to a TOML object.")
    return payload


def _typing_ratchet_state(
    text: str,
    label: str,
    *,
    allow_missing: bool = False,
) -> TypingRatchetState | None:
    payload = _pyproject_payload(text, label)
    tool_section = payload.get("tool")
    if not isinstance(tool_section, dict):
        if allow_missing:
            return None
        raise ValueError(f"{label} is missing a [tool] table.")

    pyright_section = tool_section.get("pyright")
    sattlint_section = tool_section.get("sattlint")
    if not isinstance(pyright_section, dict) or not isinstance(sattlint_section, dict):
        if allow_missing:
            return None
        raise ValueError(f"{label} is missing typing ratchet configuration.")

    typing_ratchet_section = sattlint_section.get("typing_ratchet")
    if not isinstance(typing_ratchet_section, dict):
        if allow_missing:
            return None
        raise ValueError(f"{label} is missing [tool.sattlint.typing_ratchet].")

    strict_paths = _normalized_string_list(pyright_section.get("strict", []), f"{label} [tool.pyright].strict")
    strict_roots = _normalized_string_list(
        typing_ratchet_section.get("strict_roots", []),
        f"{label} [tool.sattlint.typing_ratchet].strict_roots",
    )
    debt_allowlist = _normalized_string_list(
        typing_ratchet_section.get("debt_allowlist", []),
        f"{label} [tool.sattlint.typing_ratchet].debt_allowlist",
    )
    if not strict_roots:
        raise ValueError(f"{label} typing ratchet strict_roots must not be empty.")

    return TypingRatchetState(
        strict_paths=strict_paths,
        strict_roots=strict_roots,
        debt_allowlist=debt_allowlist,
    )


def _path_is_within_roots(rel_path: str, roots: Sequence[str]) -> bool:
    return any(rel_path == root or rel_path.startswith(f"{root}/") for root in roots)


def _typing_scope_expansion_roots(
    base_roots: Sequence[str],
    head_roots: Sequence[str],
) -> tuple[str, ...]:
    return tuple(rel_root for rel_root in head_roots if not _path_is_within_roots(rel_root, base_roots))


def _typing_scope_python_files(repo_root: Path, roots: Sequence[str]) -> tuple[str, ...]:
    files: list[str] = []
    for root_text in roots:
        root_path = repo_root / root_text
        if not root_path.exists():
            raise ValueError(f"{PYPROJECT_PATH} typing strict root {root_text!r} does not exist.")
        if root_path.is_file():
            if root_path.suffix.casefold() != ".py":
                raise ValueError(f"{PYPROJECT_PATH} typing strict root {root_text!r} must point to Python code.")
            files.append(root_text)
            continue
        files.extend(path.relative_to(repo_root).as_posix() for path in sorted(root_path.rglob("*.py")))
    return tuple(dict.fromkeys(files))


def _typing_ratchet_state_errors(
    *,
    repo_root: Path,
    added_files: Sequence[str],
    changed_files: Sequence[str] = (),
    base_state: TypingRatchetState | None = None,
    state: TypingRatchetState,
) -> list[str]:
    errors: list[str] = []
    strict_paths = set(state.strict_paths)
    debt_allowlist = set(state.debt_allowlist)
    scope_files = set(_typing_scope_python_files(repo_root, state.strict_roots))

    overlap = sorted(strict_paths & debt_allowlist)
    if overlap:
        errors.append("Pyright strict paths overlap the typing debt allowlist: " + ", ".join(overlap) + ".")

    strict_outside_scope = sorted(strict_paths - scope_files)
    if strict_outside_scope:
        errors.append(
            "Pyright strict paths fall outside the typing ratchet scope or reference missing files: "
            + ", ".join(strict_outside_scope)
            + "."
        )

    debt_outside_scope = sorted(debt_allowlist - scope_files)
    if debt_outside_scope:
        errors.append(
            "Typing debt allowlist paths fall outside the typing ratchet scope or reference missing files: "
            + ", ".join(debt_outside_scope)
            + "."
        )

    uncovered_scope_files = sorted(scope_files - strict_paths - debt_allowlist)
    if uncovered_scope_files:
        errors.append("Typing ratchet scope has uncovered Python files: " + ", ".join(uncovered_scope_files) + ".")

    added_scope_files = sorted(
        rel_path
        for rel_path in added_files
        if rel_path.endswith(".py") and _path_is_within_roots(rel_path, state.strict_roots)
    )
    added_scope_file_set = set(added_scope_files)
    for rel_path in added_scope_files:
        if rel_path in debt_allowlist:
            errors.append(
                "Typing debt allowlist grew with a new scoped file: "
                f"{rel_path}. New files under the strict scope must land in tool.pyright.strict."
            )
        elif rel_path not in strict_paths:
            errors.append(f"New file under the typing strict scope is not covered by tool.pyright.strict: {rel_path}.")

    touched_scope_debt = sorted(
        rel_path
        for rel_path in changed_files
        if rel_path.endswith(".py")
        and rel_path not in added_scope_file_set
        and rel_path in debt_allowlist
        and _path_is_within_roots(rel_path, state.strict_roots)
    )
    for rel_path in touched_scope_debt:
        if (
            base_state is not None
            and rel_path in base_state.debt_allowlist
            and _typing_scope_expansion_roots(base_state.strict_roots, state.strict_roots)
        ):
            continue
        errors.append(
            "Touched file under the typing strict scope remains in typing debt allowlist: "
            f"{rel_path}. Touched files under the strict scope must move to tool.pyright.strict."
        )

    return errors


def _typing_ratchet_backslide_errors(
    base_state: TypingRatchetState | None,
    head_state: TypingRatchetState,
) -> list[str]:
    if base_state is None:
        return []

    errors: list[str] = []
    base_roots = set(base_state.strict_roots)
    head_roots = set(head_state.strict_roots)
    base_strict = set(base_state.strict_paths)
    head_strict = set(head_state.strict_paths)
    base_debt = set(base_state.debt_allowlist)
    head_debt = set(head_state.debt_allowlist)
    expanded_roots = _typing_scope_expansion_roots(base_state.strict_roots, head_state.strict_roots)

    for rel_root in sorted(
        rel_root for rel_root in base_roots - head_roots if not _path_is_within_roots(rel_root, head_state.strict_roots)
    ):
        errors.append(f"Typing strict scope shrank: removed strict root {rel_root}.")

    for rel_path in sorted(base_strict - head_strict):
        if rel_path in head_debt:
            errors.append(
                f"Pyright strict coverage moved into typing debt: {rel_path}. Fix types first; do not rebaseline."
            )
        else:
            errors.append(f"Pyright strict coverage removed: {rel_path}. Fix types first; do not rebaseline.")

    for rel_path in sorted(head_debt - base_debt):
        if _path_is_within_roots(rel_path, expanded_roots) and not _path_is_within_roots(
            rel_path, base_state.strict_roots
        ):
            continue
        errors.append(f"Typing debt allowlist grew: {rel_path}. Fix types first; do not add new exceptions.")

    return errors


def _metric_mapping(payload: dict[str, Any], label: str) -> dict[str, int]:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"{label} is missing a metrics object.")
    normalized: dict[str, int] = {}
    for key, value in metrics.items():
        if not isinstance(value, int):
            raise ValueError(f"{label} metric {key!r} must be an integer.")
        normalized[str(key)] = value
    return normalized


def _structural_file_line_exception_mapping(payload: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    raw = payload.get("file_line_exceptions")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label} file_line_exceptions must be a JSON object keyed by repo-relative path.")

    normalized: dict[str, dict[str, Any]] = {}
    for raw_path, value in raw.items():
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"{label} file_line_exceptions keys must be non-empty strings.")
        if not isinstance(value, dict):
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}] must be a JSON object.")

        max_lines = value.get("max_lines")
        reason = value.get("reason")
        if not isinstance(max_lines, int) or max_lines <= 0:
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}].max_lines must be a positive integer.")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}].reason must be a non-empty string.")

        normalized[raw_path.replace("\\", "/").strip("/")] = {
            "max_lines": int(max_lines),
            "reason": reason.strip(),
        }

    return dict(sorted(normalized.items()))


def _coverage_basis_points(payload: dict[str, Any], label: str) -> int:
    metrics = _metric_mapping(payload, label)
    value = metrics.get("min_line_rate_basis_points")
    if value is None:
        raise ValueError(f"{label} is missing metrics.min_line_rate_basis_points.")
    return value


def _coverage_summary_basis_points(payload: dict[str, Any], label: str) -> int:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError(f"{label} is missing a summary object.")

    raw_total_line_rate = summary.get("total_line_rate")
    try:
        total_line_rate = Decimal(str(raw_total_line_rate))
    except InvalidOperation as exc:
        raise ValueError(f"{label} summary.total_line_rate must be a decimal between 0 and 1.") from exc

    if total_line_rate < 0 or total_line_rate > 1:
        raise ValueError(f"{label} summary.total_line_rate must be between 0 and 1.")

    return int((total_line_rate * Decimal("10000")).quantize(Decimal("1")))


def _expected_coverage_floor_basis_points(payload: dict[str, Any], label: str) -> int:
    baseline_basis_points = _coverage_summary_basis_points(payload, label)
    return max(baseline_basis_points - COVERAGE_FLOOR_BUFFER_BASIS_POINTS, 0)


def _coverage_floor_decimal_from_basis_points(value: int) -> Decimal:
    return Decimal(value) / Decimal("100")


def _cov_fail_under(text: str, label: str) -> Decimal:
    payload = tomllib.loads(text)
    addopts = payload.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("addopts", [])
    if not isinstance(addopts, list):
        raise ValueError(f"{label} addopts must be a list.")
    for entry in addopts:
        if not isinstance(entry, str):
            continue
        if not entry.startswith("--cov-fail-under="):
            continue
        raw_value = entry.split("=", 1)[1].strip()
        try:
            return Decimal(raw_value)
        except InvalidOperation as exc:
            raise ValueError(f"{label} has an invalid --cov-fail-under value: {raw_value!r}.") from exc
    raise ValueError(f"{label} is missing --cov-fail-under in [tool.pytest.ini_options].addopts.")


def _approval_record_errors(rel_path: str, text: str) -> list[str]:
    errors: list[str] = []
    if not APPROVAL_BY_RE.search(text):
        errors.append(f"Approval record {rel_path} is missing an 'Approved-by:' line.")
    if not APPROVAL_REASON_RE.search(text):
        errors.append(f"Approval record {rel_path} is missing a 'Reason:' line.")
    return errors


def _normalize_coverage_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/").lstrip("./")
    if not normalized:
        return ""
    if normalized.startswith(("src/", "tests/")):
        return normalized
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        return normalized
    return f"src/{normalized}"


def _new_python_file_paths(added_files: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        path for path in added_files if path.endswith(".py") and path.startswith(("src/", "tests/", "scripts/"))
    )


def _new_markdown_file_paths(added_files: Sequence[str]) -> tuple[str, ...]:
    return tuple(path for path in added_files if path.endswith(".md"))


def _new_file_size_errors(repo_root: Path, added_files: Sequence[str]) -> list[str]:
    errors: list[str] = []
    for rel_path in _new_python_file_paths(added_files):
        path = repo_root / rel_path
        if not path.exists():
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > NEW_PYTHON_FILE_LINE_LIMIT:
            errors.append(
                f"New Python file {rel_path} is {line_count} lines; new files must stay at or under {NEW_PYTHON_FILE_LINE_LIMIT} lines."
            )
    for rel_path in _new_markdown_file_paths(added_files):
        path = repo_root / rel_path
        if not path.exists():
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > NEW_MARKDOWN_FILE_LINE_LIMIT:
            errors.append(
                f"New Markdown file {rel_path} is {line_count} lines; new files must stay at or under {NEW_MARKDOWN_FILE_LINE_LIMIT} lines."
            )
    return errors


def _new_file_coverage_errors(repo_root: Path, added_files: Sequence[str]) -> list[str]:
    coverage_path = repo_root / "coverage.xml"
    if not coverage_path.exists():
        return []

    added_source_files = tuple(path for path in added_files if path.endswith(".py") and path.startswith("src/"))
    if not added_source_files:
        return []

    root_xml = ElementTree.fromstring(coverage_path.read_text(encoding="utf-8"))
    coverage_by_path: dict[str, int] = {}
    for class_node in root_xml.findall(".//class"):
        normalized_path = _normalize_coverage_filename(class_node.attrib.get("filename", ""))
        if not normalized_path.startswith("src/"):
            continue
        line_rate = float(class_node.attrib.get("line-rate", "0") or 0)
        coverage_by_path[normalized_path] = round(line_rate * 10000)

    errors: list[str] = []
    for rel_path in added_source_files:
        basis_points = coverage_by_path.get(rel_path)
        if basis_points is None:
            errors.append(
                f"New source file {rel_path} is missing from coverage.xml; new source files must start at 100% coverage."
            )
            continue
        if basis_points < NEW_SOURCE_FILE_COVERAGE_BASIS_POINTS:
            errors.append(
                f"New source file {rel_path} is covered at {basis_points / 100:.2f}%; new source files must start at 100.00% coverage."
            )
    return errors


def evaluate_policy_change(
    *,
    repo_root: Path = REPO_ROOT,
    changed_files: Sequence[str],
    current_text_by_path: Mapping[str, str],
    base_text_by_path: Mapping[str, str | None],
) -> list[str]:
    changed = tuple(dict.fromkeys(path for path in changed_files if path))
    protected = tuple(path for path in changed if path in PROTECTED_PATHS)
    if not protected:
        return []

    errors: list[str] = []
    approval_paths = tuple(path for path in changed if _is_approval_record_path(path))
    if not approval_paths:
        protected_list = ", ".join(protected)
        errors.append(
            "Ratchet edits require explicit approval. "
            f"Add {APPROVAL_RECORD_HINT} with 'Approved-by:' and 'Reason:' before changing: {protected_list}."
        )
    else:
        for approval_path in approval_paths:
            text = current_text_by_path.get(approval_path, "")
            errors.extend(_approval_record_errors(approval_path, text))

    if STRUCTURAL_RATCHET_PATH in protected:
        base_text = base_text_by_path.get(STRUCTURAL_RATCHET_PATH)
        head_text = current_text_by_path.get(STRUCTURAL_RATCHET_PATH)
        if base_text is not None and head_text is not None:
            base_payload = _parse_json_payload(base_text, STRUCTURAL_RATCHET_PATH)
            head_payload = _parse_json_payload(head_text, STRUCTURAL_RATCHET_PATH)
            base_metrics = _metric_mapping(base_payload, STRUCTURAL_RATCHET_PATH)
            head_metrics = _metric_mapping(head_payload, STRUCTURAL_RATCHET_PATH)
            base_exceptions = _structural_file_line_exception_mapping(base_payload, STRUCTURAL_RATCHET_PATH)
            head_exceptions = _structural_file_line_exception_mapping(head_payload, STRUCTURAL_RATCHET_PATH)
            markdown_scope_migration = (
                "markdown_file_max_lines" not in base_metrics and "markdown_file_max_lines" in head_metrics
            )
            for metric_name, base_value in sorted(base_metrics.items()):
                head_value = head_metrics.get(metric_name)
                if head_value is None:
                    errors.append(
                        f"Structural ratchet changed without metric {metric_name!r}; keep the ratchet schema stable."
                    )
                    continue
                if head_value > base_value:
                    errors.append(
                        f"Structural ratchet loosened: {metric_name} {base_value} -> {head_value}. Fix code first; do not rebaseline."
                    )

            if "file_line_exceptions" in base_payload:
                for rel_path, base_entry in sorted(base_exceptions.items()):
                    head_entry = head_exceptions.get(rel_path)
                    if head_entry is None:
                        continue
                    if head_entry["max_lines"] > base_entry["max_lines"]:
                        errors.append(
                            "Structural file-line exception loosened: "
                            f"{rel_path} {base_entry['max_lines']} -> {head_entry['max_lines']}. "
                            "Fix code first; do not widen the exception."
                        )

                for rel_path in sorted(set(head_exceptions) - set(base_exceptions)):
                    if markdown_scope_migration and rel_path.endswith(".md"):
                        continue
                    errors.append(
                        "Structural file-line exception added: "
                        f"{rel_path} @ {head_exceptions[rel_path]['max_lines']} lines. "
                        "Fix code first; do not add new exceptions."
                    )

    if COVERAGE_RATCHET_PATH in protected:
        base_text = base_text_by_path.get(COVERAGE_RATCHET_PATH)
        head_text = current_text_by_path.get(COVERAGE_RATCHET_PATH)
        if head_text is not None:
            head_payload = _parse_json_payload(head_text, COVERAGE_RATCHET_PATH)
            head_value = _coverage_basis_points(head_payload, COVERAGE_RATCHET_PATH)
            expected_head_value = _expected_coverage_floor_basis_points(head_payload, COVERAGE_RATCHET_PATH)
            if head_value != expected_head_value:
                errors.append(
                    "Coverage ratchet floor must equal the recorded baseline minus 1.00 percentage point: "
                    f"expected min_line_rate_basis_points {expected_head_value}, found {head_value}."
                )
        if base_text is not None and head_text is not None:
            base_payload = _parse_json_payload(base_text, COVERAGE_RATCHET_PATH)
            head_payload = _parse_json_payload(head_text, COVERAGE_RATCHET_PATH)
            base_baseline = _coverage_summary_basis_points(base_payload, COVERAGE_RATCHET_PATH)
            head_baseline = _coverage_summary_basis_points(head_payload, COVERAGE_RATCHET_PATH)
            if head_baseline < base_baseline:
                errors.append(
                    "Coverage baseline decreased: "
                    f"total_line_rate {base_baseline / 100:.2f}% -> {head_baseline / 100:.2f}%. "
                    "Fix code or tests first; do not rebaseline."
                )

    if PYPROJECT_PATH in protected:
        base_text = base_text_by_path.get(PYPROJECT_PATH)
        head_text = current_text_by_path.get(PYPROJECT_PATH)
        if head_text is not None:
            head_value = _cov_fail_under(head_text, PYPROJECT_PATH)
            coverage_text = current_text_by_path.get(COVERAGE_RATCHET_PATH)
            if coverage_text is not None:
                coverage_payload = _parse_json_payload(coverage_text, COVERAGE_RATCHET_PATH)
                expected_floor = _coverage_floor_decimal_from_basis_points(
                    _expected_coverage_floor_basis_points(coverage_payload, COVERAGE_RATCHET_PATH)
                )
                if head_value != expected_floor:
                    errors.append(
                        "Pytest coverage floor must equal the recorded coverage baseline minus 1.00 percentage point: "
                        f"expected --cov-fail-under={expected_floor:.2f}, found {head_value}."
                    )

            head_state = _typing_ratchet_state(head_text, PYPROJECT_PATH)
            if head_state is None:
                raise ValueError(f"{PYPROJECT_PATH} is missing typing ratchet configuration.")
            base_state = _typing_ratchet_state(base_text, PYPROJECT_PATH, allow_missing=True) if base_text else None
            errors.extend(_typing_ratchet_state_errors(repo_root=repo_root, added_files=(), state=head_state))
            errors.extend(_typing_ratchet_backslide_errors(base_state, head_state))

    if COVERAGE_RATCHET_PATH in protected and PYPROJECT_PATH not in protected:
        coverage_text = current_text_by_path.get(COVERAGE_RATCHET_PATH)
        pyproject_text = current_text_by_path.get(PYPROJECT_PATH)
        if coverage_text is not None and pyproject_text is not None:
            coverage_payload = _parse_json_payload(coverage_text, COVERAGE_RATCHET_PATH)
            expected_floor = _coverage_floor_decimal_from_basis_points(
                _expected_coverage_floor_basis_points(coverage_payload, COVERAGE_RATCHET_PATH)
            )
            pyproject_floor = _cov_fail_under(pyproject_text, PYPROJECT_PATH)
            if pyproject_floor != expected_floor:
                errors.append(
                    "Pytest coverage floor must stay aligned with the checked-in coverage ratchet: "
                    f"expected --cov-fail-under={expected_floor:.2f}, found {pyproject_floor}."
                )

    return errors


def run_policy_check(repo_root: Path = REPO_ROOT, env: Mapping[str, str] | None = None) -> list[str]:
    context = _detect_change_context(repo_root, env)
    errors = _new_file_size_errors(repo_root, context.added_files)
    errors.extend(_new_file_coverage_errors(repo_root, context.added_files))

    relevant_paths = tuple(
        path for path in context.changed_files if path in PROTECTED_PATHS or _is_approval_record_path(path)
    )
    current_paths = tuple(dict.fromkeys((*relevant_paths, PYPROJECT_PATH, COVERAGE_RATCHET_PATH)))
    current_text_by_path = _load_current_texts(repo_root, current_paths)
    pyproject_text = current_text_by_path.get(PYPROJECT_PATH)
    if pyproject_text is None:
        raise ValueError(f"{PYPROJECT_PATH} is missing.")
    current_typing_state = _typing_ratchet_state(pyproject_text, PYPROJECT_PATH)
    if current_typing_state is None:
        raise ValueError(f"{PYPROJECT_PATH} is missing typing ratchet configuration.")
    base_pyproject_text = None
    if context.base_ref is not None:
        base_pyproject_text = _load_base_texts(repo_root, context.base_ref, (PYPROJECT_PATH,)).get(PYPROJECT_PATH)
    base_typing_state = (
        _typing_ratchet_state(base_pyproject_text, PYPROJECT_PATH, allow_missing=True) if base_pyproject_text else None
    )
    errors.extend(
        _typing_ratchet_state_errors(
            repo_root=repo_root,
            added_files=context.added_files,
            changed_files=context.changed_files,
            base_state=base_typing_state,
            state=current_typing_state,
        )
    )

    if not relevant_paths:
        return errors
    base_text_by_path = _load_base_texts(repo_root, context.base_ref, relevant_paths)
    errors.extend(
        evaluate_policy_change(
            repo_root=repo_root,
            changed_files=context.changed_files,
            current_text_by_path=current_text_by_path,
            base_text_by_path=base_text_by_path,
        )
    )
    return errors


def main() -> int:
    try:
        errors = run_policy_check()
    except (OSError, RuntimeError, ValueError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        print(f"ratchet-policy: {exc}", file=sys.stderr)
        return 1

    if not errors:
        print("ratchet-policy: OK")
        return 0

    print("ratchet-policy: blocked", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
