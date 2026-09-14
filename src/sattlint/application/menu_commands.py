"""Menu commands for the application layer.

The terminal-independent analysis workflow behind the ICF validation menu
action.  This is the menu-oriented counterpart to the CLI command handlers
in :mod:`sattlint.cli.commands`; the roles are distinct and the name reflects
that split.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef

from ..analyzers.icf import parse_icf_file, validate_icf_entries_against_program
from ..config.types import ConfigDict
from ..models.project_graph import ProjectGraph, merge_project_basepicture
from . import output as output_module


def run_icf_validation(
    cfg: ConfigDict,
    *,
    configured_icf_files_fn: Callable[[ConfigDict], tuple[Any, list[Any]]],
    load_program_ast_fn: Callable[[ConfigDict, str], tuple[BasePicture, ProjectGraph]],
    validate_icf_entries_against_program_fn: Callable[..., Any] = validate_icf_entries_against_program,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    icf_dir, icf_files = configured_icf_files_fn(cfg)
    if icf_dir is None:
        output_module.emit_output("❌ icf_dir is not set in the config. Set it before running ICF validation.")
        if pause_fn is not None:
            pause_fn()
        return

    if not icf_dir.exists() or not icf_dir.is_dir():
        output_module.emit_output(f"❌ icf_dir does not exist or is not a directory: {icf_dir}")
        if pause_fn is not None:
            pause_fn()
        return

    if not icf_files:
        output_module.emit_output(f"⚠ No .icf files found in {icf_dir}")
        if pause_fn is not None:
            pause_fn()
        return

    total_entries = 0
    total_valid = 0
    total_invalid = 0
    total_skipped = 0
    files_failed = 0

    output_module.emit_output("\n--- ICF Validation (per program) ---")

    for icf_file in icf_files:
        program_name = icf_file.stem
        entries = parse_icf_file(icf_file)
        if not entries:
            output_module.emit_output(f"⚠ {icf_file.name}: no entries found")
            continue

        succeeded, loaded_program = output_module.run_logged_cli_action(
            cfg,
            action=lambda program_name=program_name: load_program_ast_fn(cfg, program_name),
            debug_message=f"ICF validation failed while loading program {program_name!r} from {icf_file}",
            user_message=f"❌ {icf_file.name}: failed to load program {program_name!r}: {{error}}",
        )
        if not succeeded or loaded_program is None:
            files_failed += 1
            continue
        program_bp, graph = loaded_program
        program_bp = merge_project_basepicture(program_bp, graph)

        moduletype_index: dict[str, list[ModuleTypeDef]] = {}
        for bp in cast(dict[str, BasePicture], graph.ast_by_name).values():
            for mt in cast(list[ModuleTypeDef] | None, bp.moduletype_defs) or []:
                key = mt.name.casefold()
                moduletype_index.setdefault(key, []).append(mt)

        report = output_module.run_with_live_status(
            f"Validating ICF entries for {program_name}",
            lambda program_bp=program_bp, entries=entries, program_name=program_name, moduletype_index=moduletype_index: (
                validate_icf_entries_against_program_fn(
                    program_bp,
                    entries,
                    expected_program=program_name,
                    debug=cfg.get("debug", False),
                    moduletype_index=moduletype_index,
                )
            ),
        )
        output_module.emit_output(report.summary())
        output_module.emit_output("")

        total_entries += report.total_entries
        total_valid += report.valid_entries
        total_invalid += len(report.issues)
        total_skipped += report.skipped_entries

    output_module.emit_output("Summary:")
    output_module.emit_output(f"  Files processed: {len(icf_files)}")
    output_module.emit_output(f"  Files failed: {files_failed}")
    output_module.emit_output(f"  Entries: {total_entries}")
    output_module.emit_output(f"  Valid: {total_valid}")
    output_module.emit_output(f"  Invalid: {total_invalid}")
    output_module.emit_output(f"  Skipped: {total_skipped}")

    if pause_fn is not None:
        pause_fn()
