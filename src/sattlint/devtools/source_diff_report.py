"""Review-friendly reports for draft `.s` versus official `.x` source pairs."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from sattline_parser.api import read_text_with_fallback
from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattlint import cli_output
from sattlint.devtools._diff_rendering import (
    build_unified_diff_lines,
    normalize_layout_text,
    summarize_unified_diff_lines,
)
from sattlint.devtools._io import emit_progress, sanitize_repo_path
from sattlint.devtools._source_diff_cli import (
    DEFAULT_JSON_OUTPUT_FILENAME,
    DEFAULT_MARKDOWN_OUTPUT_FILENAME,
    render_markdown,
)
from sattlint.devtools._source_diff_cli import (
    build_cli_parser as _build_cli_parser,
)
from sattlint.devtools._source_diff_cli import (
    run_cli as _run_cli,
)
from sattlint.devtools._source_diff_cli import (
    write_report_artifacts as _write_report_artifacts,
)
from sattlint.devtools._source_diff_deltas import (
    build_inline_diff_lines as _build_inline_diff_lines,
)
from sattlint.devtools._source_diff_deltas import (
    collect_promoted_singlemodule_entries as _collect_promoted_singlemodule_entries,
)
from sattlint.devtools._source_diff_deltas import (
    diff_modulecode_detail as _diff_modulecode_detail,
)
from sattlint.devtools._source_diff_deltas import (
    diff_modulecode_entities as _diff_modulecode_entities,
)
from sattlint.devtools._source_diff_deltas import (
    diff_moduledef_detail as _diff_moduledef_detail,
)
from sattlint.devtools._source_diff_deltas import (
    diff_nested_inline_module_code_diffs as _diff_nested_inline_module_code_diffs,
)
from sattlint.devtools._source_diff_deltas import (
    diff_submodule_details as _diff_submodule_details,
)
from sattlint.devtools._source_diff_deltas import (
    diff_variable_details as _diff_variable_details,
)
from sattlint.devtools._source_diff_deltas import (
    format_change_value as _format_change_value,
)
from sattlint.devtools._source_diff_deltas import (
    format_summary_delta as _format_summary_delta,
)
from sattlint.devtools._source_diff_details import (
    basepicture_detail as _basepicture_detail,
)
from sattlint.devtools._source_diff_details import (
    collect_inline_module_details as _collect_inline_module_details,
)
from sattlint.devtools._source_diff_details import (
    collect_moduletype_instance_details as _collect_moduletype_instance_details,
)
from sattlint.devtools._source_diff_details import (
    datatype_signature as _datatype_signature,
)
from sattlint.devtools._source_diff_details import (
    entry_name_sort_key as _entry_name_sort_key,
)
from sattlint.devtools._source_diff_details import (
    format_qualifiers as _format_qualifiers,
)
from sattlint.devtools._source_diff_details import (
    format_submodule_summary as _format_submodule_summary,
)
from sattlint.devtools._source_diff_details import (
    format_variable_summary as _format_variable_summary,
)
from sattlint.devtools._source_diff_details import (
    inline_module_detail as _inline_module_detail,
)
from sattlint.devtools._source_diff_details import (
    is_promoted_moduletype_name as _is_promoted_moduletype_name,
)
from sattlint.devtools._source_diff_details import (
    leaf_module_name as _leaf_module_name,
)
from sattlint.devtools._source_diff_details import (
    module_content_signature as _module_content_signature,
)
from sattlint.devtools._source_diff_details import (
    module_header_signature as _module_header_signature,
)
from sattlint.devtools._source_diff_details import (
    modulecode_detail as _modulecode_detail,
)
from sattlint.devtools._source_diff_details import (
    modulecode_entity_code_lines as _modulecode_entity_code_lines,
)
from sattlint.devtools._source_diff_details import (
    modulecode_entity_detail as _modulecode_entity_detail,
)
from sattlint.devtools._source_diff_details import (
    modulecode_signature as _modulecode_signature,
)
from sattlint.devtools._source_diff_details import (
    moduledef_detail as _moduledef_detail,
)
from sattlint.devtools._source_diff_details import (
    moduledef_signature as _moduledef_signature,
)
from sattlint.devtools._source_diff_details import (
    moduletype_detail as _moduletype_detail,
)
from sattlint.devtools._source_diff_details import (
    path_has_prefix as _path_has_prefix,
)
from sattlint.devtools._source_diff_details import (
    render_modulecode_entity_lines as _render_modulecode_entity_lines,
)
from sattlint.devtools._source_diff_details import (
    stable_signature_text as _stable_signature_text,
)
from sattlint.devtools._source_diff_details import (
    stable_signature_value as _stable_signature_value,
)
from sattlint.devtools._source_diff_details import (
    submodule_detail as _submodule_detail,
)
from sattlint.devtools._source_diff_details import (
    submodule_details as _submodule_details,
)
from sattlint.devtools._source_diff_details import (
    submodule_kind as _submodule_kind,
)
from sattlint.devtools._source_diff_details import (
    submodule_signature as _submodule_signature,
)
from sattlint.devtools._source_diff_details import (
    variable_detail as _variable_detail,
)
from sattlint.devtools._source_diff_details import (
    variable_details as _variable_details,
)
from sattlint.devtools._source_diff_details import (
    variable_signature as _variable_signature,
)
from sattlint.devtools._source_diff_runtime import (
    discover_pairs as _discover_pairs,
)
from sattlint.devtools._source_diff_runtime import (
    parse_side_for_report as _parse_side_for_report,
)
from sattlint.devtools._source_diff_runtime import (
    resolve_explicit_pair as _resolve_explicit_pair,
)
from sattlint.devtools._source_diff_sections import (
    build_ast_comparison_sections as _build_ast_comparison_sections,
)
from sattlint.devtools._source_diff_sections import (
    build_basepicture_section as _build_basepicture_section,
)
from sattlint.devtools._source_diff_sections import (
    build_datatype_section as _build_datatype_section,
)
from sattlint.devtools._source_diff_sections import (
    build_module_entry as _build_module_entry,
)
from sattlint.devtools._source_diff_sections import (
    build_moduletype_section as _build_moduletype_section,
)
from sattlint.devtools._source_diff_sections import (
    build_named_entries_section as _build_named_entries_section,
)
from sattlint.devtools._source_diff_sections import (
    build_singlemodule_section as _build_singlemodule_section,
)
from sattlint.devtools._source_diff_sections import (
    full_module_details as _full_module_details,
)
from sattlint.repo_paths import repo_root_from

# These compatibility re-exports are kept live for tests and external callers that
# still reach into this facade for the split helper functions and constants.
_COMPAT_PRIVATE_EXPORTS = (
    DEFAULT_JSON_OUTPUT_FILENAME,
    DEFAULT_MARKDOWN_OUTPUT_FILENAME,
    _build_inline_diff_lines,
    _collect_promoted_singlemodule_entries,
    _diff_modulecode_detail,
    _diff_modulecode_entities,
    _diff_moduledef_detail,
    _diff_nested_inline_module_code_diffs,
    _diff_submodule_details,
    _diff_variable_details,
    _format_change_value,
    _format_summary_delta,
    _basepicture_detail,
    _collect_inline_module_details,
    _collect_moduletype_instance_details,
    _datatype_signature,
    _entry_name_sort_key,
    _format_qualifiers,
    _format_submodule_summary,
    _format_variable_summary,
    _inline_module_detail,
    _is_promoted_moduletype_name,
    _leaf_module_name,
    _module_content_signature,
    _module_header_signature,
    _modulecode_detail,
    _modulecode_entity_code_lines,
    _modulecode_entity_detail,
    _modulecode_signature,
    _moduletype_detail,
    _moduledef_detail,
    _moduledef_signature,
    _path_has_prefix,
    _render_modulecode_entity_lines,
    _stable_signature_text,
    _stable_signature_value,
    _submodule_detail,
    _submodule_details,
    _submodule_kind,
    _submodule_signature,
    _variable_detail,
    _variable_details,
    _variable_signature,
    _build_basepicture_section,
    _build_datatype_section,
    _build_module_entry,
    _build_moduletype_section,
    _build_named_entries_section,
    _build_singlemodule_section,
    _full_module_details,
)


def _source_diff_repo_root() -> Path:
    try:
        return repo_root_from(Path(__file__))
    except RuntimeError:
        return Path(__file__).resolve().parent


REPO_ROOT = _source_diff_repo_root()


def _pair_name(draft_file: Path, official_file: Path) -> str:
    if draft_file.stem.casefold() == official_file.stem.casefold():
        return draft_file.stem
    return f"{draft_file.stem} vs {official_file.stem}"


def _read_source_text(path: Path) -> str:
    source_text = read_text_with_fallback(path)
    if is_compressed(source_text):
        source_text, _ = preprocess_sl_text(source_text)
    return source_text


def build_pair_report(
    draft_file: Path,
    official_file: Path,
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    resolved_workspace_root = workspace_root.resolve()
    resolved_draft = draft_file.resolve()
    resolved_official = official_file.resolve()

    errors: list[dict[str, str]] = []
    draft_text: str | None = None
    official_text: str | None = None

    try:
        draft_text = _read_source_text(resolved_draft)
    except (OSError, UnicodeError) as exc:
        errors.append({"side": "draft", "error": str(exc), "error_type": type(exc).__name__})
    try:
        official_text = _read_source_text(resolved_official)
    except (OSError, UnicodeError) as exc:
        errors.append({"side": "official", "error": str(exc), "error_type": type(exc).__name__})

    draft_bp, draft_parse_ok, draft_validation_ok, draft_errors = _parse_side_for_report(
        draft_text,
        source_path=resolved_draft,
        side="draft",
    )
    official_bp, official_parse_ok, official_validation_ok, official_errors = _parse_side_for_report(
        official_text,
        source_path=resolved_official,
        side="official",
    )
    errors.extend(draft_errors)
    errors.extend(official_errors)

    sanitized_draft = sanitize_repo_path(resolved_draft, workspace_root=resolved_workspace_root)
    sanitized_official = sanitize_repo_path(resolved_official, workspace_root=resolved_workspace_root)
    diff_lines: list[str] = []
    summary = {"addition_count": 0, "deletion_count": 0, "changed_line_count": 0}
    if draft_text is not None and official_text is not None:
        diff_lines = build_unified_diff_lines(
            resolved_official,
            workspace_root=resolved_workspace_root,
            original=official_text,
            transformed=draft_text,
            to_file=sanitized_draft,
        )
        summary = summarize_unified_diff_lines(diff_lines)

    sections: list[dict[str, Any]] = []
    if draft_bp is not None and official_bp is not None:
        sections = _build_ast_comparison_sections(draft_bp, official_bp)

    classification = "error"
    if draft_bp is not None and official_bp is not None and draft_text is not None and official_text is not None:
        if draft_text == official_text:
            classification = "identical"
        elif normalize_layout_text(draft_text) == normalize_layout_text(official_text):
            classification = "layout-only"
        else:
            classification = "structural"

    status = "error"
    if classification != "error":
        status = "ok" if not errors else "partial"

    return {
        "pair_name": _pair_name(resolved_draft, resolved_official),
        "draft_file": sanitized_draft,
        "official_file": sanitized_official,
        "status": status,
        "classification": classification,
        "changed": summary["changed_line_count"] > 0,
        "parse_checks": {
            "draft_parse_ok": draft_parse_ok,
            "official_parse_ok": official_parse_ok,
        },
        "validation_checks": {
            "draft_validation_ok": draft_validation_ok,
            "official_validation_ok": official_validation_ok,
        },
        "summary": summary,
        "sections": sections,
        "errors": errors,
    }


def build_source_diff_report(
    workspace_root: Path = REPO_ROOT,
    *,
    draft_file: str | None = None,
    official_file: str | None = None,
    discover_pairs: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    resolved_workspace_root = workspace_root.resolve()
    if progress_callback is not None:
        progress_callback("Source diff: resolving comparison pairs")

    pairs, selection_errors = _resolve_explicit_pair(
        workspace_root=resolved_workspace_root,
        draft_file=draft_file,
        official_file=official_file,
    )
    if not pairs and not selection_errors and discover_pairs:
        pairs = _discover_pairs(resolved_workspace_root)
        if not pairs:
            selection_errors.append(
                {
                    "draft_file": "",
                    "official_file": "",
                    "message": "No same-basename .s/.x pairs were found. Use --draft-file and --official-file to compare one explicit pair.",
                }
            )
    elif not pairs and not selection_errors:
        selection_errors.append(
            {
                "draft_file": "",
                "official_file": "",
                "message": "Select one explicit pair with --draft-file and --official-file, or use --discover-pairs.",
            }
        )

    pair_reports: list[dict[str, Any]] = []
    for index, (resolved_draft, resolved_official) in enumerate(pairs, start=1):
        if progress_callback is not None:
            progress_callback(
                f"Source diff: comparing {index}/{len(pairs)} {sanitize_repo_path(resolved_draft, workspace_root=resolved_workspace_root)}"
            )
        pair_reports.append(
            build_pair_report(
                resolved_draft,
                resolved_official,
                workspace_root=resolved_workspace_root,
            )
        )

    error_count = len(selection_errors) + sum(1 for report in pair_reports if report["status"] != "ok")
    status = "ok"
    if error_count and not pair_reports:
        status = "error"
    elif error_count:
        status = "partial"

    return {
        "generated_by": "sattlint.devtools.source_diff_report",
        "report_kind": "source-diff-report",
        "status": status,
        "workspace_root": sanitize_repo_path(resolved_workspace_root, workspace_root=resolved_workspace_root),
        "summary": {
            "compared_pair_count": len(pair_reports),
            "changed_pair_count": sum(1 for report in pair_reports if report["changed"]),
            "identical_pair_count": sum(1 for report in pair_reports if report["classification"] == "identical"),
            "layout_only_pair_count": sum(1 for report in pair_reports if report["classification"] == "layout-only"),
            "structural_pair_count": sum(1 for report in pair_reports if report["classification"] == "structural"),
            "error_count": error_count,
        },
        "pairs": pair_reports,
        "selection_errors": selection_errors,
    }


def build_cli_parser(*, prog: str = "sattlint-source-diff-report", add_help: bool = True) -> argparse.ArgumentParser:
    return _build_cli_parser(default_workspace_root=str(REPO_ROOT), prog=prog, add_help=add_help)


def main(argv: Sequence[str] | None = None) -> int:
    return _run_cli(
        argv,
        default_workspace_root=REPO_ROOT,
        emit_progress_fn=emit_progress,
        build_source_diff_report_fn=build_source_diff_report,
        write_report_artifacts_fn=_write_report_artifacts,
        render_json_output_fn=cli_output.render_json_output,
        render_markdown_fn=render_markdown,
    )


if __name__ == "__main__":
    raise SystemExit(main())
