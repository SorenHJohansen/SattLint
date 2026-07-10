from __future__ import annotations

import json
import os
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

try:
    from scripts import _ratchet_policy_context as ratchet_context
    from scripts import _ratchet_policy_debt as ratchet_debt
    from scripts import _ratchet_policy_protected as ratchet_protected
    from scripts import _ratchet_policy_touch as ratchet_touch
    from scripts import _ratchet_policy_typing as ratchet_typing
    from scripts._repo_paths import repo_root_from
except ModuleNotFoundError:  # pragma: no cover - direct script execution resolves from scripts/
    import _ratchet_policy_context as ratchet_context
    import _ratchet_policy_debt as ratchet_debt
    import _ratchet_policy_protected as ratchet_protected
    import _ratchet_policy_touch as ratchet_touch
    import _ratchet_policy_typing as ratchet_typing
    from _repo_paths import repo_root_from

REPO_ROOT = repo_root_from(Path(__file__))
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

STRUCTURAL_RATCHET_PATH = ratchet_context.STRUCTURAL_RATCHET_PATH
COVERAGE_RATCHET_PATH = ratchet_context.COVERAGE_RATCHET_PATH
FILE_DEBT_RATCHET_PATH = ratchet_context.FILE_DEBT_RATCHET_PATH
PYPROJECT_PATH = ratchet_context.PYPROJECT_PATH
PROTECTED_PATHS = ratchet_context.PROTECTED_PATHS
APPROVAL_RECORD_PREFIX = ratchet_context.APPROVAL_RECORD_PREFIX
APPROVAL_RECORD_HINT = ratchet_context.APPROVAL_RECORD_HINT
APPROVAL_BY_RE = ratchet_context.APPROVAL_BY_RE
APPROVAL_REASON_RE = ratchet_context.APPROVAL_REASON_RE
NEW_PYTHON_FILE_LINE_LIMIT = ratchet_context.NEW_PYTHON_FILE_LINE_LIMIT
NEW_MARKDOWN_FILE_LINE_LIMIT = ratchet_context.NEW_MARKDOWN_FILE_LINE_LIMIT
NEW_SOURCE_FILE_COVERAGE_BASIS_POINTS = ratchet_context.NEW_SOURCE_FILE_COVERAGE_BASIS_POINTS
COVERAGE_FLOOR_BUFFER_BASIS_POINTS = ratchet_context.COVERAGE_FLOOR_BUFFER_BASIS_POINTS
FILE_DEBT_RATCHET_SCHEMA_KIND = ratchet_context.FILE_DEBT_RATCHET_SCHEMA_KIND
FILE_DEBT_RATCHET_SCHEMA_VERSION = ratchet_context.FILE_DEBT_RATCHET_SCHEMA_VERSION
FILE_DEBT_ALLOWED_PREFIXES = ratchet_context.FILE_DEBT_ALLOWED_PREFIXES
LEGACY_MARKDOWN_STRUCTURAL_METRICS = ratchet_context.LEGACY_MARKDOWN_STRUCTURAL_METRICS
FILE_DEBT_TOUCH_RULES = ratchet_context.FILE_DEBT_TOUCH_RULES
FILE_DEBT_TOUCH_RULE_RANKS = ratchet_context.FILE_DEBT_TOUCH_RULE_RANKS
FIRST_STRUCTURAL_DEBT_PROOF_COMMAND = ratchet_context.FIRST_STRUCTURAL_DEBT_PROOF_COMMAND

ChangeContext = ratchet_context.ChangeContext
TypingRatchetState = ratchet_context.TypingRatchetState

_git = ratchet_context.git
_normalize_changed_files = ratchet_context.normalize_changed_files
_normalize_added_files = ratchet_context.normalize_added_files
_normalize_rel_path = ratchet_context.normalize_rel_path
_merge_unique_paths = ratchet_context.merge_unique_paths
_is_approval_record_path = ratchet_context.is_approval_record_path
_load_current_texts = ratchet_context.load_current_texts
_parse_json_payload = ratchet_context.parse_json_payload
_normalized_string_list = ratchet_context.normalized_string_list
_pyproject_payload = ratchet_context.pyproject_payload

