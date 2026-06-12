from __future__ import annotations

import logging

from .config_types import ConfigDict


def debug_enabled(cfg: ConfigDict) -> bool:
    return bool(cfg.get("debug", False))


def log_debug_exception(cfg: ConfigDict, message: str, *, logger: logging.Logger) -> None:
    del cfg
    logger.exception(message)
