from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from .config_types import ConfigDict
from .models.project_graph import ProjectGraph

LoadedProject = tuple[str, BasePicture, ProjectGraph]


def collect_source_diff_pairs_for_paths(source_paths: set[Path]) -> list[tuple[Path, Path]]:
    grouped: dict[tuple[Path, str], dict[str, Path]] = {}
    for source_path in source_paths:
        resolved = source_path.resolve()
        suffix = resolved.suffix.casefold()
        if suffix not in {".s", ".x"}:
            continue
        key = (resolved.parent, resolved.stem.casefold())
        pair = grouped.setdefault(key, {})

        if suffix == ".s":
            pair["draft"] = resolved
        elif suffix == ".x":
            pair["official"] = resolved

        sibling_draft = resolved.with_suffix(".s")
        sibling_official = resolved.with_suffix(".x")
        if sibling_draft.exists():
            pair["draft"] = sibling_draft.resolve()
        if sibling_official.exists():
            pair["official"] = sibling_official.resolve()

    pairs: list[tuple[Path, Path]] = []
    for pair in grouped.values():
        draft = pair.get("draft")
        official = pair.get("official")
        if draft is None or official is None:
            continue
        pairs.append((draft, official))
    return sorted(pairs, key=lambda item: (item[0].stem.casefold(), str(item[0]).casefold()))


def run_source_diff_report(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[[ConfigDict], Iterator[LoadedProject]],
    source_paths_for_current_target_fn: Callable[[BasePicture, ProjectGraph], set[Path]],
    live_status_line_factory: Callable[[], Any],
    build_pair_report_fn: Callable[..., dict[str, Any]],
    render_markdown_fn: Callable[[dict[str, Any]], str],
    emit_output_fn: Callable[[str], None],
    pause_fn: Callable[[], None],
) -> None:
    workspace_root = Path(cfg.get("program_dir") or ".").resolve()
    pair_reports: list[dict[str, Any]] = []
    selection_errors: list[dict[str, str]] = []
    seen_pairs: set[tuple[Path, Path]] = set()

    unique_pairs: list[tuple[Path, Path]] = []
    with live_status_line_factory() as status_update_fn:
        status_update_fn("Source diff: resolving comparison pairs")
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
            status_update_fn(f"Source diff: collecting comparison pairs for {target_name}")
            source_paths = source_paths_for_current_target_fn(project_bp, graph)
            target_pairs = collect_source_diff_pairs_for_paths(source_paths)
            if not target_pairs:
                selection_errors.append(
                    {
                        "draft_file": "",
                        "official_file": "",
                        "message": f"No same-basename .s/.x pair was found for analysis target '{target_name}'.",
                    }
                )
                continue

            for draft_file, official_file in target_pairs:
                pair_key = (draft_file.resolve(), official_file.resolve())
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                unique_pairs.append((draft_file, official_file))

        total_pairs = len(unique_pairs)
        for index, (draft_file, official_file) in enumerate(unique_pairs, start=1):
            status_update_fn(f"Source diff: comparing {index}/{total_pairs} {draft_file.name}")
            pair_reports.append(
                build_pair_report_fn(
                    draft_file,
                    official_file,
                    workspace_root=workspace_root,
                )
            )

    error_count = len(selection_errors) + sum(1 for report in pair_reports if report["status"] == "error")
    status = "ok"
    if error_count and not pair_reports:
        status = "error"
    elif error_count:
        status = "partial"

    report = {
        "generated_by": "sattlint.app.tools_menu",
        "report_kind": "source-diff-report",
        "status": status,
        "workspace_root": str(workspace_root),
        "summary": {
            "compared_pair_count": len(pair_reports),
            "changed_pair_count": sum(1 for item in pair_reports if item["changed"]),
            "identical_pair_count": sum(1 for item in pair_reports if item["classification"] == "identical"),
            "layout_only_pair_count": sum(1 for item in pair_reports if item["classification"] == "layout-only"),
            "structural_pair_count": sum(1 for item in pair_reports if item["classification"] == "structural"),
            "error_count": error_count,
        },
        "pairs": pair_reports,
        "selection_errors": selection_errors,
    }
    emit_output_fn(render_markdown_fn(report))
    pause_fn()
