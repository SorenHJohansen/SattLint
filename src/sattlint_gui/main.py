from __future__ import annotations

from .theme import SattLintTheme
from .window import SattLintWindow


def create_window(*, theme: SattLintTheme | None = None) -> SattLintWindow:
    return SattLintWindow(theme=theme)


def gui() -> int:
    window = create_window()
    window.mainloop()
    return 0


__all__ = ["create_window", "gui"]
