"""Console output glue for the application layer.

Terminal-independent output helpers (emitting lines, flushing stdout, running a
callable under a live status line, and handling analysis cancellation). Elevated
from the old flat ``app_analysis`` module as part of the Phase 2 layered
refactor.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import console as console_module

emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]


def run_with_live_status(status_text: str, run_fn: Callable[[], Any]) -> Any:
    with console_module.live_status_line() as status_update_fn:
        status_update_fn(status_text)
        return run_fn()


def handle_analysis_cancellation(*, pause_fn: Callable[[], None] | None) -> None:
    emit_output("\nOperation canceled. Returning to the menu.")
    if pause_fn is not None:
        pause_fn()
