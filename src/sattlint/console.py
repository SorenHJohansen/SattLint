"""Terminal presentation helpers with optional Rich integration."""

from __future__ import annotations

import builtins
import sys
from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    from rich.console import Console  # type: ignore[import-untyped]
    from rich.markup import escape as _rich_escape  # type: ignore[import-untyped]
    from rich.panel import Panel  # type: ignore[import-untyped]
    from rich.progress import track as rich_track  # type: ignore[import-untyped]
    from rich.syntax import Syntax  # type: ignore[import-untyped]
    from rich.table import Table  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional dependency path
    Console = None
    Panel = None
    Syntax = None
    Table = None
    rich_track = None

    def _rich_escape(text: str) -> str:  # type: ignore[misc]
        return text


_RICH_AVAILABLE = Console is not None
_STDOUT_CONSOLE = None if Console is None else Console()
_STDERR_CONSOLE = None if Console is None else Console(stderr=True)
_STATUS_PREFIXES = {
    "error": "ERROR",
    "info": "INFO",
    "success": "OK",
    "warning": "WARNING",
}
_STATUS_STYLES = {
    "error": "bold red",
    "info": "bold blue",
    "success": "bold green",
    "warning": "bold yellow",
}


def print_output(
    *objects: object,
    sep: str = " ",
    end: str = "\n",
    file: Any | None = None,
    flush: bool = False,
) -> None:
    """Generic output wrapper for app-facing text while preserving print() semantics."""
    builtins.print(*objects, sep=sep, end=end, file=file, flush=flush)


class _LiveStatusLine:
    def __init__(self, *, file: Any | None = None) -> None:
        self._file = file if file is not None else sys.stdout
        self._enabled = bool(getattr(self._file, "isatty", lambda: False)())
        self._last_width = 0

    def update(self, message: str) -> None:
        if not self._enabled:
            return
        text = " ".join(str(message).splitlines()).strip()
        width = max(self._last_width, len(text))
        print_output(f"\r{text.ljust(width)}", end="", file=self._file, flush=True)
        self._last_width = width

    def clear(self) -> None:
        if not self._enabled or self._last_width <= 0:
            return
        print_output(f"\r{' ' * self._last_width}\r", end="", file=self._file, flush=True)
        self._last_width = 0


@contextmanager
def live_status_line(*, file: Any | None = None):
    status_line = _LiveStatusLine(file=file)
    try:
        yield status_line.update
    finally:
        status_line.clear()


def has_rich() -> bool:
    return _RICH_AVAILABLE


def print_status(message: str, *, level: str = "info", stderr: bool = False) -> None:
    prefix = _STATUS_PREFIXES.get(level, "INFO")
    if _RICH_AVAILABLE:
        console = _STDERR_CONSOLE if stderr else _STDOUT_CONSOLE
        if console is not None:
            style = _STATUS_STYLES.get(level, "bold")
            console.print(
                f"[{style}]{prefix}[/{style}] {_rich_escape(message)}",
                soft_wrap=True,
            )
            return

    print_output(f"{prefix} {message}")


def print_panel(title: str, body: str, *, stderr: bool = False) -> None:
    if _RICH_AVAILABLE:
        console = _STDERR_CONSOLE if stderr else _STDOUT_CONSOLE
        if console is not None and Panel is not None:
            console.print(Panel(body, title=title, expand=False))
            return

    print_output(f"\n--- {title} ---")
    print_output(body)


def print_table(title: str, columns: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
    if _RICH_AVAILABLE:
        console = _STDOUT_CONSOLE
        if console is not None and Table is not None:
            table = Table(title=title, show_lines=False)
            for column in columns:
                table.add_column(column)
            for row in rows:
                table.add_row(*(str(value) for value in row))
            console.print(table)
            return

    print_output(title)
    if not rows:
        print_output("  (none)")
        return

    widths = [len(column) for column in columns]
    normalized_rows = [[str(value) for value in row] for row in rows]
    for row in normalized_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header = "  ".join(column.ljust(widths[index]) for index, column in enumerate(columns))
    divider = "  ".join("-" * width for width in widths)
    print_output(header)
    print_output(divider)
    for row in normalized_rows:
        print_output("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def track_items(iterable: Iterable[Any], *, description: str) -> Iterable[Any]:
    if _RICH_AVAILABLE and rich_track is not None:
        return rich_track(iterable, description=description)
    return iterable


def print_syntax_excerpt(file_path: Path, line: int | None, column: int | None) -> None:
    if not _RICH_AVAILABLE or Syntax is None or line is None or not file_path.exists():
        return

    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return

    console = _STDERR_CONSOLE
    if console is None or Panel is None:
        return
    console.print(
        Panel(
            Syntax(
                source,
                "text",
                line_numbers=True,
                word_wrap=False,
                highlight_lines={line},
            ),
            title=f"{file_path}:{line}{'' if column is None else f':{column}'}",
            expand=False,
        )
    )
