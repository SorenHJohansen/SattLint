"""Single-file syntax check CLI command.

Elevated from the old flat ``app_base`` module as part of the Phase 2 layered
refactor.  Owns ``run_syntax_check_command`` and the text/json formatting that
back the ``syntax-check`` CLI verb.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .. import console as console_module
from .. import engine as engine_module
from .._exit_codes import EXIT_FAILURE, EXIT_SUCCESS, EXIT_USAGE_ERROR
from ..cli_output import emit_text_or_json


def _format_syntax_error(result: engine_module.SyntaxValidationResult) -> str:
    location = ""
    if result.line is not None and result.column is not None:
        location = f":{result.line}:{result.column}"
    elif result.line is not None:
        location = f":{result.line}"

    detail = result.message or "Unknown error"
    return f"ERROR [{result.stage}] {result.file_path}{location}: {detail}"


def _format_syntax_warning(file_path: Path, message: str) -> str:
    return f"WARNING [validation] {file_path}: {message}"


def _syntax_check_json_payload(
    *,
    file_path: Path,
    ok: bool,
    stage: str,
    message: str | None,
    line: int | None,
    column: int | None,
    warnings: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "file_path": str(file_path),
        "ok": ok,
        "stage": stage,
        "message": message,
        "line": line,
        "column": column,
        "warnings": list(warnings),
    }


def run_syntax_check_command(file_path: str, *, output_format: str = "text") -> int:
    target_path = Path(file_path)
    if not target_path.exists() or not target_path.is_file():
        if output_format == "json":
            emit_text_or_json(
                text="",
                json_payload=_syntax_check_json_payload(
                    file_path=target_path,
                    ok=False,
                    stage="io",
                    message="File not found",
                    line=None,
                    column=None,
                    warnings=(),
                ),
                output_format="json",
                emit_text_fn=console_module.print_output,
            )
        else:
            console_module.print_output(f"ERROR [io] {target_path}: File not found", file=sys.stderr)
        return EXIT_USAGE_ERROR

    result = engine_module.validate_single_file_syntax(target_path)
    json_payload = _syntax_check_json_payload(
        file_path=result.file_path,
        ok=result.ok,
        stage=result.stage,
        message=result.message,
        line=result.line,
        column=result.column,
        warnings=result.warnings,
    )
    if result.ok:
        if output_format == "json":
            emit_text_or_json(
                text="",
                json_payload=json_payload,
                output_format="json",
                emit_text_fn=console_module.print_output,
            )
            return EXIT_SUCCESS
        for warning in result.warnings:
            console_module.print_output(_format_syntax_warning(result.file_path, warning), file=sys.stderr)
        console_module.print_output("OK")
        return EXIT_SUCCESS

    if output_format == "json":
        emit_text_or_json(
            text="",
            json_payload=json_payload,
            output_format="json",
            emit_text_fn=console_module.print_output,
        )
        return EXIT_FAILURE

    console_module.print_output(_format_syntax_error(result), file=sys.stderr)
    return EXIT_FAILURE
