from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SattLintTheme:
    bg_main: str = "#f4f1ea"
    bg_panel: str = "#e7dfd1"
    btn_bg: str = "#d6ccb8"
    btn_active: str = "#c5b89d"
    accent: str = "#355c4d"
    input_bg: str = "#fbf8f2"
    text: str = "#1f2722"
    console_bg: str = "#18211d"
    console_text: str = "#d7eadf"
    sidebar_width: int = 200


DEFAULT_THEME = SattLintTheme()

__all__ = ["DEFAULT_THEME", "SattLintTheme"]
