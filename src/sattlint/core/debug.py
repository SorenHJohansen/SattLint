"""CLI-independent debug utilities.

Tiny debug helpers shared across layers. These are primitives, not
orchestration: one reads the config debug flag, and one reports a failed load
without a traceback unless debug mode is on.
"""

from __future__ import annotations

import logging

from ..config.types import ConfigDict


def debug_enabled(cfg: ConfigDict) -> bool:
    return bool(cfg.get("debug", False))


def log_load_failure(
    message: str,
    *,
    exc: BaseException,
    logger: logging.Logger,
    debug: bool,
) -> None:
    """Report a failed load, with a traceback only when debug is enabled.

    A normal run gets one debug-level line, so a broken target never prints a
    full traceback into the terminal. Debug mode keeps the traceback for the
    developer.
    """
    if debug:
        logger.exception(message)
        return
    logger.debug("%s: %s", message, exc)
