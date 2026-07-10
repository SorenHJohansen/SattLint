from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from defusedxml import ElementTree  # type: ignore[import-untyped]

try:
    from scripts import _ratchet_policy_context as ratchet_context
    from scripts import _ratchet_policy_debt as ratchet_debt
except ModuleNotFoundError:  # pragma: no cover - direct script execution resolves from scripts/
    import _ratchet_policy_context as ratchet_context
    import _ratchet_policy_debt as ratchet_debt


def new_python_file_paths(added_files: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        path for path in added_files if path.endswith(".py") and path.startswith(("src/", "tests/", "scripts/"))
    )


def new_markdown_file_paths(added_files: Sequence[str]) -> tuple[str, ...]:
    return tuple(path for path in added_files if path.endswith(".md"))


def touched_python_file_paths(changed_files: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        path for path in changed_files if path.endswith(".py") and path.startswith(("src/", "tests/", "scripts/"))
    )


def touched_markdown_file_paths(changed_files: Sequence[str]) -> tuple[str, ...]:
    return tuple(path for path in changed_files if path.endswith(".md"))


def touched_file_size_errors(
    repo_root: Path,
    changed_files: Sequence[str],
    *,
    file_debt_state: Mapping[str, dict[str, dict[str, object]]],
    structural_exceptions: Mapping[str, dict[str, object]],
) -> list[str]:
    errors: list[str] = []

    for rel_path in touched_python_file_paths(changed_files):
        path = repo_root / rel_path
        if not path.exists():
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count <= ratchet_context.NEW_PYTHON_FILE_LINE_LIMIT:
            continue
        if "structural" in file_debt_state.get(rel_path, {}):
            continue
        if rel_path in structural_exceptions:
            errors.append(
                "Touched structural exception file missing per-file debt entry does not meet the "
                f"{ratchet_context.NEW_PYTHON_FILE_LINE_LIMIT}-line target: {rel_path} is {line_count} lines."
            )
            continue
        errors.append(
            f"Touched Python file {rel_path} is {line_count} lines; AI-touched Python files must stay at or under {ratchet_context.NEW_PYTHON_FILE_LINE_LIMIT} lines."
        )

    for rel_path in touched_markdown_file_paths(changed_files):
        path = repo_root / rel_path
        if not path.exists():
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count <= ratchet_context.NEW_MARKDOWN_FILE_LINE_LIMIT:
            continue
        if "structural" in file_debt_state.get(rel_path, {}):
            continue
        if rel_path in structural_exceptions:
            errors.append(
                "Touched structural exception file missing per-file debt entry does not meet the "
                f"{ratchet_context.NEW_MARKDOWN_FILE_LINE_LIMIT}-line target: {rel_path} is {line_count} lines."
            )
            continue
        errors.append(
            f"Touched Markdown file {rel_path} is {line_count} lines; AI-touched Markdown files must stay at or under {ratchet_context.NEW_MARKDOWN_FILE_LINE_LIMIT} lines."
        )

    return errors


def new_file_size_errors(repo_root: Path, added_files: Sequence[str]) -> list[str]:
    errors: list[str] = []
    for rel_path in new_python_file_paths(added_files):
        path = repo_root / rel_path
        if not path.exists():
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > ratchet_context.NEW_PYTHON_FILE_LINE_LIMIT:
            errors.append(
                f"New Python file {rel_path} is {line_count} lines; new files must stay at or under {ratchet_context.NEW_PYTHON_FILE_LINE_LIMIT} lines."
            )
    for rel_path in new_markdown_file_paths(added_files):
        path = repo_root / rel_path
        if not path.exists():
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > ratchet_context.NEW_MARKDOWN_FILE_LINE_LIMIT:
            errors.append(
                f"New Markdown file {rel_path} is {line_count} lines; new files must stay at or under {ratchet_context.NEW_MARKDOWN_FILE_LINE_LIMIT} lines."
            )
    return errors


def new_file_coverage_errors(repo_root: Path, added_files: Sequence[str]) -> list[str]:
    coverage_path = repo_root / "coverage.xml"
    if not coverage_path.exists():
        return []

    added_source_files = tuple(path for path in added_files if path.endswith(".py") and path.startswith("src/"))
    if not added_source_files:
        return []

    root_xml = ElementTree.fromstring(coverage_path.read_text(encoding="utf-8"))
    coverage_by_path: dict[str, int] = {}
    for class_node in root_xml.findall(".//class"):
        normalized_path = ratchet_debt.normalize_coverage_filename(class_node.attrib.get("filename", ""))
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
        if basis_points < ratchet_context.NEW_SOURCE_FILE_COVERAGE_BASIS_POINTS:
            errors.append(
                f"New source file {rel_path} is covered at {basis_points / 100:.2f}%; new source files must start at 100.00% coverage."
            )
    return errors
