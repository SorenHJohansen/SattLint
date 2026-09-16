from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class MenuInteraction:
    choose_menu_option: Callable[..., str]
    prompt: Callable[..., str]
    confirm: Callable[[str], bool]
    pause: Callable[[], None]
