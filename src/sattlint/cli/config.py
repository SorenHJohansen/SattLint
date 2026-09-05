"""CLI-facing configuration actions.

Wraps the canonical :mod:`sattlint.config` persistence with the terminal
feedback the interactive CLI expects, elevated from the old flat ``app_base``
module as part of the Phase 2 layered refactor.
"""

from __future__ import annotations

from pathlib import Path

from .. import config as config_module
from .. import console as console_module
from ..config_types import ConfigDict


def save_config(path: Path, cfg: ConfigDict) -> None:
    config_module.save_config(path, cfg)
    console_module.print_output("Config saved")
