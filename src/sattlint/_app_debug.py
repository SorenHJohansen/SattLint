from __future__ import annotations

import logging
from typing import Any

ConfigDict = dict[str, Any]


def debug_enabled(cfg: ConfigDict) -> bool:
    return bool(cfg.get("debug", False))


def log_debug_exception(cfg: ConfigDict, message: str, *, logger: logging.Logger) -> None:
    if debug_enabled(cfg):
        logger.exception(message)
