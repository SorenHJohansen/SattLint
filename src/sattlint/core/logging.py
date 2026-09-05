"""Logging configuration for SattLint.

Owns the module-wide logger, default log levels, and debug-mode toggling,
elevated from the old flat ``app_base`` module as part of Phase 2.
"""

from __future__ import annotations

import logging

from ..config_types import ConfigDict

log = logging.getLogger("SattLint")


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    log.setLevel(logging.INFO)


def apply_debug(cfg: ConfigDict) -> None:
    level = logging.DEBUG if cfg.get("debug") else logging.INFO
    logging.getLogger().setLevel(level)
    log.setLevel(level)
