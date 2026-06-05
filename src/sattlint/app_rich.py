from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from . import app_support as app_support_module
from . import console as console_module


def print_menu(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> None:
    if not console_module.has_rich():
        app_support_module.print_menu(
            title,
            options,
            print_fn=console_module.print_output,
            intro=intro,
            note=note,
        )
        return

    body_parts = [part.strip() for part in (intro, note) if part and part.strip()]
    body = "\n\n".join(body_parts) if body_parts else "Select an option."
    console_module.print_panel(title, body)
    console_module.print_table(
        f"{title} Options",
        ["Key", "Action", "Description"],
        [
            (
                getattr(option, "key", ""),
                getattr(option, "label", ""),
                getattr(option, "description", ""),
            )
            for option in options
        ],
    )