_path_is_within_roots = ratchet_typing.path_is_within_roots
_typing_scope_expansion_roots = ratchet_typing.typing_scope_expansion_roots
_typing_scope_python_files = ratchet_typing.typing_scope_python_files
_typing_ratchet_state = ratchet_typing.typing_ratchet_state
_typing_ratchet_state_errors = ratchet_typing.typing_ratchet_state_errors
_typing_ratchet_backslide_errors = ratchet_typing.typing_ratchet_backslide_errors

_metric_mapping = ratchet_debt.metric_mapping
_structural_file_line_exception_mapping = ratchet_debt.structural_file_line_exception_mapping
_file_debt_touch_rule = ratchet_debt.file_debt_touch_rule
_effective_structural_touch_rule = ratchet_debt.effective_structural_touch_rule
_structural_debt_guidance = ratchet_debt.structural_debt_guidance
_normalized_file_debt_dimension = ratchet_debt.normalized_file_debt_dimension
_file_debt_ratchet_state = ratchet_debt.file_debt_ratchet_state
_file_debt_ratchet_backslide_errors = ratchet_debt.file_debt_ratchet_backslide_errors
_file_debt_surface_errors = ratchet_debt.file_debt_surface_errors
_file_debt_ratchet_addition_errors = ratchet_debt.file_debt_ratchet_addition_errors
_coverage_basis_points = ratchet_debt.coverage_basis_points
_coverage_summary_basis_points = ratchet_debt.coverage_summary_basis_points
_expected_coverage_floor_basis_points = ratchet_debt.expected_coverage_floor_basis_points
_coverage_floor_decimal_from_basis_points = ratchet_debt.coverage_floor_decimal_from_basis_points
_cov_fail_under = ratchet_debt.cov_fail_under
_normalize_coverage_filename = ratchet_debt.normalize_coverage_filename
_coverage_basis_points_by_path = ratchet_debt.coverage_basis_points_by_path
_line_count = ratchet_debt.line_count
_file_debt_runtime_errors = ratchet_debt.file_debt_runtime_errors
_file_debt_stale_entry_errors = ratchet_debt.file_debt_stale_entry_errors

_new_python_file_paths = ratchet_touch.new_python_file_paths
_new_markdown_file_paths = ratchet_touch.new_markdown_file_paths
_touched_python_file_paths = ratchet_touch.touched_python_file_paths
_touched_markdown_file_paths = ratchet_touch.touched_markdown_file_paths
_touched_file_size_errors = ratchet_touch.touched_file_size_errors
_new_file_size_errors = ratchet_touch.new_file_size_errors
_new_file_coverage_errors = ratchet_touch.new_file_coverage_errors


def _detect_untracked_approval_records(repo_root: Path) -> tuple[str, ...]:
    completed = _git(repo_root, "ls-files", "--others", "--exclude-standard", ".github/approvals")
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Failed to inspect untracked approval records.")
    return tuple(path for path in _normalize_changed_files(completed.stdout) if _is_approval_record_path(path))


def _detect_change_context(repo_root: Path, env: Mapping[str, str] | None = None) -> ChangeContext:
    effective_env = os.environ if env is None else env
    untracked_approval_records = _detect_untracked_approval_records(repo_root)
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
        if worktree_files or untracked_approval_records:
            return ChangeContext(
                _merge_unique_paths(worktree_files, untracked_approval_records),
                _merge_unique_paths(_normalize_added_files(worktree_added.stdout), untracked_approval_records),
                "HEAD",
                "worktree",
            )

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


def _load_base_texts(repo_root: Path, base_ref: str | None, rel_paths: Sequence[str]) -> dict[str, str | None]:
    texts: dict[str, str | None] = dict.fromkeys(rel_paths)
    if base_ref is None:
        return texts
    for rel_path in rel_paths:
        completed = _git(repo_root, "show", f"{base_ref}:{rel_path}")
        if completed.returncode == 0:
            texts[rel_path] = completed.stdout
    return texts


