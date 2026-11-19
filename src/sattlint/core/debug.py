"""CLI-independent debug utilities.

Tiny debug helpers shared across layers. These are primitives, not
orchestration: one reads the config debug flag, the other logs the active
exception with its traceback.
"""

from __future__ import annotations

import logging

from ..config.types import ConfigDict


def debug_enabled(cfg: ConfigDict) -> bool:
    return bool(cfg.get("debug", False))


def log_debug_exception(message: str, *, logger: logging.Logger) -> None:
    logger.exception(message)
