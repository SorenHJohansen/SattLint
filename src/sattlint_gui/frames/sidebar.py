from __future__ import annotations

from collections.abc import Callable, Sequence
from tkinter import ttk


class SidebarFrame(ttk.Frame):
    def __init__(self, parent, *, items: Sequence[str], on_select: Callable[[str], None]) -> None:
        super().__init__(parent, style="Sidebar.TFrame", padding=16)
        self.columnconfigure(0, weight=1)
        self._buttons: dict[str, ttk.Button] = {}

        ttk.Label(self, text="Views", style="SidebarTitle.TLabel").grid(row=0, column=0, sticky="ew", pady=(0, 12))

        for row, item in enumerate(items, start=1):
            button = ttk.Button(
                self, text=item, style="Nav.TButton", command=lambda name=item: self._handle_select(name, on_select)
            )
            button.grid(row=row, column=0, sticky="ew", pady=4)
            self._buttons[item] = button

    def set_selected(self, name: str) -> None:
        for item, button in self._buttons.items():
            button.configure(style="Selected.Nav.TButton" if item == name else "Nav.TButton")

    def _handle_select(self, name: str, on_select: Callable[[str], None]) -> None:
        self.set_selected(name)
        on_select(name)


__all__ = ["SidebarFrame"]
