"""Preview-first workspace refactoring helpers for safe, deterministic rewrites."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from sattlint.core.semantic import build_source_snapshot_from_basepicture, discover_workspace_sources
from sattlint.engine import parse_source_text
from sattlint.path_sanitizer import sanitize_path_for_report
from sattlint.semantic_analysis import build_variable_semantic_artifacts
from sattlint.tracing import collect_ast_summary

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_FILENAME = "refactoring_preview.json"
DEFAULT_REFACTORING_KIND = "normalize-layout"


def _emit_refactoring_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _sanitize_repo_path(path: Path, *, workspace_root: Path) -> str:
    return sanitize_path_for_report(path, repo_root=workspace_root) or path.as_posix()


def _normalize_layout(source_text: str) -> str:
    normalized_newlines = source_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_lines: list[str] = []
    previous_blank = False
    for raw_line in normalized_newlines.split("\n"):
        line = raw_line.rstrip()
        is_blank = line == ""
        if is_blank and previous_blank:
            continue
        normalized_lines.append(line)
        previous_blank = is_blank

    while normalized_lines and normalized_lines[-1] == "":
        normalized_lines.pop()
    return "\n".join(normalized_lines) + "\n"


def _apply_refactoring(source_text: str, *, refactoring_kind: str) -> str:
    if refactoring_kind != DEFAULT_REFACTORING_KIND:
        raise ValueError(f"Unsupported refactoring kind: {refactoring_kind}")
    return _normalize_layout(source_text)


def _definition_signature(definition: Any) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    canonical = getattr(definition, "canonical_path", None)
    canonical_segments = tuple(str(segment) for segment in getattr(canonical, "segments", ()) or ())
    declaration_module_path = tuple(
        str(segment) for segment in getattr(definition, "declaration_module_path", ()) or ()
    )
    field_path = tuple(str(segment) for segment in getattr(definition, "field_path", ()) or ())
    return canonical_segments, declaration_module_path, field_path


def _snapshot_signature(snapshot: Any) -> dict[str, Any]:
    definitions = sorted(_definition_signature(definition) for definition in getattr(snapshot, "definitions", []))
    call_signatures = len(getattr(snapshot, "call_signatures", []) or [])
    diagnostics = len(getattr(snapshot, "diagnostics", []) or [])
    return {
        "definitions": definitions,
        "call_signatures": call_signatures,
        "diagnostics": diagnostics,
    }


def _build_diff_lines(source_file: Path, *, workspace_root: Path, original: str, transformed: str) -> list[str]:
    label = _sanitize_repo_path(source_file, workspace_root=workspace_root)
    return list(
        difflib.unified_diff(
            original.splitlines(),
            transformed.splitlines(),
            fromfile=label,
            tofile=label,
            lineterm="",
        )
    )


def _diff_summary(diff_lines: list[str]) -> dict[str, int]:
    additions = 0
    deletions = 0
    for line in diff_lines:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return {
        "addition_count": additions,
        "deletion_count": deletions,
        "changed_line_count": additions + deletions,
    }


def build_refactoring_candidate(
    source_file: Path,
    *,
    workspace_root: Path,
    refactoring_kind: str = DEFAULT_REFACTORING_KIND,
) -> tuple[dict[str, Any], str | None]:
    resolved_workspace_root = workspace_root.resolve()
    resolved_source_file = source_file.resolve()
    sanitized_source = _sanitize_repo_path(resolved_source_file, workspace_root=resolved_workspace_root)

    try:
        original_text = resolved_source_file.read_text(encoding="utf-8")
        transformed_text = _apply_refactoring(original_text, refactoring_kind=refactoring_kind)

        original_bp = parse_source_text(original_text)
        transformed_bp = parse_source_text(transformed_text)
        structural_summary_equal = collect_ast_summary(original_bp) == collect_ast_summary(transformed_bp)

        original_snapshot = build_source_snapshot_from_basepicture(
            original_bp,
            resolved_source_file,
            workspace_root=resolved_workspace_root,
            collect_variable_diagnostics=False,
            _analysis_provider=build_variable_semantic_artifacts,
        )
        transformed_snapshot = build_source_snapshot_from_basepicture(
            transformed_bp,
            resolved_source_file,
            workspace_root=resolved_workspace_root,
            collect_variable_diagnostics=False,
            _analysis_provider=build_variable_semantic_artifacts,
        )
        semantic_signature_equal = _snapshot_signature(original_snapshot) == _snapshot_signature(transformed_snapshot)
        changed = transformed_text != original_text
        diff_lines = _build_diff_lines(
            resolved_source_file,
            workspace_root=resolved_workspace_root,
            original=original_text,
            transformed=transformed_text,
        )
        safe_to_apply = structural_summary_equal and semantic_signature_equal
        candidate = {
            "source_file": sanitized_source,
            "refactoring_kind": refactoring_kind,
            "status": "ok",
            "changed": changed,
            "applied": False,
            "safety_contract": {
                "preview_first": True,
                "safe_to_apply": safe_to_apply,
                "justification": (
                    "Whitespace normalization preserved the structural AST summary and semantic snapshot signature."
                    if safe_to_apply
                    else "Safety checks failed; preview only."
                ),
            },
            "safety_checks": {
                "original_parse_ok": True,
                "transformed_parse_ok": True,
                "structural_summary_equal": structural_summary_equal,
                "semantic_signature_equal": semantic_signature_equal,
            },
            "diff": diff_lines,
            "summary": _diff_summary(diff_lines),
            "errors": [],
        }
        return candidate, transformed_text
    except Exception as exc:
        candidate = {
            "source_file": sanitized_source,
            "refactoring_kind": refactoring_kind,
            "status": "error",
            "changed": False,
            "applied": False,
            "safety_contract": {
                "preview_first": True,
                "safe_to_apply": False,
                "justification": "The candidate could not be validated safely.",
            },
            "safety_checks": {
                "original_parse_ok": False,
                "transformed_parse_ok": False,
                "structural_summary_equal": False,
                "semantic_signature_equal": False,
            },
            "diff": [],
            "summary": {"addition_count": 0, "deletion_count": 0, "changed_line_count": 0},
            "errors": [{"error": str(exc), "error_type": type(exc).__name__}],
        }
        return candidate, None


def _resolve_selected_files(
    discovery: Any,
    *,
    workspace_root: Path,
    entry_files: Sequence[str] | None,
) -> tuple[list[Path], list[dict[str, Any]]]:
    if not entry_files:
        return list(discovery.program_files), []

    selected: list[Path] = []
    errors: list[dict[str, Any]] = []
    known_paths = {
        _sanitize_repo_path(path, workspace_root=workspace_root).casefold(): path for path in discovery.program_files
    }
    for raw_entry in entry_files:
        value = raw_entry.strip()
        if not value:
            continue
        candidate_path = Path(value)
        resolved = (
            candidate_path.resolve() if candidate_path.is_absolute() else (workspace_root / candidate_path).resolve()
        )
        sanitized = _sanitize_repo_path(resolved, workspace_root=workspace_root)
        matched = known_paths.get(sanitized.casefold())
        if matched is None:
            errors.append({"entry_file": sanitized, "message": f"Unknown entry-file selector: {value}"})
            continue
        selected.append(matched)
    return selected, errors


def build_refactoring_report(
    workspace_root: Path = REPO_ROOT,
    *,
    entry_files: Sequence[str] | None = None,
    refactoring_kind: str = DEFAULT_REFACTORING_KIND,
    apply: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    resolved_workspace_root = workspace_root.resolve()
    if progress_callback is not None:
        progress_callback("Refactoring: discovering workspace sources")
    discovery = discover_workspace_sources(resolved_workspace_root)
    selected_files, selection_errors = _resolve_selected_files(
        discovery,
        workspace_root=resolved_workspace_root,
        entry_files=entry_files,
    )

    candidates: list[dict[str, Any]] = []
    applied_change_count = 0
    for index, source_file in enumerate(selected_files, start=1):
        sanitized_source = _sanitize_repo_path(source_file, workspace_root=resolved_workspace_root)
        if progress_callback is not None:
            progress_callback(f"Refactoring: previewing {index}/{len(selected_files)} {sanitized_source}")
        candidate, transformed_text = build_refactoring_candidate(
            source_file,
            workspace_root=resolved_workspace_root,
            refactoring_kind=refactoring_kind,
        )
        if (
            apply
            and candidate["status"] == "ok"
            and candidate["changed"]
            and candidate["safety_contract"]["safe_to_apply"]
        ):
            if transformed_text is None:
                raise RuntimeError("Refactoring candidate was marked safe to apply without transformed text.")
            try:
                source_file.write_text(transformed_text, encoding="utf-8")
            except OSError as exc:
                candidate["status"] = "error"
                candidate["errors"].append({"error": str(exc), "error_type": type(exc).__name__})
            else:
                candidate["applied"] = True
                applied_change_count += 1
        candidates.append(candidate)

    changed_candidate_count = sum(1 for candidate in candidates if candidate["changed"])
    safe_candidate_count = sum(1 for candidate in candidates if candidate["safety_contract"]["safe_to_apply"])
    error_count = len(selection_errors) + sum(1 for candidate in candidates if candidate["status"] == "error")
    status = "ok"
    if error_count and not candidates:
        status = "error"
    elif error_count:
        status = "partial"

    return {
        "generated_by": "sattlint.devtools.refactoring",
        "report_kind": "refactoring-preview",
        "status": status,
        "workspace_root": _sanitize_repo_path(resolved_workspace_root, workspace_root=resolved_workspace_root),
        "refactoring_kind": refactoring_kind,
        "apply_mode": "apply" if apply else "dry-run",
        "summary": {
            "selected_entry_count": len(selected_files),
            "changed_candidate_count": changed_candidate_count,
            "safe_candidate_count": safe_candidate_count,
            "applied_change_count": applied_change_count,
            "error_count": error_count,
        },
        "candidates": sorted(candidates, key=lambda item: str(item["source_file"]).casefold()),
        "selection_errors": selection_errors,
    }


def _render_text_report(report: dict[str, Any]) -> str:
    lines = [
        "SattLint refactoring preview",
        f"Status: {report['status']}",
        f"Workspace root: {report['workspace_root']}",
        f"Mode: {report['apply_mode']}",
        f"Selected entries: {report['summary']['selected_entry_count']}",
        f"Changed candidates: {report['summary']['changed_candidate_count']}",
        f"Applied changes: {report['summary']['applied_change_count']}",
        "",
        "Candidates:",
    ]
    if not report["candidates"]:
        lines.append("- none")
    for candidate in report["candidates"]:
        lines.append(
            f"- {candidate['source_file']}: status={candidate['status']} changed={candidate['changed']} safe={candidate['safety_contract']['safe_to_apply']} applied={candidate['applied']}"
        )
    return "\n".join(lines)


def _write_refactoring_report(output_dir: Path, report: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / DEFAULT_OUTPUT_FILENAME
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def _parse_refactoring_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sattlint-refactoring",
        description="Preview and optionally apply explicitly safe workspace refactorings.",
    )
    parser.add_argument(
        "--workspace-root",
        default=str(REPO_ROOT),
        help="Workspace root to scan for entry files.",
    )
    parser.add_argument(
        "--entry-file",
        action="append",
        default=[],
        help="Optional entry file path to preview or apply. May be provided multiple times.",
    )
    parser.add_argument(
        "--refactoring-kind",
        default=DEFAULT_REFACTORING_KIND,
        help="Refactoring kind to run. Defaults to normalize-layout.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply validated changes to disk. Dry-run preview remains the default.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly request preview mode without writing changes.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format for stdout.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory that receives refactoring_preview.json.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Suppress progress messages on stderr.",
    )
    return parser.parse_args(list(argv) if argv is not None else sys.argv[1:])


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_refactoring_args(argv)
    apply = bool(args.apply and not args.dry_run)
    progress_callback = None if args.no_progress else _emit_refactoring_progress
    report = build_refactoring_report(
        Path(args.workspace_root).resolve(),
        entry_files=list(args.entry_file),
        refactoring_kind=str(args.refactoring_kind),
        apply=apply,
        progress_callback=progress_callback,
    )
    output_error: OSError | None = None
    if args.output_dir:
        try:
            _write_refactoring_report(Path(args.output_dir).resolve(), report)
        except OSError as exc:
            output_error = exc

    if args.format == "text":
        print(_render_text_report(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    if output_error is not None:
        print(f"refactoring output error: {output_error}", file=sys.stderr, flush=True)
        return 1
    return 0 if report["status"] in {"ok", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
