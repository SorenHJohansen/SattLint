"""Structured output helpers for the headless CLI.

The CLI keeps machine-readable data on stdout and human diagnostics on stderr.
Every JSON document carries a ``schema_version`` so agents can pin the contract.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ..utils.terminal_text import sanitize_terminal_text
from ._payloads import ErrorPayload

SCHEMA_VERSION = 2


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


def write_stream(stream: Any, text: str) -> None:
    """Write through a text stream without failing on a legacy code page.

    ``PYTHONIOENCODING=ascii`` and legacy Windows consoles raise
    ``UnicodeEncodeError`` on the first non-ASCII character, which would turn a
    complete result into an internal error. The fallback encodes the document
    as UTF-8 with backslash escapes and writes to the underlying buffer.
    """
    try:
        stream.write(text)
    except UnicodeEncodeError:
        buffer = getattr(stream, "buffer", None)
        if buffer is None:
            raise
        buffer.write(text.encode("utf-8", errors="backslashreplace"))
    stream.flush()


def encode_json_document(payload: Mapping[str, object]) -> str:
    """Serialize a standalone JSON document, one per stream."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def encode_json_record(payload: Mapping[str, object]) -> str:
    """Serialize one NDJSON record as a single line."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def _resolve_output_path(output: Path) -> Path:
    return output.expanduser().resolve()


def _write_text(text: str, output: Path | None) -> None:
    if output is None:
        write_stream(sys.stdout, text)
        return
    resolved = _resolve_output_path(output)
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise CliError(
            f"Could not write {resolved}: {exc}",
            code="output_write_failed",
            exit_code=2,
        ) from exc


def emit_json(payload: Mapping[str, object], *, output: Path | None = None) -> None:
    _write_text(encode_json_document(payload), output)


def emit_ndjson(records: Iterable[Mapping[str, object]], *, output: Path | None = None) -> None:
    """Write NDJSON records as they are produced.

    Each record is flushed before the next one is requested from the iterator,
    so a consumer reads partial results while the run is still feeding them.
    """
    if output is None:
        for record in records:
            write_stream(sys.stdout, encode_json_record(record))
        return

    resolved = _resolve_output_path(output)
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(encode_json_record(record))
                handle.flush()
    except OSError as exc:
        raise CliError(
            f"Could not write {resolved}: {exc}",
            code="output_write_failed",
            exit_code=2,
        ) from exc


def emit_text(lines: Iterable[str], *, output: Path | None = None) -> None:
    """Write human text, neutralizing control characters in every line.

    Lines are sanitized before they are joined, so a finding or target name
    cannot inject a second output line. Tabs are kept for column alignment;
    newlines are refused because the sink owns the line structure.
    """
    text = "\n".join(sanitize_terminal_text(line, keep_tabs=True) for line in lines)
    if text:
        text += "\n"
    _write_text(text, output)


def emit_error(error: CliError, *, output_format: str) -> None:
    if output_format in {"json", "ndjson", "sarif"}:
        write_stream(sys.stderr, encode_json_document(error_payload(error)))
        return
    write_stream(sys.stderr, f"sattlint: {sanitize_terminal_text(error.message, keep_tabs=True)}\n")
    for key, value in error.details.items():
        label = sanitize_terminal_text(str(key), keep_tabs=True)
        detail = sanitize_terminal_text(str(value), keep_tabs=True)
        write_stream(sys.stderr, f"  {label}: {detail}\n")


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
    "encode_json_document",
    "encode_json_record",
    "error_payload",
    "output_path",
]
