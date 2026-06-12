from __future__ import annotations

from typing import Any, cast

from .entry import CommandHandlers, RunParsedArgsCommandFn, RunSyntaxCheckCommandFn


def build_command_handlers(
    *,
    defaults: CommandHandlers | None = None,
    overrides: CommandHandlers | None = None,
) -> CommandHandlers:
    resolved: dict[str, object] = {}
    if defaults is not None:
        resolved.update(defaults)
    if overrides is not None:
        resolved.update(overrides)
    return cast(CommandHandlers, resolved)


def build_base_command_handlers(
    *,
    syntax_check_fn: RunSyntaxCheckCommandFn,
    repo_audit_fn: RunParsedArgsCommandFn,
    source_diff_fn: RunParsedArgsCommandFn,
    trace_fn: RunParsedArgsCommandFn | None = None,
    overrides: CommandHandlers | None = None,
) -> CommandHandlers:
    defaults: dict[str, object] = {
        "syntax_check": syntax_check_fn,
        "repo_audit": repo_audit_fn,
        "source_diff": source_diff_fn,
    }
    if trace_fn is not None:
        defaults["trace"] = trace_fn
    return build_command_handlers(
        defaults=cast(CommandHandlers, defaults),
        overrides=overrides,
    )


def build_app_command_handlers(app_module: Any) -> CommandHandlers:
    return build_command_handlers(
        overrides=cast(
            CommandHandlers,
            {
                "syntax_check": app_module.run_syntax_check_command,
                "validate_config": app_module.run_validate_config_command,
                "analyze": app_module.run_analyze_command,
                "simulate": app_module.run_simulate_command,
                "docgen": app_module.run_docgen_command,
                "cache_prune": app_module.run_cache_prune_command,
                "telemetry_summary": app_module.run_telemetry_summary_command,
                "format_icf": app_module.run_format_icf_command,
                "trace": app_module.run_trace_command,
            },
        )
    )
