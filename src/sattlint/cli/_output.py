"""Structured output helpers for the headless CLI.

The CLI keeps machine-readable data on stdout and human diagnostics on stderr.
Every JSON document carries a ``schema_version`` so agents can pin the contract.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

from ._payloads import ErrorPayload

SCHEMA_VERSION = 1


class CliError(Exception):
    """A user-facing CLI failure with a stable machine-readable code."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "cli_error",
        exit_code: int = 2,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.exit_code = exit_code
        self.details = dict(details or {})


def error_payload(error: CliError) -> ErrorPayload:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "error",
        "error": {
            "code": error.code,
            "message": error.message,
            "details": dict(error.details),
        },
    }


def _write_text(text: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(text)
        sys.stdout.flush()
        return
    resolved = output.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(text, encoding="utf-8")


def emit_json(payload: Mapping[str, object], *, output: Path | None = None) -> None:
    _write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", output)


def emit_ndjson(records: Iterable[Mapping[str, object]], *, output: Path | None = None) -> None:
    text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    _write_text(text, output)


def emit_text(lines: Iterable[str], *, output: Path | None = None) -> None:
    text = "\n".join(lines)
    if text:
        text += "\n"
    _write_text(text, output)


def emit_error(error: CliError, *, output_format: str) -> None:
    if output_format == "json":
        sys.stderr.write(json.dumps(error_payload(error), ensure_ascii=False) + "\n")
        sys.stderr.flush()
        return
    sys.stderr.write(f"sattlint: {error.message}\n")
    for key, value in error.details.items():
        sys.stderr.write(f"  {key}: {value}\n")
    sys.stderr.flush()


def output_path(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return Path(value)


__all__ = [
    "SCHEMA_VERSION",
    "CliError",
    "emit_error",
    "emit_json",
    "emit_ndjson",
    "emit_text",
    "error_payload",
    "output_path",
]
