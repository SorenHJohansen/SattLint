# pyright: reportUnusedFunction=false
from __future__ import annotations

import argparse
import importlib
from pathlib import Path
from typing import Any, cast


def _app() -> Any:
    from . import app as app_module  # noqa: PLC0415

    return app_module


def run_cli(argv: list[str]) -> int:
    app = _app()
    return app.app_startup_module.run_cli_from_app(argv, app_module=app)


def run_validate_config_command(
    cfg: dict[str, object],
    *,
    config_path: Path,
    default_used: bool,
    output_format: str = "text",
) -> int:
    app = _app()
    return app.app_startup_module.run_validate_config_command_from_app(
        cfg,
        config_path=config_path,
        default_used=default_used,
        output_format=output_format,
        app_module=app,
    )


def run_analyze_command(
    cfg: dict[str, object],
    *,
    selected_keys: list[str] | None,
    selected_issue_kinds: frozenset[str] | None = None,
    use_cache: bool,
    output_format: str = "text",
) -> int:
    app = _app()
    return app.app_startup_module.run_analyze_command_from_app(
        cfg,
        selected_keys=selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        use_cache=use_cache,
        output_format=output_format,
        app_module=app,
    )


def _simulate_target(
    cfg: dict[str, object],
    *,
    target_path: str,
    module_name: str,
    mode: str,
    max_scans: int,
    use_cache: bool,
) -> Any:
    from .simulation import simulate_snapshot_target  # noqa: PLC0415

    app = _app()
    del cfg, use_cache
    snapshot = app.load_workspace_snapshot(
        Path(target_path),
        collect_variable_diagnostics=False,
    )
    return simulate_snapshot_target(
        snapshot,
        module_name=module_name,
        mode=mode,
        max_scans=max_scans,
    )


def run_simulate_command(
    cfg: dict[str, object],
    *,
    target_path: str,
    module_name: str,
    mode: str,
    max_scans: int,
    output_format: str,
    output_path: str | None,
    use_cache: bool,
) -> int:
    app = _app()
    return app.app_startup_module.run_simulate_command_from_app(
        cfg,
        target_path=target_path,
        module_name=module_name,
        mode=mode,
        max_scans=max_scans,
        output_format=output_format,
        output_path=output_path,
        use_cache=use_cache,
        app_module=app,
    )


def run_cache_prune_command(*, cache_dir: str | None = None, output_format: str = "text") -> int:
    app = _app()
    return app.app_startup_module.run_cache_prune_command_from_app(
        cache_dir=cache_dir,
        output_format=output_format,
        app_module=app,
    )


def run_telemetry_summary_command(
    cfg: dict[str, object],
    *,
    config_path: Path,
    output_format: str,
    output_path: str | None,
) -> int:
    app = _app()
    return app.app_startup_module.run_telemetry_summary_command_from_app(
        cfg,
        config_path=config_path,
        output_format=output_format,
        output_path=output_path,
        app_module=app,
    )


def _configured_icf_files(cfg: dict[str, object]) -> tuple[Path | None, list[Path]]:
    app = _app()
    return cast(tuple[Path | None, list[Path]], app.app_support.configured_icf_files(cfg))


def run_format_icf_command(cfg: dict[str, object], *, check: bool = False, output_format: str = "text") -> int:
    app = _app()
    return cast(
        int,
        app.app_support.run_format_icf_command(
            cfg,
            check=check,
            output_format=output_format,
            print_fn=print,
            exit_success=app.EXIT_SUCCESS,
            exit_usage_error=app.EXIT_USAGE_ERROR,
        ),
    )


def run_trace_command(args: argparse.Namespace) -> int:
    tracing_module = importlib.import_module("sattlint.tracing")
    return cast(int, tracing_module.run_parsed_args(args))


def run_icf_formatter(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_startup_module.run_icf_formatter_from_app(cfg, app_module=app)


def show_config(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_startup_module.show_config_from_app(cfg, app_module=app)
