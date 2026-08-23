# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportUnusedImport=false
from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sattline_parser.models.ast_model import BasePicture

from sattlint import (
    _app_analysis_from_app,
    _app_docs_from_app,
    _app_graphics_from_app,
    _app_menus_from_app,
    _app_startup_docs_graphics,
    _app_startup_from_app,
    app,
    app_graphics,
)
from sattlint.cli import command_handlers as cli_command_handlers
from sattlint.models.project_graph import ProjectGraph

__all__ = [
    "Any",
    "BasePicture",
    "Path",
    "ProjectGraph",
    "SimpleNamespace",
    "_app_analysis_from_app",
    "_app_docs_from_app",
    "_app_graphics_from_app",
    "_app_menus_from_app",
    "_app_startup_docs_graphics",
    "_app_startup_from_app",
    "_build_startup_app_module",
    "app",
    "app_graphics",
    "cast",
    "cli_command_handlers",
    "pytest",
    "runpy",
    "sys",
]


def _build_startup_app_module() -> SimpleNamespace:
    return SimpleNamespace(
        sys=SimpleNamespace(argv=["sattlint", "analyze"]),
        app_base=SimpleNamespace(run_cli=lambda *args, **kwargs: 0),
        app_cli_commands=SimpleNamespace(
            run_validate_config_command=lambda *args, **kwargs: 0,
            run_analyze_command=lambda *args, **kwargs: 0,
            run_simulate_command=lambda *args, **kwargs: 0,
            run_docgen_command=lambda *args, **kwargs: 0,
            run_telemetry_summary_command=lambda *args, **kwargs: 0,
        ),
        app_telemetry=SimpleNamespace(telemetry_output_path_for_config=lambda path: Path("telemetry.json")),
        telemetry_summary=SimpleNamespace(
            summarize_telemetry_file=lambda path: {"path": str(path)},
            render_text_summary=lambda summary: str(summary),
        ),
        app_graphics=SimpleNamespace(
            show_config=lambda *args, **kwargs: None,
            discover_graphics_rule_selector_options=lambda *args, **kwargs: [],
            pick_or_prompt_graphics_rule_selector_value=lambda *args, **kwargs: "selector",
            annotate_graphics_entries_with_structure_paths=lambda *args, **kwargs: [],
            graphics_rules_menu=lambda *args, **kwargs: None,
            prompt_graphics_rule_definition_with_config=lambda *args, **kwargs: {"rule": "value"},
            collect_graphics_layout_entries_for_target=lambda *args, **kwargs: [],
            run_graphics_rules_validation=lambda *args, **kwargs: None,
        ),
        app_docs=SimpleNamespace(
            get_documentation_unit_selection=lambda: {"mode": "all"},
            preview_documentation_unit_candidates=lambda *args, **kwargs: None,
            configure_documentation_scope_by_moduletype=lambda *args, **kwargs: True,
            configure_documentation_scope_by_instance_path=lambda *args, **kwargs: False,
            reset_documentation_scope=lambda *args, **kwargs: True,
            run_generate_documentation=lambda *args, **kwargs: None,
            documentation_menu=lambda *args, **kwargs: True,
        ),
        app_menus=SimpleNamespace(
            dump_menu=lambda *args, **kwargs: None,
            config_menu=lambda *args, **kwargs: True,
            tools_menu=lambda *args, **kwargs: None,
            run_main_loop=lambda *args, **kwargs: None,
        ),
        app_support=SimpleNamespace(
            print_menu=lambda *args, **kwargs: None,
            summarize_targets=lambda *args, **kwargs: "targets",
            show_help=lambda *args, **kwargs: None,
        ),
        CONFIG_PATH=Path("config.toml"),
        EXIT_SUCCESS=0,
        EXIT_USAGE_ERROR=2,
        build_cli_parser=lambda: object(),
        run_syntax_check_command=lambda _path: 0,
        load_config=lambda _path: ({"debug": False}, False),
        apply_debug=lambda _cfg: None,
        run_cli=lambda _argv: 0,
        run_validate_config_command=lambda _cfg, **_kwargs: 0,
        run_analyze_command=lambda _cfg, **_kwargs: 0,
        run_simulate_command=lambda _cfg, **_kwargs: 0,
        run_docgen_command=lambda _cfg, **_kwargs: 0,
        run_telemetry_summary_command=lambda _cfg, **_kwargs: 0,
        run_format_icf_command=lambda _cfg: 0,
        pause=lambda: None,
        get_graphics_rules_path=lambda: Path("graphics.json"),
        load_graphics_rules=lambda _path=None: ({"rules": []}, False),
        save_graphics_rules=lambda _path, _rules: None,
        _graphics_rule_label=lambda _rule: "Rule",
        _graphics_rule_config_line=lambda _rule: "config-line",
        clear_screen=lambda: None,
        choose_menu_option=lambda *args, **kwargs: "b",
        build_menu_interaction=lambda: SimpleNamespace(kind="interaction"),
        _get_analyzed_targets=lambda _cfg: ["Root"],
        _summarize_targets=lambda _cfg: "targets",
        _has_analyzed_targets=lambda _cfg: True,
        _target_is_library=lambda _cfg, _target_name: False,
        ensure_ast_cache=lambda _cfg: True,
        emit_output=lambda *_args: None,
        self_check=lambda _cfg: True,
        _iter_loaded_projects=lambda _cfg, use_cache=True: iter([]),
        _collect_graphics_layout_entries_for_target=lambda *args, **kwargs: [],
        _discover_graphics_rule_selector_options=lambda *args, **kwargs: [],
        _annotate_graphics_entries_with_structure_paths=lambda entries, *_args, **_kwargs: entries,
        _prompt_graphics_rule_definition_with_config=lambda _cfg: {"rule": "value"},
        _pick_or_prompt_graphics_rule_selector_value=lambda *args, **kwargs: "selector",
        _split_csv_values=lambda raw: raw.split(","),
        _print_menu=lambda *args, **kwargs: None,
        _menu_option=lambda key, label, description: (key, label, description),
        confirm=lambda _message: True,
        prompt=lambda _message, default=None: default or "value",
        quit_app=lambda: None,
        save_config=lambda _path, _cfg: None,
        target_exists=lambda _target, _cfg: True,
        graphics_rules_menu=lambda _cfg: None,
        show_config=lambda _cfg: None,
        documentation_menu=lambda _cfg: True,
        config_menu=lambda _cfg: True,
        tools_menu=lambda _cfg: None,
        dump_menu=lambda _cfg: None,
        analysis_menu=lambda _cfg: None,
        _require_targets_for_menu_action=lambda _cfg, _action: True,
        force_refresh_ast=lambda _cfg: None,
        refresh_analysis_caches=lambda _cfg: None,
        run_source_diff_report=lambda _cfg: None,
        analyze_variables=lambda *args, **kwargs: None,
        classify_documentation_structure=lambda *args, **kwargs: [],
        discover_documentation_unit_candidates=lambda *args, **kwargs: [],
        QuitAppError=RuntimeError,
    )
