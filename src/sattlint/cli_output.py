from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any, Literal

type OutputFormat = Literal["text", "json"]


def add_output_format_argument(
    parser: argparse.ArgumentParser,
    *,
    default: OutputFormat = "text",
    include_json_alias: bool = False,
    help_text: str = "Output format",
) -> None:
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default=default,
        help=help_text,
    )
    if include_json_alias:
        parser.add_argument(
            "--json",
            action="store_true",
            help="Alias for --format json",
        )


def resolve_output_format(args: object, *, default: OutputFormat = "text") -> OutputFormat:
    if bool(getattr(args, "json", False)):
        return "json"
    return "json" if getattr(args, "format", default) == "json" else "text"


def render_json_output(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def emit_text_or_json(
    *,
    text: str,
    json_payload: Any,
    output_format: OutputFormat,
    emit_text_fn: Callable[[str], None],
) -> None:
    if output_format == "json":
        emit_text_fn(render_json_output(json_payload))
        return
    emit_text_fn(text)