def _explicit_base_ref(repo_root: Path, env: Mapping[str, str] | None = None) -> str | None:
    effective_env = os.environ if env is None else env
    base_ref_name = effective_env.get("SATTLINT_RATCHET_BASE_REF")
    if not base_ref_name and effective_env.get("GITHUB_BASE_REF"):
        base_ref_name = f"origin/{effective_env['GITHUB_BASE_REF']}"
    if base_ref_name:
        return base_ref_name

    head = _git(repo_root, "rev-parse", "--verify", "HEAD")
    if head.returncode == 0:
        return "HEAD"
    return None


def _visible_approval_record_paths(repo_root: Path) -> tuple[str, ...]:
    tracked = _git(repo_root, "diff", "--name-only", "--diff-filter=ACMR", "HEAD", "--", ".github/approvals")
    tracked_paths = _normalize_changed_files(tracked.stdout) if tracked.returncode == 0 else ()
    return _merge_unique_paths(tracked_paths, _detect_untracked_approval_records(repo_root))


def evaluate_policy_change(
    *,
    repo_root: Path = REPO_ROOT,
    changed_files: Sequence[str],
    current_text_by_path: Mapping[str, str],
    base_text_by_path: Mapping[str, str | None],
) -> list[str]:
    return ratchet_protected.evaluate_policy_change(
        repo_root=repo_root,
        changed_files=changed_files,
        current_text_by_path=current_text_by_path,
        base_text_by_path=base_text_by_path,
        typing_ratchet_state_fn=_typing_ratchet_state,
        typing_ratchet_state_errors_fn=_typing_ratchet_state_errors,
        typing_ratchet_backslide_errors_fn=_typing_ratchet_backslide_errors,
    )


