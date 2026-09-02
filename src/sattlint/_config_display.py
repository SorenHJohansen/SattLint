"""Internal config-display helpers.

Relocated from the removed app/CLI graphics layer so the kept ``show_config``
command remains available without the graphics-rules feature.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from .config_types import ConfigDict
from .core.telemetry import telemetry_output_path


def format_config_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value in (None, ""):
        return "(not set)"
    return str(value)


def print_config_section(
    title: str,
    rows: Sequence[tuple[str, object | str | bool | Path]],
    *,
    emit_output_fn: Callable[..., None],
    format_config_scalar_fn: Callable[[object], str],
) -> None:
    emit_output_fn(title)
    if not rows:
        emit_output_fn("  (none)")
        return

    label_width = max(len(label) for label, _ in rows)
    for label, value in rows:
        emit_output_fn(f"  {label:<{label_width}}  {format_config_scalar_fn(value)}")


def print_config_list(
    title: str,
    items: list[object],
    *,
    emit_output_fn: Callable[..., None],
    format_config_scalar_fn: Callable[[object], str],
) -> None:
    emit_output_fn(title)
    if not items:
        emit_output_fn("  (none)")
        return

    for index, item in enumerate(items, 1):
        emit_output_fn(f"  [{index}] {format_config_scalar_fn(item)}")


def show_config(
    cfg: ConfigDict,
    *,
    emit_output_fn: Callable[..., None],
) -> None:
    general_rows = [
        ("mode", cfg["mode"]),
        ("debug", cfg["debug"]),
    ]
    telemetry_cfg = cast(dict[str, object], cfg.get("telemetry", {}))
    telemetry_rows = [
        ("enabled", telemetry_cfg.get("enabled", False)),
        ("path", telemetry_output_path()),
    ]
    directory_rows = [
        ("program_dir", cfg["program_dir"]),
        ("ABB_lib_dir", cfg["ABB_lib_dir"]),
        ("icf_dir", cfg["icf_dir"]),
    ]

    def _scalar(value: object) -> str:
        return format_config_scalar(value)

    emit_output_fn("\nCurrent Configuration")
    emit_output_fn("=" * 21)
    emit_output_fn()
    print_config_list(
        "Analyzed Programs And Libraries",
        list(cfg["analyzed_programs_and_libraries"]),
        emit_output_fn=emit_output_fn,
        format_config_scalar_fn=_scalar,
    )
    emit_output_fn()
    print_config_section(
        "General",
        general_rows,
        emit_output_fn=emit_output_fn,
        format_config_scalar_fn=_scalar,
    )
    emit_output_fn()
    print_config_section(
        "Telemetry",
        telemetry_rows,
        emit_output_fn=emit_output_fn,
        format_config_scalar_fn=_scalar,
    )
    emit_output_fn()
    print_config_section(
        "Directories",
        directory_rows,
        emit_output_fn=emit_output_fn,
        format_config_scalar_fn=_scalar,
    )
    emit_output_fn()
    print_config_list(
        "Other Library Directories",
        list(cfg["other_lib_dirs"]),
        emit_output_fn=emit_output_fn,
        format_config_scalar_fn=_scalar,
    )
    emit_output_fn()
