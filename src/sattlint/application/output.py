"""Console output glue for the application layer.

Terminal-independent output helpers (emitting lines, flushing stdout, running a
callable under a live status line, logging failed CLI actions without aborting,
and handling analysis cancellation).  Elevated from the old flat ``app_analysis``
module as part of the Phase 2 layered refactor.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .. import console as console_module
from ..config_types import ConfigDict
from ..core import debug as debug_module

log = logging.getLogger("SattLint")
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]


def run_with_live_status(status_text: str, run_fn: Callable[[], Any]) -> Any:
    with console_module.live_status_line() as status_update_fn:
        status_update_fn(status_text)
        return run_fn()


def run_logged_cli_action(
    cfg: ConfigDict,
    *,
    action: Callable[[], Any],
    debug_message: str,
    user_message: str,
) -> tuple[bool, Any | None]:
    try:
        return True, action()
    except Exception as exc:  # noqa: BLE001 - CLI analysis commands should log failures and continue cleanly
        debug_module.log_debug_exception(cfg, debug_message, logger=log)
        emit_output(user_message.format(error=exc))
        return False, None


def handle_analysis_cancellation(*, pause_fn: Callable[[], None] | None) -> None:
    emit_output("\nOperation canceled. Returning to the menu.")
    if pause_fn is not None:
        pause_fn()