def run_policy_check(repo_root: Path = REPO_ROOT, env: Mapping[str, str] | None = None) -> list[str]:
    context = _detect_change_context(repo_root, env)
    errors = _new_file_size_errors(repo_root, context.added_files)
    errors.extend(_new_file_coverage_errors(repo_root, context.added_files))

    relevant_paths = tuple(
        path for path in context.changed_files if path in PROTECTED_PATHS or _is_approval_record_path(path)
    )
    current_paths = tuple(
        dict.fromkeys(
            (*relevant_paths, PYPROJECT_PATH, COVERAGE_RATCHET_PATH, FILE_DEBT_RATCHET_PATH, STRUCTURAL_RATCHET_PATH)
        )
    )
    current_text_by_path = _load_current_texts(repo_root, current_paths)
    pyproject_text = current_text_by_path.get(PYPROJECT_PATH)
    if pyproject_text is None:
        raise ValueError(f"{PYPROJECT_PATH} is missing.")
    current_typing_state = _typing_ratchet_state(pyproject_text, PYPROJECT_PATH)
    if current_typing_state is None:
        raise ValueError(f"{PYPROJECT_PATH} is missing typing ratchet configuration.")
    file_debt_text = current_text_by_path.get(FILE_DEBT_RATCHET_PATH)
    current_file_debt_state = _file_debt_ratchet_state(file_debt_text, FILE_DEBT_RATCHET_PATH) if file_debt_text else {}
    structural_text = current_text_by_path.get(STRUCTURAL_RATCHET_PATH)
    current_structural_exceptions = (
        _structural_file_line_exception_mapping(
            _parse_json_payload(structural_text, STRUCTURAL_RATCHET_PATH),
            STRUCTURAL_RATCHET_PATH,
        )
        if structural_text is not None
        else {}
    )
    errors.extend(_file_debt_surface_errors(current_file_debt_state))
    errors.extend(_file_debt_stale_entry_errors(repo_root=repo_root, file_debt_state=current_file_debt_state))
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
    errors.extend(
        _file_debt_runtime_errors(
            repo_root=repo_root,
            context=context,
            file_debt_state=current_file_debt_state,
            structural_exceptions=current_structural_exceptions,
            typing_state=current_typing_state,
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


def run_policy_check_for_paths(
    changed_files: Sequence[str],
    *,
    repo_root: Path = REPO_ROOT,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    explicit_paths = tuple(
        dict.fromkeys(_normalize_rel_path(path) for path in changed_files if _normalize_rel_path(path))
    )
    if not explicit_paths:
        return []

    approval_paths: tuple[str, ...] = ()
    if any(path in PROTECTED_PATHS for path in explicit_paths):
        approval_paths = _visible_approval_record_paths(repo_root)

    current_text_by_path = _load_current_texts(
        repo_root,
        (PYPROJECT_PATH, FILE_DEBT_RATCHET_PATH, STRUCTURAL_RATCHET_PATH, COVERAGE_RATCHET_PATH),
    )
    file_debt_text = current_text_by_path.get(FILE_DEBT_RATCHET_PATH)
    file_debt_state = _file_debt_ratchet_state(file_debt_text, FILE_DEBT_RATCHET_PATH) if file_debt_text else {}
    structural_text = current_text_by_path.get(STRUCTURAL_RATCHET_PATH)
    structural_exceptions = (
        _structural_file_line_exception_mapping(
            _parse_json_payload(structural_text, STRUCTURAL_RATCHET_PATH),
            STRUCTURAL_RATCHET_PATH,
        )
        if structural_text is not None
        else {}
    )
    errors = _touched_file_size_errors(
        repo_root,
        explicit_paths,
        file_debt_state=file_debt_state,
        structural_exceptions=structural_exceptions,
    )

    touched_runtime_paths = tuple(
        path for path in explicit_paths if path in file_debt_state or path in structural_exceptions
    )
    if touched_runtime_paths:
        pyproject_text = current_text_by_path.get(PYPROJECT_PATH)
        if pyproject_text is None:
            raise ValueError(f"{PYPROJECT_PATH} is missing.")
        typing_state = _typing_ratchet_state(pyproject_text, PYPROJECT_PATH)
        if typing_state is None:
            raise ValueError(f"{PYPROJECT_PATH} is missing typing ratchet configuration.")
        errors.extend(
            _file_debt_runtime_errors(
                repo_root=repo_root,
                context=ChangeContext(
                    changed_files=_merge_unique_paths(explicit_paths, approval_paths),
                    added_files=(),
                    base_ref=_explicit_base_ref(repo_root, env),
                    source="explicit-paths",
                ),
                file_debt_state=file_debt_state,
                structural_exceptions=structural_exceptions,
                typing_state=typing_state,
                enforce_unlisted_source_coverage=False,
                enforce_unlisted_structural_exception_size=False,
            )
        )
        errors.extend(
            _file_debt_stale_entry_errors(
                repo_root=repo_root,
                file_debt_state={path: file_debt_state[path] for path in explicit_paths if path in file_debt_state},
            )
        )

    protected_paths = tuple(
        path
        for path in _merge_unique_paths(explicit_paths, approval_paths)
        if path in PROTECTED_PATHS or _is_approval_record_path(path)
    )
    if not protected_paths:
        return errors

    current_policy_paths = tuple(
        dict.fromkeys(
            (*protected_paths, PYPROJECT_PATH, COVERAGE_RATCHET_PATH, FILE_DEBT_RATCHET_PATH, STRUCTURAL_RATCHET_PATH)
        )
    )
    current_policy_text_by_path = _load_current_texts(repo_root, current_policy_paths)
    base_text_by_path = _load_base_texts(repo_root, _explicit_base_ref(repo_root, env), protected_paths)
    errors.extend(
        evaluate_policy_change(
            repo_root=repo_root,
            changed_files=_merge_unique_paths(explicit_paths, approval_paths),
            current_text_by_path=current_policy_text_by_path,
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
