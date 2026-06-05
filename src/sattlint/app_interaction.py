from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MenuInteraction:
    choose_menu_option: Callable[..., str]
    prompt: Callable[..., str]
    confirm: Callable[[str], bool]
    pause: Callable[[], None]


def build_menu_interaction(
    *,
    print_menu_fn: Callable[..., None],
    choose_menu_option_fn: Callable[..., str] | None = None,
    prompt_fn: Callable[..., str] | None = None,
    confirm_fn: Callable[[str], bool] | None = None,
    pause_fn: Callable[[], None] | None = None,
) -> MenuInteraction:
    if choose_menu_option_fn is None:

        def _default_choose_menu_option_fn(
            title: str,
            options: Sequence[Any],
            *,
            intro: str | None = None,
            note: str | None = None,
        ) -> str:
            print_menu_fn(title, options, intro=intro, note=note)
            return input("> ").strip().lower()

        choose_menu_option_fn = _default_choose_menu_option_fn

    if prompt_fn is None:

        def _default_prompt_fn(message: str, default: str | None = None) -> str:
            if default is not None:
                return input(f"{message} [{default}]: ").strip() or default
            return input(f"{message}: ").strip()

        prompt_fn = _default_prompt_fn

    if confirm_fn is None:

        def _default_confirm_fn(message: str) -> bool:
            return input(f"{message} [y/N]: ").strip().lower() in ("y", "yes")

        confirm_fn = _default_confirm_fn

    if pause_fn is None:

        def _default_pause_fn() -> None:
            input("\nPress Enter to continue...")

        pause_fn = _default_pause_fn

    return MenuInteraction(
        choose_menu_option=choose_menu_option_fn,
        prompt=prompt_fn,
        confirm=confirm_fn,
        pause=pause_fn,
    )
