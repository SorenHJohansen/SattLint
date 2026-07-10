from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    from scripts import _ratchet_policy_context as ratchet_context
    from scripts import _ratchet_policy_debt as ratchet_debt
    from scripts import _ratchet_policy_typing as ratchet_typing
except ModuleNotFoundError:  # pragma: no cover - direct script execution resolves from scripts/
    import _ratchet_policy_context as ratchet_context
    import _ratchet_policy_debt as ratchet_debt
    import _ratchet_policy_typing as ratchet_typing


def approval_record_errors(rel_path: str, text: str) -> list[str]:
    errors: list[str] = []
    if not ratchet_context.APPROVAL_BY_RE.search(text):
        errors.append(f"Approval record {rel_path} is missing an 'Approved-by:' line.")
    if not ratchet_context.APPROVAL_REASON_RE.search(text):
        errors.append(f"Approval record {rel_path} is missing a 'Reason:' line.")
    return errors


def evaluate_policy_change(
    *,
    repo_root: Path,
    changed_files: Sequence[str],
    current_text_by_path: Mapping[str, str],
    base_text_by_path: Mapping[str, str | None],
    typing_ratchet_state_fn=ratchet_typing.typing_ratchet_state,
    typing_ratchet_state_errors_fn=ratchet_typing.typing_ratchet_state_errors,
    typing_ratchet_backslide_errors_fn=ratchet_typing.typing_ratchet_backslide_errors,
) -> list[str]:
    changed = tuple(dict.fromkeys(path for path in changed_files if path))
    protected = tuple(path for path in changed if path in ratchet_context.PROTECTED_PATHS)
    if not protected:
        return []

    errors: list[str] = []
    approval_paths = tuple(path for path in changed if ratchet_context.is_approval_record_path(path))
    if not approval_paths:
        protected_list = ", ".join(protected)
        errors.append(
            "Ratchet edits require explicit approval. "
            f"Add {ratchet_context.APPROVAL_RECORD_HINT} with 'Approved-by:' and 'Reason:' before changing: {protected_list}."
        )
    else:
        for approval_path in approval_paths:
            errors.extend(approval_record_errors(approval_path, current_text_by_path.get(approval_path, "")))

    if ratchet_context.STRUCTURAL_RATCHET_PATH in protected:
        base_text = base_text_by_path.get(ratchet_context.STRUCTURAL_RATCHET_PATH)
        head_text = current_text_by_path.get(ratchet_context.STRUCTURAL_RATCHET_PATH)
        if base_text is not None and head_text is not None:
            base_payload = ratchet_context.parse_json_payload(base_text, ratchet_context.STRUCTURAL_RATCHET_PATH)
            head_payload = ratchet_context.parse_json_payload(head_text, ratchet_context.STRUCTURAL_RATCHET_PATH)
            base_metrics = ratchet_debt.metric_mapping(base_payload, ratchet_context.STRUCTURAL_RATCHET_PATH)
            head_metrics = ratchet_debt.metric_mapping(head_payload, ratchet_context.STRUCTURAL_RATCHET_PATH)
            base_exceptions = ratchet_debt.structural_file_line_exception_mapping(
                base_payload, ratchet_context.STRUCTURAL_RATCHET_PATH
            )
            head_exceptions = ratchet_debt.structural_file_line_exception_mapping(
                head_payload, ratchet_context.STRUCTURAL_RATCHET_PATH
            )
            markdown_head_metrics = sorted(
                metric for metric in head_metrics if metric in ratchet_context.LEGACY_MARKDOWN_STRUCTURAL_METRICS
            )
            if markdown_head_metrics:
                errors.append(
                    "Structural ratchet must not track Markdown file metrics: " + ", ".join(markdown_head_metrics) + "."
                )
            for rel_path in sorted(path for path in head_exceptions if path.endswith(".md")):
                errors.append(f"Structural file-line exceptions must not target Markdown paths: {rel_path}.")
            for metric_name, base_value in sorted(base_metrics.items()):
                head_value = head_metrics.get(metric_name)
                if head_value is None:
                    if metric_name in ratchet_context.LEGACY_MARKDOWN_STRUCTURAL_METRICS:
                        continue
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
                            f"Structural file-line exception loosened: {rel_path} {base_entry['max_lines']} -> {head_entry['max_lines']}. Fix code first; do not widen the exception."
                        )
                for rel_path in sorted(set(head_exceptions) - set(base_exceptions)):
                    errors.append(
                        f"Structural file-line exception added: {rel_path} @ {head_exceptions[rel_path]['max_lines']} lines. Fix code first; do not add new exceptions."
                    )

    if ratchet_context.COVERAGE_RATCHET_PATH in protected:
        base_text = base_text_by_path.get(ratchet_context.COVERAGE_RATCHET_PATH)
        head_text = current_text_by_path.get(ratchet_context.COVERAGE_RATCHET_PATH)
        if head_text is not None:
            head_payload = ratchet_context.parse_json_payload(head_text, ratchet_context.COVERAGE_RATCHET_PATH)
            head_value = ratchet_debt.coverage_basis_points(head_payload, ratchet_context.COVERAGE_RATCHET_PATH)
            expected_head_value = ratchet_debt.expected_coverage_floor_basis_points(
                head_payload, ratchet_context.COVERAGE_RATCHET_PATH
            )
            if head_value != expected_head_value:
                errors.append(
                    "Coverage ratchet floor must equal the recorded baseline minus 1.00 percentage point: "
                    f"expected min_line_rate_basis_points {expected_head_value}, found {head_value}."
                )
        if base_text is not None and head_text is not None:
            base_payload = ratchet_context.parse_json_payload(base_text, ratchet_context.COVERAGE_RATCHET_PATH)
            head_payload = ratchet_context.parse_json_payload(head_text, ratchet_context.COVERAGE_RATCHET_PATH)
            base_baseline = ratchet_debt.coverage_summary_basis_points(
                base_payload, ratchet_context.COVERAGE_RATCHET_PATH
            )
            head_baseline = ratchet_debt.coverage_summary_basis_points(
                head_payload, ratchet_context.COVERAGE_RATCHET_PATH
            )
            if head_baseline < base_baseline:
                errors.append(
                    "Coverage baseline decreased: "
                    f"total_line_rate {base_baseline / 100:.2f}% -> {head_baseline / 100:.2f}%. Fix code or tests first; do not rebaseline."
                )

    if ratchet_context.PYPROJECT_PATH in protected:
        base_text = base_text_by_path.get(ratchet_context.PYPROJECT_PATH)
        head_text = current_text_by_path.get(ratchet_context.PYPROJECT_PATH)
        if head_text is not None:
            head_value = ratchet_debt.cov_fail_under(head_text, ratchet_context.PYPROJECT_PATH)
            coverage_text = current_text_by_path.get(ratchet_context.COVERAGE_RATCHET_PATH)
            if coverage_text is not None:
                coverage_payload = ratchet_context.parse_json_payload(
                    coverage_text, ratchet_context.COVERAGE_RATCHET_PATH
                )
                expected_floor = ratchet_debt.coverage_floor_decimal_from_basis_points(
                    ratchet_debt.expected_coverage_floor_basis_points(
                        coverage_payload, ratchet_context.COVERAGE_RATCHET_PATH
                    )
                )
                if head_value != expected_floor:
                    errors.append(
                        "Pytest coverage floor must equal the recorded coverage baseline minus 1.00 percentage point: "
                        f"expected --cov-fail-under={expected_floor:.2f}, found {head_value}."
                    )

            head_state = typing_ratchet_state_fn(head_text, ratchet_context.PYPROJECT_PATH)
            if head_state is None:
                raise ValueError(f"{ratchet_context.PYPROJECT_PATH} is missing typing ratchet configuration.")
            base_typing_state = (
                typing_ratchet_state_fn(base_text, ratchet_context.PYPROJECT_PATH, allow_missing=True)
                if base_text
                else None
            )
            errors.extend(
                typing_ratchet_state_errors_fn(
                    repo_root=repo_root,
                    added_files=(),
                    base_state=base_typing_state,
                    state=head_state,
                )
            )
            errors.extend(typing_ratchet_backslide_errors_fn(base_typing_state, head_state))

    if ratchet_context.COVERAGE_RATCHET_PATH in protected and ratchet_context.PYPROJECT_PATH not in protected:
        coverage_text = current_text_by_path.get(ratchet_context.COVERAGE_RATCHET_PATH)
        pyproject_text = current_text_by_path.get(ratchet_context.PYPROJECT_PATH)
        if coverage_text is not None and pyproject_text is not None:
            coverage_payload = ratchet_context.parse_json_payload(coverage_text, ratchet_context.COVERAGE_RATCHET_PATH)
            expected_floor = ratchet_debt.coverage_floor_decimal_from_basis_points(
                ratchet_debt.expected_coverage_floor_basis_points(
                    coverage_payload, ratchet_context.COVERAGE_RATCHET_PATH
                )
            )
            pyproject_floor = ratchet_debt.cov_fail_under(pyproject_text, ratchet_context.PYPROJECT_PATH)
            if pyproject_floor != expected_floor:
                errors.append(
                    "Pytest coverage floor must stay aligned with the checked-in coverage ratchet: "
                    f"expected --cov-fail-under={expected_floor:.2f}, found {pyproject_floor}."
                )

    if ratchet_context.FILE_DEBT_RATCHET_PATH in protected:
        base_text = base_text_by_path.get(ratchet_context.FILE_DEBT_RATCHET_PATH)
        head_text = current_text_by_path.get(ratchet_context.FILE_DEBT_RATCHET_PATH)
        if head_text is not None:
            head_state = ratchet_debt.file_debt_ratchet_state(head_text, ratchet_context.FILE_DEBT_RATCHET_PATH)
            errors.extend(ratchet_debt.file_debt_surface_errors(head_state))
            structural_text = current_text_by_path.get(ratchet_context.STRUCTURAL_RATCHET_PATH)
            if structural_text is None:
                raise ValueError(f"{ratchet_context.STRUCTURAL_RATCHET_PATH} is missing.")
            pyproject_text = current_text_by_path.get(ratchet_context.PYPROJECT_PATH)
            if pyproject_text is None:
                raise ValueError(f"{ratchet_context.PYPROJECT_PATH} is missing.")

            structural_payload = ratchet_context.parse_json_payload(
                structural_text, ratchet_context.STRUCTURAL_RATCHET_PATH
            )
            structural_exceptions = ratchet_debt.structural_file_line_exception_mapping(
                structural_payload, ratchet_context.STRUCTURAL_RATCHET_PATH
            )
            base_structural_exceptions: dict[str, dict[str, Any]] = {}
            base_structural_text = base_text_by_path.get(ratchet_context.STRUCTURAL_RATCHET_PATH)
            if base_structural_text is not None:
                base_structural_payload = ratchet_context.parse_json_payload(
                    base_structural_text, ratchet_context.STRUCTURAL_RATCHET_PATH
                )
                base_structural_exceptions = ratchet_debt.structural_file_line_exception_mapping(
                    base_structural_payload, ratchet_context.STRUCTURAL_RATCHET_PATH
                )
            typing_state = typing_ratchet_state_fn(pyproject_text, ratchet_context.PYPROJECT_PATH)
            if typing_state is None:
                raise ValueError(f"{ratchet_context.PYPROJECT_PATH} is missing typing ratchet configuration.")
            coverage_by_path = ratchet_debt.coverage_basis_points_by_path(repo_root)

            base_file_debt_state: dict[str, dict[str, dict[str, Any]]] = {}
            if base_text is not None:
                base_file_debt_state = ratchet_debt.file_debt_ratchet_state(
                    base_text, ratchet_context.FILE_DEBT_RATCHET_PATH
                )

            errors.extend(
                ratchet_debt.file_debt_ratchet_addition_errors(
                    base_file_debt_state,
                    head_state,
                    structural_exceptions=structural_exceptions,
                    base_structural_exceptions=base_structural_exceptions,
                    typing_debt_allowlist=typing_state.debt_allowlist,
                    coverage_by_path=coverage_by_path,
                )
            )
            errors.extend(ratchet_debt.file_debt_ratchet_backslide_errors(base_file_debt_state, head_state))

    return errors
